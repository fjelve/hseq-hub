"""Carga datos de ejemplo en la empresa de un usuario administrador, desde la consola.

Uso (dentro del contenedor):
    docker exec hseq_api python -m app.cargar_demo --email cliente@empresa.com

Solo actúa sobre cuentas sin actividad real (sin hallazgos, incidentes, horas ni auditorías
respondidas). No pide la contraseña del usuario.
"""
import argparse
import sys

from app.database import SessionLocal
from app.models import Empresa, Usuario
from app.routes.demo import cargar_datos_demo, cuenta_sin_actividad


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--email", required=True, help="correo de un administrador de la empresa")
    a = p.parse_args()
    db = SessionLocal()
    try:
        user = db.query(Usuario).filter(Usuario.email == a.email.strip().lower()).first()
        if not user or user.rol != "admin":
            print("No existe un administrador con ese correo.", file=sys.stderr)
            return 1
        emp = db.get(Empresa, user.empresa_id)
        if not cuenta_sin_actividad(db, emp.id):
            print(f"La empresa '{emp.nombre}' ya tiene actividad; no se cargó nada.", file=sys.stderr)
            return 1
        cargar_datos_demo(db, user, actor=None)
        print(f"Datos de ejemplo cargados en '{emp.nombre}' ({emp.sector}, {emp.pais}).")
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main())
