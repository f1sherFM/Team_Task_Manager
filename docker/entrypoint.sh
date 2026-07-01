#!/usr/bin/env sh
set -eu

python - <<'PY'
import os
import time

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "team_task_manager.settings")

import django
from django.db import connection
from django.db.utils import OperationalError

django.setup()

max_attempts = int(os.getenv("DB_WAIT_ATTEMPTS", "30"))
delay_seconds = float(os.getenv("DB_WAIT_DELAY", "1"))

for attempt in range(1, max_attempts + 1):
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
        break
    except OperationalError:
        if attempt == max_attempts:
            raise
        time.sleep(delay_seconds)
PY

python manage.py migrate --noinput
python manage.py collectstatic --noinput

exec python -m gunicorn team_task_manager.asgi:application -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:${PORT:-8000} --workers ${WEB_CONCURRENCY:-3}
