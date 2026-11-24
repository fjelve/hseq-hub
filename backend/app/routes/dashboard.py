from datetime import date

from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.auth import current_user
from app.database import get_db
from app.models import Auditoria, Hallazgo, Usuario

router = APIRouter(tags=["Dashboard"])


@router.get("/dashboard")
def dashboard(user: Usuario = Depends(current_user), db: Session = Depends(get_db)):
    eid = user.empresa_id
    base = db.query(Hallazgo).filter(Hallazgo.empresa_id == eid)
    por_estado = dict(db.query(Hallazgo.estado, func.count()).filter(Hallazgo.empresa_id == eid)
                      .group_by(Hallazgo.estado).all())
    por_sev = dict(db.query(Hallazgo.severidad, func.count())
                   .filter(Hallazgo.empresa_id == eid, Hallazgo.estado != "cerrado")
                   .group_by(Hallazgo.severidad).all())
    abiertos = base.filter(Hallazgo.estado != "cerrado").count()
    vencidos = base.filter(Hallazgo.estado != "cerrado",
                           Hallazgo.fecha_compromiso < date.today()).count()
    ult = (db.query(Auditoria).filter(Auditoria.empresa_id == eid, Auditoria.estado == "cerrada")
           .order_by(Auditoria.id.desc()).limit(10).all())
    puntajes = [a.puntaje for a in ult if a.puntaje is not None]
    return {
        "hallazgos_abiertos": abiertos,
        "hallazgos_vencidos": vencidos,
        "hallazgos_por_estado": por_estado,
        "abiertos_por_severidad": por_sev,
        "auditorias_pendientes": db.query(Auditoria).filter(
            Auditoria.empresa_id == eid, Auditoria.estado != "cerrada").count(),
        "cumplimiento_promedio": round(sum(puntajes) / len(puntajes)) if puntajes else None,
    }
