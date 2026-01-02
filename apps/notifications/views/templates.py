"""
Views for notification templates.
"""
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from drf_spectacular.utils import extend_schema, extend_schema_view, OpenApiParameter

from apps.core.constants import TEMPLATE_VARIABLES
from apps.notifications.models import NotificationTemplate
from apps.notifications.serializers.templates import (
    NotificationTemplateSerializer,
    NotificationTemplateCreateSerializer,
    TemplatePreviewSerializer,
    TemplateVariablesSerializer,
)
from apps.notifications.services.template_service import template_service


@extend_schema_view(
    list=extend_schema(
        summary="List notification templates",
        description="Get all notification templates, optionally filtered by channel or target.",
        tags=["Templates"],
    ),
    retrieve=extend_schema(
        summary="Get template details",
        tags=["Templates"],
    ),
    create=extend_schema(
        summary="Create a new template",
        tags=["Templates"],
    ),
    update=extend_schema(
        summary="Update a template",
        tags=["Templates"],
    ),
    partial_update=extend_schema(
        summary="Partially update a template",
        tags=["Templates"],
    ),
    destroy=extend_schema(
        summary="Delete a template",
        tags=["Templates"],
    ),
)
class NotificationTemplateViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing notification templates.
    """
    queryset = NotificationTemplate.objects.all()
    serializer_class = NotificationTemplateSerializer

    def get_serializer_class(self):
        if self.action in ["create", "update", "partial_update"]:
            return NotificationTemplateCreateSerializer
        return NotificationTemplateSerializer

    def get_queryset(self):
        queryset = NotificationTemplate.objects.all()

        # Filter by channel
        channel = self.request.query_params.get("channel")
        if channel:
            queryset = queryset.filter(channel=channel)

        # Filter by target
        target = self.request.query_params.get("target")
        if target:
            queryset = queryset.filter(target=target)

        # Filter by taller_id
        taller_id = self.request.query_params.get("taller_id")
        if taller_id:
            queryset = queryset.filter(taller_id=taller_id)

        # Filter by active status
        is_active = self.request.query_params.get("is_active")
        if is_active is not None:
            queryset = queryset.filter(is_active=is_active.lower() == "true")

        return queryset.order_by("-created_at")

    @extend_schema(
        summary="Preview a template",
        description="Render a template with example or provided values.",
        request=TemplatePreviewSerializer,
        responses={200: {"type": "object", "properties": {"preview": {"type": "string"}}}},
        tags=["Templates"],
    )
    @action(detail=False, methods=["post"])
    def preview(self, request):
        """
        Preview a template with example values.
        """
        serializer = TemplatePreviewSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        body = serializer.validated_data["body"]
        context = serializer.validated_data.get("context", {})

        # Use provided context or fall back to examples
        preview = template_service.preview_template(body, context)

        return Response({"preview": preview})

    @extend_schema(
        summary="Get available template variables",
        description="List all available variables that can be used in templates.",
        responses={200: TemplateVariablesSerializer(many=True)},
        tags=["Templates"],
    )
    @action(detail=False, methods=["get"])
    def variables(self, request):
        """
        Get list of available template variables.
        """
        serializer = TemplateVariablesSerializer(TEMPLATE_VARIABLES, many=True)
        return Response(serializer.data)
