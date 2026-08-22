from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings
from app.api.v1 import endpoints_os, endpoints_dbms, endpoints_schema, ws_telemetry

app = FastAPI(
    title=settings.PROJECT_NAME,
    openapi_url=f"{settings.API_V1_STR}/openapi.json"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(endpoints_os.router, prefix=f"{settings.API_V1_STR}/os", tags=["OS Simulator"])
app.include_router(endpoints_dbms.router, prefix=f"{settings.API_V1_STR}/dbms", tags=["DBMS Simulator"])
app.include_router(endpoints_schema.router, prefix=f"{settings.API_V1_STR}/schema", tags=["Faculty Engine"])
app.include_router(ws_telemetry.router, prefix=f"{settings.API_V1_STR}/ws", tags=["Telemetry"])

@app.get("/")
def read_root():
    return {"message": "Welcome to Concept-to-System Simulation Sandbox Backend API"}
