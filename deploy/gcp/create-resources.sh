#!/bin/sh
# Creates the GCP resources for dj_money: project, Cloud SQL, backup bucket, static IP, firewall, VM.
# Usage: PROJECT_ID=dj-money-xxxx BILLING_ACCOUNT=XXXXXX-XXXXXX-XXXXXX DB_PASSWORD=... ./deploy/gcp/create-resources.sh
set -eu

: "${PROJECT_ID:?}" "${BILLING_ACCOUNT:?}" "${DB_PASSWORD:?}"
REGION=australia-southeast1
ZONE=australia-southeast1-b
SQL_INSTANCE=dj-money-pg
VM=dj-money-vm
SA=dj-money-vm@$PROJECT_ID.iam.gserviceaccount.com
BUCKET=$PROJECT_ID-backups

gcloud projects create "$PROJECT_ID" --name="dj-money"
gcloud billing projects link "$PROJECT_ID" --billing-account="$BILLING_ACCOUNT"
# Scope the project to this script instead of changing the global gcloud config
export CLOUDSDK_CORE_PROJECT="$PROJECT_ID"
gcloud services enable compute.googleapis.com sqladmin.googleapis.com storage.googleapis.com

# Service account for the VM: may connect to Cloud SQL and write (not delete) backups
gcloud iam service-accounts create dj-money-vm --display-name="dj_money VM"
gcloud projects add-iam-policy-binding "$PROJECT_ID" --member="serviceAccount:$SA" --role=roles/cloudsql.client --condition=None

# Cloud SQL: automated daily backups at 03:00 Brisbane (17:00 UTC), 14 kept, 7 days of point-in-time recovery
gcloud sql instances create "$SQL_INSTANCE" \
  --database-version=POSTGRES_17 --edition=ENTERPRISE --tier=db-f1-micro \
  --region="$REGION" --availability-type=zonal \
  --storage-type=SSD --storage-size=10 --storage-auto-increase \
  --backup-start-time=17:00 --retained-backups-count=14 \
  --enable-point-in-time-recovery --retained-transaction-log-days=7 \
  --deletion-protection
gcloud sql databases create dj_money --instance="$SQL_INSTANCE"
gcloud sql users create dj_money --instance="$SQL_INSTANCE" --password="$DB_PASSWORD"

# Off-instance logical backups survive even if the Cloud SQL instance is deleted
gcloud storage buckets create "gs://$BUCKET" --location="$REGION" \
  --uniform-bucket-level-access --public-access-prevention
printf '{"rule":[{"action":{"type":"Delete"},"condition":{"age":90}}]}' > /tmp/dj-money-lifecycle.json
gcloud storage buckets update "gs://$BUCKET" --lifecycle-file=/tmp/dj-money-lifecycle.json
gcloud storage buckets add-iam-policy-binding "gs://$BUCKET" --member="serviceAccount:$SA" --role=roles/storage.objectCreator
# gcloud storage cp checks the destination object first, so the VM also needs read access
gcloud storage buckets add-iam-policy-binding "gs://$BUCKET" --member="serviceAccount:$SA" --role=roles/storage.objectViewer

# Uploaded bank statements. The app talks S3 to it with an HMAC key of a dedicated service account
STATEMENTS=$PROJECT_ID-statements
STORAGE_SA=dj-money-storage@$PROJECT_ID.iam.gserviceaccount.com
gcloud storage buckets create "gs://$STATEMENTS" --location="$REGION" \
  --uniform-bucket-level-access --public-access-prevention
gcloud iam service-accounts create dj-money-storage --display-name="dj_money app storage (HMAC)"
gcloud storage buckets add-iam-policy-binding "gs://$STATEMENTS" --member="serviceAccount:$STORAGE_SA" --role=roles/storage.objectAdmin
echo "Create the app's HMAC key with: gcloud storage hmac create $STORAGE_SA (the secret is shown once)"

gcloud compute addresses create dj-money-ip --region="$REGION"
gcloud compute firewall-rules create dj-money-web --network=default \
  --allow=tcp:80,tcp:443 --target-tags=dj-money-web

gcloud compute instances create "$VM" --zone="$ZONE" --machine-type=e2-small \
  --image-family=debian-12 --image-project=debian-cloud \
  --boot-disk-size=20GB --boot-disk-type=pd-balanced \
  --address=dj-money-ip --tags=dj-money-web \
  --service-account="$SA" --scopes=cloud-platform

echo "Static IP: $(gcloud compute addresses describe dj-money-ip --region="$REGION" --format='value(address)')"
echo "Cloud SQL: $(gcloud sql instances describe "$SQL_INSTANCE" --format='value(connectionName)')"
