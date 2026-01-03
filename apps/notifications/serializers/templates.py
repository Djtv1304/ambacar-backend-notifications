"""
Serializers for notification templates.
"""
from rest_framework import serializers

from apps.notifications.models import NotificationTemplate
from apps.notifications.services.template_service import template_service


class NotificationTemplateSerializer(serializers.ModelSerializer):
    """
    Serializer for NotificationTemplate model.
    """
    variables = serializers.SerializerMethodField(read_only=True)
    preview = serializers.SerializerMethodField(read_only=True)
    service_type_name = serializers.SerializerMethodField(read_only=True)
    phase_name = serializers.SerializerMethodField(read_only=True)
    subtype_name = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = NotificationTemplate
        fields = [
            "id",
            "name",
            "subject",
            "body",
            "channel",
            "target",
            "is_default",
            "is_active",
            "taller_id",
            "service_type_id",
            "service_type_name",
            "phase_id",
            "phase_name",
            "subtype_id",
            "subtype_name",
            "variables",
            "preview",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]

    def get_variables(self, obj) -> list:
        """Extract variables from the template body."""
        return obj.get_variables()

    def get_preview(self, obj) -> str:
        """Preview the template with example values."""
        return template_service.preview_template(obj.body)

    def get_service_type_name(self, obj) -> str:
        """Get the service type name."""
        return obj.service_type.name if obj.service_type else None

    def get_phase_name(self, obj) -> str:
        """Get the phase name."""
        return obj.phase.name if obj.phase else None

    def get_subtype_name(self, obj) -> str | None:
        """Get the subtype name if exists."""
        return obj.subtype.name if obj.subtype else None


class NotificationTemplateCreateSerializer(serializers.ModelSerializer):
    """
    Serializer for creating/updating templates.
    """

    class Meta:
        model = NotificationTemplate
        fields = [
            "name",
            "subject",
            "body",
            "channel",
            "target",
            "is_default",
            "is_active",
            "taller_id",
            "service_type",  # OBLIGATORIO
            "phase",         # OBLIGATORIO
            "subtype",       # OPCIONAL
        ]

    def validate_body(self, value):
        """Validate that the template body is not empty."""
        if not value or not value.strip():
            raise serializers.ValidationError("Template body cannot be empty")
        return value

    def validate(self, data):
        """Validate that subtype belongs to service_type."""
        service_type = data.get("service_type")
        subtype = data.get("subtype")

        if subtype and subtype.parent != service_type:
            raise serializers.ValidationError({
                "subtype": "El subtipo debe pertenecer al tipo de servicio seleccionado"
            })

        return data


class TemplatePreviewSerializer(serializers.Serializer):
    """
    Serializer for template preview requests.
    """
    body = serializers.CharField()
    context = serializers.DictField(
        child=serializers.CharField(),
        required=False,
        default=dict,
    )


class TemplateVariablesSerializer(serializers.Serializer):
    """
    Serializer for available template variables.
    """
    id = serializers.CharField()
    label = serializers.CharField()
    description = serializers.CharField()
    example = serializers.CharField()
