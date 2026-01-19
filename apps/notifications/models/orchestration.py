"""
Service orchestration models.
Defines service phases, types, and notification configuration.
"""
from django.db import models

from apps.core.models import BaseModel
from apps.core.constants import NotificationChannel, NotificationTarget


class ServicePhase(BaseModel):
    """
    Represents a phase in the service workflow.

    Default phases:
    1. Agendar Cita (Schedule)
    2. Recepción (Reception)
    3. Reparación (Repair)
    4. Control Calidad (Quality Check)
    5. Entrega (Delivery)
    """
    slug = models.SlugField(
        max_length=50,
        unique=True,
        help_text="Unique identifier for API lookups (e.g., 'phase-schedule')"
    )
    name = models.CharField(
        max_length=100,
        help_text="Phase display name"
    )
    icon = models.CharField(
        max_length=50,
        help_text="Lucide icon name (e.g., 'Calendar', 'Wrench')"
    )
    order = models.PositiveIntegerField(
        db_index=True,
        help_text="Sequence order in workflow"
    )
    is_active = models.BooleanField(
        default=True,
        help_text="Whether this phase is active"
    )
    description = models.TextField(
        blank=True,
        null=True,
        help_text="Optional description of the phase"
    )

    class Meta:
        db_table = "service_phases"
        ordering = ["order"]
        verbose_name = "Service Phase"
        verbose_name_plural = "Service Phases"

    def __str__(self):
        return f"{self.order}. {self.name}"


class ServiceType(BaseModel):
    """
    Types of services offered by the workshop.

    Examples:
    - Avalúo Comercial
    - Avería/Revisión (with subtypes: Frenos, Diagnóstico, Alineación)
    - Colisión/Pintura (with subtypes: Siniestro, Golpe, Pintura)
    - Mantenimiento Preventivo
    - Avalúo MG
    """
    slug = models.SlugField(
        max_length=50,
        unique=True,
        help_text="Unique identifier for API lookups (e.g., 'mantenimiento-preventivo')"
    )
    name = models.CharField(
        max_length=100,
        help_text="Service type display name"
    )
    icon = models.CharField(
        max_length=50,
        help_text="Lucide icon name"
    )
    parent = models.ForeignKey(
        "self",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="subtypes",
        help_text="Parent service type for subtypes"
    )
    is_active = models.BooleanField(
        default=True,
        help_text="Whether this service type is active"
    )
    description = models.TextField(
        blank=True,
        null=True,
        help_text="Optional description"
    )

    class Meta:
        db_table = "service_types"
        ordering = ["name"]
        verbose_name = "Service Type"
        verbose_name_plural = "Service Types"

    def __str__(self):
        if self.parent:
            return f"{self.parent.name} > {self.name}"
        return self.name

    @property
    def is_subtype(self) -> bool:
        """Check if this is a subtype."""
        return self.parent is not None


class OrchestrationConfig(BaseModel):
    """
    Configuration that links service types to notification behavior.
    Defines the overall notification strategy for a service type.
    """
    service_type = models.ForeignKey(
        ServiceType,
        on_delete=models.CASCADE,
        related_name="orchestration_configs",
        help_text="Service type this config applies to"
    )
    target = models.CharField(
        max_length=20,
        choices=NotificationTarget.choices,
        help_text="Target audience (clients or staff)"
    )
    taller_id = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        db_index=True,
        help_text="Optional: workshop-specific config (null for global)"
    )
    is_active = models.BooleanField(
        default=True,
        help_text="Whether this config is active"
    )
    description = models.TextField(
        blank=True,
        null=True,
        help_text="Optional description of this configuration"
    )

    class Meta:
        db_table = "orchestration_configs"
        unique_together = ["service_type", "target", "taller_id"]
        verbose_name = "Orchestration Config"
        verbose_name_plural = "Orchestration Configs"

    def __str__(self):
        taller = f" (Taller: {self.taller_id})" if self.taller_id else ""
        return f"{self.service_type.name} - {self.get_target_display()}{taller}"


class PhaseChannelConfig(BaseModel):
    """
    Configuration for a specific channel within a phase.
    Links: orchestration_config -> phase -> channel -> template

    This is the core of the notification matrix.
    """
    orchestration_config = models.ForeignKey(
        OrchestrationConfig,
        on_delete=models.CASCADE,
        related_name="phase_configs",
        help_text="Parent orchestration config"
    )
    phase = models.ForeignKey(
        ServicePhase,
        on_delete=models.CASCADE,
        related_name="channel_configs",
        help_text="Service phase this applies to"
    )
    channel = models.CharField(
        max_length=20,
        choices=NotificationChannel.choices,
        help_text="Notification channel"
    )
    enabled = models.BooleanField(
        default=False,
        help_text="Whether notifications are enabled for this phase/channel"
    )
    template = models.ForeignKey(
        "notifications.NotificationTemplate",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="phase_configs",
        help_text="Template to use for this notification"
    )

    class Meta:
        db_table = "phase_channel_configs"
        unique_together = ["orchestration_config", "phase", "channel"]
        ordering = ["phase__order", "channel"]
        verbose_name = "Phase Channel Config"
        verbose_name_plural = "Phase Channel Configs"

    def __str__(self):
        status = "enabled" if self.enabled else "disabled"
        return (
            f"{self.orchestration_config.service_type.name} | "
            f"{self.phase.name} | {self.get_channel_display()} ({status})"
        )
