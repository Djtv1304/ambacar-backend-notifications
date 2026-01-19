"""
Vehicle and maintenance reminder models.
"""
from django.contrib.postgres.fields import ArrayField
from django.db import models

from apps.core.models import BaseModel
from apps.core.constants import NotificationChannel, ReminderType, ReminderStatus


class Vehicle(BaseModel):
    """
    Customer vehicle information.

    Note: This may sync from an external system.
    """
    customer_id = models.CharField(
        max_length=100,
        db_index=True,
        help_text="Customer identifier (owner)"
    )
    brand = models.CharField(
        max_length=100,
        help_text="Vehicle manufacturer (e.g., 'Great Wall')"
    )
    model = models.CharField(
        max_length=100,
        help_text="Vehicle model (e.g., 'Haval H6')"
    )
    year = models.PositiveIntegerField(
        help_text="Manufacturing year"
    )
    plate = models.CharField(
        max_length=20,
        unique=True,
        db_index=True,
        help_text="License plate number"
    )
    current_kilometers = models.PositiveIntegerField(
        default=0,
        help_text="Current odometer reading"
    )
    last_service_date = models.DateField(
        blank=True,
        null=True,
        help_text="Date of last service"
    )
    next_service_kilometers = models.PositiveIntegerField(
        blank=True,
        null=True,
        help_text="Odometer target for next service"
    )
    image_url = models.URLField(
        blank=True,
        null=True,
        help_text="Vehicle photo URL"
    )

    # Sync tracking fields (Table Projection pattern)
    last_synced_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Last time this vehicle was synced from Core service"
    )
    sync_version = models.IntegerField(
        null=True,
        blank=True,
        help_text="Version number from Core service for optimistic locking"
    )

    class Meta:
        db_table = "vehicles"
        indexes = [
            models.Index(fields=["customer_id"]),
        ]
        verbose_name = "Vehicle"
        verbose_name_plural = "Vehicles"

    def __str__(self):
        return f"{self.brand} {self.model} ({self.plate})"

    @property
    def display_name(self) -> str:
        """Return a display name for the vehicle."""
        return f"{self.brand} {self.model} {self.year}"

    def get_remaining_km(self) -> int | None:
        """Calculate remaining km until next service."""
        if self.next_service_kilometers:
            return max(0, self.next_service_kilometers - self.current_kilometers)
        return None


class MaintenanceReminder(BaseModel):
    """
    Scheduled maintenance reminder for a vehicle.
    Can be triggered by kilometers, date, or both.
    """
    vehicle = models.ForeignKey(
        Vehicle,
        on_delete=models.CASCADE,
        related_name="reminders",
        help_text="Vehicle this reminder is for"
    )
    customer_id = models.CharField(
        max_length=100,
        db_index=True,
        help_text="Customer identifier (for quick lookups)"
    )
    type = models.CharField(
        max_length=20,
        choices=ReminderType.choices,
        help_text="What triggers this reminder"
    )
    description = models.TextField(
        help_text="What maintenance is needed"
    )
    target_kilometers = models.PositiveIntegerField(
        blank=True,
        null=True,
        help_text="Odometer reading to trigger reminder"
    )
    target_date = models.DateField(
        blank=True,
        null=True,
        help_text="Date to trigger reminder"
    )
    notify_via = ArrayField(
        models.CharField(max_length=20, choices=NotificationChannel.choices),
        default=list,
        help_text="Channels to use for notification"
    )
    status = models.CharField(
        max_length=20,
        choices=ReminderStatus.choices,
        default=ReminderStatus.PENDING,
        db_index=True,
        help_text="Current status of the reminder"
    )
    notify_before_days = models.PositiveIntegerField(
        blank=True,
        null=True,
        help_text="Days before target_date to notify"
    )
    notify_before_km = models.PositiveIntegerField(
        blank=True,
        null=True,
        help_text="Km before target_kilometers to notify"
    )
    last_notified_at = models.DateTimeField(
        blank=True,
        null=True,
        help_text="Last time a notification was sent"
    )

    class Meta:
        db_table = "maintenance_reminders"
        indexes = [
            models.Index(fields=["status", "target_date"]),
            models.Index(fields=["customer_id", "status"]),
            models.Index(fields=["vehicle", "status"]),
        ]
        verbose_name = "Maintenance Reminder"
        verbose_name_plural = "Maintenance Reminders"

    def __str__(self):
        return f"{self.vehicle.plate} - {self.description[:50]}"

    def should_notify_by_date(self, today) -> bool:
        """Check if reminder should trigger based on date."""
        if self.type not in [ReminderType.DATE, ReminderType.BOTH]:
            return False
        if not self.target_date:
            return False

        from datetime import timedelta
        notify_days = self.notify_before_days or 7
        notify_date = self.target_date - timedelta(days=notify_days)
        return today >= notify_date

    def should_notify_by_km(self, current_km: int) -> bool:
        """Check if reminder should trigger based on kilometers."""
        if self.type not in [ReminderType.KILOMETERS, ReminderType.BOTH]:
            return False
        if not self.target_kilometers:
            return False

        notify_km = self.notify_before_km or 500
        trigger_km = self.target_kilometers - notify_km
        return current_km >= trigger_km

    def mark_notified(self):
        """Mark this reminder as notified."""
        from django.utils import timezone
        self.status = ReminderStatus.NOTIFIED
        self.last_notified_at = timezone.now()
        self.save(update_fields=["status", "last_notified_at", "updated_at"])

    def mark_overdue(self):
        """Mark this reminder as overdue."""
        self.status = ReminderStatus.OVERDUE
        self.save(update_fields=["status", "updated_at"])

    def mark_completed(self):
        """Mark this reminder as completed."""
        self.status = ReminderStatus.COMPLETED
        self.save(update_fields=["status", "updated_at"])


class VehiclePhaseConfig(BaseModel):
    """
    Configuración de fases personalizada para un vehículo específico.

    Permite:
    - Orden personalizado de fases
    - Fases adicionales para un vehículo
    - Activar/desactivar fases por vehículo

    CASCADE DELETE: Si se elimina la fase global o el vehículo,
    se elimina esta configuración automáticamente.
    """
    vehicle = models.ForeignKey(
        Vehicle,
        on_delete=models.CASCADE,
        related_name='custom_phase_configs',
        help_text="Vehículo al que pertenece esta configuración"
    )
    phase = models.ForeignKey(
        'notifications.ServicePhase',
        on_delete=models.CASCADE,
        related_name='vehicle_configs',
        help_text="Fase de servicio (de las fases globales)"
    )
    order = models.PositiveIntegerField(
        help_text="Orden personalizado para este vehículo"
    )
    is_active = models.BooleanField(
        default=True,
        help_text="Si esta fase está activa para este vehículo"
    )

    # Campos de sincronización
    last_synced_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Última sincronización desde Core"
    )
    sync_version = models.IntegerField(
        null=True,
        blank=True,
        help_text="Versión de sincronización desde Core"
    )

    class Meta:
        db_table = "vehicle_phase_configs"
        unique_together = ["vehicle", "phase"]
        ordering = ["order"]
        verbose_name = "Vehicle Phase Config"
        verbose_name_plural = "Vehicle Phase Configs"

    def __str__(self):
        return f"{self.vehicle.plate} - {self.phase.name} (order: {self.order})"
