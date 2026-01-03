"""
Notification template models.
"""
from django.db import models
from django.core.exceptions import ValidationError

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

    # OBLIGATORIO: Tipo de servicio principal
    service_type = models.ForeignKey(
        "notifications.ServiceType",
        on_delete=models.CASCADE,
        related_name="templates",
        limit_choices_to={"parent__isnull": True},  # Solo tipos principales
        help_text="Required: main service type for this template"
    )

    # OBLIGATORIO: Fase del servicio
    phase = models.ForeignKey(
        "notifications.ServicePhase",
        on_delete=models.CASCADE,
        related_name="templates",
        help_text="Required: service phase for this template"
    )

    # OPCIONAL: Subtipo (solo para Avería/Revisión y Colisión/Pintura)
    subtype = models.ForeignKey(
        "notifications.ServiceType",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="subtype_templates",
        limit_choices_to={"parent__isnull": False},  # Solo subtipos
        help_text="Optional: specific subtype (for services with subtypes)"
    )

    class Meta:
        db_table = "notification_templates"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["channel", "target"]),
            models.Index(fields=["taller_id", "channel"]),
            models.Index(fields=["is_active", "channel"]),
            models.Index(fields=["service_type", "phase", "channel"]),
            models.Index(fields=["service_type", "subtype", "phase"]),
        ]
        verbose_name = "Notification Template"
        verbose_name_plural = "Notification Templates"

    def __str__(self):
        subtype_info = f" > {self.subtype.name}" if self.subtype else ""
        return f"{self.name} ({self.service_type.name}{subtype_info} - {self.phase.name})"

    def clean(self):
        """Validate that subtype belongs to the selected service_type."""
        super().clean()
        if self.subtype and self.subtype.parent != self.service_type:
            raise ValidationError({
                "subtype": "El subtipo debe pertenecer al tipo de servicio seleccionado"
            })

    def get_variables(self) -> list:
        """Extract variable names from the template body."""
        import re
        pattern = re.compile(r'\{\{(\w+)\}\}')
        return list(set(pattern.findall(self.body)))
