from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings
from app.core.database import engine, Base, SessionLocal
from app.models.models import ClassSubject, User
from app.api.v1 import endpoints_os, endpoints_dbms, endpoints_schema, ws_telemetry, endpoints_auth, endpoints_admin, endpoints_content
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from app.api.v1.endpoints_auth import limiter

# Create DB Tables
Base.metadata.create_all(bind=engine)

# Seed database on startup
def seed_db():
    db = SessionLocal()
    try:
        # Seed classes
        if not db.query(ClassSubject).first():
            c1 = ClassSubject(name="Operating Systems", code="OS")
            c2 = ClassSubject(name="Database Management Systems", code="DBMS")
            db.add_all([c1, c2])
            db.commit()
            print("[SEED] Default classes seeded.")
            
        # Seed default Admin account
        admin = db.query(User).filter(User.role == "admin").first()
        if not admin:
            from app.core.security import get_password_hash
            admin_user = User(
                id="admin-default-uuid-1122",
                email="admin@collegename.edu",
                password_hash=get_password_hash("AdminPassword123!"),
                role="admin",
                status="active"
            )
            db.add(admin_user)
            db.commit()
            print("--- [SEED] Default Admin created: admin@collegename.edu / AdminPassword123! ---")
    except Exception as e:
        print(f"[SEED ERROR] Could not seed database: {e}")
    finally:
        db.close()

seed_db()

app = FastAPI(
    title=settings.PROJECT_NAME,
    openapi_url=f"{settings.API_V1_STR}/openapi.json"
)

# Enforce secure CORS origins (wildcards are blocked when allow_credentials is True)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000", "http://localhost:8000", "http://127.0.0.1:8000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# SlowAPI Rate limiting setup
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# Include Routers
app.include_router(endpoints_auth.router, prefix=f"{settings.API_V1_STR}/auth", tags=["Authentication"])
app.include_router(endpoints_admin.router, prefix=f"{settings.API_V1_STR}/admin", tags=["Administration"])
app.include_router(endpoints_content.router, prefix=f"{settings.API_V1_STR}/content", tags=["Class Content"])
app.include_router(endpoints_os.router, prefix=f"{settings.API_V1_STR}/os", tags=["OS Simulator"])
app.include_router(endpoints_dbms.router, prefix=f"{settings.API_V1_STR}/dbms", tags=["DBMS Simulator"])
app.include_router(endpoints_schema.router, prefix=f"{settings.API_V1_STR}/schema", tags=["Faculty Engine"])
app.include_router(ws_telemetry.router, prefix=f"{settings.API_V1_STR}/ws", tags=["Telemetry"])

@app.get("/")
def read_root():
    return {"message": "Welcome to MENTORVEE Concept-to-System Simulation Backend API"}
