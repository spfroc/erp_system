import json
import os

import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()

from apps.data_store.models import TransactionRecord

PROJECT_ID = "pj-a0dd9f16"
rows = []
for tx in TransactionRecord.objects.filter(is_deleted=False, project_id=PROJECT_ID).order_by("-created_at")[:80]:
    td = tx.data or {}
    rows.append(
        {
            "id": tx.id,
            "type": td.get("type") or getattr(tx, "type", None),
            "amount": td.get("amount") or str(getattr(tx, "amount", "")),
            "status": td.get("status") or getattr(tx, "status", None),
            "remark": td.get("remark"),
            "salesOrderId": td.get("salesOrderId"),
            "orderNo": td.get("orderNo"),
            "account": td.get("account"),
            "date": td.get("date"),
        }
    )
print(json.dumps(rows, ensure_ascii=False, indent=2))
print("COUNT", len(rows))
