"""
URL configuration for synchronization (internal API) endpoints.
"""
from django.urls import path
from .views import (
    SyncCustomerView,
    SyncVehicleView,
    SyncGlobalPhasesView,
    SyncVehiclePhasesView,
    TaskStatusView,
)

app_name = "synchronization"

urlpatterns = [
    # Customer and Vehicle sync
    path("customers/sync/", SyncCustomerView.as_view(), name="sync-customer"),
    path("vehicles/sync/", SyncVehicleView.as_view(), name="sync-vehicle"),

    # Phase sync
    path("phases/sync/", SyncGlobalPhasesView.as_view(), name="sync-global-phases"),
    path(
        "vehicles/<str:plate>/phases/sync/",
        SyncVehiclePhasesView.as_view(),
        name="sync-vehicle-phases"
    ),

    # Task status
    path("tasks/<str:task_id>/status/", TaskStatusView.as_view(), name="task-status"),
]
