#!/bin/bash
# Respaldo diario de la base de HSEQ Hub (PostgreSQL en el contenedor hseq_db).
# Instalado en /usr/local/bin/hseq_backup.sh y programado en /etc/cron.d/hseq-backup.
# Guarda un volcado comprimido, comprueba que se pueda leer y borra los de más de 14 días.
set -euo pipefail

DIR=/var/backups/hseq
RETENCION_DIAS=14
ARCHIVO="$DIR/hseq_$(date +%F_%H%M).sql.gz"

umask 077
mkdir -p "$DIR"

docker exec hseq_db pg_dump -U hseq -d hseq --no-owner | gzip > "$ARCHIVO.tmp"

# Un volcado vacío o dañado no debe reemplazar un respaldo bueno ni contarse como respaldo.
if ! gzip -t "$ARCHIVO.tmp" || [ "$(stat -c %s "$ARCHIVO.tmp")" -lt 2000 ]; then
    rm -f "$ARCHIVO.tmp"
    echo "$(date '+%F %T') ERROR: el respaldo salió vacío o dañado" >&2
    exit 1
fi
mv "$ARCHIVO.tmp" "$ARCHIVO"
find "$DIR" -name 'hseq_*.sql.gz' -mtime +"$RETENCION_DIAS" -delete
echo "$(date '+%F %T') OK $ARCHIVO ($(du -h "$ARCHIVO" | cut -f1)), respaldos guardados: $(ls "$DIR"/hseq_*.sql.gz | wc -l)"
