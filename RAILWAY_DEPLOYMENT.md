# Deploying the ChapelFlow backend on Railway

Create an API service from this repository with root directory `chapelflow-backend`. Railway will detect its Dockerfile. Set the service's start command to `/app/start-railway.sh`, pre-deploy command to `/app/release-railway.sh`, and healthcheck path to `/health/`. The pre-deploy command runs migrations and seeds role permissions before the API starts. It does not create accounts or reset passwords.

Set `DJANGO_SETTINGS_MODULE=config.settings.railway` and configure these service variables in Railway:

- `SECRET_KEY`: a strong, persistent secret.
- `DATABASE_URL`: the intended PostgreSQL database connection URL.
- `REDIS_URL`: the intended Redis connection URL for Celery.
- `ALLOWED_HOSTS`: comma-separated public API hostname(s), without scheme or port.
- `CORS_ALLOWED_ORIGINS` and `CSRF_TRUSTED_ORIGINS`: comma-separated HTTPS frontend origins.
- `PUBLIC_BACKEND_URL`: the public HTTPS API origin.
- Storage provider and credentials, SMTP settings, and payment settings for enabled features, as defined in `chapelflow-backend/config/settings/base.py`.

Use durable private storage for uploads and reports. A container's local filesystem is not a production backup or durable shared media store. Preserve the existing database and media when migrating; do not point the service at a new empty database expecting existing accounts and records to appear.

Run Celery worker and beat as separate Railway services using the same image and required shared variables. Set their start commands to `/app/start-celery.sh worker` and `/app/start-celery.sh beat`; run only one beat instance. Configure the pre-deploy migration command on the API service only.

On a new, empty installation, run the project's role and chapel bootstrap commands as an intentional one-off operation after reviewing their effects. `release.sh` also invokes `bootstrap_super_admin`, which can reset an existing administrator password to the configured environment value; do not run it automatically on an existing database.

After deployment, verify `/health/`, `/readiness/`, login, attendance, uploads, email and payments against the deployed system. Point the frontend API proxy to the verified Railway API origin only after it is ready. Confirm backups and a restore before launch.
