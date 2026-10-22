# dj_money

**dj_money** is a system for collecting, aggregating, and analyzing financial data from various bank accounts. The project allows you to automatically upload statements, parse them, categorize transactions, and build personal finance analytics.

## Main Features
- Import statements from different banks (supports CSV, XLSX, and other formats)
- Automatic categorization of expenses and income
- Storage of transaction history and exchange rates
- Integration with cloud storage (e.g., Yandex S3)
- Asynchronous task processing (parsing, uploading, categorization)
- Web interface for management and statistics viewing

## Technologies
- **Python 3**
- **Django** — main backend framework
- **Celery** — asynchronous tasks (parsing, file upload, categorization)
- **Redis** — message broker for Celery
- **Docker** and **docker-compose** — containerization and easy launch
- **PostgreSQL** — database
- **boto3** — working with S3-compatible storage

## Quick Start (locally via Docker)

1. Clone the repository:
   ```bash
   git clone <repo_url>
   cd dj_money
   ```
2. Create a `.env` file with the required environment variables (`settings.py` for details).
3. Start the services (dev):
   ```bash
   docker-compose -f docker-compose.yml -f docker-compose.dev.yml up --build
   ```
4. To run Celery tasks, use:
   ```bash
   docker-compose -f docker-compose.yml -f docker-compose.dev.yml run --rm celery
   ```
5. The application will be available at http://localhost:8000

## Deployment (GCP)

Production is one GCE VM running `docker-compose.gcp.yml`, with Postgres in Cloud SQL.

- **Deploy:** push to `main`. GitHub Actions runs the tests, builds the image into Artifact Registry and rolls it out on the VM, migrations included (`.github/workflows/deploy.yml`).
- **Rollback:** re-run the `deploy` job of an older successful run.
- **One-off commands:** Actions → Manage → Run workflow, e.g. `backfill_exchange_rates --start 2021-01-01`.
- **Config:** the production `.env` lives in Secret Manager and is applied on the next deploy:
  ```bash
  gcloud secrets versions access latest --secret=dj-money-env --project=dj-money-d4ee > prod.env
  # edit prod.env, then
  gcloud secrets versions add dj-money-env --data-file=prod.env --project=dj-money-d4ee && rm prod.env
  ```
- **Shell on the VM:** `gcloud compute ssh dj-money-vm --zone=australia-southeast1-b --tunnel-through-iap`

First-time setup: `deploy/gcp/create-resources.sh` and `provision.sh` create the VM, then `deploy/gcp/setup-cicd.sh` connects it to GitHub Actions.

## Project Structure
- `money/` — main Django app (models, views, parsers, tasks)
- `blog/` — additional apps
- `media/` — uploaded files and statements
- `Dockerfile`, `docker-compose.yml` — containerization

## Contacts & Support
For questions and suggestions, create an issue or email the address listed in the project profile.