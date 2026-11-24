# Arquitectura — HSEQ Hub

**Repo:** `github.com/fjelve/hseq-hub` · **Carpeta local:** `Soc\Soc\HSEQ-Hub`
**Stack:** FastAPI + SQLAlchemy 2 + PostgreSQL 16 (SQLite en desarrollo) + frontend HTML/JS + Docker + Nginx
**Alcance:** SaaS multiempresa de gestión HSEQ, calidad y sostenibilidad para minería e industria en Chile y Perú.

Este documento distingue lo **implementado** (existe en el código y tiene pruebas) de lo **propuesto** (no existe todavía). Las secciones 7 y 8 son propuestas.

---

## 1. Visión general

```
                         ┌────────────────────────────┐
                         │   Usuarios (por empresa)   │
                         │ admin · auditor · responsable│
                         └──────────────┬─────────────┘
                                        │ HTTPS
                         ┌──────────────▼─────────────┐
                         │   Cloudflare (CDN/WAF/SSL) │   ← propuesto, como el resto del ecosistema
                         └──────────────┬─────────────┘
                         ┌──────────────▼─────────────┐
                         │  Nginx (reverse proxy)     │
                         │  /      → frontend estático│
                         │  /api/  → API :8003        │
                         └───────┬──────────────┬─────┘
                                 │              │
                  ┌──────────────▼───┐   ┌──────▼────────────────┐
                  │ Frontend (SPA     │   │ hseq_api (FastAPI)    │
                  │ HTML + JS, sin    │   │  • REST /api/v1       │
                  │ build)            │   │  • JWT + roles        │
                  └───────────────────┘   │  • Bucle de alertas   │
                                          └───┬───────────────┬───┘
                                              │               │
                                   ┌──────────▼───┐    ┌──────▼───────┐
                                   │ hseq_db      │    │ SMTP (correo)│
                                   │ PostgreSQL 16│    └──────────────┘
                                   └──────────────┘
```

## 2. Componentes del backend (implementado)

```
backend/app/
├── main.py            Arranque: crea tablas, siembra checklists, lanza el bucle de alertas
├── config.py          Variables de entorno (falla en producción si SECRET_KEY es la de ejemplo)
├── database.py        Motor SQLAlchemy y sesión por request
├── auth.py            bcrypt, JWT HS256 (8 h), dependencia de rol
├── models.py          15 tablas (sección 3)
├── schemas.py         Validación de entrada y salida (Pydantic)
├── seed_plantillas.py 19 checklists globales (ISO, Chile, Perú, sostenibilidad)
├── routes/
│   ├── auth.py          registro de empresa, login, usuarios
│   ├── hallazgos.py     CAPA: hallazgos, acciones, cierre con verificación
│   ├── auditorias.py    plantillas, auditorías, respuestas, cierre
│   ├── incidentes.py    incidentes, horas trabajadas, índices de frecuencia y severidad
│   ├── legal.py         requisitos legales y permisos con vencimiento
│   ├── ambiental.py     consumos mensuales
│   ├── sostenibilidad.py emisiones, factores, metas, indicadores sociales, índice GRI
│   ├── dashboard.py     indicadores consolidados
│   └── demo.py          carga de datos de ejemplo (solo cuentas vacías)
└── services/
    ├── alertas.py        revisión periódica de vencimientos y envío de correo
    └── sostenibilidad.py cálculo de huella de carbono, estado de metas, mapeo GRI / NIIF S2
```

| Módulo | Rutas principales (`/api/v1`) | Roles que escriben |
|---|---|---|
| Autenticación | `/auth/registro`, `/auth/login`, `/auth/me`, `/usuarios` | admin (usuarios) |
| Hallazgos / CAPA | `/hallazgos`, `/hallazgos/{id}/acciones`, `/hallazgos/{id}/cerrar` | admin, auditor |
| Auditorías | `/plantillas`, `/auditorias`, `/auditorias/{id}/respuestas`, `/auditorias/{id}/cerrar` | admin, auditor |
| Incidentes | `/incidentes`, `/horas-trabajadas`, `/kpis-seguridad` | admin, auditor |
| Requisitos legales | `/requisitos`, `/requisitos/{id}/renovar` | admin, auditor |
| Sostenibilidad | `/ambiental`, `/emisiones`, `/factores`, `/metas`, `/social`, `/reporte/gri` | admin, auditor |
| Resumen | `/dashboard` | lectura para todos |

El rol `responsable` solo lee, y puede completar las acciones que tiene asignadas.

## 3. Modelo de datos (implementado)

```
Empresa (tenant) ──┬── Usuario
  sector, pais     │
                   ├── Hallazgo ──── Accion (1:N)
                   │      ▲
                   │      │ genera automáticamente
                   ├── Auditoria ── Respuesta ── PlantillaItem ── PlantillaAuditoria
                   │                              (plantillas globales: empresa_id NULL)
                   ├── Incidente ────────┘ (abre hallazgo si es accidente o casi accidente grave)
                   ├── HorasTrabajadas
                   ├── RequisitoLegal
                   ├── IndicadorAmbiental ──► emisiones (× FactorEmpresa o factor referencial)
                   ├── IndicadorSocial
                   ├── MetaSostenibilidad
                   └── FactorEmpresa
```

Toda tabla de negocio lleva `empresa_id`, salvo las plantillas globales (`empresa_id` nulo). Hay restricciones únicas en `(empresa_id, codigo)` de hallazgos y en `(empresa_id, periodo[, tipo])` de horas e indicadores.

## 4. Flujos automáticos (implementado)

```
Auditoría ──cerrar──► puntaje % ──► por cada "no cumple" ──► Hallazgo (severidad por criticidad,
                                                                  plazo: crítica 7 d · alta 15 d · media 30 d · baja 60 d)
Incidente ──registrar──► accidente o casi accidente alta/crítica ──► Hallazgo de investigación

Hallazgo:  abierto ─► en_proceso ─► en_verificacion ─► cerrado
           (agregar acción)  (todas las acciones completas)  (causa raíz + acciones + verificación de eficacia)

Bucle de alertas (cada 60 min):
   hallazgos por vencer (3 d) o vencidos ─► correo al responsable (o a los admin)
   requisitos legales a 30 d o vencidos   ─► correo al responsable (o a los admin)
   Cada aviso se marca como enviado para no repetirlo.

Consumos mensuales ─► × factor de emisión ─► t CO2e por alcance 1, 2, 3 (parcial) ─► metas y reporte GRI / NIIF S2
```

## 5. Seguridad (implementado)

| Control | Detalle |
|---|---|
| Autenticación | bcrypt (contraseña mínima de 10 caracteres) y JWT con expiración |
| Autorización | Rol por endpoint de escritura. Pruebas automáticas para el rol `responsable` |
| Aislamiento entre empresas | Toda consulta filtra por `empresa_id` del usuario. Los IDs de otra empresa devuelven 404. Hay pruebas de aislamiento |
| Secretos | Sin valores por defecto en `docker-compose.yml`: exige `DB_PASSWORD` y `SECRET_KEY`. En producción la app no arranca con la clave de ejemplo |
| Entradas | Validación con Pydantic (rangos, formatos de periodo, listas cerradas) |
| Frontend | Todo texto dinámico se escapa antes de insertarlo; el CSV neutraliza fórmulas |
| Contenedor | La API corre como usuario sin privilegios |

## 6. Despliegue propuesto (mismo patrón que el resto del ecosistema)

```
Local (Kiro) ─► git push ─► GitHub Action (scp + ssh, clave ED25519) ─► /var/www/hseq ─► docker compose up -d --build
```

| Elemento | Propuesta |
|---|---|
| Dominio | `hseq.andrema.tech` (por confirmar) |
| Ruta en el VPS | `/var/www/hseq` |
| Contenedores | `hseq_api` en el puerto **8003**, `hseq_db` (PostgreSQL), sin publicar el puerto de la base |
| Puertos ya ocupados | 8000 Privacia · 8001 y 9001 Centinela · 8002 Radar |
| Workflow | Copia de `Radar/.github/workflows/deploy.yml` cambiando la ruta destino |
| Secretos de GitHub | `VPS_HOST`, `VPS_USER`, `VPS_SSH_KEY`, igual que los otros repos |
| Entornos | DEV y PROD con `promote.sh`, como Centinela |

Nginx debe servir el frontend y reenviar `/api/` a la API en el mismo origen. El frontend hoy apunta por defecto a `http://localhost:8000`, así que hay que definir `window.HSEQ_API` o usar rutas relativas.

## 7. Piezas del ecosistema que podemos reutilizar

| Pieza | Dónde está | Para qué sirve en HSEQ Hub |
|---|---|---|
| **Bitácora inmutable con cadena SHA-256** | `Centinela/backend/app/models/bitacora.py` | Registrar cierres de hallazgos, auditorías y cambios de factores de emisión de forma verificable. Da valor probatorio ante una auditoría de certificación |
| **Migraciones con Alembic y `entrypoint.sh`** | `Centinela/backend/alembic`, `entrypoint.sh` | Hoy HSEQ Hub usa `create_all`: cualquier cambio de esquema rompe una base ya creada (nos pasó al agregar `pais`). El entrypoint de Centinela ya maneja el caso de bases existentes |
| **Row-Level Security en PostgreSQL** | `DataCompliance/backend/rls_setup.sql` y `rls_teardown.sql` | Segunda barrera de aislamiento entre empresas si una ruta olvida filtrar por `empresa_id` |
| **Motor de marcos de cumplimiento** | `Radar/backend/app/frameworks` | Medir madurez por cláusula (ISO 45001, 14001, 9001) con el gráfico de araña. Y permite ofrecer un **sistema integrado ISO 27001 + HSEQ**, porque Radar ya trae ISO 27001 e ISO 42001 |
| **Notificaciones por correo y Slack** | `DataCompliance/backend/app/services/notificaciones.py` | Agregar Slack y plantillas HTML a las alertas, que hoy son correo de texto plano |
| **Timers con vencimiento legal** | Scheduler de Centinela | Referencia para alertas por plazo regulatorio, como el reporte de accidentes graves a la autoridad |
| **Generador de propuestas** | `generar_propuesta_pentest.py`, módulo de propuestas de CiberBlindaje | Producir la propuesta comercial de HSEQ Hub con el mismo formato |
| **Página de producto** | `Andrema/producto/` | Agregar `hseq.html` junto a Privacia, Centinela y Radar |
| **Checklists de normativa** | `CheckList Ley 21719.xlsx`, `CheckList Ley Marco 21663.xlsx` | Plantilla de formato para los checklists de Perú y Chile |
| **Lecciones de seguridad** | `ANALISIS_SEGURIDAD.md` | Evitar repetir hallazgos previos, como contraseñas por defecto en compose |

## 8. Brechas conocidas antes de producción

Estas son limitaciones reales del código actual, ordenadas por prioridad.

| # | Brecha | Riesgo | Solución propuesta |
|---|---|---|---|
| 1 | Sin migraciones de base de datos | Alto | Adoptar Alembic con el `entrypoint.sh` de Centinela |
| 2 | El registro de empresas es abierto y sin límite de intentos; el login tampoco limita intentos | Alto | Límite de intentos (por IP y por cuenta), captcha o registro por invitación |
| 3 | El bucle de alertas corre dentro de la API: con más de un worker se duplicarían los correos | Medio | Un solo worker, o un contenedor separado para alertas, o bloqueo en base de datos |
| 4 | El código de hallazgo (`HAL-AAAA-NNNN`) se calcula con un conteo. Dos altas simultáneas pueden chocar con la restricción única | Medio | Secuencia por empresa o reintento ante conflicto |
| 5 | El token JWT vive en `sessionStorage` y no hay cabecera CSP | Medio | CSP estricta en Nginx, o cookie `HttpOnly` con `SameSite` |
| 6 | Sin RLS ni bitácora inmutable | Medio | Reutilizar las piezas de la sección 7 |
| 7 | `/demo/cargar` está disponible en producción (solo en cuentas vacías, solo admin) | Bajo | Deshabilitar cuando `ENV=production` |
| 8 | Sin evidencias adjuntas (fotos, PDF) ni informes PDF | Producto | Almacenamiento de objetos (S3 o volumen) y generación de PDF |
| 9 | Sin respaldos definidos para la base de HSEQ | Alto | Agregar la base al cron de respaldos del VPS |
| 10 | Factores de emisión referenciales | Cumplimiento | Cargar factores oficiales por país y año, con fuente |

## 9. Hoja de ruta sugerida

1. **Producción mínima:** brechas 1, 2, 3, 5, 9 y el despliegue de la sección 6.
2. **Confianza de auditoría:** bitácora inmutable, RLS y adjuntos de evidencia.
3. **Producto:** informe PDF de auditoría y de sostenibilidad, inspecciones móviles sin conexión, matriz de madurez por cláusula con el motor de Radar.
4. **Escala:** alcance 3 completo, integración con ISO 27001 (Radar) y panel multiempresa para consultoras.
