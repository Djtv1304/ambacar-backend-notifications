"""
URL configuration for synchronization (internal API) endpoints.
"""
from django.urls import path
from .views import SyncCustomerView, SyncVehicleView, TaskStatusView

app_name = "synchronization"

urlpatterns = [
    path("customers/sync/", SyncCustomerView.as_view(), name="sync-customer"),
    path("vehicles/sync/", SyncVehicleView.as_view(), name="sync-vehicle"),
    path("tasks/<str:task_id>/status/", TaskStatusView.as_view(), name="task-status"),
]
