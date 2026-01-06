"""
Celery tasks for analytics.
"""
import logging
from datetime import timedelta

from celery import shared_task
from django.utils import timezone

logger = logging.getLogger(__name__)


@shared_task(queue='maintenance')
def cleanup_old_logs(days_to_keep: int = 90):
    """
    Clean up old notification logs.
    Runs weekly via Celery Beat (configured in config/celery.py).

    Args:
        days_to_keep: Number of days of logs to retain (default: 90)
    """
    from apps.notifications.models import NotificationLog

    cutoff_date = timezone.now() - timedelta(days=days_to_keep)

    deleted_count, _ = NotificationLog.objects.filter(
        created_at__lt=cutoff_date,
    ).delete()

    logger.info(f"Cleaned up {deleted_count} notification logs older than {days_to_keep} days")

    return {"deleted": deleted_count}


@shared_task(queue='maintenance')
def generate_daily_report():
    """
    Generate daily analytics report.
    Could be used to send summary emails or store metrics.
    """
    from apps.notifications.models import NotificationLog
    from apps.core.constants import NotificationStatus

    yesterday = timezone.now().date() - timedelta(days=1)
    start = timezone.make_aware(
        timezone.datetime.combine(yesterday, timezone.datetime.min.time())
    )
    end = start + timedelta(days=1)

    logs = NotificationLog.objects.filter(
        created_at__gte=start,
        created_at__lt=end,
    )

    report = {
        "date": yesterday.isoformat(),
        "total": logs.count(),
        "sent": logs.filter(status=NotificationStatus.SENT).count(),
        "delivered": logs.filter(status=NotificationStatus.DELIVERED).count(),
        "failed": logs.filter(status=NotificationStatus.FAILED).count(),
    }

    logger.info(f"Daily report for {yesterday}: {report}")

    return report
