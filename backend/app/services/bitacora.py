"""Bitácora de auditoría inmutable, encadenada con SHA-256 (una cadena por empresa).

    hash = SHA-256( [seq, empresa_id, hash_previo, ts, actor_id, actor, accion,
                     entidad, entidad_id, datos_json] )

Alterar o borrar una entrada intermedia rompe el hash de las siguientes y
`verificar` lo detecta. Además, la migración instala disparadores que impiden
UPDATE y DELETE sobre la tabla.

Limitación: borrar las ÚLTIMAS entradas no rompe la cadena. Para detectarlo hay
que guardar fuera del sistema el `ultimo_hash` y el número de entradas que
devuelve `verificar` (por ejemplo, en el informe mensual).
"""
import hashlib
import json
from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.models import EntradaBitacora, Usuario

GENESIS = "0" * 64


def _hash(seq, empresa_id, previo, ts, actor_id, actor, accion, entidad, entidad_id, datos) -> str:
    payload = json.dumps([seq, empresa_id, previo, ts, actor_id, actor, accion, entidad, entidad_id, datos],
                         ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def registrar(db: Session, empresa_id: int, actor: Optional[Usuario], accion: str,
              entidad: str, entidad_id: Optional[int] = None, datos: Optional[dict[str, Any]] = None) -> EntradaBitacora:
    """Agrega una entrada dentro de la transacción en curso (el llamador hace commit)."""
    if db.bind.dialect.name == "postgresql":  # serializa las altas de la misma empresa
        db.execute(text("SELECT pg_advisory_xact_lock(:k)"), {"k": 7_300_000_000 + empresa_id})
    db.flush()
    ultima = (db.query(EntradaBitacora).filter_by(empresa_id=empresa_id)
              .order_by(EntradaBitacora.seq.desc()).first())
    seq = ultima.seq + 1 if ultima else 1
    previo = ultima.hash_actual if ultima else GENESIS
    ts = datetime.now(timezone.utc).isoformat(timespec="microseconds")
    datos_json = json.dumps(datos or {}, sort_keys=True, ensure_ascii=False, default=str)
    actor_id = actor.id if actor else None
    actor_txt = actor.email if actor else "sistema"
    e = EntradaBitacora(empresa_id=empresa_id, seq=seq, ts=ts, actor_id=actor_id, actor=actor_txt,
                        accion=accion, entidad=entidad, entidad_id=entidad_id, datos=datos_json,
                        hash_previo=previo,
                        hash_actual=_hash(seq, empresa_id, previo, ts, actor_id, actor_txt, accion,
                                          entidad, entidad_id, datos_json))
    db.add(e)
    db.flush()
    return e


def verificar(db: Session, empresa_id: int) -> dict:
    previo, esperado, n = GENESIS, 1, 0
    for e in (db.query(EntradaBitacora).filter_by(empresa_id=empresa_id)
              .order_by(EntradaBitacora.seq).yield_per(500)):
        motivo = None
        if e.seq != esperado:
            motivo = f"Falta la entrada {esperado} (secuencia interrumpida)"
        elif e.hash_previo != previo:
            motivo = "El enlace con la entrada anterior no coincide"
        elif e.hash_actual != _hash(e.seq, e.empresa_id, e.hash_previo, e.ts, e.actor_id, e.actor,
                                    e.accion, e.entidad, e.entidad_id, e.datos):
            motivo = "El contenido de la entrada fue alterado"
        if motivo:
            return {"valida": False, "entradas": n, "ultimo_hash": previo,
                    "primer_error": {"seq": e.seq, "motivo": motivo}}
        previo, esperado, n = e.hash_actual, esperado + 1, n + 1
    return {"valida": True, "entradas": n, "ultimo_hash": previo, "primer_error": None}
