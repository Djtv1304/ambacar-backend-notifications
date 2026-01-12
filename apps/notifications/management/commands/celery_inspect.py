"""
Management command to inspect Celery worker status and configuration.

Usage:
    python manage.py celery_inspect
"""
import json
from django.core.management.base import BaseCommand
from django.conf import settings
import redis
from celery import Celery


class Command(BaseCommand):
    help = 'Inspect Celery worker status and Redis queue keys'

    def handle(self, *args, **options):
        # Connect to Redis
        redis_url = settings.CELERY_BROKER_URL
        self.stdout.write(f"\n📡 Redis URL: {redis_url}")

        r = redis.from_url(redis_url)

        try:
            r.ping()
            self.stdout.write(self.style.SUCCESS("✅ Redis connection successful\n"))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"❌ Redis connection failed: {e}"))
            return

        # List ALL keys in Redis (for debugging)
        self.stdout.write(self.style.WARNING("🔑 ALL KEYS IN REDIS:\n"))
        all_keys = r.keys("*")

        if not all_keys:
            self.stdout.write("   (empty - no keys found)")
        else:
            for key in sorted(all_keys):
                key_str = key.decode('utf-8') if isinstance(key, bytes) else key
                key_type = r.type(key).decode('utf-8')

                if key_type == 'list':
                    length = r.llen(key)
                    self.stdout.write(f"   [{key_type}] {key_str} (length: {length})")
                elif key_type == 'string':
                    self.stdout.write(f"   [{key_type}] {key_str}")
                elif key_type == 'set':
                    size = r.scard(key)
                    self.stdout.write(f"   [{key_type}] {key_str} (size: {size})")
                elif key_type == 'zset':
                    size = r.zcard(key)
                    self.stdout.write(f"   [{key_type}] {key_str} (size: {size})")
                elif key_type == 'hash':
                    size = r.hlen(key)
                    self.stdout.write(f"   [{key_type}] {key_str} (fields: {size})")
                else:
                    self.stdout.write(f"   [{key_type}] {key_str}")

        # Check Celery configuration
        self.stdout.write(f"\n⚙️  CELERY CONFIGURATION:\n")
        self.stdout.write(f"   CELERY_BROKER_URL: {settings.CELERY_BROKER_URL}")
        self.stdout.write(f"   CELERY_RESULT_BACKEND: {settings.CELERY_RESULT_BACKEND}")
        self.stdout.write(f"   CELERY_TASK_SERIALIZER: {settings.CELERY_TASK_SERIALIZER}")
        self.stdout.write(f"   CELERY_ACCEPT_CONTENT: {settings.CELERY_ACCEPT_CONTENT}")
        self.stdout.write(f"   CELERY_BROKER_HEARTBEAT: {settings.CELERY_BROKER_HEARTBEAT}")

        # Check if task_routes is configured
        from config.celery import app as celery_app
        self.stdout.write(f"\n📋 CELERY TASK ROUTES:")
        if hasattr(celery_app.conf, 'task_routes') and celery_app.conf.task_routes:
            for pattern, config in celery_app.conf.task_routes.items():
                self.stdout.write(f"   {pattern} → {config}")
        else:
            self.stdout.write("   (no task routes configured)")

        # Check registered tasks
        self.stdout.write(f"\n📦 REGISTERED CELERY TASKS:")
        registered_tasks = sorted([
            task for task in celery_app.tasks.keys()
            if not task.startswith('celery.')
        ])
        for task_name in registered_tasks:
            task = celery_app.tasks[task_name]
            queue = getattr(task, 'queue', 'default')
            self.stdout.write(f"   {task_name} → queue: {queue}")

        # Try to inspect active workers
        self.stdout.write(f"\n👷 ACTIVE WORKERS:")
        try:
            inspect = celery_app.control.inspect(timeout=5.0)

            # Get active workers
            active = inspect.active()
            if active:
                for worker_name, tasks in active.items():
                    self.stdout.write(f"   Worker: {worker_name}")
                    if tasks:
                        self.stdout.write(f"     Active tasks: {len(tasks)}")
                        for task in tasks[:3]:  # Show first 3
                            self.stdout.write(f"       - {task.get('name', 'Unknown')}")
                    else:
                        self.stdout.write(f"     Active tasks: 0")
            else:
                self.stdout.write("   ⚠️  No active workers found (may need to wait for worker to start)")

            # Get registered queues on workers
            stats = inspect.stats()
            if stats:
                for worker_name, worker_stats in stats.items():
                    self.stdout.write(f"\n   Worker: {worker_name}")
                    pool = worker_stats.get('pool', {})
                    self.stdout.write(f"     Pool: {pool.get('implementation', 'unknown')}")
                    self.stdout.write(f"     Max concurrency: {pool.get('max-concurrency', 'unknown')}")

            # Get registered tasks on workers
            registered = inspect.registered()
            if registered:
                for worker_name, tasks in registered.items():
                    notification_tasks = [t for t in tasks if 'notification' in t.lower()]
                    if notification_tasks:
                        self.stdout.write(f"\n   Worker {worker_name} - Notification tasks:")
                        for task in notification_tasks:
                            self.stdout.write(f"     - {task}")

        except Exception as e:
            self.stdout.write(self.style.WARNING(f"   ⚠️  Could not inspect workers: {e}"))
            self.stdout.write("   (This is normal if no workers are running)")

        self.stdout.write("\n")
