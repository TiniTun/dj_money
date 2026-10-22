#!/bin/bash
# Daily logical backup of the Cloud SQL database to GCS, independent of Cloud SQL's own backups.
# pipefail: a failed pg_dump must not upload a truncated file as a successful backup
set -euo pipefail

cd "$(dirname "$0")/../.."
BUCKET=$(grep '^BACKUP_BUCKET=' .env | cut -d= -f2-)
STAMP=$(date +%Y-%m-%d)

docker compose -f docker-compose.gcp.yml run --rm -T dbtools sh -c 'pg_dump -Fc "$DATABASE_URL"' \
  | gcloud storage cp - "gs://$BUCKET/daily/dj_money-$STAMP.dump"
echo "$(date -Is) backup ok: gs://$BUCKET/daily/dj_money-$STAMP.dump"
