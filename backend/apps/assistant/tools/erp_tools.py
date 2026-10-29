from __future__ import annotations

from typing import Any

from django.db.models import Q

from apps.assistant.services.tool_registry import ToolDefinition, register_tool
from apps.data_store.models import ProductRecord, PurchaseOrderRecord, SalesOrderRecord

# 禁止把完整 data JSON 交给模型；仅白名单字段
PRODUCT_FIELDS = ("id", "code", "name", "kind", "category")
ORDER_FIELDS = ("id", "order_no", "status", "project_id")


def _pick(record, fields: tuple[str, ...], extra: dict[str, Any] | None = None) -> dict[str, Any]:
    item = {field: getattr(record, field, "") for field in fields}
    data = record.data if isinstance(getattr(record, "data", None), dict) else {}
    # 额外安全字段（若存在）
    for key in ("name", "title", "customerName", "supplierName", "amount", "totalAmount"):
        if key in data and key not in item:
            value = data.get(key)
            if isinstance(value, (str, int, float)) and key.lower().find("password") < 0:
                item[key] = value
    if extra:
        item.update(extra)
    return item


def _product_search(*, params: dict[str, Any], user_data: dict) -> dict[str, Any]:
    del user_data
    keyword = str(params.get("keyword") or params.get("search") or "").strip()
    page = max(int(params.get("page") or 1), 1)
    page_size = min(max(int(params.get("page_size") or 20), 1), 100)
    qs = ProductRecord.objects.filter(is_deleted=False).order_by("-updated_at", "-id")
    if keyword:
        qs = qs.filter(Q(name__icontains=keyword) | Q(code__icontains=keyword) | Q(category__icontains=keyword))
    total = qs.count()
    rows = list(qs[(page - 1) * page_size : page * page_size])
    items = [_pick(row, PRODUCT_FIELDS) for row in rows]
    return {
        "block_type": "erp_record_list",
        "summary": f"找到 {total} 个商品。",
        "content": f"找到 {total} 个商品。",
        "data": {"collection": "products", "items": items, "total": total, "page": page, "page_size": page_size},
    }


def _sales_order_search(*, params: dict[str, Any], user_data: dict) -> dict[str, Any]:
    del user_data
    keyword = str(params.get("keyword") or params.get("search") or "").strip()
    status = str(params.get("status") or "").strip()
    page = max(int(params.get("page") or 1), 1)
    page_size = min(max(int(params.get("page_size") or 20), 1), 100)
    qs = SalesOrderRecord.objects.filter(is_deleted=False).order_by("-updated_at", "-id")
    if status:
        qs = qs.filter(status=status)
    if keyword:
        qs = qs.filter(Q(order_no__icontains=keyword) | Q(project_id__icontains=keyword) | Q(customer_org_id__icontains=keyword))
    total = qs.count()
    rows = list(qs[(page - 1) * page_size : page * page_size])
    items = [_pick(row, ORDER_FIELDS + ("customer_org_id",)) for row in rows]
    return {
        "block_type": "erp_record_list",
        "summary": f"找到 {total} 个销售订单。",
        "content": f"找到 {total} 个销售订单。",
        "data": {"collection": "salesOrders", "items": items, "total": total, "page": page, "page_size": page_size},
    }


def _purchase_order_search(*, params: dict[str, Any], user_data: dict) -> dict[str, Any]:
    del user_data
    keyword = str(params.get("keyword") or params.get("search") or "").strip()
    status = str(params.get("status") or "").strip()
    page = max(int(params.get("page") or 1), 1)
    page_size = min(max(int(params.get("page_size") or 20), 1), 100)
    qs = PurchaseOrderRecord.objects.filter(is_deleted=False).order_by("-updated_at", "-id")
    if status:
        qs = qs.filter(status=status)
    if keyword:
        qs = qs.filter(Q(order_no__icontains=keyword) | Q(project_id__icontains=keyword) | Q(supplier_org_id__icontains=keyword))
    total = qs.count()
    rows = list(qs[(page - 1) * page_size : page * page_size])
    items = [_pick(row, ORDER_FIELDS + ("supplier_org_id",)) for row in rows]
    return {
        "block_type": "erp_record_list",
        "summary": f"找到 {total} 个采购订单。",
        "content": f"找到 {total} 个采购订单。",
        "data": {"collection": "purchaseOrders", "items": items, "total": total, "page": page, "page_size": page_size},
    }


def register() -> None:
    register_tool(
        ToolDefinition(
            name="erp.product.search",
            description="查询 ERP 商品",
            input_schema={
                "type": "object",
                "properties": {
                    "keyword": {"type": "string"},
                    "page": {"type": "integer"},
                    "page_size": {"type": "integer"},
                },
            },
            permission="product.view",
            risk_level="read",
            handler=_product_search,
        )
    )
    register_tool(
        ToolDefinition(
            name="erp.sales_order.search",
            description="查询销售订单",
            input_schema={
                "type": "object",
                "properties": {
                    "keyword": {"type": "string"},
                    "status": {"type": "string"},
                    "page": {"type": "integer"},
                    "page_size": {"type": "integer"},
                },
            },
            permission="salesOrder.view",
            risk_level="read",
            handler=_sales_order_search,
        )
    )
    register_tool(
        ToolDefinition(
            name="erp.purchase_order.search",
            description="查询采购订单",
            input_schema={
                "type": "object",
                "properties": {
                    "keyword": {"type": "string"},
                    "status": {"type": "string"},
                    "page": {"type": "integer"},
                    "page_size": {"type": "integer"},
                },
            },
            permission="purchaseOrder.view",
            risk_level="read",
            handler=_purchase_order_search,
        )
    )
