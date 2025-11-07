from django.core.management.base import BaseCommand
from config.db_utils import stop_db

class Command(BaseCommand):
    help = 'Останавливает pgserver'
    requires_migrations_checks = False  # Работает без БД

    def handle(self, *args, **options):
        stop_db()
        self.stdout.write(self.style.SUCCESS('pgserver остановлен'))