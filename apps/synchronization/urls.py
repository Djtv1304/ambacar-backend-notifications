"""
URL configuration for synchronization (internal API) endpoints.
"""
from django.urls import path
from .views import SyncCustomerView, SyncVehicleView

app_name = "synchronization"

urlpatterns = [
    path("customers/sync/", SyncCustomerView.as_view(), name="sync-customer"),
    path("vehicles/sync/", SyncVehicleView.as_view(), name="sync-vehicle"),
]
