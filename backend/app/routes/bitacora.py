from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.auth import require_roles
from app.database import get_db
from app.models import EntradaBitacora, Usuario
from app.services import bitacora as svc

router = APIRouter(tags=["Bitácora"])


@router.get("/bitacora")
def listar(limite: int = Query(100, ge=1, le=500),
           user: Usuario = Depends(require_roles("admin", "auditor")), db: Session = Depends(get_db)):
    rows = (db.query(EntradaBitacora).filter_by(empresa_id=user.empresa_id)
            .order_by(EntradaBitacora.seq.desc()).limit(limite).all())
    return [{"seq": e.seq, "ts": e.ts, "actor": e.actor, "accion": e.accion, "entidad": e.entidad,
             "entidad_id": e.entidad_id, "datos": e.datos, "hash": e.hash_actual} for e in rows]


@router.get("/bitacora/verificar")
def verificar(user: Usuario = Depends(require_roles("admin", "auditor")), db: Session = Depends(get_db)):
    return svc.verificar(db, user.empresa_id)
