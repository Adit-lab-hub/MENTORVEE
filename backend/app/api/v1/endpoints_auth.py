from fastapi import APIRouter, Depends, Response, Request, HTTPException, status
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.security import get_current_user
from app.services.auth_service import AuthService
from app.models.models import User, ClassSubject
from slowapi import Limiter
from slowapi.util import get_remote_address
from typing import List

router = APIRouter()
limiter = Limiter(key_func=get_remote_address)

@router.post("/signup")
@limiter.limit("5/minute")
def signup(request: Request, payload: dict, db: Session = Depends(get_db)):
    return AuthService.signup_user(db, payload)

@router.get("/verify")
def verify(token: str, db: Session = Depends(get_db)):
    result = AuthService.verify_email(db, token)
    from fastapi.responses import HTMLResponse
    return HTMLResponse(content=f"""
        <html>
            <head>
                <title>Email Verified</title>
                <style>
                    body {{ font-family: sans-serif; display: flex; justify-content: center; align-items: center; height: 100vh; background: #0f172a; color: #f8fafc; margin: 0; }}
                    .card {{ background: #1e293b; padding: 2rem; border-radius: 8px; box-shadow: 0 4px 6px -1px rgba(0,0,0,0.1); text-align: center; }}
                    a {{ color: #38bdf8; text-decoration: none; font-weight: bold; }}
                    a:hover {{ text-decoration: underline; }}
                </style>
            </head>
            <body>
                <div class="card">
                    <h2>🎉 Verification Successful!</h2>
                    <p>{result['message']}</p>
                    <p><a href="/">Go to App Login</a></p>
                </div>
            </body>
        </html>
    """)

@router.post("/login")
@limiter.limit("10/minute")
def login(request: Request, payload: dict, response: Response, db: Session = Depends(get_db)):
    result = AuthService.login_user(db, payload)
    
    response.set_cookie(
        key="sb-access-token",
        value=result["access_token"],
        httponly=True,
        max_age=3600,
        expires=3600,
        samesite="lax",
        secure=False
    )
    response.set_cookie(
        key="sb-refresh-token",
        value=result["refresh_token"],
        httponly=True,
        max_age=7*24*3600,
        expires=7*24*3600,
        samesite="lax",
        secure=False
    )
    
    return {"message": "Login successful", "user": result["user"]}

@router.post("/logout")
def logout(response: Response):
    response.delete_cookie("sb-access-token", path="/")
    response.delete_cookie("sb-refresh-token", path="/")
    return {"message": "Logged out successfully"}

@router.post("/forgot-password")
@limiter.limit("3/minute")
def forgot_password(request: Request, payload: dict, db: Session = Depends(get_db)):
    email = payload.get("email")
    if not email:
        raise HTTPException(status_code=400, detail="Email is required")
    return AuthService.forgot_password(db, email)

@router.post("/reset-password")
@limiter.limit("3/minute")
def reset_password(request: Request, payload: dict, db: Session = Depends(get_db)):
    return AuthService.reset_password(db, payload)

@router.get("/me")
def get_me(current_user: User = Depends(get_current_user)):
    return {
        "id": current_user.id,
        "email": current_user.email,
        "role": current_user.role,
        "status": current_user.status,
        "class_id": current_user.class_id
    }

@router.get("/classes", response_model=List[dict])
def list_classes(db: Session = Depends(get_db)):
    classes = db.query(ClassSubject).all()
    return [{"id": c.id, "name": c.name, "code": c.code} for c in classes]
