from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.auth import current_user, require_roles
from app.database import get_db
from app.models import Empresa, FactorEmpresa, IndicadorSocial, MetaSostenibilidad, Usuario
from app.services import sostenibilidad as sv

router = APIRouter(tags=["Sostenibilidad"])
ESCRIBEN = ("admin", "auditor")
Periodo = Field(pattern=r"^\d{4}-(0[1-9]|1[0-2])$")
IndicadorMeta = Literal["emisiones_tco2e", "energia_kwh", "agua_m3", "combustible_l",
                        "residuos_peligrosos_kg", "residuos_no_peligrosos_kg"]


def _emp(db: Session, user: Usuario) -> Empresa:
    return db.get(Empresa, user.empresa_id)


class FactorIn(BaseModel):
    clave: Literal["combustible_l", "energia_kwh", "residuos_peligrosos_kg", "residuos_no_peligrosos_kg"]
    valor: float = Field(gt=0, le=1000)
    fuente: str = Field(min_length=3, max_length=250)


@router.get("/emisiones")
def emisiones(user: Usuario = Depends(current_user), db: Session = Depends(get_db)):
    return sv.calcular_emisiones(db, _emp(db, user))


@router.put("/factores")
def guardar_factor(data: FactorIn, user: Usuario = Depends(require_roles(*ESCRIBEN)),
                   db: Session = Depends(get_db)):
    f = db.query(FactorEmpresa).filter_by(empresa_id=user.empresa_id, clave=data.clave).first()
    if f:
        f.valor, f.fuente = data.valor, data.fuente
    else:
        db.add(FactorEmpresa(empresa_id=user.empresa_id, **data.model_dump()))
    db.commit()
    return data


class MetaIn(BaseModel):
    nombre: str = Field(min_length=3, max_length=200)
    indicador: IndicadorMeta
    anio_base: int = Field(ge=2000, le=2100)
    valor_base: float = Field(gt=0)
    anio_meta: int = Field(ge=2000, le=2100)
    reduccion_pct: float = Field(gt=0, le=100)


@router.get("/metas")
def metas(user: Usuario = Depends(current_user), db: Session = Depends(get_db)):
    emp = _emp(db, user)
    ms = db.query(MetaSostenibilidad).filter_by(empresa_id=user.empresa_id).order_by(MetaSostenibilidad.id).all()
    return [sv.estado_meta(db, emp, m) for m in ms]


@router.post("/metas", status_code=201)
def crear_meta(data: MetaIn, user: Usuario = Depends(require_roles(*ESCRIBEN)),
               db: Session = Depends(get_db)):
    if data.anio_meta <= data.anio_base:
        raise HTTPException(422, "El año meta debe ser posterior al año base")
    m = MetaSostenibilidad(empresa_id=user.empresa_id, **data.model_dump())
    db.add(m)
    db.commit()
    return sv.estado_meta(db, _emp(db, user), m)


@router.delete("/metas/{mid}", status_code=204)
def borrar_meta(mid: int, user: Usuario = Depends(require_roles(*ESCRIBEN)),
                db: Session = Depends(get_db)):
    m = db.get(MetaSostenibilidad, mid)
    if not m or m.empresa_id != user.empresa_id:
        raise HTTPException(404, "Meta no encontrada")
    db.delete(m)
    db.commit()


class SocialIn(BaseModel):
    periodo: str = Periodo
    tipo: Literal[tuple(sv.TIPOS_SOCIALES)]  # type: ignore[valid-type]
    valor: float = Field(ge=0, le=1e12)


@router.put("/social")
def guardar_social(data: SocialIn, user: Usuario = Depends(require_roles(*ESCRIBEN)),
                   db: Session = Depends(get_db)):
    if data.tipo == "mujeres_empleadas":
        tot = db.query(IndicadorSocial).filter_by(empresa_id=user.empresa_id, periodo=data.periodo,
                                                  tipo="empleados_total").first()
        if tot and data.valor > tot.valor:
            raise HTTPException(422, "Las mujeres empleadas no pueden superar el total de empleados")
    r = db.query(IndicadorSocial).filter_by(empresa_id=user.empresa_id, periodo=data.periodo,
                                            tipo=data.tipo).first()
    if r:
        r.valor = data.valor
    else:
        db.add(IndicadorSocial(empresa_id=user.empresa_id, **data.model_dump()))
    db.commit()
    return data


@router.get("/social")
def listar_social(user: Usuario = Depends(current_user), db: Session = Depends(get_db)):
    out: dict[str, dict[str, float]] = {}
    for r in (db.query(IndicadorSocial).filter_by(empresa_id=user.empresa_id)
              .order_by(IndicadorSocial.periodo).all()):
        out.setdefault(r.tipo, {})[r.periodo] = r.valor
    return {t: dict(list(s.items())[-12:]) for t, s in out.items()}


@router.get("/reporte/gri")
def reporte_gri(user: Usuario = Depends(current_user), db: Session = Depends(get_db)):
    return sv.indice_gri(db, _emp(db, user))
