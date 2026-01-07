"""
URL configuration for notifications app.
"""
from django.urls import path, include
from rest_framework.routers import DefaultRouter

from apps.notifications.views.events import EventDispatchView
from apps.notifications.views.templates import NotificationTemplateViewSet
from apps.notifications.views.orchestration import (
    ServicePhaseViewSet,
    ServiceTypeViewSet,
    OrchestrationConfigViewSet,
)
from apps.notifications.views.customers import (
    CustomerContactInfoViewSet,
    VehicleViewSet,
    MaintenanceReminderViewSet,
)
from apps.notifications.views.push_subscription import (
    PushSubscriptionView,
    PushSubscriptionStatusView,
)
from apps.notifications.views.catalog import CatalogView

# Create router for ViewSets
router = DefaultRouter()
router.register(r"templates", NotificationTemplateViewSet, basename="templates")
router.register(r"phases", ServicePhaseViewSet, basename="phases")
router.register(r"service-types", ServiceTypeViewSet, basename="service-types")
router.register(r"orchestration", OrchestrationConfigViewSet, basename="orchestration")
router.register(r"customers", CustomerContactInfoViewSet, basename="customers")
router.register(r"vehicles", VehicleViewSet, basename="vehicles")
router.register(r"reminders", MaintenanceReminderViewSet, basename="reminders")

urlpatterns = [
    # Event dispatch endpoint
    path("events/dispatch/", EventDispatchView.as_view(), name="event-dispatch"),

    # Catalog endpoint
    path("catalog/", CatalogView.as_view(), name="catalog"),

    # Push subscription endpoints
    path("push/subscribe/", PushSubscriptionView.as_view(), name="push-subscribe"),
    path(
        "push/status/<str:customer_id>/",
        PushSubscriptionStatusView.as_view(),
        name="push-status",
    ),

    # Include router URLs
    path("", include(router.urls)),
]
