# Despliegue de HSEQ Hub en el VPS

Patrón igual al de Radar y Centinela: GitHub Action → SCP → `docker compose up -d --build`.
Dominio y puerto son propuestas: `hseq.andrema.tech` y `127.0.0.1:8003`.

## Una sola vez

1. **DNS (Cloudflare):** registro `hseq` apuntando al VPS, con proxy activo.
2. **Carpeta y variables en el VPS:**
   ```bash
   mkdir -p /var/www/hseq && cd /var/www/hseq
   cp .env.example .env     # si aún no existe el código, crear el archivo a mano
   nano .env                # completar DB_PASSWORD y SECRET_KEY
   chmod 600 .env
   ```
   Generar la clave: `python3 -c "import secrets; print(secrets.token_urlsafe(48))"`.
   `DB_PASSWORD` y `SECRET_KEY` son obligatorios: sin ellos `docker compose` no arranca.
3. **Nginx** (ya instalado en el VPS): copiar `deploy/hseq.andrema.tech.conf` a `/etc/nginx/sites-available/`, enlazarlo en `sites-enabled/` y recargar (`nginx -t && systemctl reload nginx`).
4. **Secretos del repositorio en GitHub** (`VPS_HOST`, `VPS_USER`, `VPS_SSH_KEY`): los mismos que usan los otros repos.
5. **Respaldos:** agregar la base al cron de respaldos del VPS:
   ```bash
   docker exec hseq_db pg_dump -U hseq hseq | gzip > /var/backups/hseq_$(date +%F).sql.gz
   ```

## Cada despliegue

`git push` a `main` ejecuta el workflow `.github/workflows/deploy.yml`:
1. corre las pruebas (si fallan, no despliega);
2. copia el código a `/var/www/hseq`;
3. ejecuta `docker compose up -d --build` y comprueba `http://127.0.0.1:8003/health`.

Al iniciar, el contenedor aplica las migraciones de Alembic (`backend/entrypoint.sh`). Para cambiar el esquema:
```bash
cd backend
alembic revision --autogenerate -m "describe el cambio"
# revisar el archivo generado en alembic/versions/ antes de subirlo
```

## Variables

| Variable | Obligatoria | Descripción |
|---|---|---|
| `DB_PASSWORD` | sí | Contraseña de PostgreSQL |
| `SECRET_KEY` | sí | Clave para firmar los tokens. En producción la app no arranca con la de ejemplo |
| `ENV` | no | `production` por defecto en el compose |
| `TRUST_PROXY` | no | `true` por defecto. Hace que la API use la IP real que envían Cloudflare y Nginx para limitar intentos. **Ponerlo en `false` si el puerto de la API se expone directamente**, porque un atacante podría falsear su IP |
| `SMTP_*` | no | Correo para las alertas. Sin `SMTP_HOST` las alertas solo se escriben en el log |

## Verificación posterior

```bash
docker compose ps                      # api y db en estado healthy
curl -fsS http://127.0.0.1:8003/health
docker compose logs api | tail -20     # debe decir "Migraciones OK"
```

## Limitaciones conocidas

- La API corre con **un solo worker**: el bucle de alertas vive dentro del proceso y con más workers duplicaría los correos.
- El límite de intentos de login y de registro es en memoria. Tras reiniciar el contenedor se reinicia. Complementar con reglas de Cloudflare.
- Las pruebas automáticas corren sobre SQLite. El primer arranque sobre PostgreSQL se verificó en el VPS: migración `0001`, 17 tablas y disparador de la bitácora presentes.
- El sitio atiende en HTTP en el origen y Cloudflare termina el SSL (igual que Radar). Nginx solo acepta `CF-Connecting-IP` si la conexión llega desde un rango de Cloudflare; si Cloudflare cambia sus rangos (https://www.cloudflare.com/ips/), hay que actualizar `deploy/hseq.andrema.tech.conf`.
