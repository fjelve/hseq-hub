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
5. **Respaldos:** ya instalados (ver más abajo).

## Acceso y usuarios

El registro público está **cerrado**: nadie puede crear una empresa por su cuenta. El flujo es:
1. El **superadmin** (rol de plataforma) crea la empresa y su administrador desde la pantalla *Empresas*, con una contraseña inicial.
2. El cliente ingresa con esa contraseña y el sistema le obliga a cambiarla antes de usar nada.
3. El administrador de la empresa crea a sus propios usuarios (también con cambio obligatorio de contraseña).

Crear el superadmin, una sola vez, en el VPS:
```bash
docker exec -it hseq_api python -m app.crear_superadmin --email tu@correo.com --nombre "Tu Nombre"
```
Si se pasa la contraseña con `-e SUPERADMIN_PASSWORD=...` no se pide por teclado. El superadmin no ve ni modifica los datos de las empresas: solo las crea, activa o desactiva y restablece contraseñas.

## Respaldos

`deploy/hseq_backup.sh` está instalado en `/usr/local/bin/` y se ejecuta todos los días a las 03:30 (`/etc/cron.d/hseq-backup`). Guarda un volcado comprimido en `/var/backups/hseq/`, comprueba que se pueda leer y borra los de más de 14 días. Registro en `/var/log/hseq_backup.log`. Los respaldos están en el mismo disco del VPS: conviene copiarlos fuera.

Restaurar en una base temporal para comprobarlo:
```bash
docker exec hseq_db psql -U hseq -d postgres -c "CREATE DATABASE hseq_restore_test"
gunzip -c /var/backups/hseq/hseq_AAAA-MM-DD_HHMM.sql.gz | docker exec -i hseq_db psql -U hseq -d hseq_restore_test -v ON_ERROR_STOP=1
docker exec hseq_db psql -U hseq -d postgres -c "DROP DATABASE hseq_restore_test"
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
| `REGISTRO_PUBLICO` | no | `false` por defecto: solo el superadmin crea empresas. Con `true` cualquiera puede registrarse (límite de 5 por hora y por IP) |
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
