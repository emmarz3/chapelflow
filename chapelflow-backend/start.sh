#!/bin/sh
set -e

python manage.py migrate --noinput
python manage.py shell -c "from scripts.seed_roles import seed_roles; seed_roles()"
python manage.py bootstrap_super_admin
exec gunicorn config.wsgi:application --bind 0.0.0.0:${PORT:-10000} --workers 1 --threads 4 --timeout 120
