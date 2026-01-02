"""
Notification log model for tracking and analytics.
"""
from django.db import models

from apps.core.models import BaseModel
from apps.core.constants import NotificationChannel, NotificationStatus, EventType


class NotificationLog(BaseModel):
    """
    Audit log for all sent notifications.
    Used for analytics, debugging, and retry logic.
    """
    # Event information
    event_type = models.CharField(
        max_length=50,
        choices=EventType.choices,
        db_index=True,
        help_text="What triggered this notification"
    )

    # Channel and recipient
    channel = models.CharField(
        max_length=20,
        choices=NotificationChannel.choices,
        db_index=True,
        help_text="Channel used for delivery"
    )
    recipient_id = models.CharField(
        max_length=100,
        db_index=True,
        help_text="Customer/staff identifier"
    )
    recipient_address = models.CharField(
        max_length=255,
        help_text="Email address, phone number, or push endpoint"
    )

    # Template information
    template_id = models.UUIDField(
        blank=True,
        null=True,
        help_text="Template used (if any)"
    )
    template_name = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        help_text="Template name for reference"
    )

    # Content (for debugging and display)
    subject = models.CharField(
        max_length=500,
        blank=True,
        null=True,
        help_text="Subject line (for email)"
    )
    body_preview = models.TextField(
        blank=True,
        null=True,
        help_text="First 500 chars of rendered body"
    )

    # Status tracking
    status = models.CharField(
        max_length=20,
        choices=NotificationStatus.choices,
        default=NotificationStatus.PENDING,
        db_index=True,
        help_text="Current delivery status"
    )
    sent_at = models.DateTimeField(
        blank=True,
        null=True,
        help_text="When the notification was sent"
    )
    delivered_at = models.DateTimeField(
        blank=True,
        null=True,
        help_text="When delivery was confirmed"
    )
    read_at = models.DateTimeField(
        blank=True,
        null=True,
        help_text="When the notification was read"
    )

    # Error handling
    error_reason = models.TextField(
        blank=True,
        null=True,
        help_text="Error message if failed"
    )
    error_code = models.CharField(
        max_length=50,
        blank=True,
        null=True,
        help_text="Error code for categorization"
    )
    retry_count = models.PositiveIntegerField(
        default=0,
        help_text="Number of retry attempts"
    )
    max_retries = models.PositiveIntegerField(
        default=3,
        help_text="Maximum retry attempts allowed"
    )
    next_retry_at = models.DateTimeField(
        blank=True,
        null=True,
        help_text="Scheduled time for next retry"
    )

    # Context data for retry and debugging
    context_data = models.JSONField(
        default=dict,
        help_text="Original context for template rendering and channel priority"
    )

    # Correlation for tracking related notifications
    correlation_id = models.UUIDField(
        blank=True,
        null=True,
        db_index=True,
        help_text="Groups related notifications from same event"
    )
    parent_log = models.ForeignKey(
        "self",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="fallback_attempts",
        help_text="Reference to original notification if this is a fallback"
    )

    class Meta:
        db_table = "notification_logs"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["status", "channel"]),
            models.Index(fields=["recipient_id", "-created_at"]),
            models.Index(fields=["correlation_id"]),
            models.Index(fields=["sent_at"]),
            models.Index(fields=["status", "next_retry_at"]),
        ]
        verbose_name = "Notification Log"
        verbose_name_plural = "Notification Logs"

    def __str__(self):
        return f"{self.event_type} via {self.channel} to {self.recipient_id} ({self.status})"

    def mark_sent(self, message_id: str = None):
        """Mark notification as sent."""
        from django.utils import timezone
        self.status = NotificationStatus.SENT
        self.sent_at = timezone.now()
        if message_id:
            self.context_data["message_id"] = message_id
        self.save(update_fields=["status", "sent_at", "context_data", "updated_at"])

    def mark_delivered(self):
        """Mark notification as delivered."""
        from django.utils import timezone
        self.status = NotificationStatus.DELIVERED
        self.delivered_at = timezone.now()
        self.save(update_fields=["status", "delivered_at", "updated_at"])

    def mark_failed(self, error_message: str, error_code: str = None):
        """Mark notification as failed."""
        self.status = NotificationStatus.FAILED
        self.error_reason = error_message
        self.error_code = error_code
        self.save(update_fields=["status", "error_reason", "error_code", "updated_at"])

    def increment_retry(self, next_retry_at=None):
        """Increment retry count and schedule next retry."""
        self.retry_count += 1
        self.next_retry_at = next_retry_at
        self.save(update_fields=["retry_count", "next_retry_at", "updated_at"])

    def can_retry(self) -> bool:
        """Check if this notification can be retried."""
        return (
            self.status in [NotificationStatus.PENDING, NotificationStatus.FAILED] and
            self.retry_count < self.max_retries
        )

    def get_delivery_time_seconds(self) -> float | None:
        """Calculate delivery time in seconds."""
        if self.sent_at and self.delivered_at:
            delta = self.delivered_at - self.sent_at
            return delta.total_seconds()
        return None
