"""
App configuration for synchronization module.
"""
from django.apps import AppConfig


class SynchronizationConfig(AppConfig):
    """Configuration for the synchronization app."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.synchronization"
    verbose_name = "Data Synchronization"
