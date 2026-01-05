"""
Celery tasks for asynchronous data synchronization from Core service.
"""
from celery import shared_task
from django.utils import timezone
import logging

from apps.notifications.models import CustomerContactInfo, Vehicle

logger = logging.getLogger(__name__)


@shared_task(
    bind=True,
    max_retries=3,
    default_retry_delay=60,
)
def sync_customer_task(self, customer_data: dict):
    """
    Sincroniza datos de cliente desde Core a la base local.

    IMPORTANTE: Esta operación es IDEMPOTENTE.
    - Si el cliente no existe, se crea
    - Si existe, se actualizan SOLO datos de contacto
    - Las preferencias de canal (CustomerChannelPreference) NO se tocan

    Args:
        customer_data: Dict con datos del cliente desde Core
            {
                "customer_id": "CORE-12345",
                "first_name": "Juan",
                "last_name": "Pérez",
                "email": "juan@example.com",
                "phone": "+593987654321",
                "whatsapp": "+593987654321",
                "preferred_language": "es",
                "avatar_url": "https://...",
                "sync_version": 1  # optional
            }

    Returns:
        dict: {"status": "success", "customer_id": str, "action": "created|updated"}

    Raises:
        Exception: Si falla después de todos los retries
    """
    customer_id = customer_data.get("customer_id")

    try:
        # Preparar datos para update_or_create
        defaults = {
            "first_name": customer_data.get("first_name"),
            "last_name": customer_data.get("last_name", ""),
            "email": customer_data.get("email"),
            "phone": customer_data.get("phone"),
            "whatsapp": customer_data.get("whatsapp"),
            "preferred_language": customer_data.get("preferred_language", "es"),
            "avatar_url": customer_data.get("avatar_url"),
        }

        # Limpiar valores None/vacíos para evitar sobrescribir con null
        defaults = {k: v for k, v in defaults.items() if v is not None}

        # Agregar tracking de sincronización
        defaults["last_synced_at"] = timezone.now()
        if customer_data.get("sync_version"):
            defaults["sync_version"] = customer_data.get("sync_version")

        customer, created = CustomerContactInfo.objects.update_or_create(
            customer_id=customer_id, defaults=defaults
        )

        action = "created" if created else "updated"
        logger.info(
            f"Customer {customer_id} {action} successfully",
            extra={"customer_id": customer_id, "action": action},
        )

        return {
            "status": "success",
            "customer_id": customer_id,
            "action": action,
        }

    except Exception as exc:
        logger.error(
            f"Error syncing customer {customer_id}: {exc}",
            extra={"customer_id": customer_id, "error": str(exc)},
            exc_info=True,
        )
        # Retry con backoff exponencial
        raise self.retry(exc=exc)


@shared_task(
    bind=True,
    max_retries=3,
    default_retry_delay=60,
)
def sync_vehicle_task(self, vehicle_data: dict):
    """
    Sincroniza datos de vehículo desde Core a la base local.

    IMPORTANTE: Esta operación es IDEMPOTENTE.
    - Si el vehículo no existe (por placa), se crea
    - Si existe, se actualizan sus datos
    - Se respetan campos locales como last_service_date si no vienen en payload

    Args:
        vehicle_data: Dict con datos del vehículo desde Core
            {
                "vehicle_id": "VEH-9876",
                "customer_id": "CORE-12345",
                "plate": "ABC-1234",
                "brand": "Toyota",
                "model": "Corolla",
                "year": 2020,
                "current_kilometers": 50000,
                "last_service_date": "2025-01-01",  # optional
                "next_service_kilometers": 60000,  # optional
                "image_url": "https://...",  # optional
                "sync_version": 1  # optional
            }

    Returns:
        dict: {"status": "success", "plate": str, "action": "created|updated"}

    Raises:
        Exception: Si falla después de todos los retries
    """
    plate = vehicle_data.get("plate")
    customer_id = vehicle_data.get("customer_id")

    try:
        # Verificar que el cliente existe localmente
        # Si no existe, loggear advertencia pero continuar
        # (El cliente debería sincronizarse primero, pero no fallar)
        customer_exists = CustomerContactInfo.objects.filter(
            customer_id=customer_id
        ).exists()

        if not customer_exists:
            logger.warning(
                f"Vehicle {plate} references non-existent customer {customer_id}. "
                "Customer should be synced first.",
                extra={"plate": plate, "customer_id": customer_id},
            )

        # Preparar datos para update_or_create
        defaults = {
            "customer_id": customer_id,
            "brand": vehicle_data.get("brand"),
            "model": vehicle_data.get("model"),
            "year": vehicle_data.get("year"),
            "current_kilometers": vehicle_data.get("current_kilometers", 0),
            "image_url": vehicle_data.get("image_url"),
        }

        # Solo actualizar last_service_date si viene en payload
        if vehicle_data.get("last_service_date"):
            defaults["last_service_date"] = vehicle_data.get("last_service_date")

        # Solo actualizar next_service_kilometers si viene en payload
        if vehicle_data.get("next_service_kilometers"):
            defaults["next_service_kilometers"] = vehicle_data.get(
                "next_service_kilometers"
            )

        # Limpiar valores None
        defaults = {k: v for k, v in defaults.items() if v is not None}

        # Agregar tracking de sincronización
        defaults["last_synced_at"] = timezone.now()
        if vehicle_data.get("sync_version"):
            defaults["sync_version"] = vehicle_data.get("sync_version")

        vehicle, created = Vehicle.objects.update_or_create(
            plate=plate,  # Usar placa como identificador único
            defaults=defaults,
        )

        action = "created" if created else "updated"
        logger.info(
            f"Vehicle {plate} {action} successfully",
            extra={"plate": plate, "customer_id": customer_id, "action": action},
        )

        return {
            "status": "success",
            "plate": plate,
            "customer_id": customer_id,
            "action": action,
        }

    except Exception as exc:
        logger.error(
            f"Error syncing vehicle {plate}: {exc}",
            extra={"plate": plate, "error": str(exc)},
            exc_info=True,
        )
        raise self.retry(exc=exc)
