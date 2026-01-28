"""
Celery configuration for timetable_backend project.
"""
import os
from celery import Celery

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'timetable_backend.settings')

app = Celery('timetable_backend')
app.config_from_object('django.conf:settings', namespace='CELERY')
app.autodiscover_tasks()
