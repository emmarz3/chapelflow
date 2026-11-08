#!/bin/sh
set -eu

# The live Render service starts this script directly from the Dockerfile.
# Apply migrations here so newly deployed model changes are present before
# Gunicorn begins accepting API requests.
python manage.py migrate --noinput

exec gunicorn config.wsgi:application --bind 0.0.0.0:${PORT:-10000} --workers 1 --threads 4 --timeout 120
