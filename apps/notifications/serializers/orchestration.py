"""
Serializers for orchestration configuration.
"""
from rest_framework import serializers

from apps.notifications.models import (
    ServicePhase,
    ServiceType,
    OrchestrationConfig,
    PhaseChannelConfig,
)


class ServicePhaseSerializer(serializers.ModelSerializer):
    """
    Serializer for ServicePhase model.
    """

    class Meta:
        model = ServicePhase
        fields = ["id", "slug", "name", "icon", "order", "is_active", "description"]
        read_only_fields = ["id", "slug"]


class ServiceTypeSerializer(serializers.ModelSerializer):
    """
    Serializer for ServiceType model (without subtypes).
    """

    class Meta:
        model = ServiceType
        fields = ["id", "slug", "name", "icon", "parent", "is_active", "description"]
        read_only_fields = ["id", "slug"]


class ServiceTypeWithSubtypesSerializer(serializers.ModelSerializer):
    """
    Serializer for ServiceType with nested subtypes.
    """
    subtypes = serializers.SerializerMethodField()

    class Meta:
        model = ServiceType
        fields = ["id", "slug", "name", "icon", "is_active", "description", "subtypes"]
        read_only_fields = ["id", "slug"]

    def get_subtypes(self, obj):
        """Get child subtypes."""
        if obj.is_subtype:
            return []
        subtypes = obj.subtypes.filter(is_active=True)
        return ServiceTypeSerializer(subtypes, many=True).data


class PhaseChannelConfigSerializer(serializers.ModelSerializer):
    """
    Serializer for PhaseChannelConfig model.
    """
    phase_name = serializers.CharField(source="phase.name", read_only=True)
    template_name = serializers.CharField(source="template.name", read_only=True)

    class Meta:
        model = PhaseChannelConfig
        fields = [
            "id",
            "phase",
            "phase_name",
            "channel",
            "enabled",
            "template",
            "template_name",
        ]
        read_only_fields = ["id"]


class OrchestrationConfigSerializer(serializers.ModelSerializer):
    """
    Serializer for OrchestrationConfig model.
    """
    service_type_name = serializers.CharField(
        source="service_type.name",
        read_only=True,
    )
    phase_configs = PhaseChannelConfigSerializer(many=True, read_only=True)

    class Meta:
        model = OrchestrationConfig
        fields = [
            "id",
            "service_type",
            "service_type_name",
            "target",
            "taller_id",
            "is_active",
            "description",
            "phase_configs",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]


class OrchestrationConfigCreateSerializer(serializers.ModelSerializer):
    """
    Serializer for creating/updating orchestration configs.
    """

    class Meta:
        model = OrchestrationConfig
        fields = [
            "service_type",
            "target",
            "taller_id",
            "is_active",
            "description",
        ]


class PhaseChannelConfigUpdateSerializer(serializers.Serializer):
    """
    Serializer for batch updating phase channel configs.
    """
    phase_id = serializers.UUIDField()
    channel = serializers.ChoiceField(choices=["email", "push", "whatsapp"])
    enabled = serializers.BooleanField()
    template_id = serializers.UUIDField(required=False, allow_null=True)


class OrchestrationMatrixUpdateSerializer(serializers.Serializer):
    """
    Serializer for updating the entire orchestration matrix.
    """
    configs = PhaseChannelConfigUpdateSerializer(many=True)
