"""
Celery tasks for notification processing.
"""
import logging
from datetime import timedelta

from celery import shared_task
from django.conf import settings
from django.db import models
from django.utils import timezone

from apps.core.constants import NotificationChannel, NotificationStatus, ReminderStatus
from apps.core.ports import NotificationPayload

logger = logging.getLogger(__name__)

# Adapter registry - initialized lazily
_adapters = None


def get_adapters():
    """Lazy initialization of adapters to avoid import issues."""
    global _adapters
    if _adapters is None:
        from apps.notifications.adapters import EmailAdapter, WhatsAppAdapter, WebPushAdapter
        _adapters = {
            NotificationChannel.EMAIL: EmailAdapter(),
            NotificationChannel.WHATSAPP: WhatsAppAdapter(),
            NotificationChannel.PUSH: WebPushAdapter(),
        }
    return _adapters


@shared_task(
    bind=True,
    max_retries=3,
    default_retry_delay=60,
    autoretry_for=(Exception,),
    retry_backoff=True,  # Exponential backoff enabled
    queue='notifications',
)
def send_notification_task(self, log_id: str):
    """
    Celery task to send a single notification.
    Handles success, failure, and fallback scheduling.

    Args:
        log_id: UUID of the NotificationLog entry
    """
    from apps.notifications.models import NotificationLog
    from apps.notifications.services.dispatch_service import dispatch_service

    try:
        log = NotificationLog.objects.get(id=log_id)
    except NotificationLog.DoesNotExist:
        logger.error(f"NotificationLog {log_id} not found")
        return {"error": "Log not found"}

    # Skip if already processed successfully
    if log.status in [NotificationStatus.SENT, NotificationStatus.DELIVERED]:
        logger.info(f"Notification {log_id} already {log.status}, skipping")
        return {"status": "skipped", "reason": f"Already {log.status}"}

    # Get appropriate adapter
    adapters = get_adapters()
    adapter = adapters.get(log.channel)

    if not adapter:
        log.mark_failed(f"Unknown channel: {log.channel}", "UNKNOWN_CHANNEL")
        return {"error": f"Unknown channel: {log.channel}"}

    # Check if adapter is configured
    if not adapter.is_configured():
        log.mark_failed(
            f"Channel {log.channel} is not configured",
            f"{log.channel.upper()}_NOT_CONFIGURED"
        )
        return {"error": f"Channel {log.channel} not configured"}

    # Build payload
    full_body = log.context_data.get("full_body", log.body_preview)
    payload = NotificationPayload(
        recipient=log.recipient_address,
        subject=log.subject,
        body=full_body,
        metadata={
            "customer_id": log.recipient_id,
            "log_id": str(log.id),
        }
    )

    # Send notification
    result = adapter.send(payload)

    if result.success:
        log.mark_sent(result.message_id)
        logger.info(f"Notification {log_id} sent successfully via {log.channel}")
        return {
            "status": "sent",
            "message_id": result.message_id,
            "channel": log.channel,
        }
    else:
        log.retry_count += 1
        log.error_reason = result.error_message
        log.error_code = result.error_code

        if log.retry_count >= log.max_retries:
            log.status = NotificationStatus.FAILED
            log.save()

            logger.warning(
                f"Notification {log_id} failed after {log.retry_count} retries: "
                f"{result.error_message}"
            )

            # Schedule fallback on next priority channel
            fallback_log = dispatch_service.schedule_fallback(log)

            return {
                "status": "failed",
                "error": result.error_message,
                "error_code": result.error_code,
                "retries": log.retry_count,
                "fallback_scheduled": fallback_log is not None,
                "fallback_channel": fallback_log.channel if fallback_log else None,
            }
        else:
            # Schedule retry with exponential backoff
            retry_delay = 60 * (2 ** (log.retry_count - 1))  # 60s, 120s, 240s...
            log.next_retry_at = timezone.now() + timedelta(seconds=retry_delay)
            log.save()

            logger.info(
                f"Notification {log_id} failed, scheduling retry {log.retry_count} "
                f"in {retry_delay}s"
            )

            raise self.retry(countdown=retry_delay)


@shared_task(queue='maintenance')
def check_maintenance_reminders():
    """
    Periodic task to check and send maintenance reminders.
    Runs daily via Celery Beat (configured in celery.py).

    Checks:
    1. Date-based reminders: target_date - notify_before_days <= today
    2. Kilometer-based reminders: Would need vehicle odometer updates
    """
    from apps.notifications.models import MaintenanceReminder, Vehicle
    from apps.notifications.models import CustomerContactInfo
    from apps.notifications.services.orchestration_engine import (
        orchestration_engine,
        EventPayload,
    )
    from apps.core.constants import EventType

    logger.info("Starting maintenance reminder check")

    today = timezone.now().date()
    processed = 0
    errors = 0

    # Check date-based reminders
    date_reminders = MaintenanceReminder.objects.filter(
        status=ReminderStatus.PENDING,
        type__in=["date", "both"],
        target_date__isnull=False,
    ).select_related("vehicle")

    for reminder in date_reminders:
        if reminder.should_notify_by_date(today):
            try:
                _process_reminder(reminder)
                processed += 1
            except Exception as e:
                logger.error(f"Error processing reminder {reminder.id}: {str(e)}")
                errors += 1

    # Check for overdue reminders
    overdue_reminders = MaintenanceReminder.objects.filter(
        status=ReminderStatus.PENDING,
        target_date__lt=today,
    )

    for reminder in overdue_reminders:
        reminder.mark_overdue()
        logger.info(f"Marked reminder {reminder.id} as overdue")

    logger.info(
        f"Maintenance reminder check complete: {processed} processed, {errors} errors"
    )

    return {
        "processed": processed,
        "errors": errors,
        "overdue_marked": overdue_reminders.count(),
    }


def _process_reminder(reminder):
    """
    Process a single maintenance reminder.
    Creates an event and sends it through the orchestration engine.
    """
    from apps.notifications.models import CustomerContactInfo
    from apps.notifications.services.orchestration_engine import (
        orchestration_engine,
        EventPayload,
    )
    from apps.core.constants import EventType

    customer = CustomerContactInfo.objects.filter(
        customer_id=reminder.customer_id,
    ).first()

    if not customer:
        logger.warning(f"Customer {reminder.customer_id} not found for reminder")
        return

    # Build context for template
    context = {
        "nombre": customer.full_name,
        "vehiculo": reminder.vehicle.display_name,
        "placa": reminder.vehicle.plate,
        "descripcion": reminder.description,
    }

    if reminder.target_date:
        context["fecha"] = reminder.target_date.strftime("%d de %B, %Y")

    if reminder.target_kilometers:
        context["kilometraje"] = f"{reminder.target_kilometers:,} km"

    payload = EventPayload(
        event_type=EventType.MAINTENANCE_REMINDER,
        service_type_id="mantenimiento-preventivo",
        phase_id="phase-schedule",  # Use schedule phase for reminders
        customer_id=reminder.customer_id,
        target="clients",
        context=context,
    )

    result = orchestration_engine.process_event(payload)

    if result.notifications_queued > 0:
        reminder.mark_notified()
        logger.info(
            f"Reminder {reminder.id} processed: {result.notifications_queued} notifications queued"
        )


@shared_task(queue='notifications')
def retry_failed_notifications():
    """
    Periodic task to retry failed notifications that are due for retry.
    Runs every 15 minutes via Celery Beat.

    Optimized: Early return if no notifications to retry (reduces Redis usage).
    """
    from apps.notifications.models import NotificationLog

    now = timezone.now()

    # Early return: Check count first to avoid unnecessary work
    pending_count = NotificationLog.objects.filter(
        status=NotificationStatus.FAILED,
        next_retry_at__lte=now,
        retry_count__lt=models.F("max_retries"),
    ).count()

    if pending_count == 0:
        # Don't log if there's nothing to do (reduces noise)
        return {"requeued": 0}

    # Only fetch and process if there are pending retries
    pending_retries = NotificationLog.objects.filter(
        status=NotificationStatus.FAILED,
        next_retry_at__lte=now,
        retry_count__lt=models.F("max_retries"),
    )[:100]  # Limit to 100 per batch to avoid overload

    count = 0
    for log in pending_retries:
        # Reset status and requeue
        log.status = NotificationStatus.QUEUED
        log.save(update_fields=["status", "updated_at"])

        send_notification_task.delay(str(log.id))
        count += 1

    logger.info(f"Requeued {count} failed notifications for retry")
    return {"requeued": count}


@shared_task(
    bind=True,
    max_retries=3,
    default_retry_delay=2,  # Start with 2 seconds
    retry_backoff=True,     # Exponential backoff: 2s, 4s, 8s
    retry_backoff_max=10,   # Max 10 seconds between retries
    queue='notifications',
)
def dispatch_event_task(self, event_data: dict):
    """
    Async task to dispatch notification events with automatic retries.

    This task processes events through the orchestration engine with retry logic
    to handle race conditions (e.g., customer not synced yet).

    Retry strategy:
    - Attempt 1: Immediate (0s)
    - Attempt 2: After 2s (if customer still missing, maybe sync is in progress)
    - Attempt 3: After 4s (exponential backoff)
    - Attempt 4: After 8s (final attempt)

    Args:
        event_data: Dict containing event payload fields
            {
                "event_type": str,
                "service_type_id": str,
                "phase_id": str,
                "customer_id": str,
                "target": str,
                "context": dict,
                "taller_id": str (optional),
                "subtype_id": str (optional),
                "correlation_id": str (optional),
            }

    Returns:
        dict: OrchestrationResult data

    Raises:
        Exception: After all retries exhausted
    """
    from apps.notifications.services.orchestration_engine import (
        orchestration_engine,
        EventPayload,
    )

    try:
        # Build event payload from dict
        payload = EventPayload(
            event_type=event_data["event_type"],
            service_type_id=event_data["service_type_id"],
            phase_id=event_data["phase_id"],
            customer_id=event_data["customer_id"],
            target=event_data.get("target", "clients"),
            context=event_data.get("context", {}),
            taller_id=event_data.get("taller_id"),
            subtype_id=event_data.get("subtype_id"),
            correlation_id=event_data.get("correlation_id"),
        )

        logger.info(
            f"🚀 [Attempt {self.request.retries + 1}/{self.max_retries + 1}] "
            f"Processing event {payload.event_type} for customer {payload.customer_id}"
        )

        # Process event through orchestration engine
        result = orchestration_engine.process_event(payload)

        if not result.success:
            # Check if error is retryable (customer not found, resource missing)
            retryable_errors = [
                "customer not found",
                "customer",  # Generic customer-related errors
                "not synced",
                "does not exist",
            ]

            is_retryable = any(
                err_keyword in " ".join(result.errors).lower()
                for err_keyword in retryable_errors
            )

            if is_retryable:
                logger.warning(
                    f"⚠️ Retryable error on attempt {self.request.retries + 1}: {result.errors}. "
                    f"Will retry in {self.default_retry_delay * (2 ** self.request.retries)}s"
                )
                # Retry with exponential backoff
                raise self.retry(exc=Exception(" | ".join(result.errors)))
            else:
                # Non-retryable error (config not found, validation error, etc.)
                logger.error(
                    f"❌ Non-retryable error for customer {payload.customer_id}: {result.errors}"
                )
                return {
                    "success": False,
                    "errors": result.errors,
                    "correlation_id": result.correlation_id,
                    "retries_exhausted": False,
                    "error_type": "non_retryable",
                }

        # Success!
        logger.info(
            f"✅ Successfully dispatched {result.notifications_queued} notifications "
            f"for customer {payload.customer_id} (correlation_id: {result.correlation_id})"
        )

        return {
            "success": result.success,
            "notifications_queued": result.notifications_queued,
            "errors": result.errors,
            "correlation_id": result.correlation_id,
        }

    except Exception as exc:
        # Final retry exhausted
        if self.request.retries >= self.max_retries:
            logger.error(
                f"❌ FAILED after {self.max_retries + 1} attempts for customer {event_data['customer_id']}: {exc}",
                exc_info=True
            )
            return {
                "success": False,
                "errors": [f"Failed after {self.max_retries + 1} retries: {str(exc)}"],
                "correlation_id": event_data.get("correlation_id"),
                "retries_exhausted": True,
            }

        # Will retry
        raise
