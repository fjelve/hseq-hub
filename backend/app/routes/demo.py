"""Carga de datos de ejemplo para demos. Solo en empresas sin datos."""
import random
from datetime import date, timedelta

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.auth import require_roles
from app.database import get_db
from app.models import (
    Accion, Auditoria, Empresa, HorasTrabajadas, Hallazgo, Incidente, IndicadorAmbiental,
    PlantillaAuditoria, RequisitoLegal, Respuesta, Usuario, IndicadorSocial, MetaSostenibilidad,
)
from app.routes.hallazgos import PLAZO_DIAS, crear_hallazgo
from app.services.bitacora import registrar

router = APIRouter(tags=["Demo"])

AREAS = {
    "mineria": ["Mina Rajo", "Planta Concentradora", "Taller Mecánico", "Depósito de Relaves", "Campamento"],
    "industria": ["Producción", "Almacén", "Mantenimiento", "Control de Calidad", "Despacho"],
}
ENTIDADES = {
    "chile": {"min": "Sernageomin", "amb": "SMA", "salud": "SEREMI de Salud", "trab": "Dirección del Trabajo"},
    "peru": {"min": "MINEM", "amb": "OEFA", "salud": "MINSA", "trab": "SUNAFIL"},
}
REQUISITOS = [  # (nombre, tipo, entidad, días al vencimiento, solo minería)
    ("Plan de emergencia y simulacro anual", "norma", "trab", -12, False),
    ("Certificación de equipos de izaje y grúas", "certificacion", "trab", 9, False),
    ("Monitoreo ambiental trimestral (agua y aire)", "monitoreo", "amb", 22, False),
    ("Exámenes médicos ocupacionales", "permiso", "salud", 75, False),
    ("Inspección anual de extintores y red húmeda", "certificacion", "trab", 160, False),
    ("Registro de residuos peligrosos", "permiso", "amb", 300, False),
    ("Plan de cierre: actualización", "permiso", "min", 45, True),
    ("Aprobación de operación del depósito de relaves", "permiso", "min", -3, True),
]


@router.post("/demo/cargar", status_code=201)
def cargar(user: Usuario = Depends(require_roles("admin")), db: Session = Depends(get_db)):
    eid = user.empresa_id
    if (db.query(Hallazgo).filter_by(empresa_id=eid).count()
            or db.query(Auditoria).filter_by(empresa_id=eid).count()):
        raise HTTPException(409, "La empresa ya tiene datos; la carga de ejemplo solo aplica a cuentas vacías")
    emp = db.get(Empresa, eid)
    rnd = random.Random(42)
    hoy = date.today()
    areas = AREAS[emp.sector]
    ent = ENTIDADES[emp.pais]

    plantillas = (db.query(PlantillaAuditoria)
                  .filter(PlantillaAuditoria.empresa_id.is_(None),
                          PlantillaAuditoria.pais.in_([emp.pais, "todos"]),
                          PlantillaAuditoria.sector.in_([emp.sector, "todos"]))
                  .order_by(PlantillaAuditoria.id).all())

    # Auditorías cerradas con mejora progresiva y hallazgos asociados.
    for n, (dias, falla) in enumerate([(120, .55), (90, .45), (60, .35), (30, .30)]):
        pl = plantillas[n % len(plantillas)]
        fecha = hoy - timedelta(days=dias)
        area = rnd.choice(areas)
        a = Auditoria(empresa_id=eid, plantilla_id=pl.id, area=area, fecha_programada=fecha,
                      auditor_id=user.id, estado="cerrada")
        db.add(a)
        db.flush()
        cumple = nc = 0
        for it in pl.items:
            ok = rnd.random() >= falla
            r = Respuesta(auditoria_id=a.id, item_id=it.id, resultado="cumple" if ok else "no_cumple",
                          observacion="" if ok else "Se observa incumplimiento en terreno.")
            db.add(r)
            if ok:
                cumple += 1
                continue
            nc += 1
            sev = "alta" if it.critico else rnd.choice(["media", "media", "baja"])
            h = crear_hallazgo(db, eid, {
                "titulo": f"[{pl.norma} {it.clausula}] {it.texto}"[:250], "descripcion": r.observacion,
                "origen": "auditoria", "norma": pl.norma, "area": area, "severidad": sev,
                "responsable_id": user.id})
            r.hallazgo_id = h.id
            h.fecha_compromiso = fecha + timedelta(days=PLAZO_DIAS[sev])
            if n < 2 and rnd.random() < .70:  # antiguos: casi todos cerrados
                h.causa_raiz = "Falta de verificación previa y de capacitación específica."
                h.metodo_causa = "5_porques"
                h.acciones.append(Accion(tipo="correctiva", descripcion="Capacitar al equipo y verificar el control en terreno.",
                                         responsable_id=user.id, completada=True,
                                         fecha_completada=h.fecha_compromiso - timedelta(days=3),
                                         evidencia="Registro de capacitación y acta de verificación."))
                h.estado, h.fecha_cierre = "cerrado", h.fecha_compromiso - timedelta(days=1)
                h.verificacion_eficacia = "Sin recurrencia en la inspección de seguimiento."
            else:
                h.estado = rnd.choice(["abierto", "en_proceso", "en_proceso", "en_verificacion"])
                if h.estado != "abierto":
                    h.causa_raiz = "Procedimiento no actualizado."
                    h.metodo_causa = "ishikawa"
                    h.acciones.append(Accion(tipo="correctiva", descripcion="Actualizar el procedimiento y difundirlo.",
                                             responsable_id=user.id, completada=h.estado == "en_verificacion",
                                             evidencia="Procedimiento v2 publicado." if h.estado == "en_verificacion" else ""))
        a.puntaje = round(100 * cumple / (cumple + nc)) if cumple + nc else 100
    # Una auditoría programada pendiente.
    db.add(Auditoria(empresa_id=eid, plantilla_id=plantillas[-1].id, area=rnd.choice(areas),
                     fecha_programada=hoy + timedelta(days=10), auditor_id=user.id))

    # Incidentes de los últimos 6 meses.
    incs = [(150, "accidente_ctp", "alta", 6), (68, "accidente_ctp", "media", 3),
            (110, "accidente_stp", "baja", 0), (75, "accidente_stp", "media", 0), (20, "accidente_stp", "baja", 0),
            (160, "ambiental", "media", 0), (40, "dano_propiedad", "baja", 0)]
    incs += [(rnd.randint(3, 170), "casi_accidente", rnd.choice(["baja", "media", "alta"]), 0) for _ in range(8)]
    for dias, tipo, sev, perd in incs:
        db.add(Incidente(empresa_id=eid, fecha=hoy - timedelta(days=dias), tipo=tipo, severidad=sev,
                         area=rnd.choice(areas), dias_perdidos=perd,
                         descripcion="Evento registrado para demostración."))

    # Horas trabajadas e indicadores ambientales (12 meses, con leve mejora).
    y, m = hoy.year, hoy.month
    for k in range(12):
        periodo = f"{y}-{m:02d}"
        db.add(HorasTrabajadas(empresa_id=eid, periodo=periodo, horas=rnd.randint(36000, 44000)))
        mejora = 1 - 0.02 * (11 - k)
        for tipo, base in [("energia_kwh", 210000), ("agua_m3", 5200), ("combustible_l", 36000),
                           ("residuos_peligrosos_kg", 1300), ("residuos_no_peligrosos_kg", 6800)]:
            db.add(IndicadorAmbiental(empresa_id=eid, periodo=periodo, tipo=tipo,
                                      valor=round(base * mejora * rnd.uniform(.94, 1.06), 1)))
        m -= 1
        if m == 0:
            y, m = y - 1, 12

    # Requisitos legales con distintos vencimientos.
    for nombre, tipo, e, dias, solo_min in REQUISITOS:
        if solo_min and emp.sector != "mineria":
            continue
        db.add(RequisitoLegal(empresa_id=eid, nombre=nombre, tipo=tipo, entidad=ent[e],
                              responsable_id=user.id, fecha_vencimiento=hoy + timedelta(days=dias)))
    # Indicadores sociales (12 meses).
    y, m = hoy.year, hoy.month
    for k in range(12):
        periodo = f"{y}-{m:02d}"
        recl = rnd.randint(3, 6)
        for tipo, v in [("empleados_total", 230 + (11 - k) * -1 + 12), ("mujeres_empleadas", 38 + (k // 3)),
                        ("horas_capacitacion", rnd.randint(380, 620)),
                        ("inversion_comunitaria", rnd.randint(8000, 12000)),
                        ("reclamos_comunitarios", recl), ("reclamos_resueltos", max(0, recl - rnd.randint(0, 1)))]:
            db.add(IndicadorSocial(empresa_id=eid, periodo=periodo, tipo=tipo, valor=v))
        m -= 1
        if m == 0:
            y, m = y - 1, 12

    # Metas con base calculada a partir de los datos cargados.
    db.flush()
    from app.services import sostenibilidad as sv
    em = sv.total_anual(db, emp, "emisiones_tco2e") or 1000
    agua = sv.total_anual(db, emp, "agua_m3") or 60000
    db.add_all([
        MetaSostenibilidad(empresa_id=eid, nombre="Reducir emisiones de GEI 30 % al 2030", indicador="emisiones_tco2e",
                           anio_base=hoy.year - 2, valor_base=round(em * 1.18, 1), anio_meta=2030, reduccion_pct=30),
        MetaSostenibilidad(empresa_id=eid, nombre="Reducir consumo de agua 10 %", indicador="agua_m3",
                           anio_base=hoy.year - 1, valor_base=round(agua * 1.05, 1), anio_meta=hoy.year + 2, reduccion_pct=10),
        MetaSostenibilidad(empresa_id=eid, nombre="Reducir residuos peligrosos 25 %", indicador="residuos_peligrosos_kg",
                           anio_base=hoy.year - 1, valor_base=round((sv.total_anual(db, emp, "residuos_peligrosos_kg") or 15000) * 1.5, 1),
                           anio_meta=hoy.year + 3, reduccion_pct=25),
    ])
    registrar(db, eid, user, "demo.cargar", "empresa", eid, {})
    db.commit()
    return {"ok": True}
