"""
Views for internal API endpoints (service-to-service synchronization).
"""
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from drf_spectacular.utils import extend_schema

from apps.core.authentication import InternalServiceAuthentication
from .serializers import CustomerSyncSerializer, VehicleSyncSerializer
from .tasks import sync_customer_task, sync_vehicle_task


class SyncCustomerView(APIView):
    """
    Endpoint interno para recibir actualizaciones de clientes desde Core.

    Este endpoint acepta webhooks del microservicio Core con datos de clientes
    para sincronizar localmente usando el patrón Table Projection.

    Authentication:
        Requiere header X-Internal-Secret con API key compartida.

    Response:
        202 Accepted - La tarea de sincronización ha sido encolada.
    """

    authentication_classes = [InternalServiceAuthentication]

    @extend_schema(
        summary="Sync customer from Core",
        description=(
            "Webhook endpoint for Core service to push customer updates. "
            "The request is queued immediately and processed asynchronously by Celery."
        ),
        request=CustomerSyncSerializer,
        responses={
            202: {
                "description": "Accepted for processing",
                "example": {
                    "status": "accepted",
                    "message": "Customer sync queued",
                },
            },
            400: {
                "description": "Invalid payload",
                "example": {"customer_id": ["This field is required."]},
            },
            401: {
                "description": "Invalid API key",
                "example": {"detail": "Invalid internal API key"},
            },
        },
        tags=["Internal API"],
    )
    def post(self, request):
        """Queue customer sync task."""
        serializer = CustomerSyncSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        # Despachar tarea asíncrona inmediatamente
        sync_customer_task.delay(serializer.validated_data)

        return Response(
            {"status": "accepted", "message": "Customer sync queued"},
            status=status.HTTP_202_ACCEPTED,
        )


class SyncVehicleView(APIView):
    """
    Endpoint interno para recibir actualizaciones de vehículos desde Core.

    Este endpoint acepta webhooks del microservicio Core con datos de vehículos
    para sincronizar localmente usando el patrón Table Projection.

    Authentication:
        Requiere header X-Internal-Secret con API key compartida.

    Response:
        202 Accepted - La tarea de sincronización ha sido encolada.
    """

    authentication_classes = [InternalServiceAuthentication]

    @extend_schema(
        summary="Sync vehicle from Core",
        description=(
            "Webhook endpoint for Core service to push vehicle updates. "
            "The request is queued immediately and processed asynchronously by Celery."
        ),
        request=VehicleSyncSerializer,
        responses={
            202: {
                "description": "Accepted for processing",
                "example": {
                    "status": "accepted",
                    "message": "Vehicle sync queued",
                },
            },
            400: {
                "description": "Invalid payload",
                "example": {"plate": ["This field is required."]},
            },
            401: {
                "description": "Invalid API key",
                "example": {"detail": "Invalid internal API key"},
            },
        },
        tags=["Internal API"],
    )
    def post(self, request):
        """Queue vehicle sync task."""
        serializer = VehicleSyncSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        # Despachar tarea asíncrona inmediatamente
        sync_vehicle_task.delay(serializer.validated_data)

        return Response(
            {"status": "accepted", "message": "Vehicle sync queued"},
            status=status.HTTP_202_ACCEPTED,
        )
