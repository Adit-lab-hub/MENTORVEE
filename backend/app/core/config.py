import os
from pydantic_settings import BaseSettings
from typing import List

class Settings(BaseSettings):
    PROJECT_NAME: str = "MENTORVEE Concept-to-System Simulation Engine"
    API_V1_STR: str = "/api/v1"
    
    # OS Simulation Defaults
    DEFAULT_PAGE_SIZE_KB: int = 4
    DEFAULT_PHYSICAL_RAM_MB: int = 16
    DEFAULT_CONTEXT_SWITCH_MS: float = 0.5
    
    # DBMS Simulation Defaults
    DEFAULT_BLOCK_SIZE_BYTES: int = 4096
    DEFAULT_BUFFER_POOL_SIZE: int = 100
    DEFAULT_DISK_SEEK_MS: float = 8.0
    DEFAULT_DISK_TRANSFER_MBPS: float = 100.0
    DEFAULT_CPU_LATENCY_MS: float = 0.05
    
    # LLM Settings
    GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
    
    # Security Settings
    SUPABASE_URL: str = os.getenv("SUPABASE_URL", "")
    SUPABASE_ANON_KEY: str = os.getenv("SUPABASE_ANON_KEY", "")
    SUPABASE_JWT_SECRET: str = os.getenv("SUPABASE_JWT_SECRET", "")
    
    LOCAL_JWT_SECRET: str = os.getenv("LOCAL_JWT_SECRET", "super-secret-fallback-key-change-it-in-prod")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    
    ALLOWED_EMAIL_DOMAINS: List[str] = ["collegename.edu"]
    
    MAX_UPLOAD_SIZE_MB: int = 5
    ALLOWED_UPLOAD_EXTENSIONS: List[str] = ["txt", "pdf", "json"]

    class Config:
        case_sensitive = True

settings = Settings()
