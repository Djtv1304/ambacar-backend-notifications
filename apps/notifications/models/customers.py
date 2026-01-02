"""
Customer contact and preference models.
"""
from django.db import models

from apps.core.models import BaseModel
from apps.core.constants import NotificationChannel


class CustomerContactInfo(BaseModel):
    """
    Customer contact information.

    Note: This may sync from an external CRM/main backend.
    The customer_id should match the ID in the main system.
    """
    customer_id = models.CharField(
        max_length=100,
        unique=True,
        db_index=True,
        help_text="Unique customer identifier (from main system)"
    )
    first_name = models.CharField(
        max_length=100,
        help_text="Customer's first name"
    )
    last_name = models.CharField(
        max_length=100,
        help_text="Customer's last name"
    )
    email = models.EmailField(
        blank=True,
        null=True,
        help_text="Primary email address"
    )
    phone = models.CharField(
        max_length=50,
        blank=True,
        null=True,
        help_text="Primary phone number"
    )
    whatsapp = models.CharField(
        max_length=50,
        blank=True,
        null=True,
        help_text="WhatsApp number (may differ from phone)"
    )
    preferred_language = models.CharField(
        max_length=10,
        default="es",
        help_text="ISO language code (e.g., 'es', 'en')"
    )
    avatar_url = models.URLField(
        blank=True,
        null=True,
        help_text="Profile image URL"
    )

    class Meta:
        db_table = "customer_contact_info"
        verbose_name = "Customer Contact Info"
        verbose_name_plural = "Customer Contact Info"

    def __str__(self):
        return f"{self.first_name} {self.last_name}"

    @property
    def full_name(self) -> str:
        """Return the customer's full name."""
        return f"{self.first_name} {self.last_name}"

    def get_recipient_for_channel(self, channel: str) -> str | None:
        """Get the recipient address for a given channel."""
        if channel == NotificationChannel.EMAIL:
            return self.email
        elif channel == NotificationChannel.WHATSAPP:
            return self.whatsapp or self.phone
        elif channel == NotificationChannel.PUSH:
            return self.customer_id  # Push uses customer_id to lookup subscription
        return None


class CustomerChannelPreference(BaseModel):
    """
    Customer's preference for a specific notification channel.

    Each customer can have preferences for multiple channels,
    with priority determining the order of fallback.
    """
    customer = models.ForeignKey(
        CustomerContactInfo,
        on_delete=models.CASCADE,
        related_name="channel_preferences",
        to_field="customer_id",
        db_column="customer_id",
        help_text="Customer this preference belongs to"
    )
    channel = models.CharField(
        max_length=20,
        choices=NotificationChannel.choices,
        help_text="Notification channel"
    )
    enabled = models.BooleanField(
        default=True,
        help_text="Whether the customer has enabled this channel"
    )
    priority = models.PositiveIntegerField(
        default=1,
        help_text="Order of preference (1 = highest priority)"
    )

    class Meta:
        db_table = "customer_channel_preferences"
        unique_together = ["customer", "channel"]
        ordering = ["priority"]
        verbose_name = "Customer Channel Preference"
        verbose_name_plural = "Customer Channel Preferences"

    def __str__(self):
        status = "enabled" if self.enabled else "disabled"
        return f"{self.customer} - {self.get_channel_display()} (P{self.priority}, {status})"
