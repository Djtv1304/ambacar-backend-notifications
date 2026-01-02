"""
Serializers for customer data.
"""
from rest_framework import serializers

from apps.notifications.models import (
    CustomerContactInfo,
    CustomerChannelPreference,
    Vehicle,
    MaintenanceReminder,
)


class CustomerChannelPreferenceSerializer(serializers.ModelSerializer):
    """
    Serializer for CustomerChannelPreference model.
    """
    channel_display = serializers.CharField(
        source="get_channel_display",
        read_only=True,
    )

    class Meta:
        model = CustomerChannelPreference
        fields = ["id", "channel", "channel_display", "enabled", "priority"]
        read_only_fields = ["id"]


class CustomerContactInfoSerializer(serializers.ModelSerializer):
    """
    Serializer for CustomerContactInfo model.
    """
    full_name = serializers.CharField(read_only=True)
    channel_preferences = CustomerChannelPreferenceSerializer(many=True, read_only=True)

    class Meta:
        model = CustomerContactInfo
        fields = [
            "id",
            "customer_id",
            "first_name",
            "last_name",
            "full_name",
            "email",
            "phone",
            "whatsapp",
            "preferred_language",
            "avatar_url",
            "channel_preferences",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]


class CustomerContactInfoCreateSerializer(serializers.ModelSerializer):
    """
    Serializer for creating/updating customer contact info.
    """

    class Meta:
        model = CustomerContactInfo
        fields = [
            "customer_id",
            "first_name",
            "last_name",
            "email",
            "phone",
            "whatsapp",
            "preferred_language",
            "avatar_url",
        ]


class CustomerPreferencesUpdateSerializer(serializers.Serializer):
    """
    Serializer for updating customer preferences.
    """
    channels = serializers.ListField(
        child=serializers.DictField(),
        help_text="List of channel preferences with id, enabled, and priority",
    )

    def validate_channels(self, value):
        """Validate channel preferences."""
        valid_channels = ["email", "push", "whatsapp"]
        for pref in value:
            if "channel" not in pref:
                raise serializers.ValidationError("Each preference must have a channel")
            if pref["channel"] not in valid_channels:
                raise serializers.ValidationError(
                    f"Invalid channel: {pref['channel']}"
                )
        return value


class VehicleSerializer(serializers.ModelSerializer):
    """
    Serializer for Vehicle model.
    """
    display_name = serializers.CharField(read_only=True)
    remaining_km = serializers.SerializerMethodField()

    class Meta:
        model = Vehicle
        fields = [
            "id",
            "customer_id",
            "brand",
            "model",
            "year",
            "plate",
            "display_name",
            "current_kilometers",
            "last_service_date",
            "next_service_kilometers",
            "remaining_km",
            "image_url",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]

    def get_remaining_km(self, obj) -> int | None:
        return obj.get_remaining_km()


class MaintenanceReminderSerializer(serializers.ModelSerializer):
    """
    Serializer for MaintenanceReminder model.
    """
    vehicle_plate = serializers.CharField(source="vehicle.plate", read_only=True)
    vehicle_display = serializers.CharField(source="vehicle.display_name", read_only=True)
    status_display = serializers.CharField(source="get_status_display", read_only=True)
    type_display = serializers.CharField(source="get_type_display", read_only=True)

    class Meta:
        model = MaintenanceReminder
        fields = [
            "id",
            "vehicle",
            "vehicle_plate",
            "vehicle_display",
            "customer_id",
            "type",
            "type_display",
            "description",
            "target_kilometers",
            "target_date",
            "notify_via",
            "status",
            "status_display",
            "notify_before_days",
            "notify_before_km",
            "last_notified_at",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at", "last_notified_at"]
