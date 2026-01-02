"""
Views for orchestration configuration.
"""
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from drf_spectacular.utils import extend_schema, extend_schema_view

from apps.notifications.models import (
    ServicePhase,
    ServiceType,
    OrchestrationConfig,
    PhaseChannelConfig,
)
from apps.notifications.serializers.orchestration import (
    ServicePhaseSerializer,
    ServiceTypeSerializer,
    ServiceTypeWithSubtypesSerializer,
    OrchestrationConfigSerializer,
    OrchestrationConfigCreateSerializer,
    OrchestrationMatrixUpdateSerializer,
)


@extend_schema_view(
    list=extend_schema(
        summary="List service phases",
        description="Get all service phases in order.",
        tags=["Orchestration"],
    ),
    retrieve=extend_schema(
        summary="Get phase details",
        tags=["Orchestration"],
    ),
)
class ServicePhaseViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet for service phases (read-only).
    Phases are typically seeded and not modified via API.
    """
    queryset = ServicePhase.objects.filter(is_active=True).order_by("order")
    serializer_class = ServicePhaseSerializer


@extend_schema_view(
    list=extend_schema(
        summary="List service types",
        description="Get all service types with their subtypes.",
        tags=["Orchestration"],
    ),
    retrieve=extend_schema(
        summary="Get service type details",
        tags=["Orchestration"],
    ),
)
class ServiceTypeViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet for service types (read-only).
    Service types are typically seeded and not modified via API.
    """
    serializer_class = ServiceTypeWithSubtypesSerializer

    def get_queryset(self):
        # Only return top-level types (not subtypes)
        return ServiceType.objects.filter(
            is_active=True,
            parent__isnull=True,
        ).order_by("name")


@extend_schema_view(
    list=extend_schema(
        summary="List orchestration configs",
        description="Get all orchestration configurations.",
        tags=["Orchestration"],
    ),
    retrieve=extend_schema(
        summary="Get orchestration config details",
        description="Get full orchestration config with phase channel settings.",
        tags=["Orchestration"],
    ),
    create=extend_schema(
        summary="Create orchestration config",
        tags=["Orchestration"],
    ),
    update=extend_schema(
        summary="Update orchestration config",
        tags=["Orchestration"],
    ),
    partial_update=extend_schema(
        summary="Partially update orchestration config",
        tags=["Orchestration"],
    ),
    destroy=extend_schema(
        summary="Delete orchestration config",
        tags=["Orchestration"],
    ),
)
class OrchestrationConfigViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing orchestration configurations.
    """
    queryset = OrchestrationConfig.objects.all()
    serializer_class = OrchestrationConfigSerializer

    def get_serializer_class(self):
        if self.action in ["create", "update", "partial_update"]:
            return OrchestrationConfigCreateSerializer
        return OrchestrationConfigSerializer

    def get_queryset(self):
        queryset = OrchestrationConfig.objects.select_related(
            "service_type"
        ).prefetch_related(
            "phase_configs",
            "phase_configs__phase",
            "phase_configs__template",
        )

        # Filter by service_type
        service_type_id = self.request.query_params.get("service_type_id")
        if service_type_id:
            queryset = queryset.filter(service_type_id=service_type_id)

        # Filter by target
        target = self.request.query_params.get("target")
        if target:
            queryset = queryset.filter(target=target)

        # Filter by taller_id
        taller_id = self.request.query_params.get("taller_id")
        if taller_id:
            queryset = queryset.filter(taller_id=taller_id)

        return queryset

    @extend_schema(
        summary="Update phase channel matrix",
        description="Batch update phase channel configurations for this orchestration config.",
        request=OrchestrationMatrixUpdateSerializer,
        responses={200: OrchestrationConfigSerializer},
        tags=["Orchestration"],
    )
    @action(detail=True, methods=["post"])
    def update_matrix(self, request, pk=None):
        """
        Batch update phase channel configurations.
        """
        config = self.get_object()
        serializer = OrchestrationMatrixUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        for item in serializer.validated_data["configs"]:
            PhaseChannelConfig.objects.update_or_create(
                orchestration_config=config,
                phase_id=item["phase_id"],
                channel=item["channel"],
                defaults={
                    "enabled": item["enabled"],
                    "template_id": item.get("template_id"),
                }
            )

        # Return updated config
        config.refresh_from_db()
        return Response(OrchestrationConfigSerializer(config).data)

    @extend_schema(
        summary="Initialize phase configs",
        description="Create default phase channel configs for all phases and channels.",
        responses={200: OrchestrationConfigSerializer},
        tags=["Orchestration"],
    )
    @action(detail=True, methods=["post"])
    def initialize_phases(self, request, pk=None):
        """
        Initialize phase channel configs for all phases and channels.
        Creates entries with enabled=False for any missing combinations.
        """
        config = self.get_object()
        phases = ServicePhase.objects.filter(is_active=True)
        channels = ["email", "push", "whatsapp"]

        for phase in phases:
            for channel in channels:
                PhaseChannelConfig.objects.get_or_create(
                    orchestration_config=config,
                    phase=phase,
                    channel=channel,
                    defaults={"enabled": False},
                )

        config.refresh_from_db()
        return Response(OrchestrationConfigSerializer(config).data)
