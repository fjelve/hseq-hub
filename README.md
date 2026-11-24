# HSEQ Hub

SaaS multiempresa de gestión HSEQ para **minería e industria**. Automatiza el ciclo
auditoría → hallazgo → acción correctiva (CAPA) → verificación → cierre.

## MVP incluido
- Registro de empresa (tenant) y usuarios con roles `admin`, `auditor`, `responsable`.
- Checklists de partida: ISO 45001/14001/9001 (riesgos críticos, relaves, planta) y normativa por país. Chile: DS 132, Ley 16.744/DS 594, DS 248/Ley 20.551. Perú: DS 024-2016-EM, Ley 29783, DS 040-2014-EM/Ley 28090. Cada empresa ve solo los de su país.
- Al cerrar una auditoría: puntaje de cumplimiento y un hallazgo automático por cada "no cumple", con plazo según severidad (crítica 7 d, alta 15 d, media 30 d, baja 60 d).
- CAPA: causa raíz, acciones con evidencia, cierre solo con acciones completas y verificación de eficacia.
- Alertas automáticas por correo de hallazgos por vencer y vencidos (tarea periódica).
- Incidentes con índices de frecuencia y severidad, requisitos legales con vencimientos y alertas.
- Sostenibilidad: huella de carbono (alcance 1, 2 y 3 parcial) con factores editables, metas de reducción con seguimiento, indicadores sociales e índice GRI/NIIF S2 exportable a CSV.
- Checklists de sostenibilidad: GISTM, ICMM, ISO 14064, ISO 50001, NIIF S1/S2, comunidades, Ley 21.455/REP (Chile) y Ley 30754/DL 1278 (Perú).
- Bitácora de auditoría inmutable (cadena SHA-256 por empresa, con disparadores que bloquean UPDATE y DELETE) y verificación de integridad.
- Acceso solo por invitación: el superadmin crea las empresas y sus administradores, que deben cambiar la contraseña inicial al ingresar.
- Límite de intentos en login y en el alta de empresas. Migraciones con Alembic.
- Dashboard de KPIs. Aislamiento de datos por empresa.

Los checklists son un punto de partida resumido. Cada cliente debe validarlos contra su sistema de gestión y la normativa local vigente.

## Ejecutar con Docker
```
cp .env.example .env   # completa DB_PASSWORD y SECRET_KEY
docker compose up --build
```
App y API en el mismo origen: http://localhost:8003 · Documentación: http://localhost:8003/docs
Despliegue en el VPS: ver `DEPLOY.md`. Arquitectura: ver `ARQUITECTURA.md`.

## Desarrollo y pruebas
```
cd backend
python -m venv .venv && .venv\Scripts\pip install -r requirements.txt
.venv\Scripts\python -m pytest
.venv\Scripts\alembic upgrade head          # crea el esquema (SQLite local)
.venv\Scripts\uvicorn app.main:app --reload # app en http://localhost:8000
```

## Hoja de ruta
Inspecciones móviles offline, evidencias adjuntas, informes PDF, alcance 3 completo, IA para causa raíz.

Los factores de emisión incluidos son referenciales. Cada empresa debe reemplazarlos por el factor oficial vigente antes de reportar.
