from typing import Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.auth import current_user, require_roles
from app.database import get_db
from app.models import IndicadorAmbiental, Usuario

router = APIRouter(tags=["Ambiental / ESG"])
Tipo = Literal["energia_kwh", "agua_m3", "residuos_peligrosos_kg", "residuos_no_peligrosos_kg", "combustible_l"]


class IndicadorIn(BaseModel):
    periodo: str = Field(pattern=r"^\d{4}-(0[1-9]|1[0-2])$")
    tipo: Tipo
    valor: float = Field(ge=0, le=1e12)


@router.put("/ambiental")
def guardar(data: IndicadorIn, user: Usuario = Depends(require_roles("admin", "auditor")),
            db: Session = Depends(get_db)):
    r = db.query(IndicadorAmbiental).filter_by(empresa_id=user.empresa_id, periodo=data.periodo,
                                               tipo=data.tipo).first()
    if r:
        r.valor = data.valor
    else:
        db.add(IndicadorAmbiental(empresa_id=user.empresa_id, **data.model_dump()))
    db.commit()
    return data


@router.get("/ambiental")
def listar(user: Usuario = Depends(current_user), db: Session = Depends(get_db)):
    """Serie mensual por tipo de indicador (últimos 12 periodos)."""
    rows = (db.query(IndicadorAmbiental).filter_by(empresa_id=user.empresa_id)
            .order_by(IndicadorAmbiental.periodo).all())
    out: dict[str, dict[str, float]] = {}
    for r in rows:
        out.setdefault(r.tipo, {})[r.periodo] = r.valor
    return {t: dict(list(s.items())[-12:]) for t, s in out.items()}
