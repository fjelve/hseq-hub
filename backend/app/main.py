import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.database import SessionLocal, create_tables
from app.routes import ambiental, auditorias, dashboard, demo, hallazgos, incidentes, legal, sostenibilidad
from app.routes.auth import router as auth_router
from app.seed_plantillas import seed_plantillas
from app.services.alertas import bucle_alertas

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    create_tables()
    db = SessionLocal()
    try:
        seed_plantillas(db)
    finally:
        db.close()
    task = asyncio.create_task(bucle_alertas())
    yield
    task.cancel()


app = FastAPI(title=settings.APP_NAME, version=settings.APP_VERSION, lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in settings.CORS_ORIGINS.split(",") if o.strip()],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

PREFIX = "/api/v1"
app.include_router(auth_router, prefix=PREFIX, tags=["Autenticación"])
app.include_router(hallazgos.router, prefix=PREFIX)
app.include_router(auditorias.router, prefix=PREFIX)
app.include_router(dashboard.router, prefix=PREFIX)
app.include_router(incidentes.router, prefix=PREFIX)
app.include_router(legal.router, prefix=PREFIX)
app.include_router(ambiental.router, prefix=PREFIX)
app.include_router(sostenibilidad.router, prefix=PREFIX)
app.include_router(demo.router, prefix=PREFIX)


@app.get("/health")
def health():
    return {"status": "ok", "version": settings.APP_VERSION}
