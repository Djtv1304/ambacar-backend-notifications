"""
Management command to seed initial data for the notification service.
"""
from django.core.management.base import BaseCommand
from django.db import transaction

from apps.notifications.models import (
    ServicePhase,
    ServiceType,
    NotificationTemplate,
)


class Command(BaseCommand):
    help = "Seed initial data for notification service (phases, service types, templates)"

    def add_arguments(self, parser):
        parser.add_argument(
            "--force",
            action="store_true",
            help="Force re-creation of data even if it exists",
        )

    def handle(self, *args, **options):
        force = options["force"]

        with transaction.atomic():
            phases = self._seed_phases(force)
            service_types, subtypes = self._seed_service_types(force)
            self._seed_templates(force, phases, service_types, subtypes)

        self.stdout.write(self.style.SUCCESS("Initial data seeded successfully!"))

    def _seed_phases(self, force: bool) -> dict:
        """Seed service phases and return a dict mapping phase keys to instances."""
        phases_data = [
            {"id": "phase-schedule", "name": "Agendar Cita", "icon": "Calendar", "order": 1},
            {"id": "phase-reception", "name": "Recepción", "icon": "ClipboardCheck", "order": 2},
            {"id": "phase-repair", "name": "Reparación", "icon": "Wrench", "order": 3},
            {"id": "phase-quality", "name": "Control Calidad", "icon": "ShieldCheck", "order": 4},
            {"id": "phase-delivery", "name": "Entrega", "icon": "CarFront", "order": 5},
        ]

        if force:
            ServicePhase.objects.all().delete()
            self.stdout.write("Deleted existing phases")

        phases = {}
        for data in phases_data:
            phase_id = data.pop("id")
            phase, created = ServicePhase.objects.update_or_create(
                order=data["order"],
                defaults=data,
            )
            phases[phase_id] = phase
            status = "Created" if created else "Updated"
            self.stdout.write(f"  {status} phase: {phase.name}")

        return phases

    def _seed_service_types(self, force: bool) -> tuple:
        """Seed service types and return dicts mapping type keys to instances."""
        if force:
            ServiceType.objects.all().delete()
            self.stdout.write("Deleted existing service types")

        # Main service types
        service_types_data = [
            {"id": "avaluo-comercial", "name": "Avalúo Comercial", "icon": "FileSearch"},
            {"id": "averia-revision", "name": "Avería/Revisión", "icon": "AlertTriangle"},
            {"id": "colision-pintura", "name": "Colisión/Pintura", "icon": "Paintbrush"},
            {"id": "mantenimiento-preventivo", "name": "Mantenimiento Preventivo", "icon": "Settings"},
            {"id": "avaluo-mg", "name": "Avalúo MG", "icon": "FileCheck"},
        ]

        # Subtypes
        subtypes_data = {
            "averia-revision": [
                {"id": "averia-frenos", "name": "Frenos", "icon": "Circle"},
                {"id": "averia-diagnostico", "name": "Diagnóstico", "icon": "Search"},
                {"id": "averia-alineacion", "name": "Alineación", "icon": "AlignCenter"},
            ],
            "colision-pintura": [
                {"id": "colision-siniestro", "name": "Siniestro", "icon": "AlertOctagon"},
                {"id": "colision-golpe", "name": "Golpe", "icon": "Hammer"},
                {"id": "colision-pintura", "name": "Pintura", "icon": "Paintbrush2"},
            ],
        }

        service_types = {}
        subtypes = {}

        for type_data in service_types_data:
            type_id = type_data.pop("id")
            service_type, created = ServiceType.objects.update_or_create(
                name=type_data["name"],
                parent=None,
                defaults={"icon": type_data["icon"]},
            )
            service_types[type_id] = service_type
            status = "Created" if created else "Updated"
            self.stdout.write(f"  {status} service type: {service_type.name}")

            # Create subtypes if any
            if type_id in subtypes_data:
                for subtype_data in subtypes_data[type_id]:
                    subtype_id = subtype_data.pop("id")
                    subtype, created = ServiceType.objects.update_or_create(
                        name=subtype_data["name"],
                        parent=service_type,
                        defaults={"icon": subtype_data["icon"]},
                    )
                    subtypes[subtype_id] = subtype
                    status = "Created" if created else "Updated"
                    self.stdout.write(f"    {status} subtype: {subtype.name}")

        return service_types, subtypes

    def _seed_templates(
        self,
        force: bool,
        phases: dict,
        service_types: dict,
        subtypes: dict
    ):
        """Seed notification templates linked to service types and phases."""
        if force:
            NotificationTemplate.objects.filter(is_default=True).delete()
            self.stdout.write("Deleted existing default templates")

        # Template definitions organized by service type, phase, and channel
        templates_config = self._get_templates_config()

        created_count = 0
        updated_count = 0

        for config in templates_config:
            # Resolve service_type and phase
            service_type = service_types.get(config["service_type_id"])
            phase = phases.get(config["phase_id"])
            subtype = subtypes.get(config.get("subtype_id")) if config.get("subtype_id") else None

            if not service_type or not phase:
                self.stdout.write(
                    self.style.WARNING(
                        f"  Skipping template {config['name']}: "
                        f"service_type={config['service_type_id']}, phase={config['phase_id']}"
                    )
                )
                continue

            template, created = NotificationTemplate.objects.update_or_create(
                name=config["name"],
                channel=config["channel"],
                target=config["target"],
                service_type=service_type,
                phase=phase,
                subtype=subtype,
                is_default=True,
                defaults={
                    "subject": config.get("subject"),
                    "body": config["body"],
                    "is_active": True,
                },
            )

            if created:
                created_count += 1
            else:
                updated_count += 1

        self.stdout.write(f"  Templates: {created_count} created, {updated_count} updated")

    def _get_templates_config(self) -> list:
        """Return template configuration data."""
        return [
            # ============================================
            # MANTENIMIENTO PREVENTIVO
            # ============================================

            # Fase: Agendar Cita
            {
                "name": "Mantenimiento - Cita Agendada",
                "subject": "✅ Tu cita de mantenimiento ha sido confirmada - {{Taller}}",
                "body": "Hola {{Nombre}},\n\nTu cita de mantenimiento preventivo para {{Vehículo}} ({{Placa}}) ha sido confirmada para el {{Fecha}} a las {{Hora}}.\n\nTe esperamos en {{Taller}}.\n\n¡Gracias por confiar en nosotros!",
                "channel": "email",
                "target": "clients",
                "service_type_id": "mantenimiento-preventivo",
                "phase_id": "phase-schedule",
            },
            {
                "name": "Mantenimiento - Cita (WA)",
                "body": "✅ *Cita de Mantenimiento Confirmada*\n\nHola {{Nombre}}, tu cita para {{Vehículo}} está confirmada:\n\n📅 {{Fecha}}\n⏰ {{Hora}}\n\n¡Te esperamos!",
                "channel": "whatsapp",
                "target": "clients",
                "service_type_id": "mantenimiento-preventivo",
                "phase_id": "phase-schedule",
            },
            {
                "name": "Mantenimiento - Cita (Push)",
                "body": "Tu cita de mantenimiento para {{Vehículo}} ha sido confirmada para el {{Fecha}}",
                "channel": "push",
                "target": "clients",
                "service_type_id": "mantenimiento-preventivo",
                "phase_id": "phase-schedule",
            },

            # Fase: Recepción
            {
                "name": "Mantenimiento - Vehículo Recibido",
                "subject": "🚗 Hemos recibido tu vehículo para mantenimiento - {{Taller}}",
                "body": "Hola {{Nombre}},\n\nTu {{Vehículo}} ({{Placa}}) ha sido recibido para su mantenimiento preventivo.\n\nOrden de trabajo: {{Orden}}\n\nTe mantendremos informado del progreso.",
                "channel": "email",
                "target": "clients",
                "service_type_id": "mantenimiento-preventivo",
                "phase_id": "phase-reception",
            },
            {
                "name": "Mantenimiento - Recepción (WA)",
                "body": "🚗 *Vehículo Recibido*\n\nHola {{Nombre}}, tu {{Vehículo}} ha ingresado a mantenimiento.\n\nOrden: {{Orden}}",
                "channel": "whatsapp",
                "target": "clients",
                "service_type_id": "mantenimiento-preventivo",
                "phase_id": "phase-reception",
            },
            {
                "name": "Mantenimiento - Recepción (Push)",
                "body": "Tu {{Vehículo}} ha sido recibido para mantenimiento",
                "channel": "push",
                "target": "clients",
                "service_type_id": "mantenimiento-preventivo",
                "phase_id": "phase-reception",
            },

            # Fase: Reparación
            {
                "name": "Mantenimiento - En Proceso",
                "subject": "🔧 Tu vehículo está en mantenimiento - {{Taller}}",
                "body": "Hola {{Nombre}},\n\nTu {{Vehículo}} ({{Placa}}) está siendo atendido por nuestro equipo técnico.\n\nTe notificaremos cuando esté listo.",
                "channel": "email",
                "target": "clients",
                "service_type_id": "mantenimiento-preventivo",
                "phase_id": "phase-repair",
            },
            {
                "name": "Mantenimiento - En Proceso (WA)",
                "body": "🔧 *En Mantenimiento*\n\nHola {{Nombre}}, tu {{Vehículo}} está siendo atendido.\n\nTe avisamos cuando esté listo.",
                "channel": "whatsapp",
                "target": "clients",
                "service_type_id": "mantenimiento-preventivo",
                "phase_id": "phase-repair",
            },
            {
                "name": "Mantenimiento - En Proceso (Push)",
                "body": "Tu {{Vehículo}} está en proceso de mantenimiento",
                "channel": "push",
                "target": "clients",
                "service_type_id": "mantenimiento-preventivo",
                "phase_id": "phase-repair",
            },

            # Fase: Control de Calidad
            {
                "name": "Mantenimiento - Control de Calidad",
                "subject": "✅ Control de calidad en proceso - {{Taller}}",
                "body": "Hola {{Nombre}},\n\nTu {{Vehículo}} ({{Placa}}) está pasando por nuestro control de calidad.\n\nPronto estará listo para entrega.",
                "channel": "email",
                "target": "clients",
                "service_type_id": "mantenimiento-preventivo",
                "phase_id": "phase-quality",
            },
            {
                "name": "Mantenimiento - Calidad (WA)",
                "body": "✅ *Control de Calidad*\n\nHola {{Nombre}}, tu {{Vehículo}} está en revisión final.\n\n¡Casi listo!",
                "channel": "whatsapp",
                "target": "clients",
                "service_type_id": "mantenimiento-preventivo",
                "phase_id": "phase-quality",
            },
            {
                "name": "Mantenimiento - Calidad (Push)",
                "body": "Tu {{Vehículo}} está en control de calidad",
                "channel": "push",
                "target": "clients",
                "service_type_id": "mantenimiento-preventivo",
                "phase_id": "phase-quality",
            },

            # Fase: Entrega
            {
                "name": "Mantenimiento - Listo para Entrega",
                "subject": "🎉 Tu vehículo está listo - {{Taller}}",
                "body": "Hola {{Nombre}},\n\n¡Excelentes noticias! Tu {{Vehículo}} ({{Placa}}) ya completó su mantenimiento preventivo y está listo para ser retirado.\n\nPuedes pasar a recogerlo en nuestro horario de atención.\n\n¡Gracias por tu preferencia!",
                "channel": "email",
                "target": "clients",
                "service_type_id": "mantenimiento-preventivo",
                "phase_id": "phase-delivery",
            },
            {
                "name": "Mantenimiento - Listo (WA)",
                "body": "🎉 *¡Tu vehículo está listo!*\n\nHola {{Nombre}}, tu {{Vehículo}} ({{Placa}}) ya puede ser retirado.\n\n📍 {{Taller}}",
                "channel": "whatsapp",
                "target": "clients",
                "service_type_id": "mantenimiento-preventivo",
                "phase_id": "phase-delivery",
            },
            {
                "name": "Mantenimiento - Listo (Push)",
                "body": "¡Tu {{Vehículo}} está listo para retirar!",
                "channel": "push",
                "target": "clients",
                "service_type_id": "mantenimiento-preventivo",
                "phase_id": "phase-delivery",
            },

            # ============================================
            # AVERÍA/REVISIÓN (Genéricos)
            # ============================================

            {
                "name": "Avería - Cita Agendada",
                "subject": "🔍 Tu cita de revisión ha sido confirmada - {{Taller}}",
                "body": "Hola {{Nombre}},\n\nTu cita para revisión de {{Vehículo}} ({{Placa}}) ha sido confirmada para el {{Fecha}} a las {{Hora}}.\n\nNuestro equipo evaluará tu vehículo.\n\n¡Te esperamos!",
                "channel": "email",
                "target": "clients",
                "service_type_id": "averia-revision",
                "phase_id": "phase-schedule",
            },
            {
                "name": "Avería - Cita (WA)",
                "body": "🔍 *Cita de Revisión Confirmada*\n\nHola {{Nombre}}, tu cita para {{Vehículo}} está confirmada:\n\n📅 {{Fecha}}\n⏰ {{Hora}}\n\nEvaluaremos tu vehículo.",
                "channel": "whatsapp",
                "target": "clients",
                "service_type_id": "averia-revision",
                "phase_id": "phase-schedule",
            },
            {
                "name": "Avería - Cita (Push)",
                "body": "Tu cita de revisión para {{Vehículo}} ha sido confirmada para el {{Fecha}}",
                "channel": "push",
                "target": "clients",
                "service_type_id": "averia-revision",
                "phase_id": "phase-schedule",
            },
            {
                "name": "Avería - Listo para Entrega",
                "subject": "🎉 Tu vehículo está listo - {{Taller}}",
                "body": "Hola {{Nombre}},\n\nTu {{Vehículo}} ({{Placa}}) ha sido reparado y está listo para ser retirado.\n\n¡Gracias por confiar en nosotros!",
                "channel": "email",
                "target": "clients",
                "service_type_id": "averia-revision",
                "phase_id": "phase-delivery",
            },
            {
                "name": "Avería - Listo (WA)",
                "body": "🎉 *¡Tu vehículo está listo!*\n\nHola {{Nombre}}, tu {{Vehículo}} ya puede ser retirado.\n\n📍 {{Taller}}",
                "channel": "whatsapp",
                "target": "clients",
                "service_type_id": "averia-revision",
                "phase_id": "phase-delivery",
            },
            {
                "name": "Avería - Listo (Push)",
                "body": "¡Tu {{Vehículo}} está listo para retirar!",
                "channel": "push",
                "target": "clients",
                "service_type_id": "averia-revision",
                "phase_id": "phase-delivery",
            },

            # ============================================
            # AVERÍA/REVISIÓN - SUBTIPO: FRENOS
            # ============================================

            {
                "name": "Frenos - Cita Agendada",
                "subject": "🛞 Tu cita para revisión de frenos - {{Taller}}",
                "body": "Hola {{Nombre}},\n\nTu cita para revisión de frenos de {{Vehículo}} ({{Placa}}) ha sido confirmada para el {{Fecha}} a las {{Hora}}.\n\nLa seguridad de tu vehículo es nuestra prioridad.\n\n¡Te esperamos!",
                "channel": "email",
                "target": "clients",
                "service_type_id": "averia-revision",
                "phase_id": "phase-schedule",
                "subtype_id": "averia-frenos",
            },
            {
                "name": "Frenos - Cita (WA)",
                "body": "🛞 *Revisión de Frenos*\n\nHola {{Nombre}}, tu cita para revisión de frenos está confirmada:\n\n📅 {{Fecha}}\n⏰ {{Hora}}\n\n¡Tu seguridad es nuestra prioridad!",
                "channel": "whatsapp",
                "target": "clients",
                "service_type_id": "averia-revision",
                "phase_id": "phase-schedule",
                "subtype_id": "averia-frenos",
            },

            # ============================================
            # COLISIÓN/PINTURA (Genéricos)
            # ============================================

            {
                "name": "Colisión - Cita Agendada",
                "subject": "🎨 Tu cita para reparación está confirmada - {{Taller}}",
                "body": "Hola {{Nombre}},\n\nTu cita para reparación de {{Vehículo}} ({{Placa}}) ha sido confirmada para el {{Fecha}} a las {{Hora}}.\n\nEvaluaremos los daños y te daremos un presupuesto.\n\n¡Te esperamos!",
                "channel": "email",
                "target": "clients",
                "service_type_id": "colision-pintura",
                "phase_id": "phase-schedule",
            },
            {
                "name": "Colisión - Cita (WA)",
                "body": "🎨 *Cita de Reparación*\n\nHola {{Nombre}}, tu cita para {{Vehículo}} está confirmada:\n\n📅 {{Fecha}}\n⏰ {{Hora}}",
                "channel": "whatsapp",
                "target": "clients",
                "service_type_id": "colision-pintura",
                "phase_id": "phase-schedule",
            },
            {
                "name": "Colisión - Cita (Push)",
                "body": "Tu cita de reparación para {{Vehículo}} ha sido confirmada",
                "channel": "push",
                "target": "clients",
                "service_type_id": "colision-pintura",
                "phase_id": "phase-schedule",
            },

            # ============================================
            # COLISIÓN/PINTURA - SUBTIPO: SINIESTRO
            # ============================================

            {
                "name": "Siniestro - Cita Agendada",
                "subject": "🚨 Tu cita por siniestro está confirmada - {{Taller}}",
                "body": "Hola {{Nombre}},\n\nTu cita para evaluar el siniestro de {{Vehículo}} ({{Placa}}) ha sido confirmada para el {{Fecha}} a las {{Hora}}.\n\nNuestro equipo especializado atenderá tu caso.\n\n¡Te esperamos!",
                "channel": "email",
                "target": "clients",
                "service_type_id": "colision-pintura",
                "phase_id": "phase-schedule",
                "subtype_id": "colision-siniestro",
            },

            # ============================================
            # AVALÚO COMERCIAL
            # ============================================

            {
                "name": "Avalúo - Cita Agendada",
                "subject": "📋 Tu cita de avalúo está confirmada - {{Taller}}",
                "body": "Hola {{Nombre}},\n\nTu cita para avalúo de {{Vehículo}} ({{Placa}}) ha sido confirmada para el {{Fecha}} a las {{Hora}}.\n\nNuestro perito evaluará tu vehículo.\n\n¡Te esperamos!",
                "channel": "email",
                "target": "clients",
                "service_type_id": "avaluo-comercial",
                "phase_id": "phase-schedule",
            },
            {
                "name": "Avalúo - Cita (WA)",
                "body": "📋 *Cita de Avalúo*\n\nHola {{Nombre}}, tu cita de avalúo para {{Vehículo}} está confirmada:\n\n📅 {{Fecha}}\n⏰ {{Hora}}",
                "channel": "whatsapp",
                "target": "clients",
                "service_type_id": "avaluo-comercial",
                "phase_id": "phase-schedule",
            },
            {
                "name": "Avalúo - Cita (Push)",
                "body": "Tu cita de avalúo para {{Vehículo}} ha sido confirmada",
                "channel": "push",
                "target": "clients",
                "service_type_id": "avaluo-comercial",
                "phase_id": "phase-schedule",
            },

            # ============================================
            # AVALÚO MG
            # ============================================

            {
                "name": "Avalúo MG - Cita Agendada",
                "subject": "📋 Tu cita de avalúo MG está confirmada - {{Taller}}",
                "body": "Hola {{Nombre}},\n\nTu cita para avalúo MG de {{Vehículo}} ({{Placa}}) ha sido confirmada para el {{Fecha}} a las {{Hora}}.\n\n¡Te esperamos!",
                "channel": "email",
                "target": "clients",
                "service_type_id": "avaluo-mg",
                "phase_id": "phase-schedule",
            },
            {
                "name": "Avalúo MG - Cita (WA)",
                "body": "📋 *Cita de Avalúo MG*\n\nHola {{Nombre}}, tu cita para {{Vehículo}} está confirmada:\n\n📅 {{Fecha}}\n⏰ {{Hora}}",
                "channel": "whatsapp",
                "target": "clients",
                "service_type_id": "avaluo-mg",
                "phase_id": "phase-schedule",
            },
            {
                "name": "Avalúo MG - Cita (Push)",
                "body": "Tu cita de avalúo MG para {{Vehículo}} ha sido confirmada",
                "channel": "push",
                "target": "clients",
                "service_type_id": "avaluo-mg",
                "phase_id": "phase-schedule",
            },

            # ============================================
            # STAFF TEMPLATES
            # ============================================

            {
                "name": "Staff - Nueva OT Mantenimiento",
                "body": "Nueva orden de mantenimiento: {{Orden}} - {{Vehículo}}",
                "channel": "push",
                "target": "staff",
                "service_type_id": "mantenimiento-preventivo",
                "phase_id": "phase-reception",
            },
            {
                "name": "Staff - Nueva OT Revisión",
                "body": "Nueva orden de revisión: {{Orden}} - {{Vehículo}}",
                "channel": "push",
                "target": "staff",
                "service_type_id": "averia-revision",
                "phase_id": "phase-reception",
            },
            {
                "name": "Staff - Nueva OT Colisión",
                "body": "Nueva orden de colisión/pintura: {{Orden}} - {{Vehículo}}",
                "channel": "push",
                "target": "staff",
                "service_type_id": "colision-pintura",
                "phase_id": "phase-reception",
            },
            {
                "name": "Staff - Cita Programada",
                "subject": "📅 Nueva cita programada - {{Fecha}}",
                "body": "Se ha programado una nueva cita de mantenimiento:\n\nCliente: {{Nombre}}\nVehículo: {{Vehículo}} ({{Placa}})\nFecha: {{Fecha}} {{Hora}}",
                "channel": "email",
                "target": "staff",
                "service_type_id": "mantenimiento-preventivo",
                "phase_id": "phase-schedule",
            },
        ]
