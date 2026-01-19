"""
Views for internal API endpoints (service-to-service synchronization).
"""
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from drf_spectacular.utils import extend_schema
from celery.result import AsyncResult

from apps.core.authentication import InternalServiceAuthentication
from .serializers import (
    CustomerSyncSerializer,
    VehicleSyncSerializer,
    GlobalPhaseSyncSerializer,
    VehiclePhaseSyncSerializer,
)
from .tasks import (
    sync_customer_task,
    sync_vehicle_task,
    sync_global_phases_task,
    sync_vehicle_phases_task,
)


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


# ============================================================================
# Phase Synchronization Views
# ============================================================================

class SyncGlobalPhasesView(APIView):
    """
    Endpoint interno para sincronizar fases globales desde Core.

    Las fases globales definen el flujo de servicio del taller.
    Cuando se elimina una fase (sync_mode="full" y fase no en lista),
    se eliminan en cascada los PhaseChannelConfig asociados.

    Authentication:
        Requiere header X-Internal-Secret con API key compartida.

    Response:
        202 Accepted - La tarea de sincronización ha sido encolada.
    """

    authentication_classes = [InternalServiceAuthentication]

    @extend_schema(
        summary="Sync global phases from Core",
        description=(
            "Webhook endpoint for Core service to push global phase updates. "
            "Supports 'full' mode (replace all phases, CASCADE DELETE orphans) "
            "and 'partial' mode (update only provided phases, no deletions). "
            "Processed asynchronously by Celery."
        ),
        request=GlobalPhaseSyncSerializer,
        responses={
            202: {
                "description": "Accepted for processing",
                "example": {
                    "status": "accepted",
                    "message": "Global phases sync queued",
                    "task_id": "abc-123",
                    "phases_count": 5,
                    "sync_mode": "full",
                },
            },
            400: {"description": "Invalid payload"},
            401: {"description": "Invalid API key"},
        },
        tags=["Internal API"],
    )
    def post(self, request):
        """Queue global phases sync task."""
        serializer = GlobalPhaseSyncSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        task = sync_global_phases_task.delay(serializer.validated_data)

        return Response(
            {
                "status": "accepted",
                "message": "Global phases sync queued",
                "task_id": task.id,
                "phases_count": len(serializer.validated_data["phases"]),
                "sync_mode": serializer.validated_data.get("sync_mode", "partial"),
            },
            status=status.HTTP_202_ACCEPTED,
        )


class SyncVehiclePhasesView(APIView):
    """
    Endpoint interno para sincronizar configuración de fases por vehículo.

    Permite configurar:
    - Fases adicionales para un vehículo específico
    - Orden personalizado de fases
    - Activar/desactivar fases específicas

    Authentication:
        Requiere header X-Internal-Secret con API key compartida.

    Response:
        202 Accepted - La tarea de sincronización ha sido encolada.
        404 Not Found - El vehículo no existe.
    """

    authentication_classes = [InternalServiceAuthentication]

    @extend_schema(
        summary="Sync vehicle phase configuration",
        description=(
            "Configure custom phase settings for a specific vehicle. "
            "Phases must reference existing global ServicePhase slugs. "
            "Supports 'full' mode (replace all vehicle phases) "
            "and 'partial' mode (update only provided phases)."
        ),
        request=VehiclePhaseSyncSerializer,
        responses={
            202: {
                "description": "Accepted for processing",
                "example": {
                    "status": "accepted",
                    "message": "Vehicle phases sync queued",
                    "task_id": "abc-123",
                    "plate": "ABC-1234",
                    "phases_count": 5,
                },
            },
            400: {"description": "Invalid payload or unknown phase slugs"},
            401: {"description": "Invalid API key"},
            404: {"description": "Vehicle not found"},
        },
        tags=["Internal API"],
    )
    def post(self, request, plate):
        """Queue vehicle phases sync task."""
        from apps.notifications.models import Vehicle

        # Verificar que el vehículo existe
        if not Vehicle.objects.filter(plate=plate).exists():
            return Response(
                {"error": f"Vehículo con placa '{plate}' no encontrado"},
                status=status.HTTP_404_NOT_FOUND,
            )

        serializer = VehiclePhaseSyncSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        # Agregar plate a los datos de la tarea
        task_data = {
            "plate": plate,
            **serializer.validated_data,
        }

        task = sync_vehicle_phases_task.delay(task_data)

        return Response(
            {
                "status": "accepted",
                "message": "Vehicle phases sync queued",
                "task_id": task.id,
                "plate": plate,
                "phases_count": len(serializer.validated_data["phases"]),
            },
            status=status.HTTP_202_ACCEPTED,
        )
