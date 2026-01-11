"""
Health check views for system monitoring.
"""
import time
from django.db import connection
from django.conf import settings
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from drf_spectacular.utils import extend_schema, OpenApiResponse
from celery import current_app


class DatabaseHealthView(APIView):
    """
    GET /api/v1/health/database/

    Verifica el estado de la conexión a la base de datos PostgreSQL/Supabase.
    """

    @extend_schema(
        summary="Database health check",
        description="""
Verifica el estado de la conexión a la base de datos PostgreSQL/Supabase.

Retorna información sobre:
- Estado de la conexión
- Información del servidor de base de datos (nombre, versión)
- Detalles de la conexión (host, puerto, database name)
- Si está conectado a Supabase (detección automática por hostname)

Este endpoint es útil para verificar la conectividad durante el deployment en Coolify.
        """,
        responses={
            200: OpenApiResponse(
                description="Database connection is healthy",
                response={
                    "type": "object",
                    "properties": {
                        "status": {"type": "string", "example": "healthy"},
                        "database": {
                            "type": "object",
                            "properties": {
                                "engine": {"type": "string"},
                                "name": {"type": "string"},
                                "host": {"type": "string"},
                                "port": {"type": "integer"},
                                "user": {"type": "string"},
                                "version": {"type": "string"},
                                "is_supabase": {"type": "boolean"},
                            },
                        },
                        "connection": {
                            "type": "object",
                            "properties": {
                                "max_age": {"type": "integer"},
                                "health_checks_enabled": {"type": "boolean"},
                            },
                        },
                    },
                },
            ),
            503: OpenApiResponse(
                description="Database connection failed",
                response={
                    "type": "object",
                    "properties": {
                        "status": {"type": "string", "example": "unhealthy"},
                        "error": {"type": "string"},
                    },
                },
            ),
        },
        tags=["Health"],
    )
    def get(self, request):
        try:
            # Test database connection
            with connection.cursor() as cursor:
                cursor.execute("SELECT version();")
                db_version = cursor.fetchone()[0]

            # Get database configuration
            db_config = settings.DATABASES['default']

            # Extract connection info
            host = db_config.get('HOST', 'N/A')
            port = db_config.get('PORT', 'N/A')
            name = db_config.get('NAME', 'N/A')
            user = db_config.get('USER', 'N/A')
            engine = db_config.get('ENGINE', 'N/A').split('.')[-1]

            # Check if Supabase (by hostname pattern)
            is_supabase = 'supabase.com' in str(host).lower()

            response_data = {
                "status": "healthy",
                "database": {
                    "engine": engine,
                    "name": name,
                    "host": host,
                    "port": port,
                    "user": user,
                    "version": db_version,
                    "is_supabase": is_supabase,
                },
                "connection": {
                    "max_age": db_config.get('CONN_MAX_AGE', 0),
                    "health_checks_enabled": db_config.get('CONN_HEALTH_CHECKS', False),
                },
            }

            return Response(response_data, status=status.HTTP_200_OK)

        except Exception as e:
            return Response(
                {
                    "status": "unhealthy",
                    "error": str(e),
                },
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )


class RedisHealthView(APIView):
    """
    GET /api/v1/health/redis/

    Verifica el estado de la conexión a Redis (Celery broker).
    """

    @extend_schema(
        summary="Redis health check",
        description="""
Verifica el estado de la conexión a Redis (Celery broker).

Retorna información sobre:
- Estado de la conexión
- Respuesta PING
- Latencia de conexión en milisegundos
- Longitud de colas (notifications, sync, maintenance)
- Estado del connection pool

Este endpoint es útil para verificar la conectividad a Redis desde Web/Worker/Beat en Coolify.
        """,
        responses={
            200: OpenApiResponse(
                description="Redis connection is healthy",
                response={
                    "type": "object",
                    "properties": {
                        "status": {"type": "string", "example": "healthy"},
                        "redis": {
                            "type": "object",
                            "properties": {
                                "connected": {"type": "boolean"},
                                "ping": {"type": "string"},
                                "latency_ms": {"type": "number"},
                                "url": {"type": "string"},
                            },
                        },
                        "queues": {
                            "type": "object",
                            "properties": {
                                "notifications": {"type": "integer"},
                                "sync": {"type": "integer"},
                                "maintenance": {"type": "integer"},
                            },
                        },
                        "connection_pool": {
                            "type": "object",
                            "properties": {
                                "max_connections": {"type": "integer"},
                            },
                        },
                    },
                },
            ),
            503: OpenApiResponse(
                description="Redis connection failed",
                response={
                    "type": "object",
                    "properties": {
                        "status": {"type": "string", "example": "unhealthy"},
                        "error": {"type": "string"},
                    },
                },
            ),
        },
        tags=["Health"],
    )
    def get(self, request):
        try:
            # Get Celery broker connection
            celery_app = current_app

            # Measure latency
            start_time = time.time()

            # Get connection to Redis via Celery
            with celery_app.connection_or_acquire() as conn:
                # Get Redis client
                redis_client = conn.channel().client

                # Execute PING
                ping_response = redis_client.ping()

                # Measure latency
                latency_ms = round((time.time() - start_time) * 1000, 2)

                # Get queue lengths
                queue_lengths = {
                    "notifications": redis_client.llen("notifications"),
                    "sync": redis_client.llen("sync"),
                    "maintenance": redis_client.llen("maintenance"),
                }

                # Get broker URL (mask password)
                broker_url = str(celery_app.conf.broker_url)
                if "@" in broker_url:
                    # Mask password in URL
                    parts = broker_url.split("@")
                    user_pass = parts[0].split("//")[1]
                    if ":" in user_pass:
                        broker_url = broker_url.replace(
                            user_pass.split(":")[1],
                            "****"
                        )

                # Get connection pool info
                max_connections = celery_app.conf.broker_transport_options.get(
                    'max_connections',
                    settings.CELERY_BROKER_POOL_LIMIT if hasattr(settings, 'CELERY_BROKER_POOL_LIMIT') else 'N/A'
                )

                response_data = {
                    "status": "healthy",
                    "redis": {
                        "connected": True,
                        "ping": "PONG" if ping_response else "Failed",
                        "latency_ms": latency_ms,
                        "url": broker_url,
                    },
                    "queues": queue_lengths,
                    "connection_pool": {
                        "max_connections": max_connections,
                    },
                }

                return Response(response_data, status=status.HTTP_200_OK)

        except Exception as e:
            return Response(
                {
                    "status": "unhealthy",
                    "error": str(e),
                },
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
