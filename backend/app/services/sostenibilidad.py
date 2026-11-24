"""Cálculo de huella de carbono, metas y mapeo a GRI / NIIF S2."""
from datetime import date

from sqlalchemy.orm import Session

from app.models import (
    Empresa, FactorEmpresa, HorasTrabajadas, Incidente, IndicadorAmbiental, IndicadorSocial,
    MetaSostenibilidad, RequisitoLegal,
)

# Factores REFERENCIALES (kg CO2e por unidad). No son oficiales: cada empresa debe
# reemplazarlos por el factor vigente de su autoridad (ej. Huella Chile, HC Perú, MINEM).
FACTORES_BASE = {
    "combustible_l": {"nombre": "Combustible (diésel)", "unidad": "L", "alcance": 1,
                      "valor": {"chile": 2.68, "peru": 2.68}},
    "energia_kwh": {"nombre": "Electricidad de la red", "unidad": "kWh", "alcance": 2,
                    "valor": {"chile": 0.35, "peru": 0.25}},
    "residuos_peligrosos_kg": {"nombre": "Residuos peligrosos", "unidad": "kg", "alcance": 3,
                               "valor": {"chile": 0.5, "peru": 0.5}},
    "residuos_no_peligrosos_kg": {"nombre": "Residuos no peligrosos", "unidad": "kg", "alcance": 3,
                                  "valor": {"chile": 0.45, "peru": 0.45}},
}
TIPOS_SOCIALES = ["empleados_total", "mujeres_empleadas", "horas_capacitacion",
                  "inversion_comunitaria", "reclamos_comunitarios", "reclamos_resueltos"]


def factores_efectivos(db: Session, empresa: Empresa) -> dict:
    propios = {f.clave: f for f in db.query(FactorEmpresa).filter_by(empresa_id=empresa.id)}
    out = {}
    for clave, f in FACTORES_BASE.items():
        p = propios.get(clave)
        out[clave] = {"clave": clave, "nombre": f["nombre"], "unidad": f["unidad"], "alcance": f["alcance"],
                      "valor": p.valor if p else f["valor"][empresa.pais],
                      "referencial": p is None, "fuente": p.fuente if p else "Valor referencial"}
    return out


def _ultimos_periodos(periodos: set[str], n: int = 12) -> list[str]:
    return sorted(periodos)[-n:]


def calcular_emisiones(db: Session, empresa: Empresa) -> dict:
    fac = factores_efectivos(db, empresa)
    rows = db.query(IndicadorAmbiental).filter(IndicadorAmbiental.empresa_id == empresa.id,
                                               IndicadorAmbiental.tipo.in_(list(fac))).all()
    periodos = _ultimos_periodos({r.periodo for r in rows})
    por_periodo = {p: {"alcance1": 0.0, "alcance2": 0.0, "alcance3": 0.0} for p in periodos}
    for r in rows:
        if r.periodo in por_periodo:
            f = fac[r.tipo]
            por_periodo[r.periodo][f"alcance{f['alcance']}"] += r.valor * f["valor"] / 1000  # t CO2e
    tot = {k: round(sum(v[k] for v in por_periodo.values()), 2) for k in ("alcance1", "alcance2", "alcance3")}
    tot["total"] = round(sum(tot.values()), 2)
    horas = sum(h.horas for h in db.query(HorasTrabajadas).filter(
        HorasTrabajadas.empresa_id == empresa.id, HorasTrabajadas.periodo.in_(periodos)))
    return {
        "factores": list(fac.values()),
        "por_periodo": {p: {k: round(v, 2) for k, v in d.items()} for p, d in por_periodo.items()},
        "total_12m": tot,
        "intensidad_t_por_mhh": round(tot["total"] * 1_000_000 / horas, 1) if horas else None,
    }


def total_anual(db: Session, empresa: Empresa, indicador: str) -> float | None:
    """Suma de los últimos 12 periodos del indicador (o emisiones totales)."""
    if indicador == "emisiones_tco2e":
        t = calcular_emisiones(db, empresa)["total_12m"]["total"]
        return t or None
    rows = db.query(IndicadorAmbiental).filter_by(empresa_id=empresa.id, tipo=indicador).all()
    ult = _ultimos_periodos({r.periodo for r in rows})
    vals = [r.valor for r in rows if r.periodo in ult]
    return round(sum(vals), 1) if vals else None


def estado_meta(db: Session, empresa: Empresa, m: MetaSostenibilidad) -> dict:
    actual = total_anual(db, empresa, m.indicador)
    objetivo = m.valor_base * (1 - m.reduccion_pct / 100)
    out = {"id": m.id, "nombre": m.nombre, "indicador": m.indicador, "anio_base": m.anio_base,
           "valor_base": m.valor_base, "anio_meta": m.anio_meta, "reduccion_pct": m.reduccion_pct,
           "valor_objetivo": round(objetivo, 1), "valor_actual": actual,
           "reduccion_lograda_pct": None, "reduccion_esperada_pct": None, "estado": "sin_datos"}
    if actual is None or m.valor_base <= 0:
        return out
    lograda = 100 * (m.valor_base - actual) / m.valor_base
    span = max(1, m.anio_meta - m.anio_base)
    avance_tiempo = min(1.0, max(0.0, (date.today().year - m.anio_base) / span))
    esperada = m.reduccion_pct * avance_tiempo
    out["reduccion_lograda_pct"] = round(lograda, 1)
    out["reduccion_esperada_pct"] = round(esperada, 1)
    out["estado"] = ("cumplida" if actual <= objetivo
                     else "en_camino" if lograda >= esperada else "atrasada")
    return out


def _anual_social(db: Session, eid: int) -> dict[str, float]:
    rows = db.query(IndicadorSocial).filter_by(empresa_id=eid).all()
    ult = _ultimos_periodos({r.periodo for r in rows})
    s: dict[str, float] = {}
    for r in rows:
        if r.periodo in ult:
            s[r.tipo] = s.get(r.tipo, 0) + r.valor
    # Dotación es una foto (no se suma): usar el último periodo.
    for t in ("empleados_total", "mujeres_empleadas"):
        v = [(r.periodo, r.valor) for r in rows if r.tipo == t]
        if v:
            s[t] = max(v)[1]
    return s


def indice_gri(db: Session, empresa: Empresa) -> list[dict]:
    eid = empresa.id
    em = calcular_emisiones(db, empresa)["total_12m"]
    sums = {t: total_anual(db, empresa, t) for t in
            ("energia_kwh", "combustible_l", "agua_m3", "residuos_peligrosos_kg", "residuos_no_peligrosos_kg")}
    soc = _anual_social(db, eid)
    hoy = date.today()
    ctp = db.query(Incidente).filter(Incidente.empresa_id == eid, Incidente.tipo == "accidente_ctp",
                                     Incidente.fecha >= date(hoy.year - 1, hoy.month, min(hoy.day, 28))).count()
    vencidos = db.query(RequisitoLegal).filter(RequisitoLegal.empresa_id == eid,
                                               RequisitoLegal.fecha_vencimiento < hoy).count()
    emp = soc.get("empleados_total")
    pct_mujeres = round(100 * soc["mujeres_empleadas"] / emp, 1) if emp and "mujeres_empleadas" in soc else None
    h_cap = round(soc["horas_capacitacion"] / emp, 1) if emp and "horas_capacitacion" in soc else None
    recl = soc.get("reclamos_comunitarios")
    pct_res = round(100 * soc.get("reclamos_resueltos", 0) / recl, 1) if recl else None

    def fila(cod, nombre, valor, unidad, extra=""):
        return {"codigo": cod, "indicador": nombre, "valor": valor, "unidad": unidad,
                "reportable": valor is not None, "nota": extra}
    return [
        fila("GRI 302-1", "Consumo de energía eléctrica", sums["energia_kwh"], "kWh"),
        fila("GRI 302-1", "Consumo de combustible", sums["combustible_l"], "L"),
        fila("GRI 303-5", "Consumo de agua", sums["agua_m3"], "m³"),
        fila("GRI 305-1 / NIIF S2", "Emisiones directas (alcance 1)", em["alcance1"] or None, "t CO2e", "Factores referenciales si no se reemplazaron"),
        fila("GRI 305-2 / NIIF S2", "Emisiones indirectas por energía (alcance 2)", em["alcance2"] or None, "t CO2e"),
        fila("GRI 305-3 / NIIF S2", "Otras emisiones indirectas (alcance 3, parcial)", em["alcance3"] or None, "t CO2e", "Solo residuos; el inventario completo requiere más categorías"),
        fila("GRI 306-3", "Residuos peligrosos generados", sums["residuos_peligrosos_kg"], "kg"),
        fila("GRI 306-3", "Residuos no peligrosos generados", sums["residuos_no_peligrosos_kg"], "kg"),
        fila("GRI 403-9", "Accidentes con tiempo perdido (12 m)", ctp, "casos"),
        fila("GRI 404-1", "Horas de capacitación por empleado", h_cap, "h"),
        fila("GRI 405-1", "Mujeres en la dotación", pct_mujeres, "%"),
        fila("GRI 2-25", "Reclamos comunitarios resueltos", pct_res, "%"),
        fila("GRI 2-27", "Requisitos legales vencidos", vencidos, "casos"),
    ]
