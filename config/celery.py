"""
Celery configuration for Ambacar Notification Service.
"""
import os

from celery import Celery
from celery.schedules import crontab

# Set the default Django settings module for the 'celery' program.
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.production")

app = Celery("ambacar_notifications")

# Using a string here means the worker doesn't have to serialize
# the configuration object to child processes.
app.config_from_object("django.conf:settings", namespace="CELERY")

# Load task modules from all registered Django apps.
app.autodiscover_tasks()

# Periodic tasks (Celery Beat)
app.conf.beat_schedule = {
    # Check maintenance reminders daily at 8 AM Ecuador time
    "check-maintenance-reminders-daily": {
        "task": "apps.notifications.tasks.check_maintenance_reminders",
        "schedule": crontab(hour=8, minute=0),
        "options": {"queue": "maintenance"},
    },
    # Retry failed notifications every 15 minutes
    "retry-failed-notifications": {
        "task": "apps.notifications.tasks.retry_failed_notifications",
        "schedule": crontab(minute="*/15"),
        "options": {"queue": "notifications"},
    },
    # Clean old logs weekly (Sundays at midnight)
    "cleanup-old-notification-logs": {
        "task": "apps.analytics.tasks.cleanup_old_logs",
        "schedule": crontab(day_of_week="sunday", hour=0, minute=0),
        "options": {"queue": "maintenance"},
    },
}

# Task routing
app.conf.task_routes = {
    "apps.notifications.tasks.*": {"queue": "notifications"},
    "apps.analytics.tasks.*": {"queue": "maintenance"},
    "apps.synchronization.tasks.*": {"queue": "sync"},
}


@app.task(bind=True, ignore_result=True)
def debug_task(self):
    """Debug task for testing Celery connectivity."""
    print(f"Request: {self.request!r}")
