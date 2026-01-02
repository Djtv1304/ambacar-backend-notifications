"""
Serializers for channel configuration and push subscriptions.
"""
from rest_framework import serializers

from apps.notifications.models import TallerChannelConfig, PushSubscription


class TallerChannelConfigSerializer(serializers.ModelSerializer):
    """
    Serializer for TallerChannelConfig model.
    """
    enabled_channels = serializers.SerializerMethodField()

    class Meta:
        model = TallerChannelConfig
        fields = [
            "id",
            "taller_id",
            "taller_name",
            "email_enabled",
            "email_configured",
            "push_enabled",
            "push_configured",
            "whatsapp_enabled",
            "whatsapp_configured",
            "enabled_channels",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]

    def get_enabled_channels(self, obj) -> list:
        return obj.get_enabled_channels()


class PushSubscriptionSerializer(serializers.ModelSerializer):
    """
    Serializer for PushSubscription model (read-only).
    """

    class Meta:
        model = PushSubscription
        fields = [
            "id",
            "customer_id",
            "is_active",
            "last_used_at",
            "failure_count",
            "created_at",
        ]
        read_only_fields = fields


class PushSubscriptionCreateSerializer(serializers.Serializer):
    """
    Serializer for creating a push subscription.

    The frontend sends subscription info from PushManager.subscribe():
    {
        "customer_id": "customer-001",
        "subscription": {
            "endpoint": "https://fcm.googleapis.com/fcm/send/...",
            "keys": {
                "p256dh": "base64-encoded-key",
                "auth": "base64-encoded-auth"
            }
        }
    }
    """
    customer_id = serializers.CharField(
        max_length=100,
        help_text="Customer identifier",
    )
    subscription = serializers.DictField(
        help_text="PushSubscription object from browser",
    )
    user_agent = serializers.CharField(
        max_length=500,
        required=False,
        allow_blank=True,
        help_text="Browser user agent for debugging",
    )

    def validate_subscription(self, value):
        """Validate subscription object structure."""
        if "endpoint" not in value:
            raise serializers.ValidationError("Subscription must have an endpoint")

        keys = value.get("keys", {})
        if "p256dh" not in keys or "auth" not in keys:
            raise serializers.ValidationError(
                "Subscription keys must include p256dh and auth"
            )

        return value

    def create(self, validated_data):
        """Create or update push subscription."""
        subscription = validated_data["subscription"]
        endpoint = subscription["endpoint"]
        keys = subscription["keys"]

        # Update or create subscription
        push_sub, created = PushSubscription.objects.update_or_create(
            endpoint=endpoint,
            defaults={
                "customer_id": validated_data["customer_id"],
                "p256dh_key": keys["p256dh"],
                "auth_key": keys["auth"],
                "user_agent": validated_data.get("user_agent"),
                "is_active": True,
                "failure_count": 0,
            }
        )

        return push_sub


class PushSubscriptionDeleteSerializer(serializers.Serializer):
    """
    Serializer for deleting a push subscription.
    """
    endpoint = serializers.CharField(
        help_text="Push subscription endpoint to unsubscribe",
    )
