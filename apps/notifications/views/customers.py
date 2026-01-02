"""
Views for customer data and preferences.
"""
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from drf_spectacular.utils import extend_schema, extend_schema_view

from apps.notifications.models import (
    CustomerContactInfo,
    CustomerChannelPreference,
    Vehicle,
    MaintenanceReminder,
)
from apps.notifications.serializers.customers import (
    CustomerContactInfoSerializer,
    CustomerContactInfoCreateSerializer,
    CustomerChannelPreferenceSerializer,
    CustomerPreferencesUpdateSerializer,
    VehicleSerializer,
    MaintenanceReminderSerializer,
)


@extend_schema_view(
    list=extend_schema(
        summary="List customers",
        tags=["Customers"],
    ),
    retrieve=extend_schema(
        summary="Get customer details",
        tags=["Customers"],
    ),
    create=extend_schema(
        summary="Create customer",
        tags=["Customers"],
    ),
    update=extend_schema(
        summary="Update customer",
        tags=["Customers"],
    ),
    partial_update=extend_schema(
        summary="Partially update customer",
        tags=["Customers"],
    ),
    destroy=extend_schema(
        summary="Delete customer",
        tags=["Customers"],
    ),
)
class CustomerContactInfoViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing customer contact information.
    """
    queryset = CustomerContactInfo.objects.all()
    serializer_class = CustomerContactInfoSerializer
    lookup_field = "customer_id"

    def get_serializer_class(self):
        if self.action in ["create", "update", "partial_update"]:
            return CustomerContactInfoCreateSerializer
        return CustomerContactInfoSerializer

    def get_queryset(self):
        return CustomerContactInfo.objects.prefetch_related(
            "channel_preferences"
        ).order_by("-created_at")

    @extend_schema(
        summary="Get customer preferences",
        description="Get notification preferences for a customer.",
        responses={200: CustomerChannelPreferenceSerializer(many=True)},
        tags=["Customers"],
    )
    @action(detail=True, methods=["get"])
    def preferences(self, request, customer_id=None):
        """
        Get customer notification preferences.
        """
        customer = self.get_object()
        preferences = customer.channel_preferences.all().order_by("priority")
        serializer = CustomerChannelPreferenceSerializer(preferences, many=True)
        return Response(serializer.data)

    @extend_schema(
        summary="Update customer preferences",
        description="Update notification preferences for a customer.",
        request=CustomerPreferencesUpdateSerializer,
        responses={200: CustomerChannelPreferenceSerializer(many=True)},
        tags=["Customers"],
    )
    @action(detail=True, methods=["post"])
    def update_preferences(self, request, customer_id=None):
        """
        Update customer notification preferences.
        """
        customer = self.get_object()
        serializer = CustomerPreferencesUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        for pref_data in serializer.validated_data["channels"]:
            CustomerChannelPreference.objects.update_or_create(
                customer=customer,
                channel=pref_data["channel"],
                defaults={
                    "enabled": pref_data.get("enabled", True),
                    "priority": pref_data.get("priority", 1),
                }
            )

        preferences = customer.channel_preferences.all().order_by("priority")
        return Response(
            CustomerChannelPreferenceSerializer(preferences, many=True).data
        )

    @extend_schema(
        summary="Get customer vehicles",
        description="Get all vehicles for a customer.",
        responses={200: VehicleSerializer(many=True)},
        tags=["Customers"],
    )
    @action(detail=True, methods=["get"])
    def vehicles(self, request, customer_id=None):
        """
        Get customer vehicles.
        """
        customer = self.get_object()
        vehicles = Vehicle.objects.filter(customer_id=customer.customer_id)
        serializer = VehicleSerializer(vehicles, many=True)
        return Response(serializer.data)

    @extend_schema(
        summary="Get customer reminders",
        description="Get all maintenance reminders for a customer.",
        responses={200: MaintenanceReminderSerializer(many=True)},
        tags=["Customers"],
    )
    @action(detail=True, methods=["get"])
    def reminders(self, request, customer_id=None):
        """
        Get customer maintenance reminders.
        """
        customer = self.get_object()
        reminders = MaintenanceReminder.objects.filter(
            customer_id=customer.customer_id
        ).select_related("vehicle")

        # Filter by status if provided
        status_filter = request.query_params.get("status")
        if status_filter:
            reminders = reminders.filter(status=status_filter)

        serializer = MaintenanceReminderSerializer(reminders, many=True)
        return Response(serializer.data)


@extend_schema_view(
    list=extend_schema(
        summary="List vehicles",
        tags=["Customers"],
    ),
    retrieve=extend_schema(
        summary="Get vehicle details",
        tags=["Customers"],
    ),
    create=extend_schema(
        summary="Create vehicle",
        tags=["Customers"],
    ),
    update=extend_schema(
        summary="Update vehicle",
        tags=["Customers"],
    ),
    partial_update=extend_schema(
        summary="Partially update vehicle",
        tags=["Customers"],
    ),
    destroy=extend_schema(
        summary="Delete vehicle",
        tags=["Customers"],
    ),
)
class VehicleViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing vehicles.
    """
    queryset = Vehicle.objects.all()
    serializer_class = VehicleSerializer

    def get_queryset(self):
        queryset = Vehicle.objects.all()

        # Filter by customer_id
        customer_id = self.request.query_params.get("customer_id")
        if customer_id:
            queryset = queryset.filter(customer_id=customer_id)

        # Filter by plate (search)
        plate = self.request.query_params.get("plate")
        if plate:
            queryset = queryset.filter(plate__icontains=plate)

        return queryset.order_by("-created_at")


@extend_schema_view(
    list=extend_schema(
        summary="List maintenance reminders",
        tags=["Customers"],
    ),
    retrieve=extend_schema(
        summary="Get reminder details",
        tags=["Customers"],
    ),
    create=extend_schema(
        summary="Create reminder",
        tags=["Customers"],
    ),
    update=extend_schema(
        summary="Update reminder",
        tags=["Customers"],
    ),
    partial_update=extend_schema(
        summary="Partially update reminder",
        tags=["Customers"],
    ),
    destroy=extend_schema(
        summary="Delete reminder",
        tags=["Customers"],
    ),
)
class MaintenanceReminderViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing maintenance reminders.
    """
    queryset = MaintenanceReminder.objects.all()
    serializer_class = MaintenanceReminderSerializer

    def get_queryset(self):
        queryset = MaintenanceReminder.objects.select_related("vehicle")

        # Filter by status
        status_filter = self.request.query_params.get("status")
        if status_filter:
            queryset = queryset.filter(status=status_filter)

        # Filter by customer_id
        customer_id = self.request.query_params.get("customer_id")
        if customer_id:
            queryset = queryset.filter(customer_id=customer_id)

        # Filter by vehicle_id
        vehicle_id = self.request.query_params.get("vehicle_id")
        if vehicle_id:
            queryset = queryset.filter(vehicle_id=vehicle_id)

        return queryset.order_by("-created_at")

    @extend_schema(
        summary="Mark reminder as completed",
        tags=["Customers"],
    )
    @action(detail=True, methods=["post"])
    def complete(self, request, pk=None):
        """
        Mark a reminder as completed.
        """
        reminder = self.get_object()
        reminder.mark_completed()
        return Response(MaintenanceReminderSerializer(reminder).data)
