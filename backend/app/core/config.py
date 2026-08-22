import os
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    PROJECT_NAME: str = "SysSandbox Concept-to-System Simulation Engine"
    API_V1_STR: str = "/api/v1"
    
    # OS Simulation Defaults
    DEFAULT_PAGE_SIZE_KB: int = 4
    DEFAULT_PHYSICAL_RAM_MB: int = 16  # Small memory to make thrashing easy to trigger
    DEFAULT_CONTEXT_SWITCH_MS: float = 0.5
    
    # DBMS Simulation Defaults
    DEFAULT_BLOCK_SIZE_BYTES: int = 4096
    DEFAULT_BUFFER_POOL_SIZE: int = 100  # Number of pages in memory buffer pool
    DEFAULT_DISK_SEEK_MS: float = 8.0   # HDD-like seek latency for realistic cost comparisons
    DEFAULT_DISK_TRANSFER_MBPS: float = 100.0  # Sequential read transfer speed
    DEFAULT_CPU_LATENCY_MS: float = 0.05       # Time to process a tuple / node hop
    
    # LLM Settings (for diagnostics)
    GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
    
    class Config:
        case_sensitive = True

settings = Settings()
