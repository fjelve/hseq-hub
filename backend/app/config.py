from functools import lru_cache
from pydantic_settings import BaseSettings

INSECURE_DEFAULT_KEY = "cambiar-esta-clave"


class Settings(BaseSettings):
    APP_NAME: str = "HSEQ Hub"
    APP_VERSION: str = "0.1.0"
    ENV: str = "development"  # development | production
    # Las empresas las crea el superadmin de la plataforma. Poner true solo para demos abiertas.
    REGISTRO_PUBLICO: bool = False
    DATABASE_URL: str = "sqlite:///./hseq.db"
    SECRET_KEY: str = INSECURE_DEFAULT_KEY
    TOKEN_EXPIRE_MINUTES: int = 480
    CORS_ORIGINS: str = "http://localhost:8080,http://localhost:3000"
    # Solo desarrollo y pruebas: crear tablas sin Alembic. En producción se usa `alembic upgrade head`.
    AUTO_CREATE_TABLES: bool = False
    FRONTEND_DIR: str = ""  # carpeta del frontend a servir en "/" (mismo origen que la API)

    # Límite de intentos (en memoria; por proceso)
    TRUST_PROXY: bool = False  # true solo si la API está detrás de Nginx/Cloudflare y no es accesible directo
    LOGIN_MAX_FALLOS: int = 5  # por IP y correo
    LOGIN_MAX_FALLOS_IP: int = 30  # por IP, en total
    LOGIN_VENTANA_MIN: int = 15
    REGISTRO_MAX_POR_HORA: int = 5  # altas de empresa por IP

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
