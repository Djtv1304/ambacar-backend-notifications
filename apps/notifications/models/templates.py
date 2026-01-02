"""
Notification template models.
"""
from django.db import models

from apps.core.models import BaseModel
from apps.core.constants import NotificationChannel, NotificationTarget


class NotificationTemplate(BaseModel):
    """
    Message templates for notifications.
    Supports variable interpolation using {{variable}} syntax.

    Example template body:
        "Hola {{Nombre}}, tu vehículo {{Vehículo}} ({{Placa}}) está listo."
    """
    name = models.CharField(
        max_length=255,
        help_text="Template display name"
    )
    subject = models.CharField(
        max_length=500,
        blank=True,
        null=True,
        help_text="Email subject line (optional for non-email channels)"
    )
    body = models.TextField(
        help_text="Template content with {{variables}}"
    )
    channel = models.CharField(
        max_length=20,
        choices=NotificationChannel.choices,
        db_index=True,
        help_text="Primary channel for this template"
    )
    target = models.CharField(
        max_length=20,
        choices=NotificationTarget.choices,
        db_index=True,
        help_text="Target audience (clients or staff)"
    )
    is_default = models.BooleanField(
        default=False,
        help_text="Whether this is a system default template"
    )
    is_active = models.BooleanField(
        default=True,
        help_text="Whether this template is available for use"
    )

    # Optional: link to specific taller/workshop
    taller_id = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        db_index=True,
        help_text="Optional: workshop-specific template"
    )

    class Meta:
        db_table = "notification_templates"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["channel", "target"]),
            models.Index(fields=["taller_id", "channel"]),
            models.Index(fields=["is_active", "channel"]),
        ]
        verbose_name = "Notification Template"
        verbose_name_plural = "Notification Templates"

    def __str__(self):
        return f"{self.name} ({self.get_channel_display()})"

    def get_variables(self) -> list:
        """Extract variable names from the template body."""
        import re
        pattern = re.compile(r'\{\{(\w+)\}\}')
        return list(set(pattern.findall(self.body)))
