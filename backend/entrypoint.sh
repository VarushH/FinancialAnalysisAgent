#!/bin/sh
set -e

echo "Applying database migrations..."
python manage.py migrate

echo "Starting server..."
exec daphne -b 0.0.0.0 -p 8000 config.asgi:application
