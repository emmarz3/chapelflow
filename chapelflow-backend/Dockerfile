FROM python:3.12-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq-dev gcc curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
COPY start.sh /app/start.sh
COPY start-celery.sh /app/start-celery.sh
COPY release.sh /app/release.sh
RUN chmod +x /app/start.sh /app/start-celery.sh /app/release.sh
RUN python manage.py collectstatic --noinput


RUN useradd --create-home --shell /bin/bash chapelflow \
    && mkdir -p /app/media /app/staticfiles \
    && chown -R chapelflow:chapelflow /app
USER chapelflow

EXPOSE 10000

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD curl -f http://localhost:${PORT:-10000}/health/ || exit 1

CMD ["/app/start.sh"]

