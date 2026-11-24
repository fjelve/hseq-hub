from datetime import date, timedelta
from typing import Literal, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from app.auth import current_user, require_roles
from app.database import get_db
from app.models import HorasTrabajadas, Incidente, Usuario
from app.routes.hallazgos import crear_hallazgo
from app.services.bitacora import registrar as registrar_bitacora

router = APIRouter(tags=["Incidentes y seguridad"])
ESCRIBEN = ("admin", "auditor")
Tipo = Literal["accidente_ctp", "accidente_stp", "casi_accidente", "ambiental", "dano_propiedad"]
TITULOS = {"accidente_ctp": "Accidente con tiempo perdido", "accidente_stp": "Accidente sin tiempo perdido",
           "casi_accidente": "Casi accidente", "ambiental": "Incidente ambiental",
           "dano_propiedad": "Daño a la propiedad"}


class IncidenteIn(BaseModel):
    fecha: date = Field(default_factory=date.today)
    tipo: Tipo
    severidad: Literal["baja", "media", "alta", "critica"] = "media"
    area: str = Field(default="", max_length=120)
    descripcion: str = ""
    dias_perdidos: int = Field(default=0, ge=0, le=3650)


class IncidenteOut(IncidenteIn):
    model_config = ConfigDict(from_attributes=True)
    id: int
    hallazgo_id: Optional[int] = None


class HorasIn(BaseModel):
    periodo: str = Field(pattern=r"^\d{4}-(0[1-9]|1[0-2])$")
    horas: int = Field(ge=0, le=100_000_000)


@router.get("/incidentes", response_model=list[IncidenteOut])
def listar(user: Usuario = Depends(current_user), db: Session = Depends(get_db)):
    return (db.query(Incidente).filter(Incidente.empresa_id == user.empresa_id)
            .order_by(Incidente.fecha.desc(), Incidente.id.desc()).all())


@router.post("/incidentes", response_model=IncidenteOut, status_code=201)
def registrar(data: IncidenteIn, user: Usuario = Depends(require_roles(*ESCRIBEN)),
              db: Session = Depends(get_db)):
    if data.tipo != "accidente_ctp" and data.dias_perdidos:
        raise HTTPException(422, "Solo un accidente con tiempo perdido tiene días perdidos")
    inc = Incidente(empresa_id=user.empresa_id, **data.model_dump())
    db.add(inc)
    db.flush()
    # Automático: todo lo que no sea casi accidente leve abre una investigación (CAPA).
    if data.tipo != "casi_accidente" or data.severidad in ("alta", "critica"):
        h = crear_hallazgo(db, user.empresa_id, {
            "titulo": f"Investigar: {TITULOS[data.tipo]} ({data.fecha})"[:250],
            "descripcion": data.descripcion, "origen": "incidente", "area": data.area,
            "severidad": data.severidad, "responsable_id": user.id})
        inc.hallazgo_id = h.id
    registrar_bitacora(db, user.empresa_id, user, "incidente.registrar", "incidente", inc.id,
              {"tipo": inc.tipo, "severidad": inc.severidad, "dias_perdidos": inc.dias_perdidos,
               "hallazgo_id": inc.hallazgo_id})
    db.commit()
    db.refresh(inc)
    return inc


@router.put("/horas-trabajadas")
def guardar_horas(data: HorasIn, user: Usuario = Depends(require_roles(*ESCRIBEN)),
                  db: Session = Depends(get_db)):
    r = db.query(HorasTrabajadas).filter_by(empresa_id=user.empresa_id, periodo=data.periodo).first()
    if r:
        r.horas = data.horas
    else:
        db.add(HorasTrabajadas(empresa_id=user.empresa_id, periodo=data.periodo, horas=data.horas))
    db.commit()
    return {"periodo": data.periodo, "horas": data.horas}


@router.get("/horas-trabajadas")
def listar_horas(user: Usuario = Depends(current_user), db: Session = Depends(get_db)):
    rows = (db.query(HorasTrabajadas).filter_by(empresa_id=user.empresa_id)
            .order_by(HorasTrabajadas.periodo.desc()).limit(24).all())
    return [{"periodo": r.periodo, "horas": r.horas} for r in rows]


def kpis_seguridad(db: Session, empresa_id: int) -> dict:
    """Índices de los últimos 12 meses, por millón de horas trabajadas."""
    hoy = date.today()
    desde = hoy - timedelta(days=365)
    periodo_desde = f"{desde.year}-{desde.month:02d}"
    horas = sum(h.horas for h in db.query(HorasTrabajadas).filter(
        HorasTrabajadas.empresa_id == empresa_id, HorasTrabajadas.periodo >= periodo_desde))
    incs = db.query(Incidente).filter(Incidente.empresa_id == empresa_id, Incidente.fecha >= desde).all()
    ctp = [i for i in incs if i.tipo == "accidente_ctp"]
    dias = sum(i.dias_perdidos for i in ctp)
    ultimo = db.query(Incidente).filter(Incidente.empresa_id == empresa_id,
                                        Incidente.tipo == "accidente_ctp").order_by(Incidente.fecha.desc()).first()
    por_mes: dict[str, int] = {}
    for i in incs:
        k = f"{i.fecha.year}-{i.fecha.month:02d}"
        por_mes[k] = por_mes.get(k, 0) + 1
    return {
        "horas_12m": horas,
        "accidentes_ctp_12m": len(ctp),
        "dias_perdidos_12m": dias,
        "indice_frecuencia": round(len(ctp) * 1_000_000 / horas, 2) if horas else None,
        "indice_severidad": round(dias * 1_000_000 / horas, 1) if horas else None,
        "dias_sin_accidente_ctp": (hoy - ultimo.fecha).days if ultimo else None,
        "incidentes_por_mes": dict(sorted(por_mes.items())),
        "casi_accidentes_12m": sum(1 for i in incs if i.tipo == "casi_accidente"),
    }


@router.get("/kpis-seguridad")
def kpis(user: Usuario = Depends(current_user), db: Session = Depends(get_db)):
    return kpis_seguridad(db, user.empresa_id)
