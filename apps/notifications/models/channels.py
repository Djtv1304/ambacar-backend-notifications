"""
Channel configuration models.
"""
from django.db import models

from apps.core.models import BaseModel


class TallerChannelConfig(BaseModel):
    """
    Workshop-level channel configuration.
    Determines which channels are enabled/configured for the entire taller.
    """
    taller_id = models.CharField(
        max_length=100,
        unique=True,
        db_index=True,
        help_text="Unique workshop identifier"
    )
    taller_name = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        help_text="Workshop display name"
    )

    # Email channel
    email_enabled = models.BooleanField(
        default=False,
        help_text="Whether email notifications are enabled"
    )
    email_configured = models.BooleanField(
        default=False,
        help_text="Whether email is properly configured"
    )

    # Push channel
    push_enabled = models.BooleanField(
        default=False,
        help_text="Whether push notifications are enabled"
    )
    push_configured = models.BooleanField(
        default=False,
        help_text="Whether push is properly configured"
    )

    # WhatsApp channel
    whatsapp_enabled = models.BooleanField(
        default=False,
        help_text="Whether WhatsApp notifications are enabled"
    )
    whatsapp_configured = models.BooleanField(
        default=False,
        help_text="Whether WhatsApp is properly configured"
    )

    class Meta:
        db_table = "taller_channel_configs"
        verbose_name = "Taller Channel Config"
        verbose_name_plural = "Taller Channel Configs"

    def __str__(self):
        return f"Channel Config: {self.taller_name or self.taller_id}"

    def get_enabled_channels(self) -> list:
        """Return list of enabled channel names."""
        channels = []
        if self.email_enabled:
            channels.append("email")
        if self.push_enabled:
            channels.append("push")
        if self.whatsapp_enabled:
            channels.append("whatsapp")
        return channels


class PushSubscription(BaseModel):
    """
    Web Push subscription for a customer.
    Stores VAPID subscription info from the browser.

    This is populated when a user subscribes to push notifications
    from the Next.js PWA frontend.
    """
    customer_id = models.CharField(
        max_length=100,
        db_index=True,
        help_text="Customer identifier"
    )
    endpoint = models.TextField(
        unique=True,
        help_text="Push service endpoint URL"
    )
    p256dh_key = models.TextField(
        help_text="Public key for encryption (p256dh)"
    )
    auth_key = models.TextField(
        help_text="Authentication secret"
    )
    user_agent = models.CharField(
        max_length=500,
        blank=True,
        null=True,
        help_text="Browser user agent for debugging"
    )
    is_active = models.BooleanField(
        default=True,
        help_text="Whether this subscription is active"
    )
    last_used_at = models.DateTimeField(
        blank=True,
        null=True,
        help_text="Last time a notification was sent to this subscription"
    )
    failure_count = models.PositiveIntegerField(
        default=0,
        help_text="Number of consecutive failures"
    )

    class Meta:
        db_table = "push_subscriptions"
        indexes = [
            models.Index(fields=["customer_id", "is_active"]),
        ]
        verbose_name = "Push Subscription"
        verbose_name_plural = "Push Subscriptions"

    def __str__(self):
        status = "active" if self.is_active else "inactive"
        return f"Push sub for {self.customer_id} ({status})"

    def mark_failed(self):
        """Increment failure count and deactivate if too many failures."""
        self.failure_count += 1
        if self.failure_count >= 3:
            self.is_active = False
        self.save(update_fields=["failure_count", "is_active"])

    def mark_success(self):
        """Reset failure count on successful send."""
        from django.utils import timezone
        self.failure_count = 0
        self.last_used_at = timezone.now()
        self.save(update_fields=["failure_count", "last_used_at"])
