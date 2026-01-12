"""
Management command to debug and manage Redis/Celery queues.

Usage:
    python manage.py redis_debug --inspect         # Inspect all queues
    python manage.py redis_debug --purge notifications  # Purge notifications queue
    python manage.py redis_debug --purge-all       # Purge all queues (DANGER!)
"""
import json
from django.core.management.base import BaseCommand
from django.conf import settings
import redis


class Command(BaseCommand):
    help = 'Debug and manage Redis/Celery queues'

    def add_arguments(self, parser):
        parser.add_argument(
            '--inspect',
            action='store_true',
            help='Inspect all queues and show their contents'
        )
        parser.add_argument(
            '--purge',
            type=str,
            help='Purge specific queue (notifications, sync, maintenance)'
        )
        parser.add_argument(
            '--purge-all',
            action='store_true',
            help='Purge ALL queues (DANGER!)'
        )

    def handle(self, *args, **options):
        # Connect to Redis
        redis_url = settings.CELERY_BROKER_URL
        self.stdout.write(f"\n📡 Connecting to Redis: {redis_url}")

        r = redis.from_url(redis_url)

        try:
            r.ping()
            self.stdout.write(self.style.SUCCESS("✅ Redis connection successful\n"))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"❌ Redis connection failed: {e}"))
            return

        queues = ['notifications', 'sync', 'maintenance']

        # INSPECT MODE
        if options['inspect']:
            self.stdout.write(self.style.WARNING("🔍 INSPECTING QUEUES\n"))

            for queue_name in queues:
                # Celery uses queue names as keys in Redis
                queue_key = queue_name
                queue_length = r.llen(queue_key)

                self.stdout.write(f"\n📦 Queue: {queue_name}")
                self.stdout.write(f"   Length: {queue_length}")

                if queue_length > 0:
                    # Get first 5 tasks (without removing them)
                    tasks = r.lrange(queue_key, 0, 4)
                    self.stdout.write(f"   First {min(5, queue_length)} task(s):\n")

                    for i, task_data in enumerate(tasks, 1):
                        try:
                            # Celery tasks are JSON-encoded
                            task_json = json.loads(task_data)

                            # Extract useful info
                            task_name = task_json.get('headers', {}).get('task', 'Unknown')
                            task_id = task_json.get('headers', {}).get('id', 'Unknown')
                            task_args = task_json.get('headers', {}).get('argsrepr', '()')

                            self.stdout.write(f"   [{i}] Task: {task_name}")
                            self.stdout.write(f"       ID: {task_id}")
                            self.stdout.write(f"       Args: {task_args}")

                        except json.JSONDecodeError:
                            self.stdout.write(self.style.ERROR(f"   [{i}] ⚠️  Corrupted task (not valid JSON)"))
                            self.stdout.write(f"       Raw: {task_data[:100]}...")
                        except Exception as e:
                            self.stdout.write(self.style.ERROR(f"   [{i}] ⚠️  Error parsing task: {e}"))

        # PURGE SPECIFIC QUEUE
        elif options['purge']:
            queue_name = options['purge']
            if queue_name not in queues:
                self.stdout.write(self.style.ERROR(f"❌ Invalid queue name: {queue_name}"))
                self.stdout.write(f"   Valid queues: {', '.join(queues)}")
                return

            queue_length = r.llen(queue_name)

            if queue_length == 0:
                self.stdout.write(self.style.WARNING(f"⚠️  Queue '{queue_name}' is already empty"))
                return

            self.stdout.write(self.style.WARNING(f"⚠️  About to purge queue '{queue_name}' ({queue_length} tasks)"))
            confirm = input("   Type 'yes' to confirm: ")

            if confirm.lower() == 'yes':
                deleted = r.delete(queue_name)
                self.stdout.write(self.style.SUCCESS(f"✅ Purged queue '{queue_name}' ({deleted} key(s) deleted)"))
            else:
                self.stdout.write("   Cancelled")

        # PURGE ALL QUEUES
        elif options['purge_all']:
            total_tasks = sum(r.llen(q) for q in queues)

            if total_tasks == 0:
                self.stdout.write(self.style.WARNING("⚠️  All queues are already empty"))
                return

            self.stdout.write(self.style.ERROR(f"⚠️  DANGER: About to purge ALL queues ({total_tasks} total tasks)"))
            for queue_name in queues:
                queue_length = r.llen(queue_name)
                if queue_length > 0:
                    self.stdout.write(f"   - {queue_name}: {queue_length} tasks")

            confirm = input("\n   Type 'PURGE ALL' to confirm: ")

            if confirm == 'PURGE ALL':
                for queue_name in queues:
                    r.delete(queue_name)
                self.stdout.write(self.style.SUCCESS("✅ All queues purged"))
            else:
                self.stdout.write("   Cancelled")

        # NO OPTION PROVIDED
        else:
            self.stdout.write(self.style.WARNING("⚠️  No action specified. Use --help to see available options"))
            self.stdout.write("\nExamples:")
            self.stdout.write("  python manage.py redis_debug --inspect")
            self.stdout.write("  python manage.py redis_debug --purge notifications")
            self.stdout.write("  python manage.py redis_debug --purge-all")
