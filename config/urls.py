"""
URL configuration for Ambacar Notification Service.
"""
from django.contrib import admin
from django.urls import include, path
from drf_spectacular.views import (
    SpectacularAPIView,
    SpectacularRedocView,
    SpectacularSwaggerView,
)

urlpatterns = [
    # Admin
    path("admin/", admin.site.urls),

    # Public API v1
    path("api/v1/", include([
        path("notifications/", include("apps.notifications.urls")),
        path("analytics/", include("apps.analytics.urls")),
        path("health/", include("apps.core.urls")),
    ])),

    # Internal API v1 (service-to-service communication)
    path("api/internal/v1/", include("apps.synchronization.urls")),

    # OpenAPI Schema
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),

    # Swagger UI
    path(
        "api/docs/",
        SpectacularSwaggerView.as_view(url_name="schema"),
        name="swagger-ui"
    ),

    # ReDoc
    path(
        "api/redoc/",
        SpectacularRedocView.as_view(url_name="schema"),
        name="redoc"
    ),
]

# Add debug toolbar in development
from django.conf import settings

if settings.DEBUG:
    try:
        import debug_toolbar
        urlpatterns = [
            path("__debug__/", include(debug_toolbar.urls)),
        ] + urlpatterns
    except ImportError:
        pass
