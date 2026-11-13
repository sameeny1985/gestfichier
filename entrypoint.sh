#!/bin/sh
set -e

echo ">>> Running migrations..."
python manage.py migrate --noinput

echo ">>> Creating demo data (if needed)..."
python manage.py create_demo_data || echo "Demo data command failed or already exists"

echo ">>> Collecting static files..."
python manage.py collectstatic --noinput || true

echo ">>> Starting Gunicorn..."
exec gunicorn --bind 0.0.0.0:8000 --workers 2 config.wsgi:application
