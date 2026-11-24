#!/bin/sh
# Arranque del contenedor de HSEQ Hub: migra la base y levanta la API.
#
# Mismo criterio que Centinela:
#   - base vacia                    -> alembic upgrade head (crea el esquema)
#   - esquema sin control de Alembic -> alembic stamp 0001 y luego upgrade head
#   - Alembic ya inicializado        -> alembic upgrade head (solo pendientes)
set -e
cd /app
echo "[entrypoint] Verificando estado de migraciones..."
set +e
python - <<'PY'
import sys
from sqlalchemy import create_engine, inspect
from app.config import get_settings
tablas = set(inspect(create_engine(get_settings().DATABASE_URL)).get_table_names())
if "alembic_version" in tablas:
    sys.exit(0)
sys.exit(10 if "empresas" in tablas else 20)
PY
estado=$?
set -e
if [ "$estado" -eq 10 ]; then
    echo "[entrypoint] Esquema existente sin Alembic: stamp 0001 y luego upgrade."
    alembic stamp 0001
elif [ "$estado" -eq 20 ]; then
    echo "[entrypoint] Base vacia: se crea el esquema."
fi
alembic upgrade head
echo "[entrypoint] Migraciones OK. Arrancando API (1 worker: el bucle de alertas corre dentro del proceso)."
exec uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 1
