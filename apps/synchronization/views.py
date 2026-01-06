"""
Views for internal API endpoints (service-to-service synchronization).
"""
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from drf_spectacular.utils import extend_schema
from celery.result import AsyncResult

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

        # Despachar tarea asíncrona inmediatamente y obtener el task_id
        task = sync_customer_task.delay(serializer.validated_data)

        return Response(
            {
                "status": "accepted",
                "message": "Customer sync queued",
                "task_id": task.id,  # Para rastrear la tarea
                "customer_id": serializer.validated_data.get("customer_id"),
            },
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

        # Despachar tarea asíncrona inmediatamente y obtener el task_id
        task = sync_vehicle_task.delay(serializer.validated_data)

        return Response(
            {
                "status": "accepted",
                "message": "Vehicle sync queued",
                "task_id": task.id,  # Para rastrear la tarea
                "plate": serializer.validated_data.get("plate"),
            },
            status=status.HTTP_202_ACCEPTED,
        )


class TaskStatusView(APIView):
    """
    Endpoint público para verificar el estado de una tarea de Celery.

    Útil para debugging y verificar si las tareas se están ejecutando correctamente.
    """

    @extend_schema(
        summary="Check task status",
        description="Check the status of a Celery task by its task_id",
        responses={
            200: {
                "description": "Task status",
                "example": {
                    "task_id": "abc-123-def-456",
                    "status": "SUCCESS",
                    "result": {"status": "success", "customer_id": "CLI-001"},
                    "ready": True,
                    "successful": True,
                    "failed": False,
                },
            },
        },
        tags=["Internal API"],
    )
    def get(self, request, task_id):
        """Get task status by task_id."""
        result = AsyncResult(task_id)

        response_data = {
            "task_id": task_id,
            "status": result.status,  # PENDING, STARTED, SUCCESS, FAILURE, RETRY
            "ready": result.ready(),
            "successful": result.successful() if result.ready() else None,
            "failed": result.failed() if result.ready() else None,
        }

        # Add result or error info if available
        if result.ready():
            if result.successful():
                response_data["result"] = result.result
            elif result.failed():
                response_data["error"] = str(result.info)
                response_data["traceback"] = result.traceback

        return Response(response_data)
