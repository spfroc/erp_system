"""生产一次性：去掉企业名称前缀后，按名称去重（引用迁移到保留记录）。

前缀：
  已注销 / 注销 / 自己域名

用法：
  python scripts/strip_org_name_prefixes_and_dedupe.py           # dry-run
  python scripts/strip_org_name_prefixes_and_dedupe.py --apply   # 写库
"""

from __future__ import annotations

import os
import sys
from collections import defaultdict
from typing import Any

import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()

from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from apps.data_store.models import (
    CustomerAccountRecord,
    InvoiceRecord,
    OnboardingRecord,
    OrganizationRecord,
    PlatformAccountRecord,
    ProjectRecord,
    PurchaseOrderRecord,
    SalesOrderRecord,
    ServiceOrderRecord,
    SupplierPriceRecord,
    TransactionRecord,
)

APPLY = "--apply" in sys.argv

# 长前缀优先，避免「已注销」被「注销」误切
PREFIXES = ("已注销", "自己域名", "注销")

# (model, ((column_or_empty, jsonKey), ...))
ORG_REF_SPECS: list[tuple[Any, tuple[tuple[str, str], ...]]] = [
    (
        ProjectRecord,
        (
            ("customer_org_id", "customerOrgId"),
            ("usage_unit_org_id", "usageUnitOrgId"),
            ("own_company_org_id", "ownCompanyOrgId"),
        ),
    ),
    (SalesOrderRecord, (("customer_org_id", "customerOrgId"), ("", "ownCompanyOrgId"))),
    (PurchaseOrderRecord, (("supplier_org_id", "supplierOrgId"), ("", "ownCompanyOrgId"))),
    (ServiceOrderRecord, (("customer_org_id", "customerOrgId"),)),
    (OnboardingRecord, (("customer_org_id", "customerOrgId"),)),
    (PlatformAccountRecord, (("customer_org_id", "customerOrgId"),)),
    (SupplierPriceRecord, (("supplier_org_id", "supplierOrgId"),)),
    (InvoiceRecord, (("", "buyerOrgId"), ("", "sellerOrgId"), ("", "counterpartyOrgId"))),
    (TransactionRecord, (("", "counterpartyOrgId"),)),
    (CustomerAccountRecord, (("customer_org_id", "customerOrgId"),)),
]


def strip_prefix(name: str) -> str | None:
    text = str(name or "").strip()
    if not text:
        return None
    for prefix in PREFIXES:
        if not text.startswith(prefix):
            continue
        cleaned = text[len(prefix) :].lstrip(" \t-_|·")
        if cleaned and cleaned != text:
            return cleaned
    return None


def normalize_name(name: str) -> str:
    return " ".join(str(name or "").split())


def org_score(row: OrganizationRecord) -> tuple:
    data = row.data if isinstance(row.data, dict) else {}
    code = (row.unified_credit_code or data.get("unifiedCreditCode") or "").strip()
    roles = row.roles if isinstance(row.roles, list) else []
    if not roles and isinstance(data.get("roles"), list):
        roles = data.get("roles") or []
    filled = sum(
        1
        for key in ("phone", "address", "contactName", "bankName", "bankAccount", "legalPerson")
        if str(data.get(key) or "").strip()
    )
    updated = str(data.get("updatedAt") or data.get("createdAt") or row.updated_at or "")
    return (1 if code else 0, len(roles), filled, updated, row.id)


def retarget_org_ids(id_map: dict[str, str]) -> int:
    """把 loser_id -> winner_id 的引用批量改写；返回触达记录数。"""
    if not id_map:
        return 0
    loser_ids = list(id_map.keys())
    changed = 0
    for model, fields in ORG_REF_SPECS:
        q = Q()
        for col, json_key in fields:
            if col:
                q |= Q(**{f"{col}__in": loser_ids})
            q |= Q(**{f"data__{json_key}__in": loser_ids})
        for rec in model.objects.filter(is_deleted=False).filter(q).iterator(chunk_size=300):
            data = dict(rec.data) if isinstance(rec.data, dict) else {}
            update_fields = ["data", "updated_at"]
            touched = False
            for col, json_key in fields:
                if col:
                    current = getattr(rec, col, "") or ""
                    if current in id_map:
                        setattr(rec, col, id_map[current])
                        update_fields.append(col)
                        touched = True
                current_json = data.get(json_key) or ""
                if current_json in id_map:
                    data[json_key] = id_map[current_json]
                    touched = True
            if not touched:
                continue
            data["id"] = data.get("id") or rec.id
            rec.data = data
            # update_fields 去重
            rec.save(update_fields=list(dict.fromkeys(update_fields)))
            changed += 1
    return changed


def soft_delete_org(row: OrganizationRecord, kept_id: str, now) -> None:
    data = dict(row.data) if isinstance(row.data, dict) else {}
    data["isDeleted"] = True
    data["deletedAt"] = now.isoformat()
    data["deletedBy"] = "strip_org_name_prefixes_and_dedupe"
    data["dedupeKeptId"] = kept_id
    row.data = data
    row.is_deleted = True
    row.deleted_at = now
    row.deleted_by = "strip_org_name_prefixes_and_dedupe"
    row.save(update_fields=["data", "is_deleted", "deleted_at", "deleted_by", "updated_at"])


def main() -> None:
    renamed: list[tuple[str, str, str]] = []
    for row in OrganizationRecord.objects.filter(is_deleted=False).iterator(chunk_size=500):
        data = row.data if isinstance(row.data, dict) else {}
        old_name = (row.name or data.get("name") or "").strip()
        new_name = strip_prefix(old_name)
        if not new_name:
            continue
        renamed.append((row.id, old_name, new_name))

    print(f"PREFIX_MATCH {len(renamed)} APPLY={APPLY}")
    for item in renamed[:40]:
        print(f"RENAME\t{item[0]}\t{item[1]}\t=>\t{item[2]}")
    if len(renamed) > 40:
        print(f"... and {len(renamed) - 40} more")

    rename_map = {row_id: new_name for row_id, _, new_name in renamed}
    by_name: dict[str, list[OrganizationRecord]] = defaultdict(list)
    for row in OrganizationRecord.objects.filter(is_deleted=False).iterator(chunk_size=500):
        data = row.data if isinstance(row.data, dict) else {}
        name = rename_map.get(row.id) or (row.name or data.get("name") or "")
        key = normalize_name(name)
        if key:
            by_name[key].append(row)

    dup_groups = {k: v for k, v in by_name.items() if len(v) > 1}
    print(f"DUP_GROUPS {len(dup_groups)} DUP_ROWS {sum(len(v) - 1 for v in dup_groups.values())}")
    shown = 0
    for name, rows in sorted(dup_groups.items(), key=lambda item: (-len(item[1]), item[0])):
        ranked = sorted(rows, key=org_score, reverse=True)
        print(f"DUP\t{name}\tn={len(rows)}\tKEEP={ranked[0].id}\tDROP={[r.id for r in ranked[1:]]}")
        shown += 1
        if shown >= 50:
            print(f"... and {len(dup_groups) - shown} more groups")
            break

    if not APPLY:
        print("DRY_RUN_ONLY pass --apply to write")
        return

    now = timezone.now()
    renamed_n = 0
    with transaction.atomic():
        for row_id, old_name, new_name in renamed:
            row = OrganizationRecord.objects.filter(id=row_id, is_deleted=False).first()
            if not row:
                continue
            data = dict(row.data) if isinstance(row.data, dict) else {}
            data["name"] = new_name
            data["id"] = data.get("id") or row.id
            data["nameBeforePrefixStrip"] = old_name
            row.name = new_name
            row.data = data
            row.save(update_fields=["name", "data", "updated_at"])
            renamed_n += 1

        by_name = defaultdict(list)
        for row in OrganizationRecord.objects.filter(is_deleted=False).iterator(chunk_size=500):
            data = row.data if isinstance(row.data, dict) else {}
            key = normalize_name(row.name or data.get("name") or "")
            if key:
                by_name[key].append(row)

        id_map: dict[str, str] = {}
        merge_plan: list[tuple[OrganizationRecord, list[OrganizationRecord]]] = []
        for rows in by_name.values():
            if len(rows) < 2:
                continue
            ranked = sorted(rows, key=org_score, reverse=True)
            winner = ranked[0]
            losers = ranked[1:]
            for loser in losers:
                id_map[loser.id] = winner.id
            merge_plan.append((winner, losers))

        retarget_n = retarget_org_ids(id_map)
        deleted_n = 0
        for winner, losers in merge_plan:
            for loser in losers:
                # 重新取，避免脏状态
                current = OrganizationRecord.objects.filter(id=loser.id, is_deleted=False).first()
                if not current:
                    continue
                soft_delete_org(current, winner.id, now)
                deleted_n += 1

    print(
        f"DONE renamed={renamed_n} merge_groups={len(merge_plan)} "
        f"deleted={deleted_n} retarget_touches={retarget_n}"
    )


if __name__ == "__main__":
    main()
