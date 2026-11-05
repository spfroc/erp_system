"""Migrate old admin 供应商管理→电商/代理商 (companies + platform_mall_accounts type=1).

Previously migrated designated_suppliers (定点) by mistake for this menu.
This pass imports companies; skips existing org names; only creates platform
accounts when founded_at (到期时间) >= today and mall account present.
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

SOURCE_PATH = Path("/tmp/emall_companies.json")
PLATFORM = "齐鲁云采"
DRY_RUN = False
FOCUS_NAME = "泗水县华唐商贸有限公司"


def _clean(value) -> str:
    if value is None:
        return ""
    text = str(value).strip()
    if text in {"-", "—", "null", "None", "无"}:
        return ""
    return text


def _new_id(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:8]}"


def _now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().replace(microsecond=0).isoformat()


def _not_expired(founded_at: str | None, today: str) -> bool:
    if not founded_at:
        return False  # companies always have founded_at in practice; treat missing as expired/unknown skip for accounts
    return founded_at >= today


def main() -> None:
    rows = json.loads(SOURCE_PATH.read_text(encoding="utf-8"))
    today = date.today().isoformat()
    print(f"source={len(rows)} today={today} dry_run={DRY_RUN}")

    existing_orgs = {}
    for rec in OrganizationRecord.objects.filter(is_deleted=False):
        name = _clean((rec.data or {}).get("name") or rec.name)
        if name:
            existing_orgs[name] = rec

    existing_account_names = {
        _clean((rec.data or {}).get("accountName") or rec.account_name)
        for rec in PlatformAccountRecord.objects.filter(is_deleted=False)
        if _clean((rec.data or {}).get("accountName") or rec.account_name)
    }

    stats = {
        "org_created": 0,
        "org_reused": 0,
        "pa_created": 0,
        "pa_skipped_expired": 0,
        "pa_skipped_empty_account": 0,
        "pa_skipped_exists": 0,
    }
    focus = None

    with transaction.atomic():
        for row in rows:
            name = _clean(row.get("name"))
            if not name:
                continue

            org = existing_orgs.get(name)
            if org:
                stats["org_reused"] += 1
                org_id = org.id
            else:
                org_id = _new_id("org")
                now = _now_iso()
                created = _clean(row.get("created_at")) or now
                phone = _clean(row.get("contact_mobile")) or _clean(row.get("tel_number"))
                payload = {
                    "id": org_id,
                    "name": name,
                    "entityType": "企业",
                    "roles": ["平台入驻商"],
                    "phone": phone,
                    "email": _clean(row.get("email")),
                    "legalPerson": _clean(row.get("legal_person")),
                    "unifiedCreditCode": _clean(row.get("license_code")),
                    "city": _clean(row.get("city")),
                    "address": _clean(row.get("address")),
                    "status": "正常" if int(row.get("status") or 1) == 1 else "停用",
                    "createdAt": created,
                    "updatedAt": now,
                }
                # drop empty optional strings
                payload = {k: v for k, v in payload.items() if v != "" or k in {"id", "name", "entityType", "roles", "status", "createdAt", "updatedAt"}}
                defaults = _record_defaults(OrganizationRecord, payload)
                defaults["created_at"] = dj_tz.now()
                if not DRY_RUN:
                    OrganizationRecord.objects.create(id=org_id, **defaults)
                existing_orgs[name] = type("Tmp", (), {"id": org_id, "name": name, "data": payload})()
                stats["org_created"] += 1

            founded_at = _clean(row.get("founded_at")) or None
            if not _not_expired(founded_at, today):
                stats["pa_skipped_expired"] += 1
                if name == FOCUS_NAME:
                    focus = {"org_id": org_id, "action": "org_only_expired_skip_pa", "founded_at": founded_at}
                continue

            account_name = _clean(row.get("mall_account"))
            password = _clean(row.get("mall_password"))
            if not account_name:
                stats["pa_skipped_empty_account"] += 1
                if name == FOCUS_NAME:
                    focus = {"org_id": org_id, "action": "org_only_empty_account"}
                continue

            if account_name in existing_account_names:
                stats["pa_skipped_exists"] += 1
                if name == FOCUS_NAME:
                    focus = {"org_id": org_id, "action": "pa_exists", "account": account_name}
                continue

            pa_id = _new_id("pa")
            now = _now_iso()
            created = _clean(row.get("created_at")) or now
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
                "serviceYears": 1,
                "salesOwner": "未分配",
                "currentStatus": "服务中",
                "expireDate": founded_at,
                "domain": _clean(row.get("domain")) or None,
                "icpRecordNo": _clean(row.get("icp_number")) or None,
                "note": f"旧companies#{row.get('id')};mall#{row.get('mall_account_id')}",
                "createdAt": created,
                "updatedAt": now,
            }
            payload = {k: v for k, v in payload.items() if v is not None and v != ""}
            defaults = _record_defaults(PlatformAccountRecord, payload)
            if not DRY_RUN:
                PlatformAccountRecord.objects.create(id=pa_id, **defaults)
            existing_account_names.add(account_name)
            stats["pa_created"] += 1
            if name == FOCUS_NAME:
                focus = {"org_id": org_id, "pa_id": pa_id, "action": "created", "account": account_name, "expireDate": founded_at}

        if DRY_RUN:
            transaction.set_rollback(True)

    print(json.dumps(stats, ensure_ascii=False, indent=2))
    print("FOCUS", focus)
    if not DRY_RUN:
        print(
            "totals_after",
            OrganizationRecord.objects.filter(is_deleted=False).count(),
            PlatformAccountRecord.objects.filter(is_deleted=False).count(),
        )


main()
