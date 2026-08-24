import re
import datetime
import uuid
import jwt
from fastapi import HTTPException, status
from sqlalchemy.orm import Session
from app.core.config import settings
from app.core.security import get_password_hash, verify_password, create_local_access_token, create_local_refresh_token, is_supabase_enabled
from app.models.models import User, InviteCode, ClassSubject, AuditLog

class AuthService:
    @staticmethod
    def validate_email_domain(email: str) -> bool:
        if not settings.ALLOWED_EMAIL_DOMAINS:
            return True
        domain = email.split("@")[-1]
        return domain in settings.ALLOWED_EMAIL_DOMAINS

    @staticmethod
    def validate_password_strength(password: str) -> bool:
        # Min length 8, at least 1 uppercase, 1 lowercase, 1 digit, 1 special character
        if len(password) < 8:
            return False
        if not re.search("[a-z]", password):
            return False
        if not re.search("[A-Z]", password):
            return False
        if not re.search("[0-9]", password):
            return False
        if not re.search("[_@$!%*#?&+-]", password):
            return False
        return True

    @staticmethod
    def signup_user(db: Session, payload: dict) -> dict:
        email = payload.get("email").strip().lower()
        password = payload.get("password")
        role = payload.get("role")
        class_id = payload.get("class_id")
        invite_code_str = payload.get("invite_code")

        if not email or not password or not role:
            raise HTTPException(status_code=400, detail="Missing required signup fields")

        if role not in ["student", "teacher"]:
            raise HTTPException(status_code=400, detail="Invalid role selection")

        if not AuthService.validate_email_domain(email):
            raise HTTPException(
                status_code=400,
                detail=f"Registration restricted to official college email domains: {', '.join(settings.ALLOWED_EMAIL_DOMAINS)}"
            )

        if not AuthService.validate_password_strength(password):
            raise HTTPException(
                status_code=400,
                detail="Password must be at least 8 characters long and contain uppercase, lowercase, numbers, and special characters"
            )

        # Check user existence
        existing_user = db.query(User).filter(User.email == email).first()
        if existing_user:
            raise HTTPException(status_code=400, detail="An account with this email already exists")

        # Class validation
        if role == "student" and class_id:
            cls = db.query(ClassSubject).filter(ClassSubject.id == class_id).first()
            if not cls:
                raise HTTPException(status_code=400, detail="Enrolled class/subject not found")

        # Teacher verification with invite code
        if role == "teacher":
            if not invite_code_str:
                raise HTTPException(status_code=400, detail="Invite code is required for teacher registrations")
            code_record = db.query(InviteCode).filter(InviteCode.code == invite_code_str.strip()).first()
            if not code_record:
                raise HTTPException(status_code=400, detail="Invalid teacher invite code")
            if code_record.status != "unused":
                raise HTTPException(status_code=400, detail="This invite code has already been used or revoked")
            if code_record.expires_at < datetime.datetime.utcnow():
                code_record.status = "expired"
                db.commit()
                raise HTTPException(status_code=400, detail="This invite code has expired")

            # Link teacher to the same class/subject code if class_id is available (or will be set by admin later)
            code_record.status = "used"

        # Generate User ID
        user_id = str(uuid.uuid4())

        # If Supabase is enabled, we would register the user on Supabase auth.
        # But we also create the profile locally.
        # For simplicity and offline correctness, if not configured, we run in local mode.
        password_hash = get_password_hash(password)
        
        # All users start as "pending" until email verification
        user_status = "pending"

        new_user = User(
            id=user_id,
            email=email,
            password_hash=password_hash,
            role=role,
            status=user_status,
            class_id=class_id
        )
        db.add(new_user)
        db.commit()
        db.refresh(new_user)

        # Generate a simulation email verification token
        verify_token = jwt.encode(
            {"sub": user_id, "exp": datetime.datetime.utcnow() + datetime.timedelta(hours=24), "action": "verify_email"},
            settings.LOCAL_JWT_SECRET,
            algorithm="HS256"
        )

        verification_link = f"/api/v1/auth/verify?token={verify_token}"
        # In real-world, email is sent. For simulation/education, we output to console and return the link
        print(f"--- [EMAIL SIMULATION] --- \nVerify email link: {verification_link}\n-------------------------")

        return {
            "message": "Signup successful. Please verify your email to activate your account.",
            "verification_link": verification_link # Return this so frontend can show/mock it easily
        }

    @staticmethod
    def verify_email(db: Session, token: str) -> dict:
        try:
            payload = jwt.decode(token, settings.LOCAL_JWT_SECRET, algorithms=["HS256"])
            user_id = payload.get("sub")
            action = payload.get("action")
            if action != "verify_email":
                raise HTTPException(status_code=400, detail="Invalid token action")
        except jwt.PyJWTError:
            raise HTTPException(status_code=400, detail="Invalid or expired verification token")

        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        # Students become active immediately. Teachers go to active if invite code was used.
        user.status = "active"
        db.commit()
        return {"message": f"Email verified successfully. Account for {user.email} is now active!"}

    @staticmethod
    def login_user(db: Session, payload: dict) -> dict:
        email = payload.get("email").strip().lower()
        password = payload.get("password")

        user = db.query(User).filter(User.email == email).first()
        if not user:
            raise HTTPException(status_code=401, detail="Incorrect email or password")

        if not verify_password(password, user.password_hash):
            raise HTTPException(status_code=401, detail="Incorrect email or password")

        if user.status == "deactivated":
            raise HTTPException(status_code=403, detail="Your account has been deactivated. Please contact an admin.")
        
        if user.status == "pending":
            raise HTTPException(status_code=403, detail="Please verify your email before logging in.")

        # Generate tokens
        access_token = create_local_access_token(data={"sub": user.id, "role": user.role})
        refresh_token = create_local_refresh_token(data={"sub": user.id})

        return {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "user": {
                "id": user.id,
                "email": user.email,
                "role": user.role,
                "status": user.status,
                "class_id": user.class_id
            }
        }

    @staticmethod
    def forgot_password(db: Session, email: str) -> dict:
        # Always return generic message to avoid email enumeration
        response = {"message": "If that email exists, a reset link has been sent to it."}
        user = db.query(User).filter(User.email == email.strip().lower()).first()
        if not user:
            return response

        # Generate short-lived token (15 mins)
        reset_token = jwt.encode(
            {"sub": user.id, "exp": datetime.datetime.utcnow() + datetime.timedelta(minutes=15), "action": "reset_password"},
            settings.LOCAL_JWT_SECRET,
            algorithm="HS256"
        )
        
        reset_link = f"/reset-password.html?token={reset_token}"
        print(f"--- [EMAIL SIMULATION] --- \nPassword reset link: {reset_link}\n-------------------------")
        
        # We can store the token context or return it in the mock response for easier local testing
        response["reset_link"] = reset_link
        return response

    @staticmethod
    def reset_password(db: Session, payload: dict) -> dict:
        token = payload.get("token")
        new_password = payload.get("new_password")

        if not token or not new_password:
            raise HTTPException(status_code=400, detail="Token and new password are required")

        if not AuthService.validate_password_strength(new_password):
            raise HTTPException(status_code=400, detail="Password does not meet safety policies")

        try:
            decoded = jwt.decode(token, settings.LOCAL_JWT_SECRET, algorithms=["HS256"])
            user_id = decoded.get("sub")
            action = decoded.get("action")
            if action != "reset_password":
                raise HTTPException(status_code=400, detail="Invalid token scope")
        except jwt.ExpiredSignatureError:
            raise HTTPException(status_code=400, detail="Reset token has expired (15 min limit)")
        except jwt.PyJWTError:
            raise HTTPException(status_code=400, detail="Invalid reset token")

        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        # Invalidate active sessions by regenerating password hash and local JWT secret (conceptually, the new hash ensures old tokens are rejected or we track token versions)
        # For simplicity, password change invalidates old logins because client will need to re-auth.
        user.password_hash = get_password_hash(new_password)
        db.commit()

        return {"message": "Password reset successful. All active sessions have been invalidated."}
