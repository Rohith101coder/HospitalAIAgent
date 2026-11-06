import os
from pathlib import Path
from typing import Optional
from dotenv import load_dotenv
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field

# Determine base paths to reliably locate .env whether started from root or backend/
_CURRENT_DIR = Path(__file__).resolve().parent
_BACKEND_DIR = _CURRENT_DIR.parent.parent
_ROOT_DIR = _BACKEND_DIR.parent

_ENV_LOCATIONS = [
    _BACKEND_DIR / ".env",
    _ROOT_DIR / ".env",
    Path(".env")
]

for _env_file in _ENV_LOCATIONS:
    if _env_file.is_file():
        load_dotenv(dotenv_path=_env_file, override=True)
        break


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=tuple(str(p) for p in _ENV_LOCATIONS if p.is_file()) or ".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

    # Database – TiDB Cloud / MySQL
    DB_HOST: str = "localhost"
    DB_PORT: int = 4000
    DB_USER: str = "root"
    DB_PASSWORD: str = ""
    DB_NAME: str = "medibook"
    DB_SSL_CA: Optional[str] = None
    DATABASE_URL: Optional[str] = None  # Optional override, e.g. for testing sqlite

    # OpenRouter
    OPENROUTER_API_KEY: str = ""
    OPENROUTER_MODEL: str = "openai/gpt-4o-mini"
    OPENROUTER_BASE_URL: str = "https://openrouter.ai/api/v1"
    OPENROUTER_TIMEOUT_SECONDS: int = 30
    MAX_TOOL_CALLS: int = 5

    # Brevo (Sendinblue)
    BREVO_API_KEY: str = ""
    BREVO_SENDER_EMAIL: str = "noreply@medidesk.hospital"
    BREVO_SENDER_NAME: str = "MediDesk Hospital"

    # Admin Initial Credentials
    ADMIN_EMAIL: str = "admin@medidesk.hospital"
    ADMIN_PASSWORD: str = "AdminPassword123!"

    # JWT Security
    JWT_SECRET: str = "supersecretjwtkey_change_in_production_min_32_chars!"
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRE_MINUTES: int = 60

    # Application Configuration
    APP_NAME: str = "MediDesk Agent"
    APP_ENV: str = "development"
    FRONTEND_URL: str = "http://localhost:5173"
    HOSPITAL_TIMEZONE: str = "Asia/Kolkata"
    EMERGENCY_NUMBER: str = "108"
    FRONT_DESK_EMAIL: str = "frontdesk@medidesk.hospital"

    # OTP Verification
    OTP_EXPIRY_MINUTES: int = 5
    OTP_MAX_ATTEMPTS: int = 5
    OTP_RESEND_COOLDOWN_SECONDS: int = 60

    # Sessions
    CHAT_SESSION_EXPIRY_HOURS: int = 24

    # Background Scheduler
    ENABLE_SCHEDULER: bool = True

    @property
    def sqlalchemy_database_url(self) -> str:
        """Construct database URL safely or return custom override."""
        if self.DATABASE_URL:
            return self.DATABASE_URL
        password_part = f":{self.DB_PASSWORD}" if self.DB_PASSWORD else ""
        return f"mysql+pymysql://{self.DB_USER}{password_part}@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}?charset=utf8mb4"


settings = Settings()
