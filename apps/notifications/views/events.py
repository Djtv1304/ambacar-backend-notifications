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
from apps.notifications.services.template_service import template_service


# Minimum universal context fields (basic validation before dispatch)
# These are the most common fields that almost all templates use
# Full dynamic validation happens in orchestration_engine based on actual template
MINIMUM_CONTEXT_FIELDS = {
    "clients": [
        "nombre",    # Customer name (universal)
        "vehiculo",  # Vehicle brand/model (universal)
        "placa",     # Vehicle plate (universal)
    ],
    "staff": [
        "nombre",    # Customer/staff name (universal)
        "vehiculo",  # Vehicle in service (universal)
        "placa",     # Vehicle plate (universal)
    ],
}


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
                description="Event accepted and notifications queued successfully",
            ),
            400: OpenApiResponse(
                response=EventDispatchResponseSerializer,
                description=(
                    "Bad request - Invalid data (e.g., service type not found, "
                    "customer not found, missing required data)"
                ),
            ),
            500: OpenApiResponse(
                response=EventDispatchResponseSerializer,
                description="Internal server error during event processing",
            ),
        },
        tags=["Events"],
    )
    def post(self, request):
        serializer = EventDispatchSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        data = serializer.validated_data

        # Basic validation: Check minimum universal fields
        # Skip this validation for custom events (they have different requirements)
        # Full dynamic validation (based on actual template variables) happens in orchestration_engine
        from apps.core.constants import EventType

        if data["event_type"] != EventType.CUSTOM:
            target = data.get("target", "clients")
            minimum_fields = MINIMUM_CONTEXT_FIELDS.get(target, [])

            # Normalize context keys for comparison (accent-insensitive)
            normalized_context_keys = {
                template_service._normalize(k)
                for k in data.get("context", {}).keys()
            }

            missing_minimum_fields = [
                field for field in minimum_fields
                if field not in normalized_context_keys
            ]

            if missing_minimum_fields:
                return Response(
                    {
                        "success": False,
                        "error": f"Missing minimum required context fields: {', '.join(missing_minimum_fields)}",
                        "missing_fields": missing_minimum_fields,
                        "hint": "Provide at least these universal fields in the 'context' object",
                        "minimum_fields": minimum_fields,
                        "correlation_id": str(data["correlation_id"]) if data.get("correlation_id") else None,
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )

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

        # Check if we should retry asynchronously (race condition detected)
        if not result.success:
            retryable_errors = ["customer", "not found", "not synced", "does not exist"]
            is_retryable = any(
                err_keyword in " ".join(result.errors).lower()
                for err_keyword in retryable_errors
            )

            if is_retryable:
                # Customer not found or similar race condition
                # Queue async task with retries instead of failing immediately
                from apps.notifications.tasks import dispatch_event_task

                # Convert payload to dict for Celery serialization
                event_dict = {
                    "event_type": payload.event_type,
                    "service_type_id": payload.service_type_id,
                    "phase_id": payload.phase_id,
                    "customer_id": payload.customer_id,
                    "target": payload.target,
                    "context": payload.context,
                    "taller_id": payload.taller_id,
                    "subtype_id": payload.subtype_id,
                    "correlation_id": result.correlation_id,
                }

                # Queue task with retries (2s, 4s, 8s delays)
                task = dispatch_event_task.apply_async(args=[event_dict])

                logger.info(
                    f"🔄 Retryable error detected for customer {payload.customer_id}. "
                    f"Queued async task {task.id} with automatic retries."
                )

                return Response(
                    {
                        "success": True,  # Task queued successfully
                        "correlation_id": result.correlation_id,
                        "notifications_queued": 0,
                        "message": (
                            "Customer not immediately available. "
                            "Event queued for processing with automatic retries."
                        ),
                        "task_id": task.id,
                        "retry_strategy": "Will retry after 2s, 4s, and 8s if needed",
                    },
                    status=status.HTTP_202_ACCEPTED,
                )

        # Build response
        response_data = {
            "success": result.success,
            "correlation_id": result.correlation_id,
            "notifications_queued": result.notifications_queued,
            "errors": result.errors,
        }

        response_serializer = EventDispatchResponseSerializer(response_data)

        # Determine appropriate HTTP status code
        if result.success:
            # Successfully queued notifications
            http_status = status.HTTP_202_ACCEPTED
        else:
            # Check if it's a validation error (service type not found, customer not found, etc.)
            # These indicate client-side issues with the request
            if any(
                err_msg in " ".join(result.errors).lower()
                for err_msg in [
                    "not found",
                    "no orchestration config",
                    "no es un uuid válido",
                    "is not a valid uuid",
                ]
            ):
                http_status = status.HTTP_400_BAD_REQUEST
            else:
                # Other errors are considered server-side issues
                http_status = status.HTTP_500_INTERNAL_SERVER_ERROR

        return Response(
            response_serializer.data,
            status=http_status,
        )
