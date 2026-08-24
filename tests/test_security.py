import os
# Force tests to use a separate test database
os.environ["DATABASE_URL"] = "sqlite:///./test_mentorvee.db"

import pytest
import jwt
import datetime
from fastapi.testclient import TestClient
from app.main import app
from app.core.config import settings
from app.core.database import SessionLocal, engine, Base
from app.models.models import User, InviteCode, ClassSubject, Content
from app.services.auth_service import AuthService
from app.core.security import create_local_access_token

client = TestClient(app)

@pytest.fixture(autouse=True, scope="function")
def init_db():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    # Clear tables
    db.query(Content).delete()
    db.query(InviteCode).delete()
    db.query(User).delete()
    db.query(ClassSubject).delete()
    db.commit()
    db.close()
    yield

def test_email_domain_validation():
    # settings.ALLOWED_EMAIL_DOMAINS defaults to ["collegename.edu"]
    assert AuthService.validate_email_domain("test@collegename.edu") is True
    assert AuthService.validate_email_domain("test@gmail.com") is False

def test_password_strength_validation():
    # Min length 8, uppercase, lowercase, numbers, special characters
    assert AuthService.validate_password_strength("Short1!") is False
    assert AuthService.validate_password_strength("NoDigitsAndSymbols") is False
    assert AuthService.validate_password_strength("nodigitsandsymbols1!") is False
    assert AuthService.validate_password_strength("StrongPass123!") is True

def test_student_restricted_actions():
    db = SessionLocal()
    # Create a student user
    student = User(
        id="student-test-uuid",
        email="student@collegename.edu",
        role="student",
        status="active"
    )
    db.add(student)
    db.commit()
    db.close()

    # Generate token
    token = create_local_access_token(data={"sub": "student-test-uuid", "role": "student"})
    
    # Try to access admin endpoints (e.g. generate invite code) - should fail with 403
    response = client.post(
        "/api/v1/admin/invite-codes",
        json={"email": "teacher@collegename.edu"},
        cookies={"sb-access-token": token}
    )
    assert response.status_code == 403

    # Try to create class content - should fail with 403
    response = client.post(
        "/api/v1/content",
        data={"title": "Test Material", "class_id": 1, "content_type": "material", "payload": ""},
        cookies={"sb-access-token": token}
    )
    assert response.status_code == 403

def test_teacher_invite_code_single_use():
    db = SessionLocal()
    # Create admin
    admin = User(id="admin-uuid", email="admin@collegename.edu", role="admin", status="active")
    db.add(admin)
    db.commit()
    
    # Generate code
    invite = InviteCode(
        code="TEACH-CODE1",
        created_by="admin-uuid",
        assigned_teacher_email="teacher@collegename.edu",
        status="unused",
        expires_at=datetime.datetime.utcnow() + datetime.timedelta(days=7)
    )
    db.add(invite)
    db.commit()
    db.close()

    # Register teacher using code
    payload = {
        "email": "teacher@collegename.edu",
        "password": "TeacherPass123!",
        "role": "teacher",
        "invite_code": "TEACH-CODE1"
    }
    response = client.post("/api/v1/auth/signup", json=payload)
    assert response.status_code == 200

    # Try registering again with same code - should fail with 400
    payload2 = {
        "email": "teacher2@collegename.edu",
        "password": "TeacherPass123!",
        "role": "teacher",
        "invite_code": "TEACH-CODE1"
    }
    response = client.post("/api/v1/auth/signup", json=payload2)
    assert response.status_code == 400
    assert "already been used" in response.json()["detail"]
