"""Soft-delete duplicate platform accounts: keep one per customer+platform(+qilu type).

Preference when choosing the survivor:
1. Has qiluAccountType (for 齐鲁云采)
2. Has note from migration (旧companies / 旧designated)
3. More filled credential fields
4. Newer updatedAt / createdAt
5. Stable id lexicographic max as last resort
"""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone

from django.utils import timezone as dj_tz

from apps.data_store.models import OrganizationRecord, PlatformAccountRecord

DRY_RUN = False


def _clean(value) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _type_key(rec: PlatformAccountRecord) -> str:
    if rec.platform != "齐鲁云采":
        return ""
    return _clean((rec.data or {}).get("qiluAccountType"))


def _score(rec: PlatformAccountRecord) -> tuple:
    data = rec.data or {}
    note = _clean(data.get("note"))
    migrated = 1 if ("旧companies" in note or "旧designated" in note or "mall#" in note) else 0
    has_type = 1 if _clean(data.get("qiluAccountType")) else 0
    fields = [
        data.get("accountName") or rec.account_name,
        data.get("accountPasswordMasked"),
        data.get("merchantId"),
        data.get("shopId"),
        data.get("shopName"),
        data.get("domain"),
        data.get("icpRecordNo"),
    ]
    filled = sum(1 for item in fields if _clean(item))
    updated = _clean(data.get("updatedAt") or data.get("createdAt"))
    return (has_type, migrated, filled, updated, rec.id)


def main() -> None:
    by_key: dict[tuple[str, str, str], list[PlatformAccountRecord]] = defaultdict(list)
    for rec in PlatformAccountRecord.objects.filter(is_deleted=False).iterator():
        key = (rec.customer_org_id or "", rec.platform or "", _type_key(rec))
        by_key[key].append(rec)

    dups = {key: rows for key, rows in by_key.items() if len(rows) > 1}
    print(f"duplicate_groups={len(dups)} dry_run={DRY_RUN}")

    deleted = 0
    kept = 0
    now = dj_tz.now()
    for key, rows in sorted(dups.items(), key=lambda item: (-len(item[1]), item[0])):
        org = OrganizationRecord.objects.filter(id=key[0]).first()
        org_name = org.name if org else key[0]
        ranked = sorted(rows, key=_score, reverse=True)
        winner = ranked[0]
        losers = ranked[1:]
        print(
            f"KEEP {winner.id} DROP {[item.id for item in losers]} "
            f"| {org_name} | {key[1]} | {key[2] or '-'} | accounts="
            f"{[_clean((item.data or {}).get('accountName') or item.account_name) for item in ranked]}"
        )
        kept += 1
        if DRY_RUN:
            deleted += len(losers)
            continue
        for loser in losers:
            data = dict(loser.data or {})
            data["isDeleted"] = True
            data["deletedAt"] = now.isoformat()
            data["deletedBy"] = "dedupe_platform_accounts"
            data["dedupeKeptId"] = winner.id
            loser.data = data
            loser.is_deleted = True
            loser.deleted_at = now
            loser.deleted_by = "dedupe_platform_accounts"
            loser.save(update_fields=["data", "is_deleted", "deleted_at", "deleted_by", "updated_at"])
            deleted += 1

    print(f"groups_resolved={kept} records_deleted={deleted}")


main()
