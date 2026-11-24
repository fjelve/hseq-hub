"""Alertas automáticas de acciones correctivas por vencer o vencidas."""
import asyncio
import logging
import smtplib
from datetime import date, timedelta
from email.message import EmailMessage

from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import SessionLocal
from app.models import Hallazgo, RequisitoLegal, Usuario

log = logging.getLogger("hseq.alertas")


def _enviar(destino: str, asunto: str, cuerpo: str) -> bool:
    s = get_settings()
    if not s.SMTP_HOST:
        log.info("ALERTA (sin SMTP) a %s: %s", destino, asunto)
        return False
    msg = EmailMessage()
    msg["From"], msg["To"], msg["Subject"] = s.SMTP_FROM, destino, asunto
    msg.set_content(cuerpo)
    try:
        with smtplib.SMTP(s.SMTP_HOST, s.SMTP_PORT, timeout=15) as smtp:
            smtp.starttls()
            if s.SMTP_USER:
                smtp.login(s.SMTP_USER, s.SMTP_PASSWORD)
            smtp.send_message(msg)
        return True
    except Exception:
        log.exception("No se pudo enviar el correo a %s", destino)
        return False


def revisar_vencimientos(db: Session, hoy: date | None = None) -> list[dict]:
    """Devuelve las alertas generadas. Marca vencidos como notificados para no repetir."""
    hoy = hoy or date.today()
    limite = hoy + timedelta(days=get_settings().ALERT_DAYS_BEFORE)
    alertas = []
    pendientes = (db.query(Hallazgo)
                  .filter(Hallazgo.estado != "cerrado", Hallazgo.fecha_compromiso.isnot(None),
                          Hallazgo.fecha_compromiso <= limite,
                          Hallazgo.vencido_notificado.is_(False)).all())
    for h in pendientes:
        vencido = h.fecha_compromiso < hoy
        resp = db.get(Usuario, h.responsable_id) if h.responsable_id else None
        if resp is None:  # sin responsable: avisar a los administradores de la empresa
            destinos = [u.email for u in db.query(Usuario).filter(
                Usuario.empresa_id == h.empresa_id, Usuario.rol == "admin", Usuario.activo.is_(True))]
        else:
            destinos = [resp.email]
        tipo = "VENCIDO" if vencido else "por vencer"
        asunto = f"[HSEQ] Hallazgo {h.codigo} {tipo}"
        cuerpo = (f"{h.titulo}\nSeveridad: {h.severidad}\nCompromiso: {h.fecha_compromiso}\n"
                  f"Estado: {h.estado}")
        for d in destinos:
            _enviar(d, asunto, cuerpo)
        alertas.append({"hallazgo": h.codigo, "tipo": tipo, "destinos": destinos})
        if vencido:  # los "por vencer" se avisan hasta que venzan, y luego una vez más
            h.vencido_notificado = True
    db.commit()
    return alertas


def revisar_requisitos(db: Session, hoy: date | None = None) -> list[dict]:
    """Avisa permisos y certificaciones por vencer (30 días) o vencidos. Una vez por vencimiento."""
    hoy = hoy or date.today()
    alertas = []
    rs = (db.query(RequisitoLegal).filter(RequisitoLegal.fecha_vencimiento.isnot(None),
                                          RequisitoLegal.fecha_vencimiento <= hoy + timedelta(days=30),
                                          RequisitoLegal.notificado.is_(False)).all())
    for r in rs:
        resp = db.get(Usuario, r.responsable_id) if r.responsable_id else None
        destinos = [resp.email] if resp else [u.email for u in db.query(Usuario).filter(
            Usuario.empresa_id == r.empresa_id, Usuario.rol == "admin", Usuario.activo.is_(True))]
        tipo = "VENCIDO" if r.fecha_vencimiento < hoy else "por vencer"
        for d in destinos:
            _enviar(d, f"[HSEQ] {r.nombre}: {tipo}", f"{r.nombre}\nEntidad: {r.entidad}\nVence: {r.fecha_vencimiento}")
        r.notificado = True
        alertas.append({"requisito": r.nombre, "tipo": tipo, "destinos": destinos})
    db.commit()
    return alertas


async def bucle_alertas():
    intervalo = get_settings().ALERT_INTERVAL_MINUTES * 60
    while True:
        try:
            db = SessionLocal()
            try:
                await asyncio.to_thread(revisar_vencimientos, db)
                await asyncio.to_thread(revisar_requisitos, db)
            finally:
                db.close()
        except Exception:
            log.exception("Fallo en la revisión de alertas")
        await asyncio.sleep(intervalo)
