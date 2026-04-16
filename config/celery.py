import os
from pathlib import Path

# Load .env before Django settings (same as manage.py) so Celery workers see RESEND_API_KEY, etc.
try:
    from dotenv import load_dotenv

    load_dotenv(Path(__file__).resolve().parent.parent / '.env')
except ImportError:
    pass

from celery import Celery

# Must match the Django settings used by the web app. For production workers/beat, set explicitly, e.g.:
#   export DJANGO_SETTINGS_MODULE=config.settings.production
# If unset, development settings are used (same default as manage.py).
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.development')

app = Celery('invoiceflow')

# Using a string here means the worker doesn't have to serialize
# the configuration object to child processes.
# - namespace='CELERY' means all celery-related configuration keys
#   should have a `CELERY_` prefix.
app.config_from_object('django.conf:settings', namespace='CELERY')

# Load task modules from all registered Django apps.
app.autodiscover_tasks()


@app.task(bind=True, ignore_result=True)
def debug_task(self):
    print(f'Request: {self.request!r}')
