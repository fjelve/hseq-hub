from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app import ratelimit
from app.auth import (
    create_token, current_user, hash_password, require_roles, usuario_sin_restricciones, verify_password,
)
from app.config import get_settings
from app.database import get_db
from app.models import Empresa, Usuario
from app.schemas import RegistroIn, UsuarioIn, UsuarioOut
from app.services.bitacora import registrar

router = APIRouter()

# Hash de una contraseña inexistente: se compara igual cuando el correo no existe,
# para que el tiempo de respuesta no revele qué correos están registrados.
_HASH_FALSO = hash_password("contraseña-inexistente-0000")


def crear_empresa_con_admin(db: Session, actor: Usuario | None, *, empresa: str, sector: str, pais: str,
                            nombre: str, email: str, password: str, cambiar_password: bool) -> Usuario:
    """Crea una empresa y su administrador. Lo usan el registro público y el superadmin."""
    if db.query(Usuario).filter(Usuario.email == email).first():
        raise HTTPException(409, "El correo ya está registrado")
    emp = Empresa(nombre=empresa, sector=sector, pais=pais)
    db.add(emp)
    db.flush()
    admin = Usuario(empresa_id=emp.id, nombre=nombre, email=email, rol="admin",
                    password_hash=hash_password(password), debe_cambiar_password=cambiar_password)
    db.add(admin)
    db.flush()
    registrar(db, emp.id, actor or admin, "empresa.crear", "empresa", emp.id,
              {"sector": sector, "pais": pais, "admin": email, "creada_por": (actor.email if actor else "registro público")})
    return admin


@router.get("/auth/config")
def config_publica():
    """Lo que el frontend necesita saber antes de iniciar sesión."""
    return {"registro_publico": get_settings().REGISTRO_PUBLICO}


@router.post("/auth/registro", status_code=201)
def registro(data: RegistroIn, request: Request, db: Session = Depends(get_db)):
    """Registro abierto de una empresa. Está cerrado por defecto: las empresas las crea el superadmin."""
    if not get_settings().REGISTRO_PUBLICO:
        raise HTTPException(403, "El registro está cerrado. Solicita acceso al administrador de la plataforma.")
    ip = ratelimit.ip_cliente(request)
    ratelimit.registro_ip.verificar(ip)
    ratelimit.registro_ip.registrar(ip)
    user = crear_empresa_con_admin(db, None, empresa=data.empresa, sector=data.sector, pais=data.pais,
                                   nombre=data.nombre, email=data.email.lower(), password=data.password,
                                   cambiar_password=False)
    db.commit()
    return {"access_token": create_token(user), "token_type": "bearer"}


@router.post("/auth/login")
def login(request: Request, form: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    ip = ratelimit.ip_cliente(request)
    email = form.username.lower()
    clave = f"{ip}|{email}"
    ratelimit.login_ip.verificar(ip)
    ratelimit.login_cuenta.verificar(clave)
    user = db.query(Usuario).filter(Usuario.email == email).first()
    ok = verify_password(form.password, user.password_hash if user else _HASH_FALSO)
    emp = db.get(Empresa, user.empresa_id) if user else None
    if not user or not user.activo or not ok or not emp or not emp.activa:
        ratelimit.login_ip.registrar(ip)
        ratelimit.login_cuenta.registrar(clave)
        raise HTTPException(401, "Correo o contraseña incorrectos")
    ratelimit.login_cuenta.reiniciar(clave)
    return {"access_token": create_token(user), "token_type": "bearer"}


@router.get("/auth/me")
def me(user: Usuario = Depends(usuario_sin_restricciones), db: Session = Depends(get_db)):
    emp = db.get(Empresa, user.empresa_id)
    return {"id": user.id, "nombre": user.nombre, "email": user.email, "rol": user.rol,
            "empresa": emp.nombre, "sector": emp.sector, "pais": emp.pais,
            "debe_cambiar_password": user.debe_cambiar_password}


class CambioPassword(BaseModel):
    actual: str = Field(min_length=1, max_length=72)
    nueva: str = Field(min_length=10, max_length=72)


@router.post("/auth/password")
def cambiar_password(data: CambioPassword, user: Usuario = Depends(usuario_sin_restricciones),
                     db: Session = Depends(get_db)):
    clave = f"pwd|{user.id}"
    ratelimit.login_cuenta.verificar(clave)  # frena adivinar la contraseña actual con un token robado
    if not verify_password(data.actual, user.password_hash):
        ratelimit.login_cuenta.registrar(clave)
        raise HTTPException(401, "La contraseña actual no es correcta")
    if data.nueva == data.actual:
        raise HTTPException(422, "La nueva contraseña debe ser distinta de la actual")
    ratelimit.login_cuenta.reiniciar(clave)
    user.password_hash = hash_password(data.nueva)
    user.debe_cambiar_password = False
    registrar(db, user.empresa_id, user, "usuario.password_cambio", "usuario", user.id, {})
    db.commit()
    return {"ok": True}


@router.get("/usuarios", response_model=list[UsuarioOut])
def listar_usuarios(user: Usuario = Depends(current_user), db: Session = Depends(get_db)):
    return db.query(Usuario).filter(Usuario.empresa_id == user.empresa_id,
                                    Usuario.activo.is_(True)).all()


@router.post("/usuarios", response_model=UsuarioOut, status_code=201)
def crear_usuario(data: UsuarioIn, admin: Usuario = Depends(require_roles("admin")),
                  db: Session = Depends(get_db)):
    email = data.email.lower()
    if db.query(Usuario).filter(Usuario.email == email).first():
        raise HTTPException(409, "El correo ya está registrado")
    u = Usuario(empresa_id=admin.empresa_id, nombre=data.nombre, email=email,
                password_hash=hash_password(data.password), rol=data.rol,
                debe_cambiar_password=True)  # la contraseña inicial la eligió el administrador
    db.add(u)
    db.flush()
    registrar(db, admin.empresa_id, admin, "usuario.crear", "usuario", u.id, {"email": u.email, "rol": u.rol})
    db.commit()
    db.refresh(u)
    return u
