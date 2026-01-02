"""
Django admin configuration for notifications app.
"""
from django.contrib import admin

from .models import (
    NotificationTemplate,
    ServicePhase,
    ServiceType,
    OrchestrationConfig,
    PhaseChannelConfig,
    TallerChannelConfig,
    PushSubscription,
    CustomerContactInfo,
    CustomerChannelPreference,
    Vehicle,
    MaintenanceReminder,
    NotificationLog,
)


@admin.register(NotificationTemplate)
class NotificationTemplateAdmin(admin.ModelAdmin):
    list_display = ["name", "channel", "target", "is_default", "is_active", "created_at"]
    list_filter = ["channel", "target", "is_default", "is_active"]
    search_fields = ["name", "body"]
    ordering = ["-created_at"]


@admin.register(ServicePhase)
class ServicePhaseAdmin(admin.ModelAdmin):
    list_display = ["order", "name", "icon", "is_active"]
    list_filter = ["is_active"]
    ordering = ["order"]


@admin.register(ServiceType)
class ServiceTypeAdmin(admin.ModelAdmin):
    list_display = ["name", "parent", "icon", "is_active"]
    list_filter = ["is_active", "parent"]
    search_fields = ["name"]


class PhaseChannelConfigInline(admin.TabularInline):
    model = PhaseChannelConfig
    extra = 0
    fields = ["phase", "channel", "enabled", "template"]


@admin.register(OrchestrationConfig)
class OrchestrationConfigAdmin(admin.ModelAdmin):
    list_display = ["service_type", "target", "taller_id", "is_active"]
    list_filter = ["target", "is_active"]
    search_fields = ["service_type__name", "taller_id"]
    inlines = [PhaseChannelConfigInline]


@admin.register(TallerChannelConfig)
class TallerChannelConfigAdmin(admin.ModelAdmin):
    list_display = [
        "taller_id",
        "taller_name",
        "email_enabled",
        "push_enabled",
        "whatsapp_enabled",
    ]
    search_fields = ["taller_id", "taller_name"]


@admin.register(PushSubscription)
class PushSubscriptionAdmin(admin.ModelAdmin):
    list_display = ["customer_id", "is_active", "failure_count", "last_used_at", "created_at"]
    list_filter = ["is_active"]
    search_fields = ["customer_id"]
    readonly_fields = ["endpoint", "p256dh_key", "auth_key"]


class CustomerChannelPreferenceInline(admin.TabularInline):
    model = CustomerChannelPreference
    extra = 0


@admin.register(CustomerContactInfo)
class CustomerContactInfoAdmin(admin.ModelAdmin):
    list_display = ["customer_id", "first_name", "last_name", "email", "phone"]
    search_fields = ["customer_id", "first_name", "last_name", "email"]
    inlines = [CustomerChannelPreferenceInline]


@admin.register(Vehicle)
class VehicleAdmin(admin.ModelAdmin):
    list_display = ["plate", "brand", "model", "year", "customer_id", "current_kilometers"]
    list_filter = ["brand", "year"]
    search_fields = ["plate", "customer_id"]


@admin.register(MaintenanceReminder)
class MaintenanceReminderAdmin(admin.ModelAdmin):
    list_display = [
        "vehicle",
        "description",
        "type",
        "status",
        "target_date",
        "target_kilometers",
    ]
    list_filter = ["status", "type"]
    search_fields = ["vehicle__plate", "customer_id", "description"]


@admin.register(NotificationLog)
class NotificationLogAdmin(admin.ModelAdmin):
    list_display = [
        "event_type",
        "channel",
        "recipient_id",
        "status",
        "sent_at",
        "retry_count",
    ]
    list_filter = ["status", "channel", "event_type"]
    search_fields = ["recipient_id", "correlation_id"]
    readonly_fields = [
        "event_type",
        "channel",
        "recipient_id",
        "recipient_address",
        "template_id",
        "template_name",
        "subject",
        "body_preview",
        "status",
        "sent_at",
        "delivered_at",
        "error_reason",
        "retry_count",
        "context_data",
        "correlation_id",
        "parent_log",
    ]
    date_hierarchy = "created_at"
