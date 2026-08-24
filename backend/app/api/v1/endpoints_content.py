import json
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form
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
        
    return Response(content=content.file_data, media_type=content_type, headers=headers)
