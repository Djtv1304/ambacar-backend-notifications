"""
Views for notification templates.
"""
from django.db import models
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
        queryset = NotificationTemplate.objects.select_related(
            "service_type", "phase", "subtype"
        ).all()

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

        # Filter by service_type
        service_type_id = self.request.query_params.get("service_type_id")
        if service_type_id:
            queryset = queryset.filter(service_type_id=service_type_id)

        # Filter by phase
        phase_id = self.request.query_params.get("phase_id")
        if phase_id:
            queryset = queryset.filter(phase_id=phase_id)

        # Filter by subtype (includes templates without subtype)
        subtype_id = self.request.query_params.get("subtype_id")
        if subtype_id:
            # Include templates specific to the subtype OR generic (no subtype)
            queryset = queryset.filter(
                models.Q(subtype_id=subtype_id) |
                models.Q(subtype__isnull=True)
            )

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

        Performs dynamic validation: extracts all variables from the template
        and validates that they exist in the provided context (accent-insensitive).
        """
        serializer = TemplatePreviewSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        body = serializer.validated_data["body"]
        context = serializer.validated_data.get("context", {})

        # Dynamic validation: Extract variables from template body
        template_variables = template_service.get_variables(body)

        if template_variables and context:
            # Normalize both template variables and context keys (accent-insensitive)
            normalized_required = {template_service._normalize(var) for var in template_variables}
            normalized_context_keys = {template_service._normalize(k) for k in context.keys()}

            # Find missing variables
            missing_variables = normalized_required - normalized_context_keys

            if missing_variables:
                return Response(
                    {
                        "error": f"Missing required template variables: {', '.join(sorted(missing_variables))}",
                        "missing_variables": sorted(list(missing_variables)),
                        "hint": "Provide these fields in the 'context' object",
                        "template_variables": sorted(list(template_variables)),
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )

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

    @extend_schema(
        summary="Get templates for specific context",
        description=(
            "Get templates filtered by context (service_type + phase + channel + target). "
            "If subtype_id is provided, returns templates specific to that subtype AND generic templates."
        ),
        parameters=[
            OpenApiParameter(
                "service_type_id",
                str,
                required=True,
                description="Service type ID (required)"
            ),
            OpenApiParameter(
                "phase_id",
                str,
                required=True,
                description="Phase ID (required)"
            ),
            OpenApiParameter(
                "channel",
                str,
                required=True,
                description="Notification channel: email, push, whatsapp (required)"
            ),
            OpenApiParameter(
                "target",
                str,
                required=True,
                description="Target audience: clients or staff (required)"
            ),
            OpenApiParameter(
                "subtype_id",
                str,
                required=False,
                description="Subtype ID (optional, for services with subtypes)"
            ),
        ],
        responses={200: NotificationTemplateSerializer(many=True)},
        tags=["Templates"],
    )
    @action(detail=False, methods=["get"])
    def for_context(self, request):
        """
        Get templates filtered by context.
        Returns templates that match service_type + phase + channel + target.
        If subtype_id provided, includes subtype-specific AND generic templates.
        """
        service_type_id = request.query_params.get("service_type_id")
        phase_id = request.query_params.get("phase_id")
        channel = request.query_params.get("channel")
        target = request.query_params.get("target")
        subtype_id = request.query_params.get("subtype_id")

        # Validate required parameters
        if not all([service_type_id, phase_id, channel, target]):
            return Response(
                {"error": "service_type_id, phase_id, channel, and target are required"},
                status=status.HTTP_400_BAD_REQUEST
            )

        queryset = NotificationTemplate.objects.select_related(
            "service_type", "phase", "subtype"
        ).filter(
            service_type_id=service_type_id,
            phase_id=phase_id,
            channel=channel,
            target=target,
            is_active=True
        )

        if subtype_id:
            # Include templates specific to the subtype OR generic (no subtype)
            queryset = queryset.filter(
                models.Q(subtype_id=subtype_id) |
                models.Q(subtype__isnull=True)
            )
        else:
            # Only include templates without subtype
            queryset = queryset.filter(subtype__isnull=True)

        # Order by subtype (specific first, then generic)
        queryset = queryset.order_by("-subtype_id", "-is_default", "name")

        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)
