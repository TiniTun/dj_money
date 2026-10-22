#!/bin/bash
# Rolls out one image built by GitHub Actions. Runs as root on the VM, called over IAP SSH by
# .github/workflows/deploy.yml after it has checked out the same commit in /opt/dj_money.
# Usage: deploy/gcp/deploy.sh <git-sha>
set -euo pipefail

TAG=${1:?usage: deploy.sh <git-sha>}
cd "$(dirname "$0")/../.."

PROJECT_ID=$(curl -fsS -H 'Metadata-Flavor: Google' http://metadata.google.internal/computeMetadata/v1/project/project-id)
REGISTRY=australia-southeast1-docker.pkg.dev
APP_IMAGE=$REGISTRY/$PROJECT_ID/dj-money/app:$TAG
COMPOSE="docker compose -f docker-compose.gcp.yml"

# Config lives in Secret Manager; the image tag is pinned next to it so manual compose commands
# and backup.sh keep using the deployed image. If the secret can't be read the old .env stays.
umask 077
gcloud secrets versions access latest --secret=dj-money-env > .env.next
# Leading newline: the secret may not end with one
printf '\nAPP_IMAGE=%s\n' "$APP_IMAGE" >> .env.next
mv .env.next .env

gcloud auth configure-docker "$REGISTRY" --quiet
$COMPOSE pull web

# Migrate before the new code starts serving
$COMPOSE run --rm -T web python manage.py migrate --noinput
$COMPOSE up -d --remove-orphans
docker image prune -f

DOMAIN=$(grep '^DOMAIN=' .env | cut -d= -f2-)
curl -fsS -o /dev/null --retry 10 --retry-delay 3 --retry-all-errors "https://$DOMAIN/accounts/login/"
echo "$(date -Is) deployed $APP_IMAGE"
