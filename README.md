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

## Project Structure
- `money/` — main Django app (models, views, parsers, tasks)
- `blog/` — additional apps
- `media/` — uploaded files and statements
- `Dockerfile`, `docker-compose.yml` — containerization

## Contacts & Support
For questions and suggestions, create an issue or email the address listed in the project profile.