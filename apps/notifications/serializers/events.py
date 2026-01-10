"""
Serializers for event dispatch API.
"""
from rest_framework import serializers

from apps.core.constants import EventType, NotificationTarget


class EventDispatchSerializer(serializers.Serializer):
    """
    Serializer for incoming notification events.

    Example payload:
    {
        "event_type": "appointment_scheduled",
        "service_type_id": "mantenimiento-preventivo",
        "phase_id": "phase-schedule",
        "customer_id": "customer-001",
        "target": "clients",
        "context": {
            "nombre": "Carlos Mendoza",
            "placa": "ABC123",
            "vehiculo": "Haval H6 2024",
            "fecha": "20 de Enero, 2026",
            "hora": "14:30"
        }
    }
    """
    event_type = serializers.ChoiceField(
        choices=EventType.choices,
        help_text="Type of event triggering the notification",
    )
    service_type_id = serializers.CharField(
        max_length=100,
        required=False,
        allow_null=True,
        help_text="Service type identifier (e.g., 'mantenimiento-preventivo'). Optional for custom events.",
    )
    phase_id = serializers.CharField(
        max_length=100,
        required=False,
        allow_null=True,
        help_text="Service phase identifier (e.g., 'phase-schedule'). Optional for custom events.",
    )
    customer_id = serializers.CharField(
        max_length=100,
        help_text="Customer identifier",
    )
    target = serializers.ChoiceField(
        choices=NotificationTarget.choices,
        default=NotificationTarget.CLIENTS,
        help_text="Target audience (clients or staff)",
    )
    taller_id = serializers.CharField(
        max_length=100,
        required=False,
        allow_null=True,
        help_text="Optional workshop identifier for taller-specific config",
    )
    subtype_id = serializers.CharField(
        max_length=100,
        required=False,
        allow_null=True,
        help_text="Optional service subtype identifier",
    )
    context = serializers.DictField(
        child=serializers.CharField(allow_blank=True),
        required=False,
        default=dict,
        help_text="Template variables (e.g., nombre, placa, fecha)",
    )
    correlation_id = serializers.UUIDField(
        required=False,
        allow_null=True,
        help_text="Optional correlation ID for tracking related events",
    )

    def validate(self, data):
        """
        Cross-field validation: service_type_id and phase_id are required
        for all event types EXCEPT custom.
        """
        event_type = data.get("event_type")
        service_type_id = data.get("service_type_id")
        phase_id = data.get("phase_id")

        # For non-custom events, service_type_id and phase_id are required
        if event_type != EventType.CUSTOM:
            if not service_type_id:
                raise serializers.ValidationError({
                    "service_type_id": "This field is required for non-custom events. "
                                      "Only 'custom' event type can omit this field."
                })
            if not phase_id:
                raise serializers.ValidationError({
                    "phase_id": "This field is required for non-custom events. "
                               "Only 'custom' event type can omit this field."
                })

        return data


class EventDispatchResponseSerializer(serializers.Serializer):
    """
    Response serializer for event dispatch.
    """
    success = serializers.BooleanField(
        help_text="Whether the event was processed successfully",
    )
    correlation_id = serializers.UUIDField(
        help_text="Correlation ID for tracking this batch of notifications",
    )
    notifications_queued = serializers.IntegerField(
        help_text="Number of notifications queued for sending",
    )
    errors = serializers.ListField(
        child=serializers.CharField(),
        required=False,
        help_text="List of errors if any occurred",
    )
