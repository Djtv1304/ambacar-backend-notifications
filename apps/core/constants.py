"""
Constants and enums for the notification service.
"""
from django.db import models


class NotificationChannel(models.TextChoices):
    """Available notification channels."""
    EMAIL = "email", "Email"
    PUSH = "push", "Push Notification"
    WHATSAPP = "whatsapp", "WhatsApp"


class NotificationTarget(models.TextChoices):
    """Target audience for notifications."""
    CLIENTS = "clients", "Clientes"
    STAFF = "staff", "Personal"


class NotificationStatus(models.TextChoices):
    """Status of a notification in its lifecycle."""
    PENDING = "pending", "Pendiente"
    QUEUED = "queued", "En cola"
    SENT = "sent", "Enviado"
    DELIVERED = "delivered", "Entregado"
    READ = "read", "Leído"
    BOUNCED = "bounced", "Rebotado"
    FAILED = "failed", "Fallido"


class ReminderType(models.TextChoices):
    """Type of maintenance reminder trigger."""
    KILOMETERS = "kilometers", "Kilómetros"
    DATE = "date", "Fecha"
    BOTH = "both", "Ambos"


class ReminderStatus(models.TextChoices):
    """Status of a maintenance reminder."""
    PENDING = "pending", "Pendiente"
    NOTIFIED = "notified", "Notificado"
    COMPLETED = "completed", "Completado"
    OVERDUE = "overdue", "Vencido"


class EventType(models.TextChoices):
    """
    Service workflow events that trigger notifications.
    These correspond to the service phases.
    """
    # Phase-based events
    APPOINTMENT_SCHEDULED = "appointment_scheduled", "Cita Agendada"
    VEHICLE_RECEIVED = "vehicle_received", "Vehículo Recibido"
    REPAIR_STARTED = "repair_started", "Reparación Iniciada"
    QUALITY_CHECK = "quality_check", "Control de Calidad"
    VEHICLE_READY = "vehicle_ready", "Vehículo Listo"

    # Reminder events
    MAINTENANCE_REMINDER = "maintenance_reminder", "Recordatorio de Mantenimiento"
    MAINTENANCE_OVERDUE = "maintenance_overdue", "Mantenimiento Vencido"

    # Other events
    CUSTOM = "custom", "Personalizado"


# Template variable definitions
TEMPLATE_VARIABLES = [
    {
        "id": "nombre",
        "label": "{{Nombre}}",
        "description": "Nombre del cliente",
        "example": "Carlos Mendoza",
    },
    {
        "id": "placa",
        "label": "{{Placa}}",
        "description": "Placa del vehículo",
        "example": "PCU6322",
    },
    {
        "id": "vehiculo",
        "label": "{{Vehículo}}",
        "description": "Marca y modelo del vehículo",
        "example": "Haval H6 2024",
    },
    {
        "id": "fase",
        "label": "{{Fase}}",
        "description": "Nombre de la fase actual",
        "example": "Recepción",
    },
    {
        "id": "fecha",
        "label": "{{Fecha}}",
        "description": "Fecha programada",
        "example": "20 de Diciembre, 2025",
    },
    {
        "id": "hora",
        "label": "{{Hora}}",
        "description": "Hora programada",
        "example": "14:30",
    },
    {
        "id": "orden",
        "label": "{{Orden}}",
        "description": "Número de orden de trabajo",
        "example": "OT-2025-MANT-014",
    },
    {
        "id": "tecnico",
        "label": "{{Técnico}}",
        "description": "Nombre del técnico asignado",
        "example": "Juan Técnico",
    },
    {
        "id": "taller",
        "label": "{{Taller}}",
        "description": "Nombre del taller",
        "example": "Ambacar Service",
    },
]
