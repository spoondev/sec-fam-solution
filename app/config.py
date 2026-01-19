from pydantic_settings import BaseSettings
from pydantic import Field
from pathlib import Path


class Settings(BaseSettings):
    """Application settings loaded from environment variables"""

    # API Configuration
    SEC_API_KEY: str = Field(
        default="",
        description="SEC API key from sec-api.io"
    )

    # Database
    DATABASE_URL: str = Field(
        default="sqlite:///./data/sec_filings.db",
        description="SQLite database URL"
    )

    # Document Storage
    DOCUMENT_SAVE_PATH: str = Field(
        default="./data/documents",
        description="Default path for saving downloaded documents"
    )

    # Scheduler Settings
    SCAN_DAY_OF_WEEK: int = Field(
        default=6,  # Sunday
        ge=0,
        le=6,
        description="Day of week for scheduled scan (0=Monday, 6=Sunday)"
    )
    SCAN_HOUR: int = Field(
        default=2,
        ge=0,
        le=23,
        description="Hour of day for scheduled scan (24-hour format)"
    )
    SCAN_MINUTE: int = Field(
        default=0,
        ge=0,
        le=59,
        description="Minute of hour for scheduled scan"
    )

    # Application Settings
    APP_HOST: str = Field(default="0.0.0.0")
    APP_PORT: int = Field(default=8000)
    DEBUG: bool = Field(default=False)

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "case_sensitive": True,
    }


# Global settings instance
settings = Settings()
