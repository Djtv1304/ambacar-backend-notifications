"""
Serializers for data synchronization from Core service.
"""
from rest_framework import serializers


class CustomerSyncSerializer(serializers.Serializer):
    """
    Payload esperado desde Core para sincronizar clientes.

    Example payload:
        {
            "customer_id": "CORE-12345",
            "first_name": "Juan",
            "last_name": "Pérez",
            "email": "juan.perez@example.com",
            "phone": "+593987654321",
            "whatsapp": "+593987654321",
            "sync_version": 1
        }
    """

    customer_id = serializers.CharField(
        max_length=100, help_text="ID único del cliente en Core"
    )
    first_name = serializers.CharField(max_length=255)
    last_name = serializers.CharField(
        max_length=255, required=False, allow_blank=True, default=""
    )
    email = serializers.EmailField(required=False, allow_null=True, allow_blank=True)
    phone = serializers.CharField(
        max_length=20, required=False, allow_blank=True, allow_null=True
    )
    whatsapp = serializers.CharField(
        max_length=20, required=False, allow_blank=True, allow_null=True
    )

    # Metadata de sincronización
    sync_version = serializers.IntegerField(
        required=False, help_text="Versión del registro en Core"
    )


class VehicleSyncSerializer(serializers.Serializer):
    """
    Payload esperado desde Core para sincronizar vehículos.

    Example payload:
        {
            "vehicle_id": "VEH-9876",
            "customer_id": "CORE-12345",
            "plate": "ABC-1234",
            "brand": "Toyota",
            "model": "Corolla",
            "year": 2020,
            "current_kilometers": 50000,
            "sync_version": 1
        }
    """

    vehicle_id = serializers.CharField(
        max_length=100, help_text="ID único del vehículo en Core"
    )
    customer_id = serializers.CharField(
        max_length=100, help_text="ID del dueño en Core"
    )
    plate = serializers.CharField(max_length=20)
    brand = serializers.CharField(max_length=100)
    model = serializers.CharField(max_length=100)
    year = serializers.IntegerField(required=False, allow_null=True)
    current_kilometers = serializers.IntegerField(required=False, default=0)
    last_service_date = serializers.DateField(required=False, allow_null=True)
    next_service_kilometers = serializers.IntegerField(required=False, allow_null=True)
    image_url = serializers.URLField(required=False, allow_null=True, allow_blank=True)

    # Metadata de sincronización
    sync_version = serializers.IntegerField(required=False)
