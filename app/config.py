from pathlib import Path
from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

    APP_NAME: str = "Engineering Drawing Intelligence & Design Compliance Copilot"
    APP_ENV: str = "development"
    DEBUG: bool = True
    PORT: int = 8000
    HOST: str = "127.0.0.1"

    # Database: defaults to SQLite for local development
    DATABASE_URL: str = "sqlite:///./data/eng_drawing.db"

    # Storage paths
    STORAGE_DIR: Path = Path("./data/storage")
    CHROMA_PERSIST_DIR: Path = Path("./data/chroma")
    MAX_UPLOAD_SIZE_MB: int = 50

    # Security
    SECRET_KEY: str = "engineering_drawing_secret_key_change_in_production_2026"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440

    # OCR configuration
    OCR_ENGINE: str = "rapidocr"
    OCR_CONFIDENCE_THRESHOLD: float = 0.50

    # Vision Language Model configuration
    LLM_PROVIDER: str = "openai"
    LLM_MODEL: str = "gpt-4o"
    LLM_API_KEY: Optional[str] = None
    VLM_ENABLED: bool = False
    VLM_CONFIDENCE_THRESHOLD: float = 0.70

    # Vector store
    VECTOR_DB_TYPE: str = "chroma"
    EMBEDDING_MODEL: str = "all-MiniLM-L6-v2"

    # Verification and Human Review Rules
    AUTO_APPROVE_CONFIDENCE_THRESHOLD: float = 0.88
    REQUIRE_REVIEW_ON_AMBIGUOUS_FEATURE: bool = True

    def ensure_directories(self) -> None:
        self.STORAGE_DIR.mkdir(parents=True, exist_ok=True)
        (self.STORAGE_DIR / "drawings").mkdir(parents=True, exist_ok=True)
        (self.STORAGE_DIR / "specs").mkdir(parents=True, exist_ok=True)
        (self.STORAGE_DIR / "renders").mkdir(parents=True, exist_ok=True)
        (self.STORAGE_DIR / "crops").mkdir(parents=True, exist_ok=True)
        (self.STORAGE_DIR / "reports").mkdir(parents=True, exist_ok=True)
        self.CHROMA_PERSIST_DIR.mkdir(parents=True, exist_ok=True)
        Path("./data").mkdir(parents=True, exist_ok=True)


settings = Settings()
settings.ensure_directories()
