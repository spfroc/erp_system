"""Migrate old admin designated_suppliers -> organizations + platformAccounts.

Rules:
- Source: 供应商管理 -> 电商/代理商 (designated_suppliers)
- Skip existing organizations matched by exact trimmed name (do not update)
- Only create platform accounts when not expired (expired_at is null OR >= today)
- Skip platform accounts that already exist for same customer+platform+accountName
- Existing records are never modified
"""

from __future__ import annotations

import json
import uuid
from datetime import date, datetime, timezone
from pathlib import Path

from django.db import transaction
from django.utils import timezone as dj_tz

from apps.data_store.models import OrganizationRecord, PlatformAccountRecord
from apps.data_store.views import _record_defaults

SOURCE_PATH = Path("/tmp/designated_suppliers.json")
PLATFORM = "齐鲁云采"
DRY_RUN = False


def _clean(value) -> str:
    if value is None:
        return ""
    text = str(value).strip()
    if text in {"-", "—", "null", "None"}:
        return ""
    return text


def _new_id(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:8]}"


def _now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().replace(microsecond=0).isoformat()


def _is_not_expired(expired_at: str | None, today: str) -> bool:
    if not expired_at:
        return True
    return expired_at >= today


def main() -> None:
    rows = json.loads(SOURCE_PATH.read_text(encoding="utf-8"))
    today = date.today().isoformat()
    print(f"source={len(rows)} today={today} dry_run={DRY_RUN} platform={PLATFORM}")

    existing_orgs = {}
    for rec in OrganizationRecord.objects.filter(is_deleted=False):
        name = _clean((rec.data or {}).get("name") or rec.name)
        if name:
            existing_orgs[name] = rec

    existing_pa_keys = set()
    for rec in PlatformAccountRecord.objects.filter(is_deleted=False):
        data = rec.data or {}
        key = (
            _clean(data.get("customerOrgId") or rec.customer_org_id),
            _clean(data.get("platform") or rec.platform),
            _clean(data.get("accountName") or rec.account_name),
        )
        if key[0] and key[2]:
            existing_pa_keys.add(key)

    # Also skip if same account name already exists under any platform (avoid dup credentials)
    existing_account_names = {
        _clean((rec.data or {}).get("accountName") or rec.account_name)
        for rec in PlatformAccountRecord.objects.filter(is_deleted=False)
        if _clean((rec.data or {}).get("accountName") or rec.account_name)
    }

    stats = {
        "org_created": 0,
        "org_reused": 0,
        "org_skipped_empty_name": 0,
        "pa_created": 0,
        "pa_skipped_expired": 0,
        "pa_skipped_empty_account": 0,
        "pa_skipped_exists": 0,
    }
    created_org_ids: list[str] = []
    created_pa_ids: list[str] = []
    reused_names: list[str] = []

    with transaction.atomic():
        for row in rows:
            name = _clean(row.get("name"))
            if not name:
                stats["org_skipped_empty_name"] += 1
                continue

            org = existing_orgs.get(name)
            if org:
                stats["org_reused"] += 1
                if len(reused_names) < 10:
                    reused_names.append(name)
                org_id = org.id
            else:
                org_id = _new_id("org")
                now = _now_iso()
                created = _clean(row.get("created_at")) or now
                payload = {
                    "id": org_id,
                    "name": name,
                    "entityType": "企业",
                    "roles": ["平台入驻商"],
                    "phone": _clean(row.get("contract_number")),
                    "status": "正常",
                    "createdAt": created,
                    "updatedAt": now,
                }
                defaults = _record_defaults(OrganizationRecord, payload)
                defaults["created_at"] = dj_tz.now()
                if not DRY_RUN:
                    OrganizationRecord.objects.create(id=org_id, **defaults)
                existing_orgs[name] = type("Tmp", (), {"id": org_id, "name": name, "data": payload})()
                created_org_ids.append(org_id)
                stats["org_created"] += 1

            expired_at = _clean(row.get("expired_at")) or None
            if not _is_not_expired(expired_at, today):
                stats["pa_skipped_expired"] += 1
                continue

            account_name = _clean(row.get("account"))
            password = _clean(row.get("password"))
            if not account_name:
                stats["pa_skipped_empty_account"] += 1
                continue

            pa_key = (org_id, PLATFORM, account_name)
            # 同账号名已存在（任意平台）则跳过，避免重复导入凭证
            if pa_key in existing_pa_keys or account_name in existing_account_names:
                stats["pa_skipped_exists"] += 1
                continue

            pa_id = _new_id("pa")
            now = _now_iso()
            created = _clean(row.get("created_at")) or now
            note_bits = []
            contact = _clean(row.get("contracts"))
            industry = _clean(row.get("desc"))
            remark = _clean(row.get("remark"))
            if contact:
                note_bits.append(f"联系人:{contact}")
            if industry:
                note_bits.append(industry)
            if remark:
                note_bits.append(remark)
            note_bits.append(f"旧designated#{row.get('id')}")

            payload = {
                "id": pa_id,
                "customerOrgId": org_id,
                "platform": PLATFORM,
                "accountName": account_name,
                "accountPasswordMasked": password,
                "licenseDisplayStatus": "未处理",
                "publicSecurityStatus": "未处理",
                "backendTemplateStatus": "未录入",
                "caStatus": "未办理",
                "serviceYears": int(row.get("years_of_service") or 1) or 1,
                "salesOwner": _clean(row.get("broker")) or "未分配",
                "currentStatus": "服务中",
                "note": "；".join(note_bits),
                "createdAt": created,
                "updatedAt": now,
            }
            domain = _clean(row.get("domain"))
            if domain:
                payload["domain"] = domain
            cloud_account = _clean(row.get("other_account"))
            if cloud_account:
                payload["cloudAccount"] = cloud_account
            cloud_password = _clean(row.get("other_password"))
            if cloud_password:
                payload["cloudPasswordMasked"] = cloud_password
            if expired_at:
                payload["expireDate"] = expired_at

            defaults = _record_defaults(PlatformAccountRecord, payload)
            if not DRY_RUN:
                PlatformAccountRecord.objects.create(id=pa_id, **defaults)
            existing_pa_keys.add(pa_key)
            existing_account_names.add(account_name)
            created_pa_ids.append(pa_id)
            stats["pa_created"] += 1

        if DRY_RUN:
            transaction.set_rollback(True)

    print(json.dumps(stats, ensure_ascii=False, indent=2))
    print("reused_name_sample", reused_names)
    print("created_org_sample", created_org_ids[:5])
    print("created_pa_sample", created_pa_ids[:5])
    if not DRY_RUN:
        print(
            "totals_after",
            OrganizationRecord.objects.filter(is_deleted=False).count(),
            PlatformAccountRecord.objects.filter(is_deleted=False).count(),
        )


main()
