from django.core.management.base import BaseCommand

from apps.data_store.models import TransactionRecord
from apps.data_store.views import _restore_transaction_project_id


class Command(BaseCommand):
    help = "Restore missing transaction projectId from related orders or remark order numbers."

    def handle(self, *args, **options):
        restored = 0
        still_blank = 0
        for record in TransactionRecord.objects.filter(is_deleted=False).iterator():
            data = record.data if isinstance(record.data, dict) else {}
            before = record.project_id or data.get("projectId") or ""
            data = _restore_transaction_project_id(record)
            after = record.project_id or data.get("projectId") or ""
            if after and after != before:
                restored += 1
                self.stdout.write(f"restored {record.id} -> {after}")
            elif not after:
                still_blank += 1
                self.stdout.write(f"blank {record.id} remark={data.get('remark')}")
        self.stdout.write(self.style.SUCCESS(f"restored={restored} still_blank={still_blank}"))
