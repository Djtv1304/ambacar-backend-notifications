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
    queue='sync',
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
    queue='sync',
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


# ============================================================================
# Phase Synchronization Tasks
# ============================================================================

@shared_task(
    bind=True,
    max_retries=3,
    default_retry_delay=60,
    queue='sync',
)
def sync_global_phases_task(self, sync_data: dict):
    """
    Sincroniza fases globales desde Core.

    IMPORTANTE: Esta operación es IDEMPOTENTE.

    Sync modes:
    - "full": Actualiza/crea fases en lista, ELIMINA fases no en lista
    - "partial": Solo actualiza/crea fases en lista, NO elimina

    CASCADE DELETE: Cuando una fase se elimina, PhaseChannelConfig asociados
    se eliminan automáticamente por la FK con on_delete=CASCADE.

    Args:
        sync_data: Dict con datos de sincronización
            {
                "sync_mode": "full" | "partial",
                "phases": [
                    {"slug": "phase-schedule", "name": "Agendar Cita", "icon": "Calendar", "order": 1},
                    ...
                ],
                "sync_version": 1
            }

    Returns:
        dict: {"status": "success", "created": int, "updated": int, "deleted": int}
    """
    from django.db import transaction
    from apps.notifications.models import ServicePhase

    sync_mode = sync_data.get("sync_mode", "partial")
    phases_data = sync_data.get("phases", [])

    created_count = 0
    updated_count = 0
    deleted_count = 0

    try:
        with transaction.atomic():
            # Obtener slugs que deben existir después del sync
            incoming_slugs = {p["slug"] for p in phases_data}

            # Actualizar o crear fases
            for phase_data in phases_data:
                defaults = {
                    "name": phase_data["name"],
                    "icon": phase_data["icon"],
                    "order": phase_data["order"],
                    "is_active": phase_data.get("is_active", True),
                    "description": phase_data.get("description"),
                }

                phase, created = ServicePhase.objects.update_or_create(
                    slug=phase_data["slug"],
                    defaults=defaults,
                )

                if created:
                    created_count += 1
                    logger.info(f"Created phase: {phase.slug}")
                else:
                    updated_count += 1
                    logger.info(f"Updated phase: {phase.slug}")

            # En modo "full", eliminar fases no en lista
            if sync_mode == "full":
                phases_to_delete = ServicePhase.objects.exclude(
                    slug__in=incoming_slugs
                )
                deleted_count = phases_to_delete.count()

                if deleted_count > 0:
                    deleted_slugs = list(phases_to_delete.values_list('slug', flat=True))
                    logger.warning(
                        f"Full sync: Deleting {deleted_count} phases not in sync: {deleted_slugs}. "
                        f"Associated PhaseChannelConfigs will be CASCADE DELETED."
                    )
                    phases_to_delete.delete()

        logger.info(
            f"Global phases sync completed: "
            f"created={created_count}, updated={updated_count}, deleted={deleted_count}"
        )

        return {
            "status": "success",
            "sync_mode": sync_mode,
            "created": created_count,
            "updated": updated_count,
            "deleted": deleted_count,
        }

    except Exception as exc:
        logger.error(f"Error syncing global phases: {exc}", exc_info=True)
        raise self.retry(exc=exc)


@shared_task(
    bind=True,
    max_retries=3,
    default_retry_delay=60,
    queue='sync',
)
def sync_vehicle_phases_task(self, sync_data: dict):
    """
    Sincroniza configuración de fases para un vehículo específico.

    IMPORTANTE: Esta operación es IDEMPOTENTE.

    Permite configurar:
    - Fases adicionales para un vehículo específico
    - Orden personalizado de fases
    - Activar/desactivar fases específicas

    Args:
        sync_data: Dict con datos de sincronización
            {
                "plate": "ABC-1234",
                "sync_mode": "full" | "partial",
                "phases": [
                    {"phase_slug": "phase-schedule", "order": 1, "is_active": true},
                    ...
                ],
                "sync_version": 1
            }

    Returns:
        dict: {"status": "success", "plate": str, "created": int, "updated": int, "deleted": int}
    """
    from django.db import transaction
    from apps.notifications.models import Vehicle, ServicePhase, VehiclePhaseConfig

    plate = sync_data.get("plate")
    sync_mode = sync_data.get("sync_mode", "full")
    phases_data = sync_data.get("phases", [])
    sync_version = sync_data.get("sync_version")

    created_count = 0
    updated_count = 0
    deleted_count = 0

    try:
        vehicle = Vehicle.objects.get(plate=plate)

        with transaction.atomic():
            incoming_phase_slugs = {p["phase_slug"] for p in phases_data}

            # Actualizar o crear configuraciones de fase por vehículo
            for phase_data in phases_data:
                phase = ServicePhase.objects.get(slug=phase_data["phase_slug"])

                defaults = {
                    "order": phase_data["order"],
                    "is_active": phase_data.get("is_active", True),
                    "last_synced_at": timezone.now(),
                }

                if sync_version:
                    defaults["sync_version"] = sync_version

                config, created = VehiclePhaseConfig.objects.update_or_create(
                    vehicle=vehicle,
                    phase=phase,
                    defaults=defaults,
                )

                if created:
                    created_count += 1
                else:
                    updated_count += 1

            # En modo "full", eliminar configs no en lista
            if sync_mode == "full":
                configs_to_delete = VehiclePhaseConfig.objects.filter(
                    vehicle=vehicle
                ).exclude(
                    phase__slug__in=incoming_phase_slugs
                )
                deleted_count = configs_to_delete.count()
                configs_to_delete.delete()

        logger.info(
            f"Vehicle phases sync for {plate}: "
            f"created={created_count}, updated={updated_count}, deleted={deleted_count}"
        )

        return {
            "status": "success",
            "plate": plate,
            "created": created_count,
            "updated": updated_count,
            "deleted": deleted_count,
        }

    except Vehicle.DoesNotExist:
        logger.error(f"Vehicle not found for phases sync: {plate}")
        return {
            "status": "error",
            "plate": plate,
            "error": "Vehicle not found",
        }

    except ServicePhase.DoesNotExist as exc:
        logger.error(f"ServicePhase not found during vehicle phases sync: {exc}")
        raise self.retry(exc=exc)

    except Exception as exc:
        logger.error(f"Error syncing vehicle phases for {plate}: {exc}", exc_info=True)
        raise self.retry(exc=exc)
