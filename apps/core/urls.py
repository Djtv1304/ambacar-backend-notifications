"""
URL configuration for core app.
"""
from django.urls import path
from .views import DatabaseHealthView, RedisHealthView

app_name = "core"

urlpatterns = [
    path("database/", DatabaseHealthView.as_view(), name="database-health"),
    path("redis/", RedisHealthView.as_view(), name="redis-health"),
]
