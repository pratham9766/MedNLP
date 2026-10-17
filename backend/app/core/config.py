from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="MEDNLP_", env_file="../.env", extra="ignore")
    secret_key: str = "development-only-change-before-use"
    database_url: str = "sqlite:///./mednlp.db"
    storage_dir: Path = Path("./private_uploads")
    max_upload_bytes: int = 20 * 1024 * 1024
    retention_days: int = 90

settings = Settings()
