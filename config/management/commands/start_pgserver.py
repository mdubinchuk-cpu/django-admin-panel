from django.core.management.base import BaseCommand
from config.db_utils import start_db, current_db_info, using_pgserver

class Command(BaseCommand):
    help = 'Запускает pgserver или локальный Postgres'

    def handle(self, *args, **options):
        if start_db():
            db_type = "pgserver" if using_pgserver else "локальный PostgreSQL"
            self.stdout.write(self.style.SUCCESS(f'БД запущена: {current_db_info} ({db_type})'))
        else:
            self.stdout.write(self.style.ERROR('Ошибка запуска БД'))