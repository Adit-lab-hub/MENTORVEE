import uuid
import datetime
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.security import get_current_user, RoleChecker
from app.models.models import User, ClassSubject, InviteCode, AuditLog
from typing import List

router = APIRouter(dependencies=[Depends(RoleChecker(["admin"]))])

# Helper to log admin actions
def log_action(db: Session, admin_id: str, action: str, target_user_id: str = None):
    log = AuditLog(
        admin_id=admin_id,
        action=action,
        target_user_id=target_user_id
    )
    db.add(log)
    db.commit()

# Invite Code Endpoints
@router.post("/invite-codes")
def generate_invite_code(payload: dict, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    email = payload.get("email")
    if not email:
        raise HTTPException(status_code=400, detail="Teacher email is required")
    
    code = f"TEACH-{uuid.uuid4().hex[:8].upper()}"
    expires_at = datetime.datetime.utcnow() + datetime.timedelta(days=7)
    
    invite = InviteCode(
        code=code,
        created_by=current_user.id,
        assigned_teacher_email=email.strip().lower(),
        expires_at=expires_at
    )
    db.add(invite)
    db.commit()
    
    log_action(db, current_user.id, f"Generated invite code {code} for {email}", None)
    invite_link = f"http://localhost:3000/index.html?invite={code}&email={email}"
    return {"id": invite.id, "code": code, "expires_at": expires_at, "invite_link": invite_link}

@router.get("/invite-codes")
def list_invite_codes(db: Session = Depends(get_db)):
    codes = db.query(InviteCode).all()
    # Update expired statuses dynamically
    now = datetime.datetime.utcnow()
    updated = False
    for c in codes:
        if c.status == "unused" and c.expires_at < now:
            c.status = "expired"
            updated = True
    if updated:
        db.commit()
    return [{
        "id": c.id,
        "code": c.code,
        "assigned_teacher_email": c.assigned_teacher_email,
        "status": c.status,
        "expires_at": c.expires_at
    } for c in codes]

@router.delete("/invite-codes/{code_id}")
def revoke_invite_code(code_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    code = db.query(InviteCode).filter(InviteCode.id == code_id).first()
    if not code:
        raise HTTPException(status_code=404, detail="Invite code not found")
    
    code.status = "revoked"
    db.commit()
    log_action(db, current_user.id, f"Revoked invite code {code.code} assigned to {code.assigned_teacher_email}")
    return {"message": "Invite code revoked successfully"}

# User approvals and status endpoints
@router.get("/pending-teachers")
def get_pending_teachers(db: Session = Depends(get_db)):
    teachers = db.query(User).filter(User.role == "teacher", User.status == "pending").all()
    return [{"id": t.id, "email": t.email, "created_at": t.created_at} for t in teachers]

@router.post("/users/{user_id}/approve")
def approve_teacher(user_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    user = db.query(User).filter(User.id == user_id, User.role == "teacher").first()
    if not user:
        raise HTTPException(status_code=404, detail="Teacher not found")
    
    user.status = "active"
    db.commit()
    log_action(db, current_user.id, f"Approved pending teacher account", user_id)
    return {"message": f"Account for {user.email} approved successfully"}

@router.post("/users/{user_id}/status")
def change_user_status(user_id: str, payload: dict, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    new_status = payload.get("status")
    if new_status not in ["active", "deactivated"]:
        raise HTTPException(status_code=400, detail="Invalid status. Must be active or deactivated")
        
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
        
    user.status = new_status
    db.commit()
    log_action(db, current_user.id, f"Changed user status to {new_status}", user_id)
    return {"message": f"User status updated to {new_status}"}

@router.delete("/users/{user_id}")
def delete_user(user_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
        
    email = user.email
    db.delete(user)
    db.commit()
    log_action(db, current_user.id, f"Deleted user account {email}", user_id)
    return {"message": "User deleted successfully"}

@router.get("/users")
def get_all_users(db: Session = Depends(get_db)):
    users = db.query(User).all()
    return [{
        "id": u.id,
        "email": u.email,
        "role": u.role,
        "status": u.status,
        "class_id": u.class_id,
        "class_name": u.class_subject.name if u.class_subject else None,
        "created_at": u.created_at
    } for u in users]

# Class/Subject management
@router.post("/classes")
def create_class(payload: dict, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    name = payload.get("name")
    code = payload.get("code")
    if not name or not code:
        raise HTTPException(status_code=400, detail="Class name and code are required")
        
    existing = db.query(ClassSubject).filter(ClassSubject.code == code.strip().upper()).first()
    if existing:
        raise HTTPException(status_code=400, detail="A class with this code already exists")
        
    cls = ClassSubject(
        name=name.strip(),
        code=code.strip().upper()
    )
    db.add(cls)
    db.commit()
    log_action(db, current_user.id, f"Created class/subject {name} ({code})")
    return {"id": cls.id, "name": cls.name, "code": cls.code}

@router.post("/users/{user_id}/assign-class")
def assign_class(user_id: str, payload: dict, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    class_id = payload.get("class_id")
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
        
    if class_id:
        cls = db.query(ClassSubject).filter(ClassSubject.id == class_id).first()
        if not cls:
            raise HTTPException(status_code=404, detail="Class not found")
        user.class_id = class_id
        action_msg = f"Assigned user to class {cls.name}"
    else:
        user.class_id = None
        action_msg = "Unassigned user from class"
        
    db.commit()
    log_action(db, current_user.id, action_msg, user_id)
    return {"message": "Class assignment updated successfully"}

# Audit Logs
@router.get("/audit-logs")
def view_audit_logs(db: Session = Depends(get_db)):
    logs = db.query(AuditLog).order_by(AuditLog.timestamp.desc()).all()
    return [{
        "id": l.id,
        "admin_email": l.admin.email if l.admin else "Unknown Admin",
        "action": l.action,
        "target_user_id": l.target_user_id,
        "timestamp": l.timestamp
    } for l in logs]
