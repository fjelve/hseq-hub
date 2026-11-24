"""Crea el usuario superadmin de la plataforma.

Uso (dentro del contenedor):
    docker exec -it hseq_api python -m app.crear_superadmin --email tu@correo.com --nombre "Tu Nombre"
La contraseña se pide por teclado, o se toma de la variable SUPERADMIN_PASSWORD (no queda
en el historial si se pasa con `docker exec -e`). El usuario deberá cambiarla al ingresar.
"""
import argparse
import getpass
import os
import sys

from app.auth import hash_password
from app.database import SessionLocal
from app.models import Empresa, Usuario
from app.routes.plataforma import SECTOR_PLATAFORMA


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--email", required=True)
    p.add_argument("--nombre", required=True)
    a = p.parse_args()
    email = a.email.strip().lower()
    password = os.environ.get("SUPERADMIN_PASSWORD") or getpass.getpass("Contraseña inicial (mín. 10 caracteres): ")
    if not 10 <= len(password) <= 72:
        print("La contraseña debe tener entre 10 y 72 caracteres.", file=sys.stderr)
        return 2
    db = SessionLocal()
    try:
        if db.query(Usuario).filter(Usuario.email == email).first():
            print(f"Ya existe un usuario con el correo {email}. No se modificó nada.", file=sys.stderr)
            return 1
        emp = db.query(Empresa).filter(Empresa.sector == SECTOR_PLATAFORMA).first()
        if not emp:
            emp = Empresa(nombre="Plataforma", sector=SECTOR_PLATAFORMA, pais="chile")
            db.add(emp)
            db.flush()
        db.add(Usuario(empresa_id=emp.id, nombre=a.nombre.strip(), email=email, rol="superadmin",
                       password_hash=hash_password(password), debe_cambiar_password=True))
        db.commit()
        print(f"Superadmin creado: {email}. Deberá cambiar la contraseña al ingresar.")
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main())
