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
                         │  hseq.andrema.tech → :8003 │
                         └──────────────┬─────────────┘
                                        │ 127.0.0.1:8003
                         ┌──────────────▼─────────────────────┐
                         │ hseq_api (FastAPI, 1 worker)       │
                         │  • /            frontend (HTML+JS) │
                         │  • /api/v1      REST, JWT y roles  │
                         │  • límite de intentos, bitácora    │
                         │  • bucle de alertas                │
                         └───┬───────────────────────┬────────┘
                             │                       │
                  ┌──────────▼───┐            ┌──────▼───────┐
                  │ hseq_db      │            │ SMTP (correo)│
                  │ PostgreSQL 16│            └──────────────┘
                  └──────────────┘
```

## 2. Componentes del backend (implementado)

```
backend/app/
├── main.py            Arranque: crea tablas, siembra checklists, lanza el bucle de alertas
├── config.py          Variables de entorno (falla en producción si SECRET_KEY es la de ejemplo)
├── database.py        Motor SQLAlchemy y sesión por request
├── auth.py            bcrypt, JWT HS256 (8 h), dependencia de rol
├── ratelimit.py       límite de intentos en memoria (ventana deslizante)
├── models.py          16 tablas (sección 3)
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
│   ├── bitacora.py      consulta y verificación de la bitácora
│   ├── dashboard.py     indicadores consolidados
│   └── demo.py          carga de datos de ejemplo (solo cuentas vacías)
└── services/
    ├── alertas.py        revisión periódica de vencimientos y envío de correo
    ├── bitacora.py       cadena de hashes SHA-256 y verificación
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
| Bitácora | `/bitacora`, `/bitacora/verificar` | solo lectura; admin y auditor |
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
                   ├── EntradaBitacora (cadena de hashes, solo escritura)
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
| Límite de intentos | Login: 5 fallos por IP y correo, y 30 por IP, en 15 min (429 con `Retry-After`). Alta de empresas: 5 por hora y por IP. Las cabeceras de proxy solo se creen con `TRUST_PROXY=true`. El tiempo de respuesta no revela qué correos existen |
| Bitácora inmutable | Cadena SHA-256 por empresa. Disparadores en PostgreSQL y SQLite impiden UPDATE y DELETE. `GET /bitacora/verificar` detecta alteraciones y entradas faltantes en medio de la cadena |
| Migraciones | Alembic con migración inicial `0001`. El contenedor migra al arrancar y adopta bases existentes sin recrearlas |

## 6. Despliegue (preparado, sin probar en el VPS)

```
Local (Kiro) ─► git push ─► GitHub Action: pruebas ─► scp + ssh (clave ED25519) ─► /var/www/hseq ─► docker compose up -d --build
                                                                                         └─► entrypoint: alembic upgrade head ─► uvicorn
```

| Elemento | Estado |
|---|---|
| Workflow `.github/workflows/deploy.yml` | Escrito. Corre las pruebas y solo despliega si pasan |
| `docker-compose.yml` | `hseq_api` publicado solo en `127.0.0.1:8003` y `hseq_db` sin puerto expuesto. Valida con `docker compose config` |
| Frontend | Lo sirve la propia API en el mismo origen (como Centinela y Radar), sin CORS ni URL configurable |
| Nginx | `deploy/hseq.andrema.tech.conf` (el dominio es una propuesta) |
| Pasos manuales | DNS, archivo `.env` en el VPS, Nginx y respaldos. Ver `DEPLOY.md` |
| Puertos ya ocupados | 8000 Privacia · 8001 y 9001 Centinela · 8002 Radar |
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

| # | Brecha | Estado |
|---|---|---|
| 1 | Sin migraciones de base de datos | **Resuelta.** Alembic con migración inicial y adopción de bases existentes |
| 2 | Registro abierto y sin límite de intentos | **Parcial.** Hay límite de intentos en login y alta de empresas. Falta captcha o registro por invitación |
| 3 | Alertas duplicadas con varios workers | **Mitigada.** El contenedor fija 1 worker. Si se escala, mover las alertas a un proceso aparte |
| 4 | El código `HAL-AAAA-NNNN` se calcula con un conteo y dos altas simultáneas pueden chocar | Abierta. Usar una secuencia por empresa o reintentar ante conflicto |
| 5 | Token JWT en `sessionStorage` y sin cabecera CSP | Abierta. Definir CSP en Nginx o usar cookie `HttpOnly` |
| 6 | Sin bitácora inmutable ni RLS | **Bitácora resuelta. RLS abierta** (reutilizar `rls_setup.sql` de Privacia) |
| 7 | `/demo/cargar` disponible en producción | Abierta (solo admin y solo cuentas vacías). Deshabilitar con `ENV=production` |
| 8 | Sin evidencias adjuntas ni informes PDF | Abierta (producto) |
| 9 | Sin respaldos de la base de HSEQ | Documentado en `DEPLOY.md`; falta agregarlo al cron del VPS |
| 10 | Factores de emisión referenciales | Abierta. Cargar factores oficiales por país y año |
| 11 | Despliegue no probado con Docker y PostgreSQL | Abierta. Las pruebas corren sobre SQLite. Los disparadores de la bitácora para PostgreSQL y el bloqueo `pg_advisory_xact_lock` no se ejecutaron |
| 12 | La bitácora no detecta el borrado de las últimas entradas | Abierta. Guardar fuera del sistema el último hash y el número de entradas, por ejemplo en el informe mensual |

## 9. Hoja de ruta sugerida

1. **Primer despliegue:** probar `docker compose` con PostgreSQL en local, cerrar los pasos manuales de `DEPLOY.md` y las brechas 5, 7 y 9.
2. **Confianza de auditoría:** RLS y adjuntos de evidencia.
3. **Producto:** informe PDF de auditoría y de sostenibilidad, inspecciones móviles sin conexión, matriz de madurez por cláusula con el motor de Radar.
4. **Escala:** alcance 3 completo, integración con ISO 27001 (Radar) y panel multiempresa para consultoras.