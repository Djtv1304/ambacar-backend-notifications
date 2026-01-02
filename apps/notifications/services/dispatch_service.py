"""
Notification Dispatch Service.
Handles queueing, sending, and fallback logic.
"""
import logging
from datetime import timedelta
from typing import Any, Dict, List, Optional

from django.conf import settings
from django.utils import timezone

from apps.core.constants import NotificationChannel, NotificationStatus
from apps.notifications.models import NotificationLog, CustomerContactInfo

logger = logging.getLogger(__name__)


class DispatchService:
    """
    Service for queueing and dispatching notifications via Celery.
    Handles fallback logic and retry scheduling.
    """

    def __init__(self):
        self.fallback_delay_seconds = getattr(
            settings, "NOTIFICATION_SETTINGS", {}
        ).get("FALLBACK_DELAY_SECONDS", 600)  # 10 minutes default

    def queue_notification(
        self,
        channel: str,
        recipient: str,
        subject: Optional[str],
        body: str,
        event_type: str,
        customer_id: str,
        template_id: str,
        template_name: str,
        context: Dict[str, Any],
        correlation_id: str,
        priority_order: List[str],
        parent_log_id: Optional[str] = None,
        countdown: int = 0,
    ) -> NotificationLog:
        """
        Queue a notification for async sending via Celery.
        Creates a log entry and dispatches the task.

        Args:
            channel: Notification channel (email, whatsapp, push)
            recipient: Recipient address
            subject: Optional subject (for email)
            body: Rendered message body
            event_type: Type of event that triggered this
            customer_id: Customer identifier
            template_id: Template UUID
            template_name: Template name for reference
            context: Original context for potential retries
            correlation_id: Groups related notifications
            priority_order: Channel priority for fallback
            parent_log_id: Parent log if this is a fallback
            countdown: Delay in seconds before sending

        Returns:
            NotificationLog entry
        """
        # Create log entry
        log = NotificationLog.objects.create(
            event_type=event_type,
            channel=channel,
            recipient_id=customer_id,
            recipient_address=recipient,
            template_id=template_id,
            template_name=template_name,
            subject=subject,
            body_preview=body[:500] if body else None,
            status=NotificationStatus.QUEUED,
            context_data={
                "context": context,
                "priority_order": priority_order,
                "full_body": body,  # Store full body for retry
            },
            correlation_id=correlation_id,
            parent_log_id=parent_log_id,
        )

        # Import here to avoid circular imports
        from apps.notifications.tasks import send_notification_task

        # Queue Celery task
        send_notification_task.apply_async(
            args=[str(log.id)],
            countdown=countdown,
        )

        logger.info(
            f"Queued notification {log.id} via {channel} to {recipient}, "
            f"countdown={countdown}s"
        )

        return log

    def schedule_fallback(
        self,
        failed_log: NotificationLog,
    ) -> Optional[NotificationLog]:
        """
        Schedule a fallback notification on the next priority channel.
        Called when a notification fails after max retries.

        Args:
            failed_log: The failed notification log

        Returns:
            New NotificationLog for fallback, or None if no fallback available
        """
        priority_order = failed_log.context_data.get("priority_order", [])

        # Find current channel index
        try:
            current_index = priority_order.index(failed_log.channel)
        except ValueError:
            logger.warning(f"Channel {failed_log.channel} not in priority order")
            return None

        # Check if there's a next channel
        if current_index >= len(priority_order) - 1:
            logger.info(f"No more fallback channels for log {failed_log.id}")
            return None

        next_channel = priority_order[current_index + 1]
        logger.info(
            f"Scheduling fallback from {failed_log.channel} to {next_channel} "
            f"for log {failed_log.id}"
        )

        # Get recipient for next channel
        customer = CustomerContactInfo.objects.filter(
            customer_id=failed_log.recipient_id,
        ).first()

        if not customer:
            logger.error(f"Customer {failed_log.recipient_id} not found for fallback")
            return None

        recipient = customer.get_recipient_for_channel(next_channel)
        if not recipient:
            logger.warning(
                f"No recipient for {next_channel} for customer {failed_log.recipient_id}"
            )
            # Try next channel recursively
            # Create a mock failed log to continue the chain
            mock_log = NotificationLog(
                channel=next_channel,
                recipient_id=failed_log.recipient_id,
                context_data=failed_log.context_data,
                correlation_id=failed_log.correlation_id,
            )
            return self.schedule_fallback(mock_log)

        # Get the full body from context
        full_body = failed_log.context_data.get("full_body", failed_log.body_preview)

        return self.queue_notification(
            channel=next_channel,
            recipient=recipient,
            subject=failed_log.subject,
            body=full_body,
            event_type=failed_log.event_type,
            customer_id=failed_log.recipient_id,
            template_id=str(failed_log.template_id) if failed_log.template_id else None,
            template_name=failed_log.template_name,
            context=failed_log.context_data.get("context", {}),
            correlation_id=str(failed_log.correlation_id),
            priority_order=priority_order,
            parent_log_id=str(failed_log.id),
            countdown=self.fallback_delay_seconds,
        )

    def get_pending_retries(self) -> List[NotificationLog]:
        """
        Get notifications that are due for retry.
        """
        now = timezone.now()
        return list(
            NotificationLog.objects.filter(
                status=NotificationStatus.FAILED,
                next_retry_at__lte=now,
            ).filter(
                retry_count__lt=models.F("max_retries"),
            )
        )


# Singleton instance
dispatch_service = DispatchService()


# Fix the import issue in get_pending_retries
from django.db import models  # noqa: E402
