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
            self._seed_phases(force)
            self._seed_service_types(force)
            self._seed_templates(force)

        self.stdout.write(self.style.SUCCESS("Initial data seeded successfully!"))

    def _seed_phases(self, force: bool):
        """Seed service phases."""
        phases_data = [
            {"name": "Agendar Cita", "icon": "Calendar", "order": 1},
            {"name": "Recepción", "icon": "ClipboardCheck", "order": 2},
            {"name": "Reparación", "icon": "Wrench", "order": 3},
            {"name": "Control Calidad", "icon": "ShieldCheck", "order": 4},
            {"name": "Entrega", "icon": "CarFront", "order": 5},
        ]

        if force:
            ServicePhase.objects.all().delete()
            self.stdout.write("Deleted existing phases")

        for data in phases_data:
            phase, created = ServicePhase.objects.update_or_create(
                order=data["order"],
                defaults=data,
            )
            status = "Created" if created else "Updated"
            self.stdout.write(f"  {status} phase: {phase.name}")

    def _seed_service_types(self, force: bool):
        """Seed service types."""
        if force:
            ServiceType.objects.all().delete()
            self.stdout.write("Deleted existing service types")

        # Main service types
        service_types = [
            {"name": "Avalúo Comercial", "icon": "FileSearch"},
            {"name": "Avería/Revisión", "icon": "AlertTriangle"},
            {"name": "Colisión/Pintura", "icon": "Paintbrush"},
            {"name": "Mantenimiento Preventivo", "icon": "Settings"},
            {"name": "Avalúo MG", "icon": "FileCheck"},
        ]

        # Subtypes
        subtypes = {
            "Avería/Revisión": [
                {"name": "Frenos", "icon": "Circle"},
                {"name": "Diagnóstico", "icon": "Search"},
                {"name": "Alineación", "icon": "AlignCenter"},
            ],
            "Colisión/Pintura": [
                {"name": "Siniestro", "icon": "AlertOctagon"},
                {"name": "Golpe", "icon": "Hammer"},
                {"name": "Pintura", "icon": "Paintbrush2"},
            ],
        }

        for type_data in service_types:
            service_type, created = ServiceType.objects.update_or_create(
                name=type_data["name"],
                parent=None,
                defaults={"icon": type_data["icon"]},
            )
            status = "Created" if created else "Updated"
            self.stdout.write(f"  {status} service type: {service_type.name}")

            # Create subtypes if any
            if type_data["name"] in subtypes:
                for subtype_data in subtypes[type_data["name"]]:
                    subtype, created = ServiceType.objects.update_or_create(
                        name=subtype_data["name"],
                        parent=service_type,
                        defaults={"icon": subtype_data["icon"]},
                    )
                    status = "Created" if created else "Updated"
                    self.stdout.write(f"    {status} subtype: {subtype.name}")

    def _seed_templates(self, force: bool):
        """Seed notification templates."""
        if force:
            NotificationTemplate.objects.filter(is_default=True).delete()
            self.stdout.write("Deleted existing default templates")

        templates_data = [
            # Client Email Templates
            {
                "name": "Bienvenida - Cita Agendada",
                "subject": "✅ Tu cita ha sido confirmada - {{Taller}}",
                "body": "Hola {{Nombre}},\n\nTu cita para {{Vehículo}} ({{Placa}}) ha sido confirmada para el {{Fecha}} a las {{Hora}}.\n\nTe esperamos en {{Taller}}.\n\n¡Gracias por confiar en nosotros!",
                "channel": "email",
                "target": "clients",
                "is_default": True,
            },
            {
                "name": "Vehículo en Recepción",
                "subject": "🚗 Hemos recibido tu vehículo - {{Taller}}",
                "body": "Hola {{Nombre}},\n\nTu {{Vehículo}} ({{Placa}}) ha sido recibido en nuestras instalaciones.\n\nOrden de trabajo: {{Orden}}\n\nTe mantendremos informado del progreso.",
                "channel": "email",
                "target": "clients",
                "is_default": True,
            },
            {
                "name": "Vehículo Listo para Entrega",
                "subject": "🎉 Tu vehículo está listo - {{Taller}}",
                "body": "Hola {{Nombre}},\n\n¡Excelentes noticias! Tu {{Vehículo}} ({{Placa}}) ya está listo para ser retirado.\n\nPuedes pasar a recogerlo en nuestro horario de atención.\n\n¡Gracias por tu preferencia!",
                "channel": "email",
                "target": "clients",
                "is_default": True,
            },
            # Client WhatsApp Templates
            {
                "name": "Confirmación de Cita (WA)",
                "body": "✅ *Cita Confirmada*\n\nHola {{Nombre}}, tu cita para {{Vehículo}} está confirmada:\n\n📅 {{Fecha}}\n⏰ {{Hora}}\n\n¡Te esperamos!",
                "channel": "whatsapp",
                "target": "clients",
                "is_default": True,
            },
            {
                "name": "Actualización de Progreso (WA)",
                "body": "🔧 *Actualización de Servicio*\n\nHola {{Nombre}}, tu {{Vehículo}} ahora está en: *{{Fase}}*\n\nTe seguimos informando.",
                "channel": "whatsapp",
                "target": "clients",
                "is_default": True,
            },
            {
                "name": "Vehículo Listo (WA)",
                "body": "🎉 *¡Tu vehículo está listo!*\n\nHola {{Nombre}}, tu {{Vehículo}} ({{Placa}}) ya puede ser retirado.\n\n📍 {{Taller}}",
                "channel": "whatsapp",
                "target": "clients",
                "is_default": True,
            },
            # Client Push Templates
            {
                "name": "Cita Confirmada (Push)",
                "body": "Tu cita para {{Vehículo}} ha sido confirmada para el {{Fecha}}",
                "channel": "push",
                "target": "clients",
                "is_default": True,
            },
            {
                "name": "Cambio de Fase (Push)",
                "body": "Tu vehículo {{Placa}} ahora está en: {{Fase}}",
                "channel": "push",
                "target": "clients",
                "is_default": True,
            },
            {
                "name": "Vehículo Listo (Push)",
                "body": "¡Tu {{Vehículo}} está listo para retirar!",
                "channel": "push",
                "target": "clients",
                "is_default": True,
            },
            # Staff Templates
            {
                "name": "Nueva OT Asignada",
                "body": "Se te ha asignado la orden {{Orden}} - {{Vehículo}}",
                "channel": "push",
                "target": "staff",
                "is_default": True,
            },
            {
                "name": "Resumen Diario",
                "subject": "📋 Tu resumen de órdenes - {{Fecha}}",
                "body": "Hola {{Técnico}},\n\nAquí está tu resumen de órdenes para hoy.\n\nRevisa el panel para más detalles.",
                "channel": "email",
                "target": "staff",
                "is_default": True,
            },
            # Maintenance Reminder Templates
            {
                "name": "Recordatorio de Mantenimiento (Email)",
                "subject": "🔧 Tu vehículo necesita atención - {{Taller}}",
                "body": "Hola {{Nombre}},\n\nTe recordamos que tu {{Vehículo}} ({{Placa}}) está próximo a requerir mantenimiento.\n\n{{Descripcion}}\n\nAgenda tu cita con nosotros.\n\n{{Taller}}",
                "channel": "email",
                "target": "clients",
                "is_default": True,
            },
            {
                "name": "Recordatorio de Mantenimiento (WA)",
                "body": "🔧 *Recordatorio de Mantenimiento*\n\nHola {{Nombre}}, tu {{Vehículo}} ({{Placa}}) está próximo a su servicio:\n\n{{Descripcion}}\n\n¡Agenda tu cita!",
                "channel": "whatsapp",
                "target": "clients",
                "is_default": True,
            },
        ]

        for data in templates_data:
            template, created = NotificationTemplate.objects.update_or_create(
                name=data["name"],
                channel=data["channel"],
                target=data["target"],
                is_default=True,
                defaults={
                    "subject": data.get("subject"),
                    "body": data["body"],
                },
            )
            status = "Created" if created else "Updated"
            self.stdout.write(f"  {status} template: {template.name}")
