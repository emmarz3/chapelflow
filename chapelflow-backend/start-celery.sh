#!/bin/sh
set -eu

mode="${1:-worker}"
attempt=0
while ! python manage.py migrate --check >/dev/null 2>&1; do
    attempt=$((attempt + 1))
    if [ "$attempt" -ge 60 ]; then
        echo "Database migrations were not ready after 5 minutes; refusing to start Celery." >&2
        exit 1
    fi
    sleep 5
done

case "$mode" in
    worker)
        exec celery -A config worker --loglevel=INFO --concurrency=2 --max-tasks-per-child=100
        ;;
    beat)
        exec celery -A config beat --loglevel=INFO --schedule=/tmp/celerybeat-schedule
        ;;
    *)
        echo "Usage: $0 {worker|beat}" >&2
        exit 64
        ;;
esac
