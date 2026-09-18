import os
from typing import Optional

# We use standard pydantic or pydantic_settings
try:
    from pydantic_settings import BaseSettings, SettingsConfigDict
except ImportError:
    from pydantic import BaseModel as BaseSettings
    SettingsConfigDict = None

class Settings(BaseSettings):
    PROJECT_NAME: str = "Autonomous Multi-Hospital Healthcare Access Platform"
    API_V1_STR: str = "/api"
    SECRET_KEY: str = os.getenv("JWT_SECRET", "super-secret-healthcare-prototype-key-38472918")
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 # 24 hours
    DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite:///./healthcare_platform.db")
    
    # LLM & AI configuration
    LLM_PROVIDER: str = os.getenv("LLM_PROVIDER", "structured_agent") # structured_agent, openai, gemini
    LLM_API_KEY: Optional[str] = os.getenv("LLM_API_KEY", None)
    LLM_MODEL: str = os.getenv("LLM_MODEL", "gemini-1.5-pro")
    
    # Voice configuration
    VOICE_PROVIDER: str = os.getenv("VOICE_PROVIDER", "browser") # browser, mock, external
    VOICE_API_KEY: Optional[str] = os.getenv("VOICE_API_KEY", None)
    STT_API_KEY: Optional[str] = os.getenv("STT_API_KEY", None)
    TTS_API_KEY: Optional[str] = os.getenv("TTS_API_KEY", None)
    
    model_config = SettingsConfigDict(env_file=".env", extra="allow") if SettingsConfigDict is not None else {"extra": "allow"}

settings = Settings()
