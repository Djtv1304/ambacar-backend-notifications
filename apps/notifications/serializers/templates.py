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
        ]

    def validate_body(self, value):
        """Validate that the template body is not empty."""
        if not value or not value.strip():
            raise serializers.ValidationError("Template body cannot be empty")
        return value


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
