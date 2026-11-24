from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from app.auth import create_token, current_user, hash_password, require_roles, verify_password
from app import ratelimit
from app.database import get_db
from app.services.bitacora import registrar
from app.models import Empresa, Usuario
from app.schemas import RegistroIn, UsuarioIn, UsuarioOut

router = APIRouter()

# Hash de una contraseña inexistente: se compara igual cuando el correo no existe,
# para que el tiempo de respuesta no revele qué correos están registrados.
_HASH_FALSO = hash_password("contraseña-inexistente-0000")


@router.post("/auth/registro", status_code=201)
def registro(data: RegistroIn, request: Request, db: Session = Depends(get_db)):
    """Crea una empresa (tenant) y su primer usuario administrador."""
    ip = ratelimit.ip_cliente(request)
    ratelimit.registro_ip.verificar(ip)
    ratelimit.registro_ip.registrar(ip)
    email = data.email.lower()
    if db.query(Usuario).filter(Usuario.email == email).first():
        raise HTTPException(409, "El correo ya está registrado")
    emp = Empresa(nombre=data.empresa, sector=data.sector, pais=data.pais)
    db.add(emp)
    db.flush()
    user = Usuario(empresa_id=emp.id, nombre=data.nombre, email=email,
                   password_hash=hash_password(data.password), rol="admin")
    db.add(user)
    db.flush()
    registrar(db, emp.id, user, "empresa.registro", "empresa", emp.id, {"sector": emp.sector, "pais": emp.pais})
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
    if not user or not user.activo or not ok:
        ratelimit.login_ip.registrar(ip)
        ratelimit.login_cuenta.registrar(clave)
        raise HTTPException(401, "Correo o contraseña incorrectos")
    ratelimit.login_cuenta.reiniciar(clave)
    return {"access_token": create_token(user), "token_type": "bearer"}


@router.get("/auth/me")
def me(user: Usuario = Depends(current_user), db: Session = Depends(get_db)):
    emp = db.get(Empresa, user.empresa_id)
    return {"id": user.id, "nombre": user.nombre, "email": user.email, "rol": user.rol,
            "empresa": emp.nombre, "sector": emp.sector, "pais": emp.pais}


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
                password_hash=hash_password(data.password), rol=data.rol)
    db.add(u)
    db.flush()
    registrar(db, admin.empresa_id, admin, "usuario.crear", "usuario", u.id, {"email": u.email, "rol": u.rol})
    db.commit()
    db.refresh(u)
    return u
