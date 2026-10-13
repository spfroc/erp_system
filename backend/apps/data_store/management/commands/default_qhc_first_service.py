from django.core.management.base import BaseCommand

from apps.data_store.models import ProjectRecord
from apps.data_store.views import _patch_app_state_collections

QINGHUICAI_PLATFORM = "青慧采"
FIRST_SERVICE_KIND = "首次服务"


def default_qinghuicai_service_projects() -> int:
    updated = 0
    queryset = ProjectRecord.objects.filter(is_deleted=False, type="服务项目")
    for record in queryset:
        data = dict(record.data) if isinstance(record.data, dict) else {}
        if str(data.get("sourcePlatform") or "").strip() != QINGHUICAI_PLATFORM:
            continue
        if data.get("serviceCustomerKind") == FIRST_SERVICE_KIND:
            continue
        data["serviceCustomerKind"] = FIRST_SERVICE_KIND
        record.data = data
        record.save(update_fields=["data"])
        updated += 1
    if updated:
        _patch_app_state_collections(["projects"])
    return updated


class Command(BaseCommand):
    help = "Set all 青慧采 service projects to 首次服务; leave other platforms unchanged."

    def handle(self, *args, **options):
        updated = default_qinghuicai_service_projects()
        self.stdout.write(self.style.SUCCESS(f"updated={updated}"))
