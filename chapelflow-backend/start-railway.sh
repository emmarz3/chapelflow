#!/bin/sh
set -eu

# Railway mounts volumes as root. Drop privileges after making media writable.
if [ "$(id -u)" -eq 0 ]; then
    chown chapelflow:chapelflow /app/media
    exec su -s /bin/sh chapelflow -c "exec gunicorn config.wsgi:application --bind 0.0.0.0:${PORT:-10000} --workers 1 --threads 4 --timeout 120"
fi

exec gunicorn config.wsgi:application --bind "0.0.0.0:${PORT:-10000}" --workers 1 --threads 4 --timeout 120
