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


# ---------------------------------------------------------------------------
# Normativa por país. Resumen de requisitos de cada marco, sin citar artículos.
# Verificar siempre contra el texto vigente y sus modificaciones.
# ---------------------------------------------------------------------------
PLANTILLAS += [
    {
        "clave": "cl-min-ds132",
        "nombre": "Chile minería: Reglamento de Seguridad Minera (DS 132)",
        "norma": "DS 132 (Chile)",
        "sector": "mineria",
        "pais": "chile",
        "items": [
            ("SGSST", "Sistema de gestión de seguridad y salud ocupacional implementado y aprobado por el nivel de dirección.", True),
            ("Reglamento", "Reglamento interno de higiene y seguridad vigente y difundido a los trabajadores.", False),
            ("Estudio", "Matriz de identificación de peligros y evaluación de riesgos (IPER) actualizada por faena.", True),
            ("Procedimientos", "Procedimientos de trabajo seguro para tareas críticas conocidos por quienes las ejecutan.", True),
            ("Capacitación", "Inducción de ingreso y capacitación específica registradas por trabajador y contratista.", False),
            ("Emergencias", "Plan de emergencia de la faena con simulacros según programa.", True),
            ("Investigación", "Accidentes graves y fatales informados a la autoridad y con investigación documentada.", True),
            ("Contratistas", "Gestión de seguridad de contratistas y subcontratistas con verificación de cumplimiento.", False),
            ("Estabilidad", "Estabilidad de taludes, labores subterráneas y botaderos monitoreada con registros.", True),
            ("Explosivos", "Almacenamiento, transporte y uso de explosivos conforme a procedimiento y personal autorizado.", True),
            ("Equipos", "Equipos móviles y fijos con mantención al día y dispositivos de seguridad operativos.", False),
            ("Salud", "Exámenes de salud ocupacional y de altura geográfica vigentes según exposición.", False),
        ],
    },
    {
        "clave": "cl-legal-laboral",
        "nombre": "Chile: Seguridad laboral (Ley 16.744 y DS 594, DS 40, DS 54)",
        "norma": "Ley 16.744 / DS 594 (Chile)",
        "sector": "todos",
        "pais": "chile",
        "items": [
            ("Ley 16.744", "Empresa adherida a un organismo administrador del seguro (mutualidad o ISL) y con denuncias de accidentes al día.", True),
            ("DS 40", "Obligación de informar los riesgos laborales (ODI) entregada y registrada por trabajador.", False),
            ("DS 54", "Comité Paritario de Higiene y Seguridad constituido donde corresponde, con actas y reuniones vigentes.", False),
            ("Depto.", "Departamento de prevención de riesgos o experto a cargo, según tamaño de la empresa.", False),
            ("DS 594", "Condiciones sanitarias y ambientales básicas: servicios higiénicos, agua potable, comedores.", False),
            ("DS 594", "Agentes químicos, ruido y otros agentes medidos y bajo los límites permisibles.", True),
            ("Protocolos", "Protocolos del Minsal aplicables (por ejemplo PREXOR, TMERT, sílice) implementados.", False),
            ("Ley 21.643", "Protocolo de prevención del acoso y la violencia en el trabajo implementado y difundido.", False),
        ],
    },
    {
        "clave": "cl-amb-relaves-cierre",
        "nombre": "Chile minería: Relaves (DS 248) y cierre de faenas (Ley 20.551)",
        "norma": "DS 248 / Ley 20.551 (Chile)",
        "sector": "mineria",
        "pais": "chile",
        "items": [
            ("DS 248", "Depósito de relaves con proyecto aprobado y operación conforme al mismo.", True),
            ("DS 248", "Inspecciones y monitoreo del depósito (estabilidad, niveles, filtraciones) registrados.", True),
            ("DS 248", "Plan de emergencia del depósito de relaves con simulacros.", True),
            ("Ley 20.551", "Plan de cierre de faena aprobado, con garantía financiera y actualización en los plazos exigidos.", True),
            ("RCA", "Condiciones y compromisos de la resolución de calificación ambiental (RCA) bajo seguimiento.", True),
            ("SMA", "Reportes de monitoreo a la Superintendencia del Medio Ambiente entregados en plazo.", False),
            ("Aguas", "Derechos de aprovechamiento de aguas y caudales extraídos dentro de lo autorizado.", False),
            ("Residuos", "Residuos peligrosos declarados en el sistema oficial y entregados a destinatario autorizado.", True),
        ],
    },
    {
        "clave": "pe-min-ds024",
        "nombre": "Perú minería: Reglamento de Seguridad y Salud Ocupacional en Minería (DS 024-2016-EM)",
        "norma": "DS 024-2016-EM (Perú)",
        "sector": "mineria",
        "pais": "peru",
        "items": [
            ("SGSST", "Sistema de gestión de seguridad y salud ocupacional implementado, con política y objetivos.", True),
            ("IPERC", "Matriz IPERC por actividad actualizada y revisada por los trabajadores involucrados.", True),
            ("Comité", "Comité de Seguridad y Salud Ocupacional constituido, con reuniones y actas.", False),
            ("Programa", "Programa anual de seguridad y salud ocupacional aprobado y con avance medido.", False),
            ("Capacitación", "Programa de capacitación anual ejecutado y registrado, incluido personal contratista.", False),
            ("Permisos", "Permisos de trabajo de alto riesgo (altura, espacios confinados, trabajo en caliente, energías peligrosas).", True),
            ("Bloqueo", "Procedimiento de bloqueo y etiquetado aplicado antes de intervenir equipos.", True),
            ("Emergencias", "Plan de contingencia y simulacros realizados según programa.", True),
            ("Investigación", "Incidentes y accidentes investigados, reportados al ente fiscalizador y con acciones definidas.", True),
            ("Estabilidad", "Control de estabilidad de taludes, labores subterráneas y ventilación con registros.", True),
            ("Salud", "Exámenes médicos ocupacionales vigentes (ingreso, periódicos, retiro).", False),
            ("Contratistas", "Empresas contratistas mineras con verificación de cumplimiento del reglamento.", False),
        ],
    },
    {
        "clave": "pe-legal-ley29783",
        "nombre": "Perú: Ley 29783 de Seguridad y Salud en el Trabajo y su reglamento",
        "norma": "Ley 29783 / DS 005-2012-TR (Perú)",
        "sector": "todos",
        "pais": "peru",
        "items": [
            ("Política", "Política de SST documentada, firmada por la alta dirección y difundida.", False),
            ("Reglamento", "Reglamento interno de seguridad y salud en el trabajo vigente y entregado.", False),
            ("Comité", "Comité o supervisor de SST elegido según el número de trabajadores, con actas.", True),
            ("IPERC", "Identificación de peligros y evaluación de riesgos y controles (IPERC) actualizada.", True),
            ("Registros", "Registros obligatorios de accidentes, enfermedades, monitoreos y capacitaciones al día.", True),
            ("Capacitación", "Cuatro capacitaciones al año como mínimo, con constancia por trabajador.", False),
            ("Salud", "Exámenes médicos ocupacionales vigentes según el riesgo del puesto.", False),
            ("Auditoría", "Auditoría del sistema de gestión de SST realizada en la periodicidad exigida.", False),
            ("EPP", "Equipos de protección personal entregados con registro y adecuados al riesgo.", False),
            ("Emergencias", "Plan de emergencia y simulacros al menos según lo exigido.", True),
        ],
    },
    {
        "clave": "pe-amb-min",
        "nombre": "Perú minería: Ambiental (DS 040-2014-EM) y cierre de minas (Ley 28090)",
        "norma": "DS 040-2014-EM / Ley 28090 (Perú)",
        "sector": "mineria",
        "pais": "peru",
        "items": [
            ("IGA", "Instrumento de gestión ambiental aprobado y compromisos en cumplimiento.", True),
            ("OEFA", "Reportes de monitoreo ambiental presentados al OEFA en los plazos.", True),
            ("LMP/ECA", "Efluentes y calidad de aire y agua dentro de los límites máximos permisibles y estándares de calidad.", True),
            ("Relaves", "Depósitos de relaves y botaderos con inspecciones geotécnicas y plan de contingencia.", True),
            ("Cierre", "Plan de cierre de minas aprobado, con garantía ambiental vigente.", True),
            ("Residuos", "Residuos peligrosos almacenados y entregados a una empresa operadora autorizada.", True),
            ("Social", "Compromisos de participación ciudadana y relaciones con la comunidad documentados.", False),
            ("Agua", "Autorizaciones de uso y vertimiento de agua vigentes.", False),
        ],
    },
]


# ---------------------------------------------------------------------------
# Sostenibilidad. Resúmenes de requisitos; verificar contra el texto vigente.
# ---------------------------------------------------------------------------
PLANTILLAS += [
    {
        "clave": "sos-gistm",
        "nombre": "Sostenibilidad minería: Estándar Global de Gestión de Relaves (GISTM)",
        "norma": "GISTM",
        "sector": "mineria",
        "pais": "todos",
        "items": [
            ("Comunidades", "Se involucra a las comunidades afectadas y se consideran sus derechos y riesgos en las decisiones sobre el depósito.", True),
            ("Conocimiento", "Existe una base de conocimiento integrada (geología, hidrología, geotecnia, ambiente y social) que respalda el diseño.", True),
            ("Conocimiento", "Se evalúan múltiples alternativas de ubicación y tecnología, incluida la minimización de relaves.", False),
            ("Diseño", "El diseño se basa en la consecuencia de falla y en criterios para el ciclo de vida completo, incluido el cierre.", True),
            ("Diseño", "Se aplica el método observacional y un plan de monitoreo con indicadores y umbrales de acción.", True),
            ("Gestión", "Hay un ejecutivo responsable designado para la seguridad de cada depósito.", True),
            ("Gestión", "Existe un Ingeniero Responsable (EoR) designado para cada depósito, con contrato vigente.", True),
            ("Gestión", "Un panel independiente de revisión de relaves (ITRB) revisa el diseño y la operación.", True),
            ("Gestión", "Se mantiene un sistema de gestión con política, roles, presupuesto y revisión periódica de riesgos.", False),
            ("Emergencias", "Hay un plan de respuesta a emergencias y de recuperación a largo plazo, probado con las partes interesadas.", True),
            ("Divulgación", "Se divulga públicamente información del depósito, su riesgo y su gestión.", False),
            ("Cierre", "El plan de cierre y post-cierre incluye responsabilidad financiera y monitoreo de largo plazo.", True),
        ],
    },
    {
        "clave": "sos-icmm",
        "nombre": "Sostenibilidad minería: Principios de ICMM y buenas prácticas",
        "norma": "ICMM",
        "sector": "mineria",
        "pais": "todos",
        "items": [
            ("Ética", "Políticas de ética, anticorrupción y transparencia implementadas y comunicadas.", False),
            ("Riesgos", "Gestión de riesgos incluye aspectos ambientales, sociales y de gobernanza.", True),
            ("Derechos humanos", "Se respetan los derechos humanos y los intereses de comunidades y pueblos indígenas, con diligencia debida.", True),
            ("Biodiversidad", "La biodiversidad se considera en la planificación, con jerarquía de mitigación.", False),
            ("Agua", "Gestión de agua con balance hídrico, metas y cuentas de uso a nivel de cuenca.", True),
            ("Clima", "Se gestionan las emisiones de GEI y los riesgos climáticos físicos y de transición.", True),
            ("Comunidades", "Mecanismo de reclamos accesible a las comunidades, con seguimiento de resolución.", True),
            ("Reporte", "Se publica un reporte de sostenibilidad con verificación independiente del cumplimiento.", False),
        ],
    },
    {
        "clave": "sos-ghg-14064",
        "nombre": "Sostenibilidad: Inventario de gases de efecto invernadero (ISO 14064 / GHG Protocol)",
        "norma": "ISO 14064",
        "sector": "todos",
        "pais": "todos",
        "items": [
            ("Límites", "Se definieron los límites organizacionales (control operacional o participación) y operacionales.", True),
            ("Fuentes", "Se identificaron las fuentes de alcance 1, 2 y las categorías relevantes de alcance 3.", True),
            ("Datos", "Los datos de actividad (combustible, energía, residuos) tienen origen, responsable y registro.", True),
            ("Factores", "Los factores de emisión provienen de fuentes oficiales vigentes y están documentados.", True),
            ("Año base", "Hay año base definido y política de recálculo ante cambios significativos.", False),
            ("Calidad", "Se aplican controles de calidad y se estiman las incertidumbres.", False),
            ("Verificación", "El inventario fue verificado por una tercera parte cuando se requiere o se comunica externamente.", False),
            ("Metas", "Existen metas de reducción con seguimiento y plan de acción.", False),
        ],
    },
    {
        "clave": "sos-iso50001",
        "nombre": "Sostenibilidad: Gestión de la energía (ISO 50001)",
        "norma": "ISO 50001",
        "sector": "todos",
        "pais": "todos",
        "items": [
            ("Política", "Política energética aprobada por la alta dirección y difundida.", False),
            ("Revisión", "Revisión energética identifica los usos significativos de energía.", True),
            ("Línea base", "Hay línea base energética e indicadores de desempeño (IDEn) definidos.", True),
            ("Metas", "Objetivos y metas energéticas con planes de acción y responsables.", False),
            ("Medición", "Los equipos de medición están calibrados y los datos se registran periódicamente.", False),
            ("Compras", "Criterios de eficiencia energética en compras de equipos y diseño de proyectos.", False),
        ],
    },
    {
        "clave": "sos-niif-s1-s2",
        "nombre": "Sostenibilidad: Preparación para reportar con NIIF S1 y S2",
        "norma": "NIIF S1/S2",
        "sector": "todos",
        "pais": "todos",
        "items": [
            ("Gobernanza", "El directorio supervisa los riesgos y oportunidades de sostenibilidad y clima.", True),
            ("Estrategia", "Se identificaron riesgos y oportunidades de sostenibilidad y su efecto financiero.", True),
            ("Clima", "Se realizó un análisis de escenarios climáticos para evaluar resiliencia.", False),
            ("Riesgos", "Los riesgos de sostenibilidad están integrados en la gestión de riesgos corporativa.", True),
            ("Métricas", "Se miden emisiones de alcance 1, 2 y 3 con metodología documentada.", True),
            ("Metas", "Hay metas relacionadas con el clima con seguimiento del avance.", False),
            ("Datos", "Los datos de sostenibilidad tienen controles equivalentes a los de la información financiera.", False),
        ],
    },
    {
        "clave": "sos-social-comunidades",
        "nombre": "Sostenibilidad: Relación con comunidades y pueblos indígenas",
        "norma": "OIT 169 / Social",
        "sector": "todos",
        "pais": "todos",
        "items": [
            ("Consulta", "Se identificaron los pueblos indígenas y comunidades afectadas y los procesos de consulta aplicables.", True),
            ("Participación", "Hay un plan de relacionamiento comunitario con registro de reuniones y compromisos.", False),
            ("Reclamos", "Existe un mecanismo de reclamos con plazos de respuesta y seguimiento.", True),
            ("Compromisos", "Los compromisos adquiridos con la comunidad están registrados y con responsable.", False),
            ("Empleo local", "Se promueve el empleo y la contratación de proveedores locales con indicadores.", False),
            ("Patrimonio", "Se protege el patrimonio cultural y arqueológico en el área de influencia.", False),
        ],
    },
    {
        "clave": "cl-sos-clima-rep",
        "nombre": "Chile: Cambio climático (Ley 21.455) y Responsabilidad Extendida del Productor (Ley 20.920)",
        "norma": "Ley 21.455 / Ley 20.920 (Chile)",
        "sector": "todos",
        "pais": "chile",
        "items": [
            ("Ley 21.455", "Se verificó si la empresa está obligada a reportar emisiones o a presentar planes de mitigación según los umbrales vigentes.", True),
            ("Ley 21.455", "Se identificaron los instrumentos sectoriales de adaptación y mitigación que aplican a la actividad.", False),
            ("RETC", "Las emisiones y residuos se declaran en el registro oficial (RETC) cuando corresponde.", True),
            ("Ley REP", "Se determinó si la empresa es productora de un producto prioritario (envases, neumáticos, baterías, aceites, aparatos eléctricos).", True),
            ("Ley REP", "La empresa está inscrita en un sistema de gestión y cumple las metas de recolección y valorización.", True),
            ("Residuos", "Se mantiene trazabilidad y declaración de los residuos generados.", False),
        ],
    },
    {
        "clave": "pe-sos-clima-residuos",
        "nombre": "Perú: Cambio climático (Ley 30754) y gestión de residuos sólidos",
        "norma": "Ley 30754 / DL 1278 (Perú)",
        "sector": "todos",
        "pais": "peru",
        "items": [
            ("Ley 30754", "Se verificó si la empresa tiene obligaciones de reporte de emisiones o de medidas de mitigación según su sector.", True),
            ("HC Perú", "Se evaluó la participación en la herramienta Huella de Carbono Perú y se guardan los reportes.", False),
            ("DL 1278", "Se presenta la declaración anual de manejo de residuos sólidos cuando corresponde.", True),
            ("DL 1278", "Los residuos peligrosos se transportan con manifiesto y los gestiona una empresa autorizada.", True),
            ("Residuos", "Existe un plan de minimización y manejo de residuos con segregación en la fuente.", False),
            ("Plásticos", "Se cumplen las restricciones de plásticos de un solo uso aplicables.", False),
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
                                norma=p["norma"], sector=p["sector"],
                                pais=p.get("pais", "todos"))
        for i, (cl, tx, cr) in enumerate(p["items"], start=1):
            pl.items.append(PlantillaItem(orden=i, clausula=cl, texto=tx, critico=cr))
        db.add(pl)
        creadas += 1
    db.commit()
    return creadas
