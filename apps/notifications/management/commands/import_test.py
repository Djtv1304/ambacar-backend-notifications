"""
Test imports to detect autodiscovery failures.

Usage (from Worker container):
    python manage.py import_test
"""
import sys
import traceback
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = 'Test importing all task modules to detect errors'

    def handle(self, *args, **options):
        self.stdout.write("\n" + "="*60)
        self.stdout.write("IMPORT TEST - Detecting Autodiscovery Failures")
        self.stdout.write("="*60 + "\n")

        modules_to_test = [
            'apps.notifications.tasks',
            'apps.synchronization.tasks',
            'apps.analytics.tasks',
            'config.celery',
        ]

        success_count = 0
        fail_count = 0

        for module_name in modules_to_test:
            self.stdout.write(f"\n📦 Testing: {module_name}")
            try:
                # Force import
                module = __import__(module_name, fromlist=['*'])

                # List all attributes
                attrs = [attr for attr in dir(module) if not attr.startswith('_')]
                task_attrs = [attr for attr in attrs if 'task' in attr.lower()]

                self.stdout.write(self.style.SUCCESS(f"   ✅ Import successful"))

                if task_attrs:
                    self.stdout.write(f"   Tasks found: {', '.join(task_attrs)}")
                else:
                    self.stdout.write(f"   Module attributes: {', '.join(attrs[:10])}")

                success_count += 1

            except ImportError as e:
                self.stdout.write(self.style.ERROR(f"   ❌ ImportError: {e}"))
                self.stdout.write(f"\n   Traceback:")
                traceback.print_exc(file=self.stdout._out)
                fail_count += 1

            except Exception as e:
                self.stdout.write(self.style.ERROR(f"   ❌ Unexpected error: {e}"))
                self.stdout.write(f"\n   Traceback:")
                traceback.print_exc(file=self.stdout._out)
                fail_count += 1

        # Test Celery autodiscovery
        self.stdout.write("\n" + "="*60)
        self.stdout.write("🎯 Testing Celery Autodiscovery")
        self.stdout.write("="*60 + "\n")

        try:
            from config.celery import app as celery_app

            self.stdout.write("Forcing autodiscover_tasks()...")
            celery_app.autodiscover_tasks()

            self.stdout.write(self.style.SUCCESS("✅ Autodiscovery completed\n"))

            # List all registered tasks
            registered_tasks = sorted([
                task for task in celery_app.tasks.keys()
                if not task.startswith('celery.')
            ])

            self.stdout.write(f"📋 Registered tasks ({len(registered_tasks)}):")
            for task_name in registered_tasks:
                self.stdout.write(f"   - {task_name}")

            # Check for send_notification_task
            if 'apps.notifications.tasks.send_notification_task' in registered_tasks:
                self.stdout.write(self.style.SUCCESS("\n✅ send_notification_task IS registered"))
            else:
                self.stdout.write(self.style.ERROR("\n❌ send_notification_task is NOT registered"))

        except Exception as e:
            self.stdout.write(self.style.ERROR(f"❌ Autodiscovery failed: {e}"))
            traceback.print_exc(file=self.stdout._out)

        # Test direct task import
        self.stdout.write("\n" + "="*60)
        self.stdout.write("🎯 Testing Direct Task Import")
        self.stdout.write("="*60 + "\n")

        try:
            self.stdout.write("Attempting: from apps.notifications.tasks import send_notification_task")
            from apps.notifications.tasks import send_notification_task
            self.stdout.write(self.style.SUCCESS("✅ Direct import successful"))
            self.stdout.write(f"   Task object: {send_notification_task}")
            self.stdout.write(f"   Task name: {send_notification_task.name}")
            self.stdout.write(f"   Task queue: {getattr(send_notification_task, 'queue', 'default')}")

        except ImportError as e:
            self.stdout.write(self.style.ERROR(f"❌ Direct import failed: {e}"))
            self.stdout.write("\nFull traceback:")
            traceback.print_exc(file=self.stdout._out)

        except Exception as e:
            self.stdout.write(self.style.ERROR(f"❌ Unexpected error: {e}"))
            traceback.print_exc(file=self.stdout._out)

        # Summary
        self.stdout.write("\n" + "="*60)
        self.stdout.write("SUMMARY")
        self.stdout.write("="*60)
        self.stdout.write(f"✅ Successful imports: {success_count}")
        self.stdout.write(f"❌ Failed imports: {fail_count}")
        self.stdout.write("="*60 + "\n")
