import datetime
from sqlalchemy import Column, Integer, String, DateTime, Text, ForeignKey, LargeBinary, Boolean
from sqlalchemy.orm import relationship
from app.core.database import Base

class ClassSubject(Base):
    __tablename__ = "classes"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True, nullable=False)
    code = Column(String, unique=True, index=True, nullable=False)  # e.g., CS101
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

class User(Base):
    __tablename__ = "users"
    
    id = Column(String, primary_key=True, index=True)  # UUID from Supabase or Local Auth
    email = Column(String, unique=True, index=True, nullable=False)
    password_hash = Column(String, nullable=True)      # For local fallback auth
    role = Column(String, nullable=False)             # admin, teacher, student
    status = Column(String, default="pending")        # active, pending, deactivated
    class_id = Column(Integer, ForeignKey("classes.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    
    class_subject = relationship("ClassSubject")

class InviteCode(Base):
    __tablename__ = "invite_codes"
    
    id = Column(Integer, primary_key=True, index=True)
    code = Column(String, unique=True, index=True, nullable=False)
    created_by = Column(String, ForeignKey("users.id"), nullable=False)
    assigned_teacher_email = Column(String, nullable=False)
    status = Column(String, default="unused")         # unused, used, expired
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    expires_at = Column(DateTime, nullable=False)

class Content(Base):
    __tablename__ = "contents"
    
    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    type = Column(String, nullable=False)             # material, lab
    payload = Column(Text, nullable=True)             # JSON config or text content
    file_name = Column(String, nullable=True)
    file_data = Column(LargeBinary, nullable=True)     # Binary file data
    uploaded_by = Column(String, ForeignKey("users.id"), nullable=False)
    class_id = Column(Integer, ForeignKey("classes.id"), nullable=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    
    uploader = relationship("User")
    class_subject = relationship("ClassSubject")

class AuditLog(Base):
    __tablename__ = "audit_logs"
    
    id = Column(Integer, primary_key=True, index=True)
    admin_id = Column(String, ForeignKey("users.id"), nullable=False)
    action = Column(String, nullable=False)
    target_user_id = Column(String, nullable=True)
    timestamp = Column(DateTime, default=datetime.datetime.utcnow)
    
    admin = relationship("User")
