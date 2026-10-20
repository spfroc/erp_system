"""Inspect / set a sales order to unpaid (待付款 / 未收款)."""
from __future__ import annotations

import json
import os
import sys

import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()

from apps.data_store.models import ProjectRecord, SalesOrderRecord, TransactionRecord  # noqa: E402

ORDER_NO = sys.argv[1] if len(sys.argv) > 1 else "SO-XM20260811028-01"
APPLY = "--apply" in sys.argv


def main() -> None:
    order = SalesOrderRecord.objects.filter(order_no=ORDER_NO, is_deleted=False).first()
    if not order:
        print(f"NOT_FOUND order_no={ORDER_NO}")
        sys.exit(1)

    data = dict(order.data or {})
    print("BEFORE")
    print(
        json.dumps(
            {
                "id": order.id,
                "order_no": order.order_no,
                "project_id": order.project_id,
                "status_col": order.status,
                "amount": str(order.amount),
                "receivable": str(order.receivable_amount),
                "received": str(order.received_amount),
                "data.status": data.get("status"),
                "data.receivedAmount": data.get("receivedAmount"),
                "data.receivableAmount": data.get("receivableAmount"),
                "data.paidAt": data.get("paidAt"),
                "data.updatedAt": data.get("updatedAt"),
            },
            ensure_ascii=False,
            indent=2,
        )
    )

    project = ProjectRecord.objects.filter(id=order.project_id, is_deleted=False).first()
    if project:
        pdata = dict(project.data or {})
        print(
            "PROJECT",
            json.dumps(
                {
                    "id": project.id,
                    "name": pdata.get("name") or getattr(project, "name", None),
                    "paymentStatus": pdata.get("paymentStatus"),
                    "status": pdata.get("status") or getattr(project, "status", None),
                },
                ensure_ascii=False,
            ),
        )

    related_txs = []
    for tx in TransactionRecord.objects.filter(is_deleted=False, project_id=order.project_id).order_by("-created_at")[
        :50
    ]:
        td = tx.data or {}
        if td.get("salesOrderId") == order.id or td.get("orderNo") == ORDER_NO or ORDER_NO in str(td.get("remark") or ""):
            related_txs.append(
                {
                    "id": tx.id,
                    "type": td.get("type"),
                    "amount": td.get("amount"),
                    "status": td.get("status"),
                    "remark": td.get("remark"),
                    "salesOrderId": td.get("salesOrderId"),
                }
            )
    print("RELATED_TX", json.dumps(related_txs, ensure_ascii=False, indent=2))

    if not APPLY:
        print("DRY_RUN (pass --apply to update)")
        return

    # UI「未收款」对应销售订单状态「待付款」
    order.status = "待付款"
    order.received_amount = 0
    data["status"] = "待付款"
    data["receivedAmount"] = 0
    if "paidAt" in data:
        data["paidAt"] = None
    from django.utils import timezone as dj_tz

    data["updatedAt"] = dj_tz.now().isoformat()
    order.data = data
    order.save(update_fields=["status", "received_amount", "data", "updated_at"])

    if project:
        pdata = dict(project.data or {})
        # 仅当项目收款状态明确为已收/已付款时回退为未收款
        if pdata.get("paymentStatus") in {"已付款", "已收", "部分付款", "部分收款"}:
            pdata["paymentStatus"] = "未收款"
            pdata["updatedAt"] = data["updatedAt"]
            project.data = pdata
            project.save(update_fields=["data", "updated_at"])

    order.refresh_from_db()
    print(
        "AFTER",
        json.dumps(
            {
                "status_col": order.status,
                "received": str(order.received_amount),
                "data.status": (order.data or {}).get("status"),
                "data.receivedAmount": (order.data or {}).get("receivedAmount"),
                "data.paidAt": (order.data or {}).get("paidAt"),
            },
            ensure_ascii=False,
            indent=2,
        ),
    )


if __name__ == "__main__":
    main()
