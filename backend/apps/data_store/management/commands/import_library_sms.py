"""Import legacy admin 资料库 / 短信 ndjson dumps into ERP collections."""

from __future__ import annotations

import json
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from apps.data_store.library_sms import (
    library_contact_defaults,
    normalize_library_contact,
    normalize_sms_record,
    normalize_sms_template,
    sms_record_defaults,
    sms_template_defaults,
)
from apps.data_store.models import LibraryContactRecord, SmsRecordRecord, SmsTemplateRecord

ORIGIN_BY_CODE = {
    "1": "百度",
    "2": "公共资源",
    "3": "招投标",
    "4": "齐鲁云采",
    "5": "青岛政采",
    "6": "烟台政采",
    "7": "滨州政采",
    "8": "菏泽政采",
    "9": "其他",
    "10": "其他",
    "0": "其他",
}
SIGNED_BY_CODE = {"0": "有效", "1": "已签约", "2": "无效"}


def _iso(value) -> str:
    if value is None or value == "":
        return timezone.now().isoformat()
    if hasattr(value, "isoformat"):
        return value.isoformat()
    text = str(value).strip()
    parsed = parse_datetime(text.replace(" ", "T"))
    if parsed:
        return parsed.isoformat()
    return text


def _iter_ndjson(path: Path):
    with path.open("r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            yield json.loads(line)


class Command(BaseCommand):
    help = "Import library contacts / SMS templates / SMS records from legacy ndjson export."

    def add_arguments(self, parser):
        parser.add_argument(
            "--dir",
            default="",
            help="Directory containing customers.ndjson / short_messages.ndjson / admin_note_templates.ndjson",
        )
        parser.add_argument("--batch-size", type=int, default=1000)
        parser.add_argument("--skip-contacts", action="store_true")
        parser.add_argument("--skip-sms", action="store_true")
        parser.add_argument("--skip-templates", action="store_true")
        parser.add_argument("--replace", action="store_true", help="Soft-delete existing imported rows first.")
        parser.add_argument("--limit", type=int, default=0, help="Limit rows per file (0 = all).")

    def handle(self, *args, **options):
        candidates = []
        if options["dir"]:
            candidates.append(Path(options["dir"]))
        else:
            # Prefer host-mounted imports (one) then backend-local copy.
            candidates.extend(
                [
                    Path("/imports/library_sms"),
                    Path("/app/../imports/library_sms").resolve(),
                    Path("/app/imports/library_sms"),
                    Path.cwd() / "imports" / "library_sms",
                ]
            )
        root = next((path for path in candidates if path.is_dir()), None)
        if root is None:
            raise CommandError(f"Import directory not found. Tried: {', '.join(str(p) for p in candidates)}")
        self.stdout.write(f"Using import dir: {root}")
        batch = max(100, int(options["batch_size"]))
        limit = int(options["limit"] or 0)

        if options["replace"]:
            self.stdout.write("Removing previous imported records…")
            if not options["skip_contacts"]:
                deleted, _ = LibraryContactRecord.objects.filter(id__startswith="lib-legacy-").delete()
                self.stdout.write(f"  contacts removed: {deleted}")
            if not options["skip_sms"]:
                deleted, _ = SmsRecordRecord.objects.filter(id__startswith="sms-legacy-").delete()
                self.stdout.write(f"  sms removed: {deleted}")
            if not options["skip_templates"]:
                deleted, _ = SmsTemplateRecord.objects.filter(id__startswith="smt-legacy-").delete()
                self.stdout.write(f"  templates removed: {deleted}")

        stats = {"contacts": 0, "sms": 0, "templates": 0}

        if not options["skip_templates"]:
            path = root / "admin_note_templates.ndjson"
            if path.exists():
                stats["templates"] = self._import_templates(path, batch, limit)
            else:
                self.stdout.write(self.style.WARNING(f"missing {path.name}"))

        if not options["skip_contacts"]:
            path = root / "customers.ndjson"
            if path.exists():
                stats["contacts"] = self._import_contacts(path, batch, limit)
            else:
                self.stdout.write(self.style.WARNING(f"missing {path.name}"))

        if not options["skip_sms"]:
            path = root / "short_messages.ndjson"
            failed_path = root / "failed_short_message_mobiles.ndjson"
            failed_by_task: dict[str, list] = {}
            if failed_path.exists():
                for row in _iter_ndjson(failed_path):
                    task_id = str(row.get("task_id") or "")
                    if not task_id:
                        continue
                    failed_by_task.setdefault(task_id, []).append(
                        {"mobile": row.get("mobile"), "result": row.get("result")}
                    )
            if path.exists():
                stats["sms"] = self._import_sms(path, batch, limit, failed_by_task)
            else:
                self.stdout.write(self.style.WARNING(f"missing {path.name}"))

        self.stdout.write(self.style.SUCCESS(json.dumps(stats, ensure_ascii=False)))

    def _import_templates(self, path: Path, batch: int, limit: int) -> int:
        buffer: list[SmsTemplateRecord] = []
        count = 0
        for row in _iter_ndjson(path):
            legacy_id = row.get("id")
            payload = normalize_sms_template(
                {
                    "id": f"smt-legacy-{legacy_id}",
                    "name": row.get("name") or f"模板{legacy_id}",
                    "content": row.get("content") or "",
                    "prefix": "壹知产",
                    "createdAt": _iso(row.get("created_at")),
                    "updatedAt": _iso(row.get("updated_at")),
                }
            )
            defaults = sms_template_defaults(payload)
            buffer.append(
                SmsTemplateRecord(
                    id=payload["id"],
                    is_deleted=False,
                    deleted_at=None,
                    deleted_by="",
                    **defaults,
                )
            )
            count += 1
            if len(buffer) >= batch:
                self._bulk_templates(buffer)
                buffer = []
            if limit and count >= limit:
                break
        if buffer:
            self._bulk_templates(buffer)
        self.stdout.write(f"templates imported: {count}")
        return count

    def _bulk_templates(self, rows: list[SmsTemplateRecord]):
        with transaction.atomic():
            SmsTemplateRecord.objects.bulk_create(rows, batch_size=500)

    def _import_contacts(self, path: Path, batch: int, limit: int) -> int:
        buffer: list[LibraryContactRecord] = []
        count = 0
        for row in _iter_ndjson(path):
            legacy_id = row.get("id")
            signed = SIGNED_BY_CODE.get(str(row.get("signed") if row.get("signed") is not None else "0"), "有效")
            origin_raw = str(row.get("origin") if row.get("origin") is not None else "9").strip()
            origin = ORIGIN_BY_CODE.get(origin_raw, origin_raw if origin_raw in ORIGIN_BY_CODE.values() else "其他")
            mobile = (row.get("new_mobile") or row.get("mobile") or "").strip()[:255]
            tags = []
            if row.get("tag"):
                tags = [part.strip() for part in str(row["tag"]).replace("，", ",").split(",") if part.strip()]
            payload = normalize_library_contact(
                {
                    "id": f"lib-legacy-{legacy_id}",
                    "name": (row.get("name") or "")[:255],
                    "legalPerson": row.get("legal_person") or "",
                    "mobile": mobile,
                    "email": row.get("email") or "",
                    "licenseCode": row.get("license_code") or "",
                    "address": row.get("address") or "",
                    "province": (row.get("province") or "").strip() or "山东省",
                    "city": (row.get("city") or "").strip() or "",
                    "origin": origin,
                    "signed": signed,
                    "type": row.get("type") or "其他",
                    "tags": tags,
                    "sellUserId": str(row.get("sell_id") or "") if row.get("sell_id") else "",
                    "createdAt": _iso(row.get("created_at")),
                    "updatedAt": _iso(row.get("updated_at")),
                }
            )
            # keep raw legacy fields for traceability
            payload["legacyId"] = legacy_id
            payload["platformCustomerId"] = row.get("platform_customer_id") or ""
            payload["remark"] = row.get("remark") or ""
            defaults = library_contact_defaults(payload)
            buffer.append(
                LibraryContactRecord(
                    id=payload["id"],
                    is_deleted=False,
                    deleted_at=None,
                    deleted_by="",
                    **defaults,
                )
            )
            count += 1
            if len(buffer) >= batch:
                self._bulk_contacts(buffer)
                buffer = []
                if count % 10000 == 0:
                    self.stdout.write(f"contacts… {count}")
            if limit and count >= limit:
                break
        if buffer:
            self._bulk_contacts(buffer)
        self.stdout.write(f"contacts imported: {count}")
        return count

    def _bulk_contacts(self, rows: list[LibraryContactRecord]):
        with transaction.atomic():
            LibraryContactRecord.objects.bulk_create(rows, batch_size=500)

    def _import_sms(self, path: Path, batch: int, limit: int, failed_by_task: dict[str, list]) -> int:
        buffer: list[SmsRecordRecord] = []
        count = 0
        for row in _iter_ndjson(path):
            legacy_id = row.get("id")
            task_id = str(row.get("task_id") or "")
            payload = normalize_sms_record(
                {
                    "id": f"sms-legacy-{legacy_id}",
                    "taskId": task_id[:100],
                    "mobile": str(row.get("mobile") or "")[:255],
                    "content": str(row.get("content") or "")[:500],
                    "type": str(row.get("type") or "")[:50],
                    "source": str(row.get("source") or "")[:50],
                    "result": str(row.get("msg") or row.get("code") or "")[:100],
                    "balance": row.get("balance"),
                    "failedRecords": failed_by_task.get(task_id, []),
                    "createdAt": _iso(row.get("created_at")),
                    "createdBy": "",
                }
            )
            payload["legacyId"] = legacy_id
            payload["channel"] = row.get("channel") or ""
            defaults = sms_record_defaults(payload)
            buffer.append(
                SmsRecordRecord(
                    id=payload["id"],
                    is_deleted=False,
                    deleted_at=None,
                    deleted_by="",
                    **defaults,
                )
            )
            count += 1
            if len(buffer) >= batch:
                self._bulk_sms(buffer)
                buffer = []
                if count % 10000 == 0:
                    self.stdout.write(f"sms… {count}")
            if limit and count >= limit:
                break
        if buffer:
            self._bulk_sms(buffer)
        self.stdout.write(f"sms imported: {count}")
        return count

    def _bulk_sms(self, rows: list[SmsRecordRecord]):
        with transaction.atomic():
            SmsRecordRecord.objects.bulk_create(rows, batch_size=500)
