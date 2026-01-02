"""
Views for notification analytics.
"""
from datetime import timedelta

from django.db.models import Count, Avg, F
from django.db.models.functions import TruncDate
from django.utils import timezone
from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import serializers
from drf_spectacular.utils import extend_schema, OpenApiParameter, OpenApiResponse

from apps.notifications.models import NotificationLog
from apps.core.constants import NotificationStatus


class AnalyticsSummarySerializer(serializers.Serializer):
    """
    Serializer for analytics summary response.
    """
    period_start = serializers.DateTimeField()
    period_end = serializers.DateTimeField()

    total_sent = serializers.IntegerField()
    total_delivered = serializers.IntegerField()
    total_failed = serializers.IntegerField()
    total_pending = serializers.IntegerField()
    delivery_rate = serializers.FloatField()

    avg_delivery_time_seconds = serializers.FloatField(allow_null=True)

    by_channel = serializers.DictField()
    by_status = serializers.DictField()
    by_event_type = serializers.DictField()
    daily_breakdown = serializers.ListField()


class RecentNotificationsSerializer(serializers.Serializer):
    """
    Serializer for recent notification log entries.
    """
    id = serializers.UUIDField()
    event_type = serializers.CharField()
    channel = serializers.CharField()
    recipient_id = serializers.CharField()
    status = serializers.CharField()
    sent_at = serializers.DateTimeField()
    created_at = serializers.DateTimeField()
    template_name = serializers.CharField()
    error_reason = serializers.CharField(allow_null=True)


class AnalyticsSummaryView(APIView):
    """
    GET /api/v1/analytics/summary/

    Returns aggregated notification analytics for the dashboard.
    """

    @extend_schema(
        summary="Get notification analytics summary",
        description="""
Returns aggregated notification statistics including:
- Total sent, delivered, failed counts
- Delivery rate percentage
- Average delivery time
- Breakdown by channel (email, whatsapp, push)
- Breakdown by status
- Daily trend data

Use the `days` query parameter to specify the time period (default: 30 days).
        """,
        parameters=[
            OpenApiParameter(
                name="days",
                type=int,
                location=OpenApiParameter.QUERY,
                description="Number of days to include (default: 30)",
                default=30,
            ),
        ],
        responses={
            200: OpenApiResponse(
                response=AnalyticsSummarySerializer,
                description="Analytics summary",
            ),
        },
        tags=["Analytics"],
    )
    def get(self, request):
        days = int(request.query_params.get("days", 30))
        period_end = timezone.now()
        period_start = period_end - timedelta(days=days)

        logs = NotificationLog.objects.filter(
            created_at__gte=period_start,
            created_at__lte=period_end,
        )

        # Basic counts
        total_sent = logs.filter(
            status__in=[NotificationStatus.SENT, NotificationStatus.DELIVERED]
        ).count()
        total_delivered = logs.filter(status=NotificationStatus.DELIVERED).count()
        total_failed = logs.filter(status=NotificationStatus.FAILED).count()
        total_pending = logs.filter(
            status__in=[NotificationStatus.PENDING, NotificationStatus.QUEUED]
        ).count()

        # Delivery rate
        delivery_rate = 0.0
        if total_sent > 0:
            delivery_rate = round((total_delivered / total_sent) * 100, 2)

        # Average delivery time
        avg_time = self._calculate_avg_delivery_time(logs)

        # Breakdown by channel
        by_channel = dict(
            logs.values("channel")
            .annotate(count=Count("id"))
            .values_list("channel", "count")
        )

        # Breakdown by status
        by_status = dict(
            logs.values("status")
            .annotate(count=Count("id"))
            .values_list("status", "count")
        )

        # Breakdown by event type
        by_event_type = dict(
            logs.values("event_type")
            .annotate(count=Count("id"))
            .values_list("event_type", "count")
        )

        # Daily breakdown
        daily = (
            logs.annotate(date=TruncDate("created_at"))
            .values("date")
            .annotate(
                total=Count("id"),
                sent=Count("id", filter=models.Q(status=NotificationStatus.SENT)),
                delivered=Count("id", filter=models.Q(status=NotificationStatus.DELIVERED)),
                failed=Count("id", filter=models.Q(status=NotificationStatus.FAILED)),
            )
            .order_by("date")
        )

        daily_breakdown = [
            {
                "date": item["date"].isoformat(),
                "total": item["total"],
                "sent": item["sent"],
                "delivered": item["delivered"],
                "failed": item["failed"],
            }
            for item in daily
        ]

        response_data = {
            "period_start": period_start,
            "period_end": period_end,
            "total_sent": total_sent,
            "total_delivered": total_delivered,
            "total_failed": total_failed,
            "total_pending": total_pending,
            "delivery_rate": delivery_rate,
            "avg_delivery_time_seconds": avg_time,
            "by_channel": by_channel,
            "by_status": by_status,
            "by_event_type": by_event_type,
            "daily_breakdown": daily_breakdown,
        }

        serializer = AnalyticsSummarySerializer(response_data)
        return Response(serializer.data)

    def _calculate_avg_delivery_time(self, logs) -> float | None:
        """Calculate average delivery time in seconds."""
        delivered_logs = logs.filter(
            status=NotificationStatus.DELIVERED,
            sent_at__isnull=False,
            delivered_at__isnull=False,
        )[:1000]  # Limit for performance

        if not delivered_logs.exists():
            return None

        times = []
        for log in delivered_logs:
            if log.sent_at and log.delivered_at:
                delta = log.delivered_at - log.sent_at
                times.append(delta.total_seconds())

        if times:
            return round(sum(times) / len(times), 2)
        return None


# Import models for Q filter
from django.db import models


class RecentNotificationsView(APIView):
    """
    GET /api/v1/analytics/recent/

    Returns the most recent notification log entries.
    """

    @extend_schema(
        summary="Get recent notifications",
        description="Returns the most recent notification log entries.",
        parameters=[
            OpenApiParameter(
                name="limit",
                type=int,
                location=OpenApiParameter.QUERY,
                description="Number of entries to return (default: 10, max: 100)",
                default=10,
            ),
            OpenApiParameter(
                name="channel",
                type=str,
                location=OpenApiParameter.QUERY,
                description="Filter by channel (email, whatsapp, push)",
            ),
            OpenApiParameter(
                name="status",
                type=str,
                location=OpenApiParameter.QUERY,
                description="Filter by status (sent, delivered, failed)",
            ),
        ],
        responses={
            200: RecentNotificationsSerializer(many=True),
        },
        tags=["Analytics"],
    )
    def get(self, request):
        limit = min(int(request.query_params.get("limit", 10)), 100)

        logs = NotificationLog.objects.all()

        # Filter by channel
        channel = request.query_params.get("channel")
        if channel:
            logs = logs.filter(channel=channel)

        # Filter by status
        status_filter = request.query_params.get("status")
        if status_filter:
            logs = logs.filter(status=status_filter)

        logs = logs.order_by("-created_at")[:limit]

        data = [
            {
                "id": log.id,
                "event_type": log.event_type,
                "channel": log.channel,
                "recipient_id": log.recipient_id,
                "status": log.status,
                "sent_at": log.sent_at,
                "created_at": log.created_at,
                "template_name": log.template_name,
                "error_reason": log.error_reason,
            }
            for log in logs
        ]

        serializer = RecentNotificationsSerializer(data, many=True)
        return Response(serializer.data)


class ChannelHealthView(APIView):
    """
    GET /api/v1/analytics/health/

    Returns health status for each notification channel.
    """

    @extend_schema(
        summary="Get channel health status",
        description="Returns success/failure rates for each channel in the last 24 hours.",
        responses={
            200: {
                "type": "object",
                "properties": {
                    "email": {
                        "type": "object",
                        "properties": {
                            "total": {"type": "integer"},
                            "success": {"type": "integer"},
                            "failed": {"type": "integer"},
                            "success_rate": {"type": "number"},
                            "is_healthy": {"type": "boolean"},
                        },
                    },
                    "whatsapp": {"type": "object"},
                    "push": {"type": "object"},
                },
            },
        },
        tags=["Analytics"],
    )
    def get(self, request):
        since = timezone.now() - timedelta(hours=24)
        channels = ["email", "whatsapp", "push"]
        result = {}

        for channel in channels:
            logs = NotificationLog.objects.filter(
                channel=channel,
                created_at__gte=since,
            )

            total = logs.count()
            success = logs.filter(
                status__in=[NotificationStatus.SENT, NotificationStatus.DELIVERED]
            ).count()
            failed = logs.filter(status=NotificationStatus.FAILED).count()

            success_rate = 0.0
            if total > 0:
                success_rate = round((success / total) * 100, 2)

            # Consider healthy if success rate > 90% or no attempts
            is_healthy = total == 0 or success_rate >= 90

            result[channel] = {
                "total": total,
                "success": success,
                "failed": failed,
                "success_rate": success_rate,
                "is_healthy": is_healthy,
            }

        return Response(result)
