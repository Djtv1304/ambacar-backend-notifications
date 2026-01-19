from .templates import NotificationTemplate
from .orchestration import (
    ServicePhase,
    ServiceType,
    OrchestrationConfig,
    PhaseChannelConfig,
)
from .channels import TallerChannelConfig, PushSubscription
from .customers import CustomerContactInfo, CustomerChannelPreference
from .vehicles import Vehicle, MaintenanceReminder, VehiclePhaseConfig
from .logs import NotificationLog

__all__ = [
    # Templates
    "NotificationTemplate",
    # Orchestration
    "ServicePhase",
    "ServiceType",
    "OrchestrationConfig",
    "PhaseChannelConfig",
    # Channels
    "TallerChannelConfig",
    "PushSubscription",
    # Customers
    "CustomerContactInfo",
    "CustomerChannelPreference",
    # Vehicles
    "Vehicle",
    "MaintenanceReminder",
    "VehiclePhaseConfig",
    # Logs
    "NotificationLog",
]
