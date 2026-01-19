"""
Configuración de pytest para el proyecto Ambacar Notification Service.

Este archivo configura el entorno de testing para Django y pytest.
"""

import os
import sys

import django
import pytest
from django.conf import settings

# Asegurar que el directorio del proyecto esté en el path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def pytest_configure():
    """Configurar Django antes de ejecutar los tests."""
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.development')
    os.environ.setdefault('SECRET_KEY', 'test-secret-key-for-pytest')
    os.environ.setdefault('DATABASE_URL', 'sqlite:///test_db.sqlite3')
    os.environ.setdefault('REDIS_URL', 'redis://localhost:6379/0')

    django.setup()


@pytest.fixture(scope='session')
def django_db_setup():
    """Configurar la base de datos para los tests."""
    pass


@pytest.fixture
def client():
    """Fixture para el cliente de testing de Django."""
    from django.test import Client
    return Client()


@pytest.fixture
def api_client():
    """Fixture para el cliente de API REST."""
    from rest_framework.test import APIClient
    return APIClient()