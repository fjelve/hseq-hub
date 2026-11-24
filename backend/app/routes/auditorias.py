from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.auth import current_user, require_roles
from app.database import get_db
from app.models import Auditoria, PlantillaAuditoria, Respuesta, Usuario
from app.routes.hallazgos import crear_hallazgo, validar_usuario
from app.schemas import AuditoriaIn, AuditoriaOut, PlantillaOut, RespuestaIn

router = APIRouter(tags=["Auditorías"])
ESCRIBEN = ("admin", "auditor")


@router.get("/plantillas", response_model=list[PlantillaOut])
def plantillas(sector: Optional[str] = None, user: Usuario = Depends(current_user),
               db: Session = Depends(get_db)):
    q = db.query(PlantillaAuditoria).filter(
        or_(PlantillaAuditoria.empresa_id.is_(None),
            PlantillaAuditoria.empresa_id == user.empresa_id))
    if sector:
        q = q.filter(PlantillaAuditoria.sector.in_([sector, "todos"]))
    return q.order_by(PlantillaAuditoria.id).all()


def _plantilla_visible(db: Session, user: Usuario, pid: int) -> PlantillaAuditoria:
    p = db.get(PlantillaAuditoria, pid)
    if not p or (p.empresa_id is not None and p.empresa_id != user.empresa_id):
        raise HTTPException(404, "Plantilla no encontrada")
    return p


def _auditoria(db: Session, user: Usuario, aid: int) -> Auditoria:
    a = db.get(Auditoria, aid)
    if not a or a.empresa_id != user.empresa_id:
        raise HTTPException(404, "Auditoría no encontrada")
    return a


@router.get("/auditorias", response_model=list[AuditoriaOut])
def listar(user: Usuario = Depends(current_user), db: Session = Depends(get_db)):
    return (db.query(Auditoria).filter(Auditoria.empresa_id == user.empresa_id)
            .order_by(Auditoria.id.desc()).all())


@router.post("/auditorias", response_model=AuditoriaOut, status_code=201)
def programar(data: AuditoriaIn, user: Usuario = Depends(require_roles(*ESCRIBEN)),
              db: Session = Depends(get_db)):
    _plantilla_visible(db, user, data.plantilla_id)
    validar_usuario(db, user.empresa_id, data.auditor_id)
    a = Auditoria(empresa_id=user.empresa_id, plantilla_id=data.plantilla_id, area=data.area,
                  fecha_programada=data.fecha_programada or date.today(),
                  auditor_id=data.auditor_id or user.id)
    db.add(a)
    db.commit()
    db.refresh(a)
    return a


@router.get("/auditorias/{aid}", response_model=AuditoriaOut)
def detalle(aid: int, user: Usuario = Depends(current_user), db: Session = Depends(get_db)):
    return _auditoria(db, user, aid)


@router.put("/auditorias/{aid}/respuestas", response_model=AuditoriaOut)
def responder(aid: int, data: RespuestaIn,
              user: Usuario = Depends(require_roles(*ESCRIBEN)),
              db: Session = Depends(get_db)):
    a = _auditoria(db, user, aid)
    if a.estado == "cerrada":
        raise HTTPException(409, "La auditoría está cerrada")
    item = next((i for i in a.plantilla.items if i.id == data.item_id), None)
    if not item:
        raise HTTPException(422, "El ítem no pertenece a la plantilla de la auditoría")
    r = next((x for x in a.respuestas if x.item_id == data.item_id), None)
    if r is None:
        r = Respuesta(auditoria_id=a.id, item_id=data.item_id, resultado=data.resultado)
        db.add(r)
    r.resultado = data.resultado
    r.observacion = data.observacion
    a.estado = "en_curso"
    db.commit()
    db.refresh(a)
    return a


@router.post("/auditorias/{aid}/cerrar", response_model=AuditoriaOut)
def cerrar(aid: int, user: Usuario = Depends(require_roles(*ESCRIBEN)),
           db: Session = Depends(get_db)):
    """Calcula el puntaje y crea un hallazgo por cada 'no cumple' (automático)."""
    a = _auditoria(db, user, aid)
    if a.estado == "cerrada":
        raise HTTPException(409, "La auditoría ya está cerrada")
    respondidos = {r.item_id for r in a.respuestas}
    faltan = [i.id for i in a.plantilla.items if i.id not in respondidos]
    if faltan:
        raise HTTPException(409, f"Faltan {len(faltan)} ítems por responder")

    cumple = no_cumple = 0
    for r in a.respuestas:
        if r.resultado == "cumple":
            cumple += 1
        elif r.resultado == "no_cumple":
            no_cumple += 1
            if r.hallazgo_id is None:
                sev = "alta" if r.item.critico else "media"
                h = crear_hallazgo(db, user.empresa_id, {
                    "titulo": f"[{a.plantilla.norma} {r.item.clausula}] {r.item.texto}"[:250],
                    "descripcion": r.observacion or "",
                    "origen": "auditoria",
                    "norma": a.plantilla.norma,
                    "area": a.area,
                    "severidad": sev,
                    "responsable_id": a.auditor_id,
                })
                r.hallazgo_id = h.id
    total = cumple + no_cumple
    a.puntaje = round(100 * cumple / total) if total else 100
    a.estado = "cerrada"
    db.commit()
    db.refresh(a)
    return a
