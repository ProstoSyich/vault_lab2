from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=BASE_DIR / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    database_url: str
    jwt_secret: str
    jwt_algorithm: str = "HS256"
    access_token_ttl_min: int = 60
    password_pepper: str
    password_min_length: int = 12
    environment: str = "development"
    app_name: str = "Vault"
    log_level: str = "INFO"


settings = Settings()
