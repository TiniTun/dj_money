#!/bin/sh
# One-time setup for push-to-deploy from GitHub Actions (.github/workflows/deploy.yml):
#   Artifact Registry  - images built in CI, the VM only pulls them
#   Secret Manager     - the production .env, copied once from the VM
#   Workload Identity  - GitHub gets short-lived credentials, no service account keys anywhere
#   IAP + OS Login     - CI reaches the VM over SSH without keys or a public SSH port
# Safe to re-run: existing resources are kept.
# Usage: PROJECT_ID=dj-money-d4ee ./deploy/gcp/setup-cicd.sh
set -eu

: "${PROJECT_ID:?}"
GITHUB_REPO_ID=${GITHUB_REPO_ID:-636870491} # TiniTun/dj_money; the id survives renames and can't be re-registered
REGION=australia-southeast1
ZONE=australia-southeast1-b
VM=dj-money-vm
VM_SA=dj-money-vm@$PROJECT_ID.iam.gserviceaccount.com
DEPLOY_SA=github-deploy@$PROJECT_ID.iam.gserviceaccount.com
export CLOUDSDK_CORE_PROJECT="$PROJECT_ID"
PROJECT_NUMBER=$(gcloud projects describe "$PROJECT_ID" --format='value(projectNumber)')

gcloud services enable artifactregistry.googleapis.com secretmanager.googleapis.com \
  iamcredentials.googleapis.com sts.googleapis.com iap.googleapis.com oslogin.googleapis.com

# --- Artifact Registry: keep the 10 newest images for rollbacks, drop the rest after 30 days
gcloud artifacts repositories describe dj-money --location="$REGION" >/dev/null 2>&1 ||
  gcloud artifacts repositories create dj-money --repository-format=docker --location="$REGION"
cat > /tmp/dj-money-cleanup.json <<'EOF'
[
  {"name": "keep-recent", "action": {"type": "Keep"}, "mostRecentVersions": {"keepCount": 10}},
  {"name": "delete-old", "action": {"type": "Delete"}, "condition": {"tagState": "ANY", "olderThan": "30d"}}
]
EOF
gcloud artifacts repositories set-cleanup-policies dj-money --location="$REGION" \
  --policy=/tmp/dj-money-cleanup.json --no-dry-run
gcloud artifacts repositories add-iam-policy-binding dj-money --location="$REGION" \
  --member="serviceAccount:$VM_SA" --role=roles/artifactregistry.reader

# --- Secret Manager: the first version is the .env that runs in production right now.
# It is piped straight from the VM, so it never touches this machine's disk.
gcloud secrets describe dj-money-env >/dev/null 2>&1 ||
  gcloud secrets create dj-money-env --replication-policy=user-managed --locations="$REGION"
if [ -z "$(gcloud secrets versions list dj-money-env --limit=1 --format='value(name)')" ]; then
  gcloud compute ssh "$VM" --zone="$ZONE" --command='sudo cat /opt/dj_money/.env' |
    gcloud secrets versions add dj-money-env --data-file=-
fi
gcloud secrets add-iam-policy-binding dj-money-env \
  --member="serviceAccount:$VM_SA" --role=roles/secretmanager.secretAccessor

# --- Identity for GitHub Actions: only workflows on main of this repository may impersonate it
gcloud iam service-accounts describe "$DEPLOY_SA" >/dev/null 2>&1 ||
  gcloud iam service-accounts create github-deploy --display-name="GitHub Actions deploy"
gcloud iam workload-identity-pools describe github --location=global >/dev/null 2>&1 ||
  gcloud iam workload-identity-pools create github --location=global --display-name="GitHub Actions"
gcloud iam workload-identity-pools providers describe dj-money --location=global --workload-identity-pool=github >/dev/null 2>&1 ||
  gcloud iam workload-identity-pools providers create-oidc dj-money --location=global \
    --workload-identity-pool=github --issuer-uri=https://token.actions.githubusercontent.com \
    --attribute-mapping=google.subject=assertion.sub,attribute.repository_id=assertion.repository_id,attribute.ref=assertion.ref \
    --attribute-condition="assertion.repository_id=='$GITHUB_REPO_ID' && assertion.ref=='refs/heads/main'"
gcloud iam service-accounts add-iam-policy-binding "$DEPLOY_SA" --role=roles/iam.workloadIdentityUser \
  --member="principalSet://iam.googleapis.com/projects/$PROJECT_NUMBER/locations/global/workloadIdentityPools/github/attribute.repository_id/$GITHUB_REPO_ID"

# What the deploy identity may do: push images, open an IAP tunnel, and log in to this one VM with sudo
gcloud artifacts repositories add-iam-policy-binding dj-money --location="$REGION" \
  --member="serviceAccount:$DEPLOY_SA" --role=roles/artifactregistry.writer
gcloud projects add-iam-policy-binding "$PROJECT_ID" --condition=None \
  --member="serviceAccount:$DEPLOY_SA" --role=roles/iap.tunnelResourceAccessor
gcloud projects add-iam-policy-binding "$PROJECT_ID" --condition=None \
  --member="serviceAccount:$DEPLOY_SA" --role=roles/compute.viewer
gcloud compute instances add-iam-policy-binding "$VM" --zone="$ZONE" \
  --member="serviceAccount:$DEPLOY_SA" --role=roles/compute.osAdminLogin
# OS Login on a VM with an attached service account also requires acting as that account
gcloud iam service-accounts add-iam-policy-binding "$VM_SA" \
  --member="serviceAccount:$DEPLOY_SA" --role=roles/iam.serviceAccountUser

# --- VM access: OS Login (IAM decides who gets in) and SSH from Google's IAP range only
gcloud compute instances add-metadata "$VM" --zone="$ZONE" --metadata=enable-oslogin=TRUE
gcloud compute firewall-rules describe allow-iap-ssh >/dev/null 2>&1 ||
  gcloud compute firewall-rules create allow-iap-ssh --network=default \
    --allow=tcp:22 --source-ranges=35.235.240.0/20

echo "Workload identity provider: projects/$PROJECT_NUMBER/locations/global/workloadIdentityPools/github/providers/dj-money"
echo "Deploy service account:     $DEPLOY_SA"
echo "SSH is still open to the internet via default-allow-ssh. Once deploys work, close it with:"
echo "  gcloud compute firewall-rules delete default-allow-ssh default-allow-rdp --project=$PROJECT_ID"
echo "and connect yourself with: gcloud compute ssh $VM --zone=$ZONE --tunnel-through-iap"
