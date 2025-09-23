import os
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    # API Configuration
    API_V1_STR: str = "/api/v1"
    PROJECT_NAME: str = "Customer Support AI"
    
    # Database
    DATABASE_URL: str = "sqlite:///./customer_support.db"
    
    # OpenAI Configuration
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
    
    # Voice Services (for later)
    ELEVENLABS_API_KEY: str = os.getenv("ELEVENLABS_API_KEY", "")
    
    # Authentication
    SECRET_KEY: str = os.getenv("SECRET_KEY", "your-secret-key-change-in-production")
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    
    # CORS
    BACKEND_CORS_ORIGINS: list = ["*"]  # Configure properly for production
    
    # Rate Limiting
    RATE_LIMIT_PER_MINUTE: int = 60
    
    # Environment
    ENVIRONMENT: str = os.getenv("ENVIRONMENT", "development")
    
    # Supported Languages
    SUPPORTED_LANGUAGES: list = [
        "english", "hrvatski", "slovenski", "deutsch", 
        "italiano", "français", "español", "srpski", "bosanski"
    ]
    
    class Config:
        env_file = ".env"
        extra = "ignore"  # This allows extra fields in .env to be ignored

settings = Settings()