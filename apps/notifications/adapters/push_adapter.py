"""
Web Push adapter using py-webpush (VAPID).
"""
import json
import logging

from django.conf import settings

from apps.core.ports import NotificationGateway, NotificationPayload, NotificationResult

logger = logging.getLogger(__name__)


class WebPushAdapter(NotificationGateway):
    """
    Adapter: Web Push notifications using VAPID (py-webpush).

    This works with the Next.js PWA frontend which handles:
    - Service Worker registration
    - User permission request
    - PushSubscription generation

    The subscription info is stored in PushSubscription model.
    """

    @property
    def channel_name(self) -> str:
        return "push"

    def send(self, payload: NotificationPayload) -> NotificationResult:
        """
        Send a Web Push notification.

        Args:
            payload: Contains:
                - recipient: customer_id
                - body: notification message
                - subject: notification title
                - metadata: should contain subscription_info or will be looked up

        Returns:
            NotificationResult with success status
        """
        try:
            from pywebpush import webpush, WebPushException
        except ImportError:
            return NotificationResult(
                success=False,
                error_message="py-webpush is not installed",
                error_code="PUSH_NOT_INSTALLED",
            )

        if not self.is_configured():
            return NotificationResult(
                success=False,
                error_message="VAPID keys are not configured",
                error_code="PUSH_NOT_CONFIGURED",
            )

        # Get subscription info from metadata or database
        subscription_info = payload.metadata.get("subscription_info")

        if not subscription_info:
            # Look up from database
            subscription_info = self._get_subscription_from_db(payload.recipient)
            if not subscription_info:
                return NotificationResult(
                    success=False,
                    error_message="No active push subscription found",
                    error_code="NO_PUSH_SUBSCRIPTION",
                )

        # Build push notification data
        push_data = json.dumps({
            "title": payload.subject or "Ambacar",
            "body": payload.body,
            "icon": "/icon-192x192.png",
            "badge": "/badge-72x72.png",
            "vibrate": [100, 50, 100],
            "data": payload.metadata.get("data", {}),
        })

        try:
            webpush(
                subscription_info=subscription_info,
                data=push_data,
                vapid_private_key=settings.VAPID_PRIVATE_KEY,
                vapid_claims={
                    "sub": f"mailto:{settings.VAPID_CONTACT_EMAIL}"
                }
            )

            logger.info(f"Push notification sent to {payload.recipient}")

            # Update subscription success
            self._mark_subscription_success(subscription_info["endpoint"])

            return NotificationResult(success=True)

        except WebPushException as e:
            logger.error(f"WebPush error for {payload.recipient}: {str(e)}")

            # Handle expired/unsubscribed subscriptions (HTTP 410)
            if e.response and e.response.status_code == 410:
                self._deactivate_subscription(subscription_info["endpoint"])
                return NotificationResult(
                    success=False,
                    error_message="Push subscription expired or unsubscribed",
                    error_code="PUSH_SUBSCRIPTION_EXPIRED",
                )

            # Handle other HTTP errors
            if e.response and e.response.status_code == 404:
                self._deactivate_subscription(subscription_info["endpoint"])
                return NotificationResult(
                    success=False,
                    error_message="Push subscription not found",
                    error_code="PUSH_SUBSCRIPTION_NOT_FOUND",
                )

            return NotificationResult(
                success=False,
                error_message=str(e),
                error_code="WEBPUSH_ERROR",
            )

        except Exception as e:
            logger.error(f"Unexpected push error for {payload.recipient}: {str(e)}")
            return NotificationResult(
                success=False,
                error_message=str(e),
                error_code="PUSH_UNEXPECTED_ERROR",
            )

    def validate_recipient(self, recipient: str) -> bool:
        """
        For push, recipient is customer_id.
        Validate that an active subscription exists.
        """
        from apps.notifications.models import PushSubscription
        return PushSubscription.objects.filter(
            customer_id=recipient,
            is_active=True,
        ).exists()

    def is_configured(self) -> bool:
        """
        Check if VAPID keys are configured.
        """
        return bool(
            settings.VAPID_PUBLIC_KEY and
            settings.VAPID_PRIVATE_KEY and
            settings.VAPID_CONTACT_EMAIL
        )

    def _get_subscription_from_db(self, customer_id: str) -> dict | None:
        """
        Look up subscription info from database.
        """
        from apps.notifications.models import PushSubscription

        try:
            sub = PushSubscription.objects.filter(
                customer_id=customer_id,
                is_active=True,
            ).order_by("-last_used_at").first()

            if not sub:
                return None

            return {
                "endpoint": sub.endpoint,
                "keys": {
                    "p256dh": sub.p256dh_key,
                    "auth": sub.auth_key,
                }
            }
        except PushSubscription.DoesNotExist:
            return None

    def _deactivate_subscription(self, endpoint: str):
        """
        Deactivate a subscription that is no longer valid.
        """
        from apps.notifications.models import PushSubscription
        PushSubscription.objects.filter(endpoint=endpoint).update(is_active=False)
        logger.info(f"Deactivated push subscription: {endpoint[:50]}...")

    def _mark_subscription_success(self, endpoint: str):
        """
        Mark subscription as successfully used.
        """
        from apps.notifications.models import PushSubscription
        from django.utils import timezone
        PushSubscription.objects.filter(endpoint=endpoint).update(
            failure_count=0,
            last_used_at=timezone.now(),
        )
