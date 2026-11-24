"""Checklists globales (empresa_id NULL) para minería e industria.

Son listas de verificación de partida, resumidas. Cada cliente debe revisarlas
y adaptarlas a su sistema de gestión y a la normativa local vigente.
Formato de ítem: (cláusula, texto, crítico)
"""
from sqlalchemy.orm import Session

from app.models import PlantillaAuditoria, PlantillaItem

PLANTILLAS = [
    {
        "clave": "min-riesgos-criticos",
        "nombre": "Minería: Controles de riesgos críticos",
        "norma": "ISO 45001",
        "sector": "mineria",
        "items": [
            ("8.1.2", "Existe bloqueo y etiquetado (LOTO) verificado antes de intervenir equipos.", True),
            ("8.1.2", "Trabajos en altura cuentan con permiso, arnés inspeccionado y punto de anclaje certificado.", True),
            ("8.1.2", "Ingreso a espacios confinados con permiso, medición de gases y vigía.", True),
            ("8.1.2", "Interacción vehículo liviano / equipo pesado controlada (segregación, distancias, señalización).", True),
            ("8.1.2", "Estabilidad de taludes y bancos monitoreada, con registro de inspecciones.", True),
            ("8.1.2", "Perímetro de voladura despejado y protocolo de evacuación verificado.", True),
            ("8.1.2", "Gestión de fatiga y somnolencia de operadores de equipo móvil.", False),
            ("6.1.2", "Matriz de peligros y riesgos actualizada en el último periodo definido.", False),
            ("7.2", "Personal con inducción y competencias vigentes para la tarea que ejecuta.", False),
            ("8.2", "Plan de emergencia y simulacro realizados según programa.", False),
            ("9.1", "Indicadores proactivos (inspecciones, observaciones) reportados y analizados.", False),
            ("10.2", "Incidentes con potencial de fatalidad investigados dentro del plazo definido.", True),
        ],
    },
    {
        "clave": "min-ambiental-relaves",
        "nombre": "Minería: Gestión ambiental, agua y relaves",
        "norma": "ISO 14001",
        "sector": "mineria",
        "items": [
            ("6.1.2", "Aspectos e impactos ambientales identificados y evaluados.", False),
            ("6.1.3", "Requisitos legales y permisos ambientales vigentes y controlados.", True),
            ("8.1", "Depósito de relaves con inspecciones geotécnicas y piezometría al día.", True),
            ("8.1", "Control de emisiones de material particulado (riego de caminos, monitoreo).", False),
            ("8.1", "Manejo de aguas de contacto y no contacto, con balance hídrico actualizado.", False),
            ("8.1", "Residuos peligrosos almacenados, etiquetados y retirados por gestor autorizado.", True),
            ("8.2", "Plan de respuesta a derrames y contingencias ambientales probado.", True),
            ("9.1", "Monitoreos ambientales (agua, aire, ruido) dentro de los límites exigidos.", False),
            ("8.1", "Plan de cierre de faena actualizado.", False),
        ],
    },
    {
        "clave": "ind-seguridad-planta",
        "nombre": "Industria: Seguridad en planta",
        "norma": "ISO 45001",
        "sector": "industria",
        "items": [
            ("8.1.2", "Máquinas con guardas fijas y paradas de emergencia operativas.", True),
            ("8.1.2", "Procedimiento LOTO aplicado en mantenimiento y limpieza.", True),
            ("8.1.2", "Trabajos en caliente con permiso y vigía de fuego.", True),
            ("8.1.2", "Montacargas operados por personal habilitado, con checklist diario.", False),
            ("8.1.2", "Almacenamiento de sustancias peligrosas con hojas de seguridad accesibles.", True),
            ("8.1.2", "EPP entregado, adecuado a la tarea y registrado.", False),
            ("6.1.2", "Evaluación de riesgos por puesto actualizada.", False),
            ("8.2", "Vías de evacuación libres y extintores con inspección vigente.", True),
            ("7.2", "Capacitación en seguridad registrada por trabajador.", False),
            ("10.2", "Accidentes e incidentes investigados con acciones definidas.", False),
        ],
    },
    {
        "clave": "ind-calidad-9001",
        "nombre": "Industria: Calidad de proceso",
        "norma": "ISO 9001",
        "sector": "industria",
        "items": [
            ("7.1.5", "Equipos de medición calibrados con certificado vigente.", True),
            ("7.5", "Documentos controlados, vigentes y disponibles en el punto de uso.", False),
            ("8.4", "Proveedores críticos evaluados periódicamente.", False),
            ("8.5.2", "Trazabilidad de lote o producto verificada de extremo a extremo.", True),
            ("8.6", "Liberación de producto con inspección final registrada.", True),
            ("8.7", "Producto no conforme identificado, segregado y con disposición definida.", True),
            ("9.1.2", "Satisfacción del cliente y reclamos analizados.", False),
            ("10.2", "No conformidades con análisis de causa raíz y acción correctiva.", False),
        ],
    },
    {
        "clave": "ind-ambiental-14001",
        "nombre": "Industria: Gestión ambiental",
        "norma": "ISO 14001",
        "sector": "industria",
        "items": [
            ("6.1.3", "Requisitos legales ambientales identificados y con evidencia de cumplimiento.", True),
            ("8.1", "Residuos segregados, almacenados y dispuestos con gestor autorizado.", True),
            ("8.1", "Consumos de energía y agua medidos con metas de reducción.", False),
            ("8.1", "Efluentes y emisiones monitoreados dentro de límites.", True),
            ("8.2", "Plan de emergencia ambiental con simulacro registrado.", False),
            ("9.1", "Indicadores ambientales analizados en la revisión por la dirección.", False),
        ],
    },
]


def seed_plantillas(db: Session) -> int:
    """Inserta las plantillas globales que aún no existan. Devuelve cuántas creó."""
    existentes = {c for (c,) in db.query(PlantillaAuditoria.clave)
                  .filter(PlantillaAuditoria.empresa_id.is_(None)).all()}
    creadas = 0
    for p in PLANTILLAS:
        if p["clave"] in existentes:
            continue
        pl = PlantillaAuditoria(empresa_id=None, clave=p["clave"], nombre=p["nombre"],
                                norma=p["norma"], sector=p["sector"])
        for i, (cl, tx, cr) in enumerate(p["items"], start=1):
            pl.items.append(PlantillaItem(orden=i, clausula=cl, texto=tx, critico=cr))
        db.add(pl)
        creadas += 1
    db.commit()
    return creadas
