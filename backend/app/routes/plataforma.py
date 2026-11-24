"""Administración de la plataforma: solo el rol `superadmin`.

El superadmin crea las empresas (clientes) y su primer administrador, las activa o
desactiva y restablece contraseñas. No ve ni modifica los datos de negocio de las
empresas (hallazgos, auditorías, etc.): esas rutas exigen rol admin o auditor.
"""
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.auth import hash_password, require_roles
from app.database import get_db
from app.models import Empresa, Hallazgo, Usuario
from app.routes.auth import crear_empresa_con_admin
from app.services.bitacora import registrar

router = APIRouter(prefix="/plataforma", tags=["Plataforma (superadmin)"])
SUPER = require_roles("superadmin")
SECTOR_PLATAFORMA = "plataforma"


class EmpresaIn(BaseModel):
    empresa: str = Field(min_length=2, max_length=200)
    sector: Literal["mineria", "industria"]
    pais: Literal["chile", "peru"]
    admin_nombre: str = Field(min_length=2, max_length=150)
    admin_email: EmailStr
    admin_password: str = Field(min_length=10, max_length=72)


class ActivaIn(BaseModel):
    activa: bool


class PasswordIn(BaseModel):
    nueva: str = Field(min_length=10, max_length=72)


def _empresa_cliente(db: Session, eid: int) -> Empresa:
    e = db.get(Empresa, eid)
    if not e or e.sector == SECTOR_PLATAFORMA:
        raise HTTPException(404, "Empresa no encontrada")
    return e


def _resumen(db: Session, e: Empresa) -> dict:
    return {"id": e.id, "nombre": e.nombre, "sector": e.sector, "pais": e.pais, "activa": e.activa,
            "creada_en": e.creada_en.isoformat() if e.creada_en else None,
            "usuarios": db.query(func.count(Usuario.id)).filter(Usuario.empresa_id == e.id).scalar(),
            "hallazgos": db.query(func.count(Hallazgo.id)).filter(Hallazgo.empresa_id == e.id).scalar()}


@router.get("/empresas")
def listar(_: Usuario = Depends(SUPER), db: Session = Depends(get_db)):
    es = db.query(Empresa).filter(Empresa.sector != SECTOR_PLATAFORMA).order_by(Empresa.id.desc()).all()
    return [_resumen(db, e) for e in es]


@router.post("/empresas", status_code=201)
def crear(data: EmpresaIn, su: Usuario = Depends(SUPER), db: Session = Depends(get_db)):
    admin = crear_empresa_con_admin(db, su, empresa=data.empresa, sector=data.sector, pais=data.pais,
                                    nombre=data.admin_nombre, email=data.admin_email.lower(),
                                    password=data.admin_password, cambiar_password=True)
    db.commit()
    return _resumen(db, db.get(Empresa, admin.empresa_id))


@router.patch("/empresas/{eid}")
def activar(eid: int, data: ActivaIn, su: Usuario = Depends(SUPER), db: Session = Depends(get_db)):
    e = _empresa_cliente(db, eid)
    e.activa = data.activa
    registrar(db, e.id, su, "empresa.activar" if data.activa else "empresa.desactivar", "empresa", e.id,
              {"por": su.email})
    db.commit()
    return _resumen(db, e)


@router.get("/empresas/{eid}/usuarios")
def usuarios(eid: int, _: Usuario = Depends(SUPER), db: Session = Depends(get_db)):
    _empresa_cliente(db, eid)
    us = db.query(Usuario).filter(Usuario.empresa_id == eid).order_by(Usuario.id).all()
    return [{"id": u.id, "nombre": u.nombre, "email": u.email, "rol": u.rol, "activo": u.activo,
             "debe_cambiar_password": u.debe_cambiar_password} for u in us]


@router.post("/usuarios/{uid}/password")
def restablecer_password(uid: int, data: PasswordIn, su: Usuario = Depends(SUPER),
                         db: Session = Depends(get_db)):
    u = db.get(Usuario, uid)
    if not u or u.rol == "superadmin":
        raise HTTPException(404, "Usuario no encontrado")
    _empresa_cliente(db, u.empresa_id)
    u.password_hash = hash_password(data.nueva)
    u.debe_cambiar_password = True
    registrar(db, u.empresa_id, su, "usuario.password_restablecida", "usuario", u.id, {"email": u.email})
    db.commit()
    return {"ok": True}
