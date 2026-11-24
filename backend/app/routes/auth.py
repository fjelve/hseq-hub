from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from app.auth import create_token, current_user, hash_password, require_roles, verify_password
from app.database import get_db
from app.models import Empresa, Usuario
from app.schemas import RegistroIn, UsuarioIn, UsuarioOut

router = APIRouter()


@router.post("/auth/registro", status_code=201)
def registro(data: RegistroIn, db: Session = Depends(get_db)):
    """Crea una empresa (tenant) y su primer usuario administrador."""
    email = data.email.lower()
    if db.query(Usuario).filter(Usuario.email == email).first():
        raise HTTPException(409, "El correo ya está registrado")
    emp = Empresa(nombre=data.empresa, sector=data.sector, pais=data.pais)
    db.add(emp)
    db.flush()
    user = Usuario(empresa_id=emp.id, nombre=data.nombre, email=email,
                   password_hash=hash_password(data.password), rol="admin")
    db.add(user)
    db.commit()
    return {"access_token": create_token(user), "token_type": "bearer"}


@router.post("/auth/login")
def login(form: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = db.query(Usuario).filter(Usuario.email == form.username.lower()).first()
    if not user or not user.activo or not verify_password(form.password, user.password_hash):
        raise HTTPException(401, "Correo o contraseña incorrectos")
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
    db.commit()
    db.refresh(u)
    return u
