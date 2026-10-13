from django.core.management.base import BaseCommand
from core.services import escalate_overdue

class Command(BaseCommand):
    help = "Eskalasi red tag lewat 90 hari ke antrean Komite Unit. Jalankan harian."
    def handle(self, *args, **options):
        self.stdout.write(f"{escalate_overdue()} red tag baru dieskalasikan ke Komite Unit.")
