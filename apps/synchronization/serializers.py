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


# ============================================================================
# Phase Synchronization Serializers
# ============================================================================

class PhaseSyncItemSerializer(serializers.Serializer):
    """
    Item individual de fase para sincronización.
    """
    slug = serializers.SlugField(
        max_length=50,
        help_text="Identificador único de la fase (e.g., 'phase-schedule')"
    )
    name = serializers.CharField(
        max_length=100,
        help_text="Nombre de la fase"
    )
    icon = serializers.CharField(
        max_length=50,
        help_text="Nombre del ícono Lucide"
    )
    order = serializers.IntegerField(
        min_value=1,
        help_text="Orden de la fase en el flujo"
    )
    is_active = serializers.BooleanField(
        default=True,
        help_text="Si la fase está activa"
    )
    description = serializers.CharField(
        required=False,
        allow_blank=True,
        allow_null=True,
        help_text="Descripción opcional"
    )


class GlobalPhaseSyncSerializer(serializers.Serializer):
    """
    Payload para sincronizar fases globales desde Core.

    sync_mode:
    - "full": Reemplaza todas las fases (elimina las que no están en la lista)
    - "partial": Solo actualiza/crea las fases en la lista (no elimina)

    Example payload:
        {
            "sync_mode": "full",
            "phases": [
                {"slug": "phase-schedule", "name": "Agendar Cita", "icon": "Calendar", "order": 1},
                {"slug": "phase-reception", "name": "Recepción", "icon": "ClipboardCheck", "order": 2}
            ],
            "sync_version": 2
        }
    """
    sync_mode = serializers.ChoiceField(
        choices=["full", "partial"],
        default="partial",
        help_text="Modo de sincronización: 'full' reemplaza todo, 'partial' solo actualiza"
    )
    phases = PhaseSyncItemSerializer(many=True)
    sync_version = serializers.IntegerField(
        required=False,
        help_text="Versión de sincronización"
    )

    def validate_phases(self, value):
        """Validar que no haya slugs u órdenes duplicados."""
        slugs = [p['slug'] for p in value]
        orders = [p['order'] for p in value]

        if len(slugs) != len(set(slugs)):
            raise serializers.ValidationError("Slugs de fase duplicados encontrados")

        if len(orders) != len(set(orders)):
            raise serializers.ValidationError("Valores de orden duplicados encontrados")

        return value


class VehiclePhaseSyncItemSerializer(serializers.Serializer):
    """
    Item individual de fase para configuración de vehículo.
    """
    phase_slug = serializers.SlugField(
        max_length=50,
        help_text="Slug de la fase global (debe existir en ServicePhase)"
    )
    order = serializers.IntegerField(
        min_value=1,
        help_text="Orden personalizado para este vehículo"
    )
    is_active = serializers.BooleanField(
        default=True,
        help_text="Si esta fase está activa para este vehículo"
    )


class VehiclePhaseSyncSerializer(serializers.Serializer):
    """
    Payload para sincronizar configuración de fases por vehículo.

    Permite configurar:
    - Fases adicionales para un vehículo específico
    - Orden personalizado de fases
    - Activar/desactivar fases específicas

    Example payload:
        {
            "sync_mode": "full",
            "phases": [
                {"phase_slug": "phase-schedule", "order": 1, "is_active": true},
                {"phase_slug": "phase-custom-diagnostic", "order": 2, "is_active": true},
                {"phase_slug": "phase-delivery", "order": 3, "is_active": true}
            ],
            "sync_version": 1
        }
    """
    sync_mode = serializers.ChoiceField(
        choices=["full", "partial"],
        default="full",
        help_text="Modo de sincronización: 'full' reemplaza todo, 'partial' solo actualiza"
    )
    phases = VehiclePhaseSyncItemSerializer(many=True)
    sync_version = serializers.IntegerField(required=False)

    def validate_phases(self, value):
        """Validar slugs únicos y que existan en fases globales."""
        from apps.notifications.models import ServicePhase

        phase_slugs = [p['phase_slug'] for p in value]

        # Verificar slugs duplicados
        if len(phase_slugs) != len(set(phase_slugs)):
            raise serializers.ValidationError("Slugs de fase duplicados encontrados")

        # Verificar órdenes duplicados
        orders = [p['order'] for p in value]
        if len(orders) != len(set(orders)):
            raise serializers.ValidationError("Valores de orden duplicados encontrados")

        # Validar que todas las fases existan
        existing_slugs = set(ServicePhase.objects.filter(
            slug__in=phase_slugs
        ).values_list('slug', flat=True))

        missing_slugs = set(phase_slugs) - existing_slugs
        if missing_slugs:
            raise serializers.ValidationError(
                f"Fases no encontradas en fases globales: {sorted(missing_slugs)}"
            )

        return value
