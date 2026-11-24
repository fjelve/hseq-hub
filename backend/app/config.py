from functools import lru_cache
from pydantic_settings import BaseSettings

INSECURE_DEFAULT_KEY = "cambiar-esta-clave"


class Settings(BaseSettings):
    APP_NAME: str = "HSEQ Hub"
    APP_VERSION: str = "0.1.0"
    ENV: str = "development"  # development | production
    DATABASE_URL: str = "sqlite:///./hseq.db"
    SECRET_KEY: str = INSECURE_DEFAULT_KEY
    TOKEN_EXPIRE_MINUTES: int = 480
    CORS_ORIGINS: str = "http://localhost:8080,http://localhost:3000"

    # Alertas automáticas
    ALERT_INTERVAL_MINUTES: int = 60
    ALERT_DAYS_BEFORE: int = 3  # avisar N días antes del vencimiento
    SMTP_HOST: str = ""
    SMTP_PORT: int = 587
    SMTP_USER: str = ""
    SMTP_PASSWORD: str = ""
    SMTP_FROM: str = "alertas@hseqhub.local"

    class Config:
        env_file = ".env"


@lru_cache
def get_settings() -> Settings:
    s = Settings()
    if s.ENV == "production" and s.SECRET_KEY == INSECURE_DEFAULT_KEY:
        raise RuntimeError("SECRET_KEY debe configurarse en producción")
    return s
