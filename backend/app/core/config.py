from pathlib import Path
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="MEDNLP_", env_file="../.env", extra="ignore")
    secret_key: str = "development-only-change-before-use"
    database_url: str = "sqlite:///./mednlp.db"
    storage_dir: Path = Path("./private_uploads")
    max_upload_bytes: int = Field(default=20 * 1024 * 1024, gt=0, le=1024 * 1024 * 1024)
    max_pages: int = Field(default=100, gt=0, le=500)
    cors_origins: str = "http://127.0.0.1:5173,http://localhost:5173"
    retention_days: int = 90
    tesseract_cmd: str | None = None

    @property
    def trusted_origins(self) -> list[str]:
        return [origin.strip().rstrip("/") for origin in self.cors_origins.split(",") if origin.strip()]

settings = Settings()
