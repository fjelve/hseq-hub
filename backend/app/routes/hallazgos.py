from datetime import date, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.auth import current_user, require_roles
from app.database import get_db
from app.models import Accion, Hallazgo, Usuario
from app.services.bitacora import registrar
from app.schemas import (
    AccionCompletar, AccionIn, AccionOut, CerrarIn, HallazgoIn, HallazgoOut, HallazgoUpdate,
)

router = APIRouter(prefix="/hallazgos", tags=["Hallazgos / CAPA"])

PLAZO_DIAS = {"critica": 7, "alta": 15, "media": 30, "baja": 60}
ESCRIBEN = ("admin", "auditor")


def plazo_por_severidad(sev: str) -> date:
    return date.today() + timedelta(days=PLAZO_DIAS.get(sev, 30))


def siguiente_codigo(db: Session, empresa_id: int) -> str:
    n = db.query(Hallazgo).filter(Hallazgo.empresa_id == empresa_id).count() + 1
    return f"HAL-{date.today().year}-{n:04d}"


def validar_usuario(db: Session, empresa_id: int, usuario_id: Optional[int]):
    if usuario_id is None:
        return
    u = db.get(Usuario, usuario_id)
    if not u or u.empresa_id != empresa_id:
        raise HTTPException(422, "Responsable no válido")


def obtener(db: Session, user: Usuario, hid: int) -> Hallazgo:
    h = db.get(Hallazgo, hid)
    if not h or h.empresa_id != user.empresa_id:
        raise HTTPException(404, "Hallazgo no encontrado")
    return h


def a_out(h: Hallazgo) -> HallazgoOut:
    out = HallazgoOut.model_validate(h)
    out.vencido = bool(h.estado != "cerrado" and h.fecha_compromiso
                       and h.fecha_compromiso < date.today())
    return out


def crear_hallazgo(db: Session, empresa_id: int, data: dict) -> Hallazgo:
    """Uso interno (también lo llama el módulo de auditorías)."""
    h = Hallazgo(empresa_id=empresa_id, codigo=siguiente_codigo(db, empresa_id), **data)
    if h.fecha_compromiso is None:
        h.fecha_compromiso = plazo_por_severidad(h.severidad)
    db.add(h)
    db.flush()
    return h


@router.get("", response_model=list[HallazgoOut])
def listar(estado: Optional[str] = None, severidad: Optional[str] = None,
           solo_vencidos: bool = False,
           user: Usuario = Depends(current_user), db: Session = Depends(get_db)):
    q = db.query(Hallazgo).filter(Hallazgo.empresa_id == user.empresa_id)
    if estado:
        q = q.filter(Hallazgo.estado == estado)
    if severidad:
        q = q.filter(Hallazgo.severidad == severidad)
    if solo_vencidos:
        q = q.filter(Hallazgo.estado != "cerrado", Hallazgo.fecha_compromiso < date.today())
    return [a_out(h) for h in q.order_by(Hallazgo.id.desc()).all()]


@router.post("", response_model=HallazgoOut, status_code=201)
def crear(data: HallazgoIn, user: Usuario = Depends(require_roles(*ESCRIBEN)),
          db: Session = Depends(get_db)):
    validar_usuario(db, user.empresa_id, data.responsable_id)
    h = crear_hallazgo(db, user.empresa_id, data.model_dump())
    registrar(db, user.empresa_id, user, "hallazgo.crear", "hallazgo", h.id,
              {"codigo": h.codigo, "severidad": h.severidad})
    db.commit()
    db.refresh(h)
    return a_out(h)


@router.get("/{hid}", response_model=HallazgoOut)
def detalle(hid: int, user: Usuario = Depends(current_user), db: Session = Depends(get_db)):
    return a_out(obtener(db, user, hid))


@router.patch("/{hid}", response_model=HallazgoOut)
def actualizar(hid: int, data: HallazgoUpdate,
               user: Usuario = Depends(require_roles(*ESCRIBEN)),
               db: Session = Depends(get_db)):
    h = obtener(db, user, hid)
    if h.estado == "cerrado":
        raise HTTPException(409, "El hallazgo está cerrado")
    cambios = data.model_dump(exclude_unset=True)
    validar_usuario(db, user.empresa_id, cambios.get("responsable_id"))
    for k, v in cambios.items():
        setattr(h, k, v)
    if "fecha_compromiso" in cambios:
        h.vencido_notificado = False
    registrar(db, user.empresa_id, user, "hallazgo.actualizar", "hallazgo", h.id,
              {"codigo": h.codigo, "campos": sorted(cambios)})
    db.commit()
    db.refresh(h)
    return a_out(h)


@router.post("/{hid}/acciones", response_model=AccionOut, status_code=201)
def agregar_accion(hid: int, data: AccionIn,
                   user: Usuario = Depends(require_roles(*ESCRIBEN)),
                   db: Session = Depends(get_db)):
    h = obtener(db, user, hid)
    if h.estado == "cerrado":
        raise HTTPException(409, "El hallazgo está cerrado")
    validar_usuario(db, user.empresa_id, data.responsable_id)
    a = Accion(hallazgo_id=h.id, **data.model_dump())
    db.add(a)
    if h.estado == "abierto":
        h.estado = "en_proceso"
    db.flush()
    registrar(db, user.empresa_id, user, "hallazgo.accion_agregada", "hallazgo", h.id,
              {"codigo": h.codigo, "accion_id": a.id, "tipo": a.tipo})
    db.commit()
    db.refresh(a)
    return a


@router.post("/{hid}/acciones/{aid}/completar", response_model=AccionOut)
def completar_accion(hid: int, aid: int, data: AccionCompletar,
                     user: Usuario = Depends(current_user), db: Session = Depends(get_db)):
    h = obtener(db, user, hid)
    a = db.get(Accion, aid)
    if not a or a.hallazgo_id != h.id:
        raise HTTPException(404, "Acción no encontrada")
    if user.rol == "responsable" and a.responsable_id != user.id:
        raise HTTPException(403, "Solo el responsable asignado puede completarla")
    a.completada = True
    a.fecha_completada = date.today()
    a.evidencia = data.evidencia
    # Con todas las acciones hechas, pasa a verificación de eficacia.
    if h.estado in ("abierto", "en_proceso") and all(x.completada for x in h.acciones):
        h.estado = "en_verificacion"
    registrar(db, user.empresa_id, user, "hallazgo.accion_completada", "hallazgo", h.id,
              {"codigo": h.codigo, "accion_id": a.id})
    db.commit()
    db.refresh(a)
    return a


@router.post("/{hid}/cerrar", response_model=HallazgoOut)
def cerrar(hid: int, data: CerrarIn, user: Usuario = Depends(require_roles(*ESCRIBEN)),
           db: Session = Depends(get_db)):
    h = obtener(db, user, hid)
    if h.estado == "cerrado":
        raise HTTPException(409, "Ya está cerrado")
    if not h.acciones:
        raise HTTPException(409, "Define al menos una acción antes de cerrar")
    if not all(a.completada for a in h.acciones):
        raise HTTPException(409, "Hay acciones pendientes")
    if not h.causa_raiz.strip():
        raise HTTPException(409, "Falta el análisis de causa raíz")
    h.estado = "cerrado"
    h.fecha_cierre = date.today()
    h.verificacion_eficacia = data.verificacion_eficacia
    registrar(db, user.empresa_id, user, "hallazgo.cerrar", "hallazgo", h.id,
              {"codigo": h.codigo, "acciones": len(h.acciones), "fecha_cierre": str(h.fecha_cierre)})
    db.commit()
    db.refresh(h)
    return a_out(h)
