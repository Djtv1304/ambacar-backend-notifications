"""
Health check command to run FROM THE WORKER container.

Usage (from Worker container in Coolify):
    python manage.py worker_health
"""
import os
from django.core.management.base import BaseCommand
from django.conf import settings
import redis


class Command(BaseCommand):
    help = 'Worker health check - verify Redis connectivity from Worker perspective'

    def handle(self, *args, **options):
        self.stdout.write("\n" + "="*60)
        self.stdout.write("WORKER HEALTH CHECK")
        self.stdout.write("="*60 + "\n")

        # Environment info
        self.stdout.write("🔧 ENVIRONMENT:")
        self.stdout.write(f"   Django Settings Module: {os.environ.get('DJANGO_SETTINGS_MODULE', 'NOT SET')}")
        self.stdout.write(f"   Debug Mode: {settings.DEBUG}")
        self.stdout.write(f"   Python Path: {os.sys.executable}\n")

        # Redis connection from environment
        redis_url = os.environ.get('REDIS_URL', 'NOT SET')
        self.stdout.write("📡 REDIS URL (from environment):")
        self.stdout.write(f"   {redis_url}\n")

        # Redis connection from settings
        self.stdout.write("📡 REDIS URL (from Django settings):")
        self.stdout.write(f"   {settings.CELERY_BROKER_URL}\n")

        # Check if they match
        if redis_url != settings.CELERY_BROKER_URL and redis_url != 'NOT SET':
            self.stdout.write(self.style.ERROR("⚠️  WARNING: Environment REDIS_URL differs from Django settings!"))
            self.stdout.write("   This could cause Web App and Worker to connect to different Redis instances\n")

        # Try connecting to Redis
        self.stdout.write("🔌 TESTING REDIS CONNECTION:")

        try:
            r = redis.from_url(settings.CELERY_BROKER_URL)
            ping_result = r.ping()
            self.stdout.write(self.style.SUCCESS(f"   ✅ PING successful: {ping_result}"))

            # Get server info
            info = r.info('server')
            self.stdout.write(f"   Redis version: {info.get('redis_version', 'unknown')}")
            self.stdout.write(f"   Uptime (seconds): {info.get('uptime_in_seconds', 'unknown')}")

            # Check queue lengths
            self.stdout.write("\n📦 QUEUE LENGTHS:")
            for queue in ['notifications', 'sync', 'maintenance']:
                length = r.llen(queue)
                status = "✅" if length == 0 else f"⚠️  {length} tasks"
                self.stdout.write(f"   {queue}: {status}")

            # Check Celery bindings
            bindings = r.smembers('_kombu.binding.notifications')
            if bindings:
                self.stdout.write(f"\n🔗 CELERY BINDINGS:")
                for binding in bindings:
                    self.stdout.write(f"   {binding.decode('utf-8')}")

        except redis.ConnectionError as e:
            self.stdout.write(self.style.ERROR(f"   ❌ CONNECTION ERROR: {e}"))
            self.stdout.write("\n   Possible causes:")
            self.stdout.write("   1. Redis service is not running")
            self.stdout.write("   2. Worker is in a different Docker network")
            self.stdout.write("   3. REDIS_URL hostname cannot be resolved")
            self.stdout.write("   4. Firewall blocking connection")

        except Exception as e:
            self.stdout.write(self.style.ERROR(f"   ❌ UNEXPECTED ERROR: {e}"))

        # Celery app info
        self.stdout.write("\n🎯 CELERY CONFIGURATION:")
        from config.celery import app as celery_app

        self.stdout.write(f"   Celery app name: {celery_app.main}")
        self.stdout.write(f"   Broker URL: {celery_app.conf.broker_url}")
        self.stdout.write(f"   Task serializer: {celery_app.conf.task_serializer}")
        self.stdout.write(f"   Accept content: {celery_app.conf.accept_content}")

        # Registered tasks
        self.stdout.write("\n📋 REGISTERED TASKS:")
        registered_tasks = sorted([
            task for task in celery_app.tasks.keys()
            if not task.startswith('celery.')
        ])

        if registered_tasks:
            for task_name in registered_tasks:
                self.stdout.write(f"   - {task_name}")
        else:
            self.stdout.write(self.style.WARNING("   ⚠️  No tasks registered (this is VERY bad!)"))

        # Check if send_notification_task is registered
        if 'apps.notifications.tasks.send_notification_task' in celery_app.tasks:
            self.stdout.write(self.style.SUCCESS("\n   ✅ send_notification_task is registered"))
        else:
            self.stdout.write(self.style.ERROR("\n   ❌ send_notification_task is NOT registered"))
            self.stdout.write("      This means Django autodiscovery failed")

        self.stdout.write("\n" + "="*60 + "\n")
