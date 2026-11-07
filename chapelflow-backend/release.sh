#!/bin/sh
set -eu

python manage.py migrate --noinput
python manage.py shell -c "from scripts.seed_roles import seed_roles; seed_roles()"
python manage.py bootstrap_super_admin
python manage.py bootstrap_chapel
