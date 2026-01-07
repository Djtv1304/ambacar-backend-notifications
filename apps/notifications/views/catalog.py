"""
Views for catalog lookups.
"""
from rest_framework.views import APIView
from rest_framework.response import Response
from drf_spectacular.utils import extend_schema, OpenApiResponse, OpenApiExample

from apps.notifications.models import ServicePhase, ServiceType


class CatalogView(APIView):
    """
    GET /api/v1/notifications/catalog/

    Returns all available service types and phases with their slugs.
    Useful for frontend to know valid values for dispatch endpoint.
    """

    @extend_schema(
        summary="Get notification catalog",
        description=(
            "Returns all service types and phases with their slugs. "
            "Use these slugs when calling the dispatch endpoint.\n\n"
            "**Slugs as Contract:**\n"
            "These slugs are shared between CORE and Notifications services. "
            "Use the same slugs when creating service types in CORE."
        ),
        responses={
            200: OpenApiResponse(
                description="Catalog data with service types and phases",
            ),
        },
        tags=["Catalog"],
    )
    def get(self, request):
        # Service types with subtypes
        service_types = []
        for st in ServiceType.objects.filter(parent__isnull=True, is_active=True):
            type_data = {
                "slug": st.slug,
                "name": st.name,
                "icon": st.icon,
            }
            # Add subtypes if any
            subtypes = st.subtypes.filter(is_active=True)
            if subtypes.exists():
                type_data["subtypes"] = [
                    {"slug": sub.slug, "name": sub.name, "icon": sub.icon}
                    for sub in subtypes
                ]
            service_types.append(type_data)

        # Phases
        phases = [
            {"slug": p.slug, "name": p.name, "icon": p.icon, "order": p.order}
            for p in ServicePhase.objects.filter(is_active=True).order_by("order")
        ]

        return Response({
            "service_types": service_types,
            "phases": phases,
        })
