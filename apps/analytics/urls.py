"""
URL configuration for analytics app.
"""
from django.urls import path

from apps.analytics.views import (
    AnalyticsSummaryView,
    RecentNotificationsView,
    ChannelHealthView,
)

urlpatterns = [
    path("summary/", AnalyticsSummaryView.as_view(), name="analytics-summary"),
    path("recent/", RecentNotificationsView.as_view(), name="analytics-recent"),
    path("health/", ChannelHealthView.as_view(), name="analytics-health"),
]
