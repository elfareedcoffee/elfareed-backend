from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    PROJECT_NAME: str = "Ben El Fareed Backend"
    API_V1_STR: str = "/api/v1"
    ENVIRONMENT: str = "development"
    ENABLE_HSTS: bool = False
    LOG_LEVEL: str = "INFO"
    
    # Session Encryption
    SESSION_ENCRYPTION_KEY: Optional[str] = None
    
    # SMS Configuration
    SMS_ENABLED: bool = False
    SMS_PROVIDER: Optional[str] = None
    SMS_API_KEY: Optional[str] = None
    SMS_API_SECRET: Optional[str] = None
    SMS_SENDER: Optional[str] = None
    
    # Supabase
    SUPABASE_URL: str
    SUPABASE_ANON_KEY: str
    SUPABASE_SERVICE_ROLE_KEY: str
    
    # Database
    DATABASE_URL: str
    DB_POOL_SIZE: int = 5
    DB_MAX_OVERFLOW: int = 10
    DB_POOL_TIMEOUT: int = 30

    # CORS
    ALLOWED_ORIGINS: list[str] = []
    
    # Redis (for Rate Limiting)
    REDIS_URL: Optional[str] = None
    
    # Vercel Cron Secret
    CRON_SECRET: Optional[str] = None

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

settings = Settings()
