#!/bin/bash
# Runs a one-off Django management command in a fresh container of the deployed image.
# Called by .github/workflows/manage.yml; works the same when run by hand on the VM as root.
# Usage: deploy/gcp/manage.sh backfill_exchange_rates --start 2021-01-01
set -euo pipefail

[ $# -gt 0 ] || { echo 'usage: manage.sh <command> [args...]' >&2; exit 2; }
cd "$(dirname "$0")/../.."

docker compose -f docker-compose.gcp.yml run --rm -T web python manage.py "$@"
