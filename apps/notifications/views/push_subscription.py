"""
Views for push subscription management.
"""
from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from drf_spectacular.utils import extend_schema, OpenApiResponse

from apps.notifications.models import PushSubscription
from apps.notifications.serializers.channels import (
    PushSubscriptionSerializer,
    PushSubscriptionCreateSerializer,
    PushSubscriptionDeleteSerializer,
)


class PushSubscriptionView(APIView):
    """
    Manage push notification subscriptions.

    POST: Subscribe to push notifications (create or update subscription)
    DELETE: Unsubscribe from push notifications
    """

    @extend_schema(
        summary="Subscribe to push notifications",
        description="""
Register a push subscription for a customer.
The subscription object comes from the browser's PushManager.subscribe().

**Example payload:**
```json
{
    "customer_id": "customer-001",
    "subscription": {
        "endpoint": "https://fcm.googleapis.com/fcm/send/...",
        "keys": {
            "p256dh": "base64-encoded-public-key",
            "auth": "base64-encoded-auth-secret"
        }
    },
    "user_agent": "Mozilla/5.0 ..."
}
```

This endpoint is called from the Next.js PWA after the user grants
notification permission and the service worker generates a subscription.
        """,
        request=PushSubscriptionCreateSerializer,
        responses={
            201: OpenApiResponse(
                response=PushSubscriptionSerializer,
                description="Subscription created",
            ),
            200: OpenApiResponse(
                response=PushSubscriptionSerializer,
                description="Subscription updated",
            ),
            400: OpenApiResponse(description="Invalid subscription data"),
        },
        tags=["Push"],
    )
    def post(self, request):
        serializer = PushSubscriptionCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        # Check if this is an update or create
        endpoint = serializer.validated_data["subscription"]["endpoint"]
        existing = PushSubscription.objects.filter(endpoint=endpoint).exists()

        subscription = serializer.save()

        response_serializer = PushSubscriptionSerializer(subscription)
        status_code = status.HTTP_200_OK if existing else status.HTTP_201_CREATED

        return Response(response_serializer.data, status=status_code)

    @extend_schema(
        summary="Unsubscribe from push notifications",
        description="""
Remove a push subscription.
Called when the user unsubscribes from notifications in the PWA.
        """,
        request=PushSubscriptionDeleteSerializer,
        responses={
            204: OpenApiResponse(description="Subscription removed"),
            404: OpenApiResponse(description="Subscription not found"),
        },
        tags=["Push"],
    )
    def delete(self, request):
        serializer = PushSubscriptionDeleteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        endpoint = serializer.validated_data["endpoint"]

        try:
            subscription = PushSubscription.objects.get(endpoint=endpoint)
            subscription.delete()
            return Response(status=status.HTTP_204_NO_CONTENT)
        except PushSubscription.DoesNotExist:
            return Response(
                {"error": "Subscription not found"},
                status=status.HTTP_404_NOT_FOUND,
            )


class PushSubscriptionStatusView(APIView):
    """
    Check push subscription status for a customer.
    """

    @extend_schema(
        summary="Check push subscription status",
        description="Check if a customer has an active push subscription.",
        responses={
            200: {
                "type": "object",
                "properties": {
                    "has_subscription": {"type": "boolean"},
                    "subscription_count": {"type": "integer"},
                },
            },
        },
        tags=["Push"],
    )
    def get(self, request, customer_id):
        subscriptions = PushSubscription.objects.filter(
            customer_id=customer_id,
            is_active=True,
        )

        return Response({
            "has_subscription": subscriptions.exists(),
            "subscription_count": subscriptions.count(),
        })
