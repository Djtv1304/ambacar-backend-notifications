"""
Views for event dispatch.
"""
from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from drf_spectacular.utils import extend_schema, OpenApiResponse

from apps.notifications.serializers.events import (
    EventDispatchSerializer,
    EventDispatchResponseSerializer,
)
from apps.notifications.services.orchestration_engine import (
    orchestration_engine,
    EventPayload,
)


class EventDispatchView(APIView):
    """
    POST /api/v1/notifications/events/dispatch/

    Main entry point for triggering notifications.
    Receives events from external systems (e.g., workshop management)
    and orchestrates notification delivery.

    The system will:
    1. Find matching orchestration config for the service type/phase
    2. Resolve customer preferences for channel priority
    3. Render templates with provided context
    4. Queue notifications via Celery for async delivery

    Fallback handling: If the primary channel fails, the system will
    automatically retry on the next priority channel after 10 minutes.
    """

    @extend_schema(
        summary="Dispatch a notification event",
        description="""
Receives an event from external services and queues notifications
based on orchestration configuration.

**Example payload:**
```json
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
```

**Available context variables:**
- `{{Nombre}}` - Customer name
- `{{Placa}}` - Vehicle plate
- `{{Vehículo}}` - Vehicle brand and model
- `{{Fase}}` - Current phase name
- `{{Fecha}}` - Scheduled date
- `{{Hora}}` - Scheduled time
- `{{Orden}}` - Work order number
- `{{Técnico}}` - Assigned technician
- `{{Taller}}` - Workshop name
        """,
        request=EventDispatchSerializer,
        responses={
            202: OpenApiResponse(
                response=EventDispatchResponseSerializer,
                description="Event accepted and queued for processing",
            ),
            400: OpenApiResponse(description="Invalid request data"),
        },
        tags=["Events"],
    )
    def post(self, request):
        serializer = EventDispatchSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        data = serializer.validated_data

        # Build event payload
        payload = EventPayload(
            event_type=data["event_type"],
            service_type_id=data["service_type_id"],
            phase_id=data["phase_id"],
            customer_id=data["customer_id"],
            target=data["target"],
            context=data.get("context", {}),
            taller_id=data.get("taller_id"),
            subtype_id=data.get("subtype_id"),
            correlation_id=str(data["correlation_id"]) if data.get("correlation_id") else None,
        )

        # Process event through orchestration engine
        result = orchestration_engine.process_event(payload)

        # Build response
        response_data = {
            "success": result.success,
            "correlation_id": result.correlation_id,
            "notifications_queued": result.notifications_queued,
            "errors": result.errors,
        }

        response_serializer = EventDispatchResponseSerializer(response_data)

        return Response(
            response_serializer.data,
            status=status.HTTP_202_ACCEPTED,
        )
