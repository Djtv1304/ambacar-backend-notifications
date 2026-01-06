"""
URL configuration for core app.
"""
from django.urls import path
from .views import DatabaseHealthView

app_name = "core"

urlpatterns = [
    path("database/", DatabaseHealthView.as_view(), name="database-health"),
]
