# HSEQ Hub

SaaS multiempresa de gestión HSEQ para **minería e industria**. Automatiza el ciclo
auditoría → hallazgo → acción correctiva (CAPA) → verificación → cierre.

## MVP incluido
- Registro de empresa (tenant) y usuarios con roles `admin`, `auditor`, `responsable`.
- Checklists de partida: riesgos críticos en minería, ambiental/relaves, seguridad en planta, ISO 9001, ISO 14001.
- Al cerrar una auditoría: puntaje de cumplimiento y un hallazgo automático por cada "no cumple", con plazo según severidad (crítica 7 d, alta 15 d, media 30 d, baja 60 d).
- CAPA: causa raíz, acciones con evidencia, cierre solo con acciones completas y verificación de eficacia.
- Alertas automáticas por correo de hallazgos por vencer y vencidos (tarea periódica).
- Dashboard de KPIs. Aislamiento de datos por empresa.

Los checklists son un punto de partida resumido. Cada cliente debe validarlos contra su sistema de gestión y la normativa local vigente.

## Ejecutar con Docker
```
cp .env.example .env   # completa DB_PASSWORD y SECRET_KEY
docker compose up --build
```
App: http://localhost:8080 · API/Docs: http://localhost:8000/docs

## Desarrollo y pruebas
```
cd backend
python -m venv .venv && .venv\Scripts\pip install -r requirements.txt
.venv\Scripts\python -m pytest
.venv\Scripts\uvicorn app.main:app --reload
```

## Hoja de ruta
Inspecciones móviles offline, matriz legal, huella de carbono/ESG, informes PDF, IA para causa raíz.
