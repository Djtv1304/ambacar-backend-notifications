"""
Notification Orchestration Engine.
Core business logic for processing events and dispatching notifications.
"""
import logging
import uuid
import unicodedata
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

    @staticmethod
    def _normalize(text: str) -> str:
        """
        Normalize text for case-insensitive and accent-insensitive matching.
        Same as TemplateService._normalize().
        """
        nfd = unicodedata.normalize('NFD', text)
        without_accents = ''.join(
            char for char in nfd
            if unicodedata.category(char) != 'Mn'
        )
        return without_accents.lower()

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
            # Special handling for custom events (no service_type/phase required)
            if payload.event_type == EventType.CUSTOM:
                return self._process_custom_event(payload, correlation_id)

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

            # Step 3: Get customer info (with auto-create from context if not exists)
            customer = self._get_customer(payload.customer_id, payload.context)
            if not customer:
                logger.error(
                    f"❌ Customer {payload.customer_id} not found and could not be auto-created. "
                    f"Ensure 'nombre' is provided in context or sync customer first."
                )
                return OrchestrationResult(
                    success=False,
                    notifications_queued=0,
                    errors=[
                        f"Customer {payload.customer_id} not found. "
                        "Provide 'nombre' in context or sync customer before dispatching notifications."
                    ],
                    correlation_id=correlation_id,
                )

            # Step 4: Get customer preferences
            preferences = self._get_customer_preferences(payload.customer_id)

            # Step 4.5: Enrich context minimally (only nombre if missing)
            enriched_context = self._enrich_context_minimal(payload, customer)

            # Step 4.6: Dynamic validation - extract variables from templates and validate context
            validation_result = self._validate_template_variables(
                enabled_channels,
                enriched_context,
            )
            if not validation_result["valid"]:
                logger.error(
                    f"Template validation failed for customer {payload.customer_id}: "
                    f"Missing variables: {validation_result['missing_variables']}"
                )
                return OrchestrationResult(
                    success=False,
                    notifications_queued=0,
                    errors=[
                        f"Missing required template variables: {', '.join(validation_result['missing_variables'])}. "
                        f"Please provide these fields in the 'context' object."
                    ],
                    correlation_id=correlation_id,
                )

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
                        enriched_context,
                    )

                    rendered_subject = None
                    if channel_config.template.subject:
                        rendered_subject = template_service.render(
                            channel_config.template.subject,
                            enriched_context,
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
                        context=enriched_context,
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

    def _process_custom_event(
        self,
        payload: EventPayload,
        correlation_id: str,
    ) -> OrchestrationResult:
        """
        Process custom events without requiring service_type/phase.

        Custom events:
        - Don't use OrchestrationConfig
        - Use only email and whatsapp channels (no push)
        - Require 'subject' and 'body' in context
        - Can optionally use template variables for personalization

        Args:
            payload: Event data with event_type = "custom"
            correlation_id: Correlation ID for tracking

        Returns:
            OrchestrationResult with queued notification count
        """
        errors = []
        notifications_queued = 0

        logger.info(f"Processing custom event for customer {payload.customer_id}")

        # Step 1: Validate required context fields for custom events
        if "subject" not in payload.context or "body" not in payload.context:
            return OrchestrationResult(
                success=False,
                notifications_queued=0,
                errors=[
                    "Custom events require 'subject' and 'body' in context. "
                    "Example: {'subject': 'Welcome!', 'body': 'Hello {{Nombre}}...', 'nombre': 'Carlos'}"
                ],
                correlation_id=correlation_id,
            )

        # Step 2: Get customer info
        customer = self._get_customer(payload.customer_id)
        if not customer:
            logger.error(f"Customer not found: {payload.customer_id}")
            return OrchestrationResult(
                success=False,
                notifications_queued=0,
                errors=["Customer not found"],
                correlation_id=correlation_id,
            )

        # Step 3: Enrich context minimally (add customer name if missing)
        enriched_context = self._enrich_context_minimal(payload, customer)

        # Step 4: Render subject and body with template variables
        subject = enriched_context.get("subject", "")
        body = enriched_context.get("body", "")

        try:
            rendered_subject = template_service.render(subject, enriched_context)
            rendered_body = template_service.render(body, enriched_context)
        except Exception as e:
            return OrchestrationResult(
                success=False,
                notifications_queued=0,
                errors=[f"Template rendering failed: {str(e)}"],
                correlation_id=correlation_id,
            )

        # Step 5: Define channels for custom events (only email and whatsapp)
        custom_channels = [NotificationChannel.EMAIL, NotificationChannel.WHATSAPP]

        # Step 6: Queue notifications for available channels
        for channel in custom_channels:
            recipient = customer.get_recipient_for_channel(channel)
            if recipient:
                try:
                    dispatch_service.queue_notification(
                        channel=channel,
                        recipient=recipient,
                        subject=rendered_subject,
                        body=rendered_body,
                        event_type=payload.event_type,
                        customer_id=payload.customer_id,
                        template_id=None,  # No template used for custom events
                        template_name="custom_event",
                        context=enriched_context,
                        correlation_id=correlation_id,
                        priority_order=[NotificationChannel.EMAIL, NotificationChannel.WHATSAPP],
                    )

                    notifications_queued += 1
                    logger.info(f"Queued custom {channel} notification to {recipient}")

                except Exception as e:
                    error_msg = f"Failed to queue custom {channel}: {str(e)}"
                    errors.append(error_msg)
                    logger.error(error_msg)
            else:
                logger.info(f"No {channel} recipient for customer {payload.customer_id}")

        # Step 7: Check if at least one notification was queued
        if notifications_queued == 0:
            return OrchestrationResult(
                success=False,
                notifications_queued=0,
                errors=["No valid email or whatsapp contact for this customer"],
                correlation_id=correlation_id,
            )

        return OrchestrationResult(
            success=len(errors) == 0,
            notifications_queued=notifications_queued,
            errors=errors,
            correlation_id=correlation_id,
        )

    def _enrich_context_minimal(
        self,
        payload: EventPayload,
        customer: CustomerContactInfo,
    ) -> Dict[str, Any]:
        """
        Minimal context enrichment: ONLY add customer name if missing.

        User requirement: Only enrich when unambiguous.
        Do NOT enrich vehiculo, taller, or placa (ambiguous - customer may have multiple vehicles/talleres).

        Context from request ALWAYS takes precedence.
        """
        enriched = {}

        # Normalize keys for comparison
        normalized_keys = {self._normalize(k) for k in payload.context.keys()}

        # Only enrich 'nombre' if not present
        if "nombre" not in normalized_keys:
            enriched["Nombre"] = customer.full_name

        # Merge: request context overrides enriched
        return {**enriched, **payload.context}

    def _validate_template_variables(
        self,
        enabled_channels: List,
        enriched_context: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Dynamic validation: Extract variables from templates and validate against context.

        This ensures that ALL variables used in templates are present in the context.
        Validation is accent-insensitive (Vehículo matches Vehiculo).

        Args:
            enabled_channels: List of PhaseChannelConfig with templates
            enriched_context: Context dictionary (already enriched)

        Returns:
            Dict with 'valid' (bool) and 'missing_variables' (list)
        """
        all_required_variables = set()

        # Extract variables from all enabled channel templates
        for channel_config in enabled_channels:
            template = channel_config.template
            if not template:
                continue

            # Extract variables from template body
            body_vars = template_service.get_variables(template.body)
            all_required_variables.update(body_vars)

            # Extract variables from subject (if exists)
            if template.subject:
                subject_vars = template_service.get_variables(template.subject)
                all_required_variables.update(subject_vars)

        # Normalize both required variables and context keys (accent-insensitive)
        normalized_required = {self._normalize(var) for var in all_required_variables}
        normalized_context_keys = {self._normalize(k) for k in enriched_context.keys()}

        # Find missing variables
        missing_variables = normalized_required - normalized_context_keys

        return {
            "valid": len(missing_variables) == 0,
            "missing_variables": sorted(list(missing_variables)),
        }

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

    def _auto_create_customer_from_context(
        self,
        customer_id: str,
        context: Dict[str, Any]
    ) -> Optional[CustomerContactInfo]:
        """
        Auto-create customer from dispatch context if data is available.

        This solves race conditions where sync hasn't completed yet.
        The sync task will update the customer later (idempotent).

        Args:
            customer_id: Customer identifier from Core
            context: Dispatch context that may contain customer data

        Returns:
            Created customer or None if insufficient data
        """
        # Extract customer data from context (case-insensitive)
        nombre = None
        email = None
        phone = None
        whatsapp = None

        # Normalize context keys for case-insensitive lookup
        normalized_context = {self._normalize(k): v for k, v in context.items()}

        # Try to extract name
        if "nombre" in normalized_context:
            nombre = normalized_context["nombre"]

        # Try to extract contact info
        if "email" in normalized_context:
            email = normalized_context["email"]
        if "phone" in normalized_context or "telefono" in normalized_context:
            phone = normalized_context.get("phone") or normalized_context.get("telefono")
        if "whatsapp" in normalized_context:
            whatsapp = normalized_context["whatsapp"]

        # Minimum requirement: customer_id + nombre
        if not nombre:
            logger.warning(
                f"Cannot auto-create customer {customer_id}: missing 'nombre' in context"
            )
            return None

        # Split name into first_name and last_name
        name_parts = nombre.strip().split(maxsplit=1)
        first_name = name_parts[0]
        last_name = name_parts[1] if len(name_parts) > 1 else ""

        try:
            customer = CustomerContactInfo.objects.create(
                customer_id=customer_id,
                first_name=first_name,
                last_name=last_name,
                email=email,
                phone=phone,
                whatsapp=whatsapp,
            )

            logger.info(
                f"✅ Auto-created customer {customer_id} from dispatch context "
                f"(name: {nombre}, email: {email})"
            )

            return customer

        except Exception as e:
            logger.error(
                f"Failed to auto-create customer {customer_id}: {e}",
                exc_info=True
            )
            return None

    def _get_customer(self, customer_id: str, context: Dict[str, Any] = None) -> Optional[CustomerContactInfo]:
        """
        Retrieve customer contact information.

        If customer doesn't exist and context is provided, attempt to auto-create
        from context to solve race conditions with sync tasks.

        Args:
            customer_id: Customer identifier
            context: Optional dispatch context for auto-creation

        Returns:
            CustomerContactInfo or None
        """
        customer = CustomerContactInfo.objects.filter(
            customer_id=customer_id,
        ).first()

        # If not found and we have context, try auto-create
        if not customer and context:
            logger.info(
                f"Customer {customer_id} not found in database, attempting auto-create from context"
            )
            customer = self._auto_create_customer_from_context(customer_id, context)

        return customer

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

        # Then, add any enabled channels not in preferences (excluding explicitly disabled ones)
        # Query which channels customer explicitly disabled
        disabled_channels = set(
            CustomerChannelPreference.objects.filter(
                customer__customer_id=customer.customer_id,
                enabled=False
            ).values_list('channel', flat=True)
        )

        for channel, config in enabled_channel_map.items():
            # Skip if already used OR explicitly disabled by customer
            if channel not in used_channels and channel not in disabled_channels:
                recipient = customer.get_recipient_for_channel(channel)
                if recipient:
                    result.append((config, recipient))
                    used_channels.add(channel)

        return result


# Singleton instance
orchestration_engine = OrchestrationEngine()
