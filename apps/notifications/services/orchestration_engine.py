"""
Notification Orchestration Engine.
Core business logic for processing events and dispatching notifications.
"""
import logging
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from apps.core.constants import NotificationChannel, EventType, NotificationTarget
from apps.core.exceptions import (
    OrchestrationConfigNotFoundError,
    RecipientNotFoundError,
)
from apps.notifications.models import (
    OrchestrationConfig,
    PhaseChannelConfig,
    CustomerContactInfo,
    CustomerChannelPreference,
    ServiceType,
    ServicePhase,
)
from apps.notifications.services.template_service import template_service
from apps.notifications.services.dispatch_service import dispatch_service

logger = logging.getLogger(__name__)


@dataclass
class EventPayload:
    """
    Incoming event from external service.
    This is the input to the orchestration engine.
    """
    event_type: str
    service_type_id: str
    phase_id: str
    customer_id: str
    target: str = NotificationTarget.CLIENTS
    context: Dict[str, Any] = field(default_factory=dict)
    taller_id: Optional[str] = None
    subtype_id: Optional[str] = None
    correlation_id: Optional[str] = None


@dataclass
class OrchestrationResult:
    """
    Result of orchestration processing.
    """
    success: bool
    notifications_queued: int
    errors: List[str]
    correlation_id: str


class OrchestrationEngine:
    """
    Core business logic for notification orchestration.

    Flow:
    1. Receive event payload
    2. Find matching orchestration config
    3. Get customer preferences
    4. Determine which channels to use
    5. Render templates
    6. Queue notifications for async sending
    """

    def process_event(self, payload: EventPayload) -> OrchestrationResult:
        """
        Main entry point for processing notification events.

        Args:
            payload: Event data including type, customer, and context

        Returns:
            OrchestrationResult with queued notification count and any errors
        """
        correlation_id = payload.correlation_id or str(uuid.uuid4())
        errors = []
        notifications_queued = 0

        logger.info(
            f"Processing event {payload.event_type} for customer {payload.customer_id}, "
            f"correlation_id: {correlation_id}"
        )

        try:
            # Step 1: Find orchestration config
            config = self._find_orchestration_config(payload)
            if not config:
                logger.warning(
                    f"No orchestration config found for service_type={payload.service_type_id}, "
                    f"phase={payload.phase_id}, target={payload.target}"
                )
                return OrchestrationResult(
                    success=False,
                    notifications_queued=0,
                    errors=["No orchestration config found for this service type/phase"],
                    correlation_id=correlation_id,
                )

            # Step 2: Get phase channel configs
            phase_configs = self._get_phase_configs(config, payload.phase_id)
            enabled_channels = [pc for pc in phase_configs if pc.enabled and pc.template]

            if not enabled_channels:
                logger.info(f"No channels enabled for phase {payload.phase_id}")
                return OrchestrationResult(
                    success=True,
                    notifications_queued=0,
                    errors=["No channels enabled for this phase"],
                    correlation_id=correlation_id,
                )

            # Step 3: Get customer info
            customer = self._get_customer(payload.customer_id)
            if not customer:
                logger.error(f"Customer not found: {payload.customer_id}")
                return OrchestrationResult(
                    success=False,
                    notifications_queued=0,
                    errors=["Customer not found"],
                    correlation_id=correlation_id,
                )

            # Step 4: Get customer preferences
            preferences = self._get_customer_preferences(payload.customer_id)

            # Step 5: Resolve channels and recipients
            channels_to_notify = self._resolve_channels(
                enabled_channels,
                preferences,
                customer,
            )

            if not channels_to_notify:
                logger.warning(f"No valid channels for customer {payload.customer_id}")
                return OrchestrationResult(
                    success=True,
                    notifications_queued=0,
                    errors=["No valid channels available for this customer"],
                    correlation_id=correlation_id,
                )

            # Build priority order for fallback
            priority_order = [c[0].channel for c in channels_to_notify]

            # Step 6: Queue notifications for each channel
            for channel_config, recipient in channels_to_notify:
                try:
                    # Render template
                    rendered_body = template_service.render(
                        channel_config.template.body,
                        payload.context,
                    )

                    rendered_subject = None
                    if channel_config.template.subject:
                        rendered_subject = template_service.render(
                            channel_config.template.subject,
                            payload.context,
                        )

                    # Queue notification
                    dispatch_service.queue_notification(
                        channel=channel_config.channel,
                        recipient=recipient,
                        subject=rendered_subject,
                        body=rendered_body,
                        event_type=payload.event_type,
                        customer_id=payload.customer_id,
                        template_id=str(channel_config.template.id),
                        template_name=channel_config.template.name,
                        context=payload.context,
                        correlation_id=correlation_id,
                        priority_order=priority_order,
                    )

                    notifications_queued += 1
                    logger.info(
                        f"Queued {channel_config.channel} notification to {recipient}"
                    )

                except Exception as e:
                    error_msg = f"Failed to queue {channel_config.channel}: {str(e)}"
                    errors.append(error_msg)
                    logger.error(error_msg)

            return OrchestrationResult(
                success=len(errors) == 0,
                notifications_queued=notifications_queued,
                errors=errors,
                correlation_id=correlation_id,
            )

        except Exception as e:
            # Improve error messages for common issues
            error_message = str(e)

            # Handle UUID validation errors for service_type_id
            if "no es un uuid válido" in error_message.lower() or "is not a valid uuid" in error_message.lower():
                error_message = (
                    f"Service type '{payload.service_type_id}' not found. "
                    f"Please ensure service types are seeded using 'python manage.py seed_initial_data' "
                    f"and use the correct UUID from the database."
                )

            logger.exception(f"Orchestration error: {error_message}")
            return OrchestrationResult(
                success=False,
                notifications_queued=0,
                errors=[error_message],
                correlation_id=correlation_id,
            )

    def _find_orchestration_config(
        self,
        payload: EventPayload,
    ) -> Optional[OrchestrationConfig]:
        """
        Find the matching orchestration configuration.
        Looks up ServiceType by slug, then tries taller-specific config first,
        and falls back to global.
        """
        # First, find the ServiceType by slug
        service_type = ServiceType.objects.filter(slug=payload.service_type_id).first()
        if not service_type:
            logger.warning(f"ServiceType not found with slug: {payload.service_type_id}")
            return None

        filters = {
            "service_type": service_type,
            "target": payload.target,
            "is_active": True,
        }

        # Try taller-specific config first
        if payload.taller_id:
            config = OrchestrationConfig.objects.filter(
                **filters,
                taller_id=payload.taller_id,
            ).select_related("service_type").first()
            if config:
                return config

        # Fall back to global config (no taller_id)
        return OrchestrationConfig.objects.filter(
            **filters,
            taller_id__isnull=True,
        ).select_related("service_type").first()

    def _get_phase_configs(
        self,
        config: OrchestrationConfig,
        phase_id: str,
    ) -> List[PhaseChannelConfig]:
        """
        Get channel configs for a specific phase.
        Looks up ServicePhase by slug.
        """
        # Find the ServicePhase by slug
        phase = ServicePhase.objects.filter(slug=phase_id).first()
        if not phase:
            logger.warning(f"ServicePhase not found with slug: {phase_id}")
            return []

        return list(
            config.phase_configs.filter(
                phase=phase,
            ).select_related("template", "phase")
        )

    def _get_customer(self, customer_id: str) -> Optional[CustomerContactInfo]:
        """
        Retrieve customer contact information.
        """
        return CustomerContactInfo.objects.filter(
            customer_id=customer_id,
        ).first()

    def _get_customer_preferences(
        self,
        customer_id: str,
    ) -> List[CustomerChannelPreference]:
        """
        Get customer channel preferences ordered by priority.
        """
        return list(
            CustomerChannelPreference.objects.filter(
                customer__customer_id=customer_id,
                enabled=True,
            ).order_by("priority")
        )

    def _resolve_channels(
        self,
        enabled_configs: List[PhaseChannelConfig],
        preferences: List[CustomerChannelPreference],
        customer: CustomerContactInfo,
    ) -> List[tuple]:
        """
        Resolve which channels to use and in what order.
        Returns list of (PhaseChannelConfig, recipient) tuples.

        Logic:
        1. Start with customer preferences (in priority order)
        2. For each preference, check if the channel is enabled in config
        3. Verify recipient exists for that channel
        4. Add any enabled channels not in preferences at the end
        """
        result = []
        enabled_channel_map = {c.channel: c for c in enabled_configs}
        used_channels = set()

        # First, add channels in preference order
        for pref in preferences:
            if pref.channel in enabled_channel_map and pref.channel not in used_channels:
                config = enabled_channel_map[pref.channel]
                recipient = customer.get_recipient_for_channel(pref.channel)
                if recipient:
                    result.append((config, recipient))
                    used_channels.add(pref.channel)

        # Then, add any enabled channels not in preferences
        for channel, config in enabled_channel_map.items():
            if channel not in used_channels:
                recipient = customer.get_recipient_for_channel(channel)
                if recipient:
                    result.append((config, recipient))
                    used_channels.add(channel)

        return result


# Singleton instance
orchestration_engine = OrchestrationEngine()
