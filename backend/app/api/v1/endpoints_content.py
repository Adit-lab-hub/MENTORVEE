import json
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form, Request
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.security import get_current_user, RoleChecker
from app.core.config import settings
from app.models.models import User, Content, ClassSubject
from fastapi.responses import Response
from typing import Optional

router = APIRouter()

# Input sanitization
def sanitize_text(text: str) -> str:
    if not text:
        return ""
    # Simple HTML escaping to prevent XSS
    return text.replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;").replace("'", "&#x27;")

@router.get("")
def list_content(class_id: Optional[int] = None, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    query = db.query(Content)
    
    if current_user.role == "student":
        # Students see content for both OS and DBMS classes
        query = query.join(ClassSubject).filter(ClassSubject.code.in_(["OS", "DBMS"]))
    elif current_user.role == "teacher":
        if class_id:
            query = query.filter(Content.class_id == class_id)
        else:
            query = query.filter(Content.uploaded_by == current_user.id)
            
    contents = query.order_by(Content.created_at.desc()).all()
    return [{
        "id": c.id,
        "title": c.title,
        "description": c.description,
        "type": c.type,
        "payload": c.payload,
        "file_name": c.file_name,
        "has_file": c.file_data is not None,
        "class_id": c.class_id,
        "class_name": c.class_subject.name if c.class_subject else "General",
        "created_at": c.created_at,
        "uploaded_by": c.uploaded_by
    } for c in contents]

@router.post("")
def create_content(
    title: str = Form(...),
    description: str = Form(""),
    class_id: int = Form(...),
    content_type: str = Form(...), # "material" or "lab"
    payload: str = Form(""),
    file: Optional[UploadFile] = File(None),
    focus_topic: str = Form("none"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    # Check permissions
    if current_user.role not in ["teacher", "admin"]:
        raise HTTPException(status_code=403, detail="Only teachers and admins can create content")
        
    cls = db.query(ClassSubject).filter(ClassSubject.id == class_id).first()
    if not cls:
        raise HTTPException(status_code=400, detail="Target class/subject not found")

    file_name = None
    file_data = None
    
    if file:
        # Check extension
        ext = file.filename.split(".")[-1].lower()
        if ext not in settings.ALLOWED_UPLOAD_EXTENSIONS:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid file type. Allowed extensions: {', '.join(settings.ALLOWED_UPLOAD_EXTENSIONS)}"
            )
            
        # Read content and check size
        contents = file.file.read()
        if len(contents) > settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024:
            raise HTTPException(
                status_code=400,
                detail=f"File size exceeds limit of {settings.MAX_UPLOAD_SIZE_MB}MB"
            )
            
        file_name = file.filename
        file_data = contents

    # For labs, validate JSON payload
    if content_type == "lab":
        try:
            json.loads(payload)
        except json.JSONDecodeError:
            raise HTTPException(status_code=400, detail="Invalid JSON payload configuration for lab")
    else:
        # For educational material, store the selected focus topic inside payload
        payload_data = {"focus_topic": focus_topic}
        payload = json.dumps(payload_data)

    new_content = Content(
        title=sanitize_text(title),
        description=sanitize_text(description),
        type=content_type,
        payload=payload,
        file_name=file_name,
        file_data=file_data,
        uploaded_by=current_user.id,
        class_id=class_id
    )
    db.add(new_content)
    db.commit()
    db.refresh(new_content)
    
    return {"message": "Content created successfully", "id": new_content.id}

@router.delete("/{content_id}")
def delete_content(content_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    content = db.query(Content).filter(Content.id == content_id).first()
    if not content:
        raise HTTPException(status_code=404, detail="Content not found")
        
    # Check ownership
    if current_user.role == "teacher" and content.uploaded_by != current_user.id:
        raise HTTPException(status_code=403, detail="You do not have permission to delete this content")
    elif current_user.role not in ["teacher", "admin"]:
        raise HTTPException(status_code=403, detail="Forbidden")
        
    db.delete(content)
    db.commit()
    return {"message": "Content deleted successfully"}

@router.get("/{content_id}/download")
def download_file(content_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    content = db.query(Content).filter(Content.id == content_id).first()
    if not content or not content.file_data:
        raise HTTPException(status_code=404, detail="File not found")
        
    # Check class access for students
    if current_user.role == "student" and content.class_id != current_user.class_id:
        raise HTTPException(status_code=403, detail="Access denied to this file")
        
    headers = {
        "Content-Disposition": f"attachment; filename=\"{content.file_name}\""
    }
    
    # Basic content-type detection
    ext = content.file_name.split(".")[-1].lower()
    content_type = "application/octet-stream"
    if ext == "pdf":
        content_type = "application/pdf"
    elif ext == "txt":
        content_type = "text/plain"
    elif ext == "json":
        content_type = "application/json"
        
from app.schemas.content_schemas import MaterialAnalysisResponse, SourceUploadRequest
from app.services.diagram_service import DiagramService

@router.post("/extract-visuals", response_model=MaterialAnalysisResponse)
async def extract_visuals(
    request: Request,
    file: Optional[UploadFile] = File(None),
    raw_text: Optional[str] = Form(None),
    title: Optional[str] = Form(None),
    focus_topic: Optional[str] = Form(None)
):
    """Processes uploaded educational source material (PDF/TXT/MD/Raw Text) and produces
    an interactive Mermaid flowchart and curated educational video references."""
    file_bytes = None
    filename = ""
    content_type = request.headers.get("content-type", "")

    # Check if JSON payload was sent
    if "application/json" in content_type:
        try:
            body_json = await request.json()
            if isinstance(body_json, dict):
                raw_text = body_json.get("raw_text") or raw_text
                title = body_json.get("title") or title
                focus_topic = body_json.get("focus_topic") or focus_topic
        except Exception:
            pass

    if file and file.filename:
        filename = file.filename
        ext = filename.split(".")[-1].lower() if "." in filename else ""
        if ext not in settings.ALLOWED_UPLOAD_EXTENSIONS:
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported file format '.{ext}'. Allowed: {', '.join(settings.ALLOWED_UPLOAD_EXTENSIONS)}"
            )

        file_bytes = await file.read()
        max_bytes = settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024
        if len(file_bytes) > max_bytes:
            raise HTTPException(
                status_code=400,
                detail=f"Uploaded file exceeds maximum limit of {settings.MAX_UPLOAD_SIZE_MB}MB"
            )

    if not file_bytes and not (raw_text and raw_text.strip()):
        raise HTTPException(
            status_code=400,
            detail="Please provide a valid source file (.pdf, .txt, .md) or paste text notes."
        )

    try:
        analysis = DiagramService.analyze_and_generate(
            file_bytes=file_bytes,
            raw_text=raw_text,
            filename=filename,
            title=title,
            focus_topic=focus_topic
        )
        return analysis
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to process and analyze source material: {str(e)}")

@router.post("/{content_id}/analyze", response_model=MaterialAnalysisResponse)
def analyze_stored_content(
    content_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Analyzes an already uploaded class note or material stored in the database."""
    content = db.query(Content).filter(Content.id == content_id).first()
    if not content:
        raise HTTPException(status_code=404, detail="Content not found")

    # Check class access for students
    if current_user.role == "student" and content.class_id != current_user.class_id:
        raise HTTPException(status_code=403, detail="Access denied to this class resource")

    focus_topic = None
    if content.payload:
        try:
            p_data = json.loads(content.payload)
            focus_topic = p_data.get("focus_topic")
        except Exception:
            pass

    try:
        if content.file_data:
            analysis = DiagramService.analyze_and_generate(
                file_bytes=content.file_data,
                filename=content.file_name or "document.pdf",
                title=content.title,
                focus_topic=focus_topic
            )
        else:
            analysis = DiagramService.analyze_and_generate(
                raw_text=content.description or content.title,
                title=content.title,
                focus_topic=focus_topic
            )
        return analysis
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error generating visual analysis: {str(e)}")
