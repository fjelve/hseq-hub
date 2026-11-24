from datetime import date, timedelta
from typing import Literal, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from app.auth import current_user, require_roles
from app.database import get_db
from app.models import RequisitoLegal, Usuario
from app.routes.hallazgos import validar_usuario

router = APIRouter(tags=["Requisitos legales"])
ESCRIBEN = ("admin", "auditor")
POR_VENCER_DIAS = 30


class RequisitoIn(BaseModel):
    nombre: str = Field(min_length=3, max_length=250)
    tipo: Literal["permiso", "licencia", "certificacion", "monitoreo", "norma"] = "permiso"
    entidad: str = Field(default="", max_length=150)
    responsable_id: Optional[int] = None
    fecha_vencimiento: Optional[date] = None
    notas: str = ""


class RequisitoOut(RequisitoIn):
    model_config = ConfigDict(from_attributes=True)
    id: int
    estado: str = "vigente"
    dias_restantes: Optional[int] = None


def estado_de(r: RequisitoLegal, hoy: date | None = None):
    hoy = hoy or date.today()
    if r.fecha_vencimiento is None:
        return "sin_fecha", None
    dias = (r.fecha_vencimiento - hoy).days
    return ("vencido" if dias < 0 else "por_vencer" if dias <= POR_VENCER_DIAS else "vigente"), dias


def a_out(r: RequisitoLegal) -> RequisitoOut:
    o = RequisitoOut.model_validate(r)
    o.estado, o.dias_restantes = estado_de(r)
    return o


@router.get("/requisitos", response_model=list[RequisitoOut])
def listar(user: Usuario = Depends(current_user), db: Session = Depends(get_db)):
    rs = db.query(RequisitoLegal).filter(RequisitoLegal.empresa_id == user.empresa_id).all()
    return sorted((a_out(r) for r in rs), key=lambda o: (o.dias_restantes is None, o.dias_restantes or 0))


@router.post("/requisitos", response_model=RequisitoOut, status_code=201)
def crear(data: RequisitoIn, user: Usuario = Depends(require_roles(*ESCRIBEN)),
          db: Session = Depends(get_db)):
    validar_usuario(db, user.empresa_id, data.responsable_id)
    r = RequisitoLegal(empresa_id=user.empresa_id, **data.model_dump())
    db.add(r)
    db.commit()
    db.refresh(r)
    return a_out(r)


@router.post("/requisitos/{rid}/renovar", response_model=RequisitoOut)
def renovar(rid: int, nueva_fecha: date, user: Usuario = Depends(require_roles(*ESCRIBEN)),
            db: Session = Depends(get_db)):
    r = db.get(RequisitoLegal, rid)
    if not r or r.empresa_id != user.empresa_id:
        raise HTTPException(404, "Requisito no encontrado")
    if nueva_fecha <= date.today():
        raise HTTPException(422, "La nueva fecha debe ser futura")
    r.fecha_vencimiento = nueva_fecha
    r.notificado = False
    db.commit()
    db.refresh(r)
    return a_out(r)
