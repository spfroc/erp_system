from __future__ import annotations

import re
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Any

from django.db.models import Count, OuterRef, Q, Subquery, Sum

from apps.assistant.services.chart_params import resolve_chart_type
from apps.assistant.services.tool_registry import ToolDefinition, register_tool
from apps.data_store.models import (
    InvoiceRecord,
    OnboardingRecord,
    OrganizationRecord,
    ProductRecord,
    ProjectRecord,
    PurchaseOrderRecord,
    SalesOrderRecord,
    ServiceOrderRecord,
    TransactionRecord,
)

# 禁止把完整 data JSON 交给模型；仅白名单字段
PRODUCT_FIELDS = ("id", "code", "name", "kind", "category")
ORDER_FIELDS = ("id", "order_no", "status", "project_id")
CONFIRMED_INVOICE_STATUS = "已确认"


def _pick(record, fields: tuple[str, ...], extra: dict[str, Any] | None = None) -> dict[str, Any]:
    item = {field: getattr(record, field, "") for field in fields}
    data = record.data if isinstance(getattr(record, "data", None), dict) else {}
    for key in ("name", "title", "customerName", "supplierName", "amount", "totalAmount"):
        if key in data and key not in item:
            value = data.get(key)
            if isinstance(value, (str, int, float)) and key.lower().find("password") < 0:
                item[key] = value
    if extra:
        item.update(extra)
    return item


def _data(record) -> dict[str, Any]:
    return record.data if isinstance(getattr(record, "data", None), dict) else {}


def _org_name_map(org_ids: list[str] | set[str]) -> dict[str, str]:
    ids = [str(item) for item in org_ids if item]
    if not ids:
        return {}
    rows = OrganizationRecord.objects.filter(is_deleted=False, id__in=ids).only("id", "name")
    return {row.id: row.name or row.id for row in rows}


def _find_orgs(keyword: str, *, limit: int = 20) -> list[OrganizationRecord]:
    keyword = (keyword or "").strip()
    if not keyword:
        return []
    return list(
        OrganizationRecord.objects.filter(is_deleted=False)
        .filter(Q(name__icontains=keyword) | Q(unified_credit_code__icontains=keyword) | Q(id=keyword))
        .order_by("name")[:limit]
    )


def _customer_keyword(params: dict[str, Any]) -> str:
    return str(
        params.get("customer")
        or params.get("customer_name")
        or params.get("keyword")
        or params.get("search")
        or ""
    ).strip()


def _page_params(params: dict[str, Any]) -> tuple[int, int]:
    page = max(int(params.get("page") or 1), 1)
    page_size = min(max(int(params.get("page_size") or 20), 1), 100)
    return page, page_size


def _product_search(*, params: dict[str, Any], user_data: dict) -> dict[str, Any]:
    del user_data
    keyword = str(params.get("keyword") or params.get("search") or "").strip()
    page, page_size = _page_params(params)
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
    customer = _customer_keyword(params)
    status = str(params.get("status") or "").strip()
    page, page_size = _page_params(params)
    qs = SalesOrderRecord.objects.filter(is_deleted=False).order_by("-updated_at", "-id")
    if status:
        qs = qs.filter(status=status)
    org_ids: list[str] = []
    if customer:
        org_ids = [org.id for org in _find_orgs(customer, limit=40)]
        if org_ids:
            qs = qs.filter(customer_org_id__in=org_ids)
        else:
            qs = qs.filter(
                Q(customer_org_id__icontains=customer)
                | Q(order_no__icontains=customer)
                | Q(project_id__icontains=customer)
            )
    elif keyword:
        org_ids = [org.id for org in _find_orgs(keyword, limit=40)]
        q = Q(order_no__icontains=keyword) | Q(project_id__icontains=keyword) | Q(customer_org_id__icontains=keyword)
        if org_ids:
            q |= Q(customer_org_id__in=org_ids)
        qs = qs.filter(q)
    total = qs.count()
    rows = list(qs[(page - 1) * page_size : page * page_size])
    names = _org_name_map({row.customer_org_id for row in rows})
    items = [
        _pick(
            row,
            ORDER_FIELDS + ("customer_org_id", "amount"),
            {
                "customer_name": names.get(row.customer_org_id, ""),
                "amount": str(row.amount),
            },
        )
        for row in rows
    ]
    return {
        "block_type": "erp_record_list",
        "summary": f"找到 {total} 个销售订单。",
        "content": f"找到 {total} 个销售订单。",
        "data": {
            "collection": "salesOrders",
            "items": items,
            "total": total,
            "page": page,
            "page_size": page_size,
            "customer": customer or keyword,
        },
    }


def _purchase_order_search(*, params: dict[str, Any], user_data: dict) -> dict[str, Any]:
    del user_data
    keyword = str(params.get("keyword") or params.get("search") or "").strip()
    status = str(params.get("status") or "").strip()
    page, page_size = _page_params(params)
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


def _service_order_search(*, params: dict[str, Any], user_data: dict) -> dict[str, Any]:
    del user_data
    keyword = str(params.get("keyword") or params.get("search") or "").strip()
    customer = _customer_keyword(params)
    status = str(params.get("status") or "").strip()
    page, page_size = _page_params(params)
    qs = ServiceOrderRecord.objects.filter(is_deleted=False).order_by("-updated_at", "-id")
    if status:
        qs = qs.filter(status=status)
    lookup = customer or keyword
    if lookup:
        org_ids = [org.id for org in _find_orgs(lookup, limit=40)]
        q = Q(order_no__icontains=lookup) | Q(project_id__icontains=lookup) | Q(customer_org_id__icontains=lookup)
        if org_ids:
            q |= Q(customer_org_id__in=org_ids)
        qs = qs.filter(q)
    total = qs.count()
    rows = list(qs[(page - 1) * page_size : page * page_size])
    names = _org_name_map({row.customer_org_id for row in rows})
    items = [
        _pick(
            row,
            ORDER_FIELDS + ("customer_org_id", "service_id", "amount"),
            {
                "customer_name": names.get(row.customer_org_id, ""),
                "amount": str(row.amount),
            },
        )
        for row in rows
    ]
    return {
        "block_type": "erp_record_list",
        "summary": f"找到 {total} 个服务订单。",
        "content": f"找到 {total} 个服务订单。",
        "data": {
            "collection": "serviceOrders",
            "items": items,
            "total": total,
            "page": page,
            "page_size": page_size,
            "customer": lookup,
        },
    }


def _parse_day(value: str) -> date | None:
    text = (value or "").strip()
    if not text:
        return None
    for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%Y.%m.%d", "%Y-%m-%d %H:%M:%S", "%Y/%m/%d %H:%M:%S"):
        try:
            return datetime.strptime(text[:19], fmt).date()
        except ValueError:
            continue
    match = re.match(r"^(\d{4})[-/.](\d{1,2})[-/.](\d{1,2})", text)
    if not match:
        return None
    try:
        return date(int(match.group(1)), int(match.group(2)), int(match.group(3)))
    except ValueError:
        return None


def _expiry_window_end(*, within_months: int = 0, within_days: int = 0) -> date | None:
    today = date.today()
    if within_days > 0:
        return today + timedelta(days=within_days)
    if within_months > 0:
        month = today.month - 1 + within_months
        year = today.year + month // 12
        month = month % 12 + 1
        day = min(today.day, [31, 29 if year % 4 == 0 and (year % 100 != 0 or year % 400 == 0) else 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31][month - 1])
        return date(year, month, day)
    return None


def _date_in_expiry_window(
    raw: str,
    *,
    window_end: date | None,
    include_overdue: bool,
) -> bool:
    day = _parse_day(raw)
    if not day:
        return False
    today = date.today()
    if window_end is None:
        return True
    if include_overdue and day < today:
        # 已过期：仍落在窗口回溯范围内（同长度）
        lookback_start = today - (window_end - today)
        return lookback_start <= day < today
    return today <= day <= window_end


def _customer_expiry(*, params: dict[str, Any], user_data: dict) -> dict[str, Any]:
    del user_data
    keyword = _customer_keyword(params)
    # 防止把「一个月内过期 用户」整句当成客户名
    if keyword and re.fullmatch(r".*(过期|到期|月内|天内|用户|名称).*", keyword) and len(keyword) <= 20:
        if not _find_orgs(keyword, limit=1):
            keyword = ""
    page, page_size = _page_params(params)
    within_months = int(params.get("within_months") or 0)
    within_days = int(params.get("within_days") or 0)
    include_overdue = bool(params.get("include_overdue"))
    window_end = _expiry_window_end(within_months=within_months, within_days=within_days)

    orgs = _find_orgs(keyword, limit=30) if keyword else []
    org_ids = [org.id for org in orgs]
    qs = ProjectRecord.objects.filter(is_deleted=False).order_by("-updated_at", "-id")
    if org_ids:
        qs = qs.filter(customer_org_id__in=org_ids)
    elif keyword:
        qs = qs.filter(
            Q(name__icontains=keyword)
            | Q(project_no__icontains=keyword)
            | Q(customer_org_id__icontains=keyword)
        )
    # 有时间窗时多取一些再内存过滤；否则只取有到期日的
    candidates = list(qs[:500] if window_end else qs.exclude(data__serviceEndDate__isnull=True).exclude(data__serviceEndDate="")[:500])

    onboard_by_org: dict[str, str] = {}
    target_ids = org_ids or list({row.customer_org_id for row in candidates if row.customer_org_id})
    if target_ids:
        for board in OnboardingRecord.objects.filter(is_deleted=False, customer_org_id__in=target_ids).order_by("-updated_at")[:500]:
            expire = str(_data(board).get("expireDate") or "").strip()
            if expire and board.customer_org_id not in onboard_by_org:
                onboard_by_org[board.customer_org_id] = expire

    names = _org_name_map({row.customer_org_id for row in candidates} | set(org_ids))
    items = []
    for row in candidates:
        payload = _data(row)
        end_date = str(payload.get("serviceEndDate") or "").strip()
        onboard_expire = onboard_by_org.get(row.customer_org_id, "")
        if window_end:
            hit = _date_in_expiry_window(end_date, window_end=window_end, include_overdue=include_overdue) or _date_in_expiry_window(
                onboard_expire, window_end=window_end, include_overdue=include_overdue
            )
            if not hit:
                continue
        elif not end_date and not onboard_expire:
            continue
        items.append(
            {
                "id": row.id,
                "project_no": row.project_no,
                "name": row.name,
                "type": row.type,
                "status": row.status,
                "customer_org_id": row.customer_org_id,
                "customer_name": names.get(row.customer_org_id, ""),
                "service_start_date": str(payload.get("serviceStartDate") or ""),
                "service_end_date": end_date,
                "onboarding_expire_date": onboard_expire,
                "invoice_status": str(payload.get("invoiceStatus") or ""),
            }
        )

    total = len(items)
    paged = items[(page - 1) * page_size : page * page_size]
    if window_end:
        label = f"{within_months or ''}个月内" if within_months else f"{within_days}天内"
        label = f"{label}到期/过期" + ("（含已过期）" if include_overdue else "")
    else:
        label = keyword or "全部"
    return {
        "block_type": "erp_record_list",
        "summary": f"找到 {total} 条与「{label}」相关的客户/项目到期信息。",
        "content": f"找到 {total} 条与「{label}」相关的客户/项目到期信息。",
        "data": {
            "collection": "customerExpiry",
            "items": paged,
            "total": total,
            "page": page,
            "page_size": page_size,
            "within_months": within_months or None,
            "within_days": within_days or None,
            "customers": [{"id": org.id, "name": org.name} for org in orgs[:10]],
        },
    }


def _project_status(*, params: dict[str, Any], user_data: dict) -> dict[str, Any]:
    del user_data
    code = str(params.get("project_no") or params.get("keyword") or params.get("search") or "").strip()
    if not code:
        return {
            "block_type": "clarification",
            "summary": "请提供项目编号",
            "content": "请提供项目编号或平台订单号，例如：26922000001159238971 查询该项目的开票状态。",
            "data": {},
        }
    qs = ProjectRecord.objects.filter(is_deleted=False).filter(
        Q(project_no=code)
        | Q(id=code)
        | Q(project_no__icontains=code)
        | Q(data__platformOrderNo=code)
        | Q(data__platformOrderNo__icontains=code)
    ).order_by("-updated_at", "-id")
    rows = list(qs[:10])
    if not rows:
        return {
            "block_type": "error",
            "summary": "未找到项目",
            "content": f"未找到编号「{code}」对应的项目。",
            "data": {"project_no": code},
        }
    names = _org_name_map({row.customer_org_id for row in rows})
    items = []
    for row in rows:
        payload = _data(row)
        service_orders = ServiceOrderRecord.objects.filter(is_deleted=False, project_id=row.id).count()
        sales_orders = SalesOrderRecord.objects.filter(is_deleted=False, project_id=row.id).count()
        items.append(
            {
                "id": row.id,
                "project_no": row.project_no,
                "name": row.name,
                "type": row.type,
                "status": row.status,
                "customer_name": names.get(row.customer_org_id, ""),
                "invoice_status": str(payload.get("invoiceStatus") or ""),
                "payment_status": str(payload.get("paymentStatus") or ""),
                "service_end_date": str(payload.get("serviceEndDate") or ""),
                "platform_order_no": str(payload.get("platformOrderNo") or ""),
                "service_order_count": service_orders,
                "sales_order_count": sales_orders,
            }
        )
    first = items[0]
    content = (
        f"项目「{first.get('project_no') or first.get('name')}」开票状态："
        f"{first.get('invoice_status') or '未填写'}；"
        f"客户：{first.get('customer_name') or '-'}；"
        f"服务到期：{first.get('service_end_date') or '-'}。"
    )
    return {
        "block_type": "erp_record_list",
        "summary": content,
        "content": content,
        "data": {"collection": "projectStatus", "items": items, "total": len(items), "page": 1, "page_size": len(items)},
    }


def _money(value: Any) -> str:
    try:
        return f"{Decimal(str(value or 0)):.2f}"
    except Exception:  # noqa: BLE001
        return "0.00"


def _resolve_tx_period(params: dict[str, Any]) -> tuple[str, str]:
    date_from = str(params.get("date_from") or params.get("dateFrom") or "").strip()
    date_to = str(params.get("date_to") or params.get("dateTo") or "").strip()
    if date_from or date_to:
        return date_from, date_to
    period = str(params.get("relative_period") or "").strip()
    if period in {"all", "全部", "累计", "all_time"}:
        return "", ""
    today = date.today()
    if period == "yesterday":
        day = today - timedelta(days=1)
        return day.isoformat(), day.isoformat()
    if period == "today":
        return today.isoformat(), today.isoformat()
    if period == "day_before_yesterday":
        day = today - timedelta(days=2)
        return day.isoformat(), day.isoformat()
    if period == "last_30_days":
        return (today - timedelta(days=30)).isoformat(), today.isoformat()
    if period == "this_week":
        start = today - timedelta(days=today.weekday())
        return start.isoformat(), today.isoformat()
    if period == "this_month":
        return today.replace(day=1).isoformat(), today.isoformat()
    if period == "last_month":
        first_this = today.replace(day=1)
        last_prev = first_this - timedelta(days=1)
        return last_prev.replace(day=1).isoformat(), last_prev.isoformat()
    if period.startswith("last_") and period.endswith("_days"):
        try:
            days = max(1, min(int(period[len("last_") : -len("_days")]), 365))
            return (today - timedelta(days=days)).isoformat(), today.isoformat()
        except ValueError:
            pass
    return "", ""


def _tx_period_q(date_from: str, date_to: str) -> Q:
    """按交易日（优先 occurredAt，否则 date）过滤；两端均可空。"""
    if not date_from and not date_to:
        return Q()
    end_exclusive = ""
    if date_to:
        end_exclusive = (date.fromisoformat(date_to) + timedelta(days=1)).isoformat()
    by_occurred = Q()
    by_date = Q()
    if date_from:
        by_occurred &= Q(data__occurredAt__gte=date_from)
        by_date &= Q(date__gte=date_from)
    if end_exclusive:
        by_occurred &= Q(data__occurredAt__lt=end_exclusive)
        by_date &= Q(date__lte=date_to)
    # occurredAt 为空时回退 date 列
    empty_occurred = Q(data__occurredAt__isnull=True) | Q(data__occurredAt="")
    return by_occurred | (empty_occurred & by_date)


INCOME_TX_TYPES = ("收款", "后返")


def _transaction_stats(*, params: dict[str, Any], user_data: dict) -> dict[str, Any]:
    """按项目类型汇总交易流水（默认收入：收款/后返）。"""
    del user_data
    date_from, date_to = _resolve_tx_period(params)
    project_type = str(params.get("project_type") or params.get("projectType") or "").strip()
    tx_type = str(params.get("type") or "").strip()
    chart_type = resolve_chart_type(params)

    qs = TransactionRecord.objects.filter(is_deleted=False).exclude(status="作废")
    try:
        from apps.data_store.finance_statements import orphaned_transaction_ids

        orphan_ids = orphaned_transaction_ids()
        if orphan_ids:
            qs = qs.exclude(id__in=orphan_ids)
    except Exception:  # noqa: BLE001
        pass

    period_q = _tx_period_q(date_from, date_to)
    if period_q:
        qs = qs.filter(period_q)

    if tx_type:
        qs = qs.filter(type=tx_type)
    else:
        qs = qs.filter(type__in=INCOME_TX_TYPES)

    project_type_sq = ProjectRecord.objects.filter(id=OuterRef("project_id")).values("type")[:1]
    qs = qs.annotate(project_type=Subquery(project_type_sq))
    if project_type in {"服务项目", "商品项目"}:
        qs = qs.filter(project_type=project_type)

    grouped = {
        row["project_type"] or "未关联项目": {
            "count": int(row["count"] or 0),
            "amount_sum": _money(row["amount_sum"]),
        }
        for row in qs.values("project_type")
        .annotate(count=Count("id"), amount_sum=Sum("amount"))
        .order_by("project_type")
    }
    service = grouped.get("服务项目") or {"count": 0, "amount_sum": "0.00"}
    product = grouped.get("商品项目") or {"count": 0, "amount_sum": "0.00"}
    other_amount = Decimal("0.00")
    other_count = 0
    for key, row in grouped.items():
        if key in {"服务项目", "商品项目"}:
            continue
        other_count += int(row["count"])
        other_amount += Decimal(row["amount_sum"])

    period_label = f"{date_from} ~ {date_to}" if date_from and date_to else "全部时间"
    kind_label = tx_type or "收款/后返"
    content = (
        f"{period_label} {kind_label}流水："
        f"服务项目 {service['amount_sum']} 元（{service['count']} 笔），"
        f"商品项目 {product['amount_sum']} 元（{product['count']} 笔）"
        + (f"；其他/未关联 {other_amount:.2f} 元（{other_count} 笔）" if other_count else "")
        + "。"
    )
    items = [
        {"label": "时间范围", "value": period_label},
        {"label": "流水类型", "value": kind_label},
        {"label": "服务项目流水", "value": f"{service['amount_sum']} 元（{service['count']} 笔）"},
        {"label": "商品项目流水", "value": f"{product['amount_sum']} 元（{product['count']} 笔）"},
    ]
    if other_count:
        items.append({"label": "其他/未关联", "value": f"{other_amount:.2f} 元（{other_count} 笔）"})
    data: dict[str, Any] = {
        "title": "项目交易流水统计",
        "date_from": date_from or None,
        "date_to": date_to or None,
        "type": kind_label,
        "service_project": service,
        "product_project": product,
        "items": items,
    }
    if chart_type:
        categories = ["服务项目", "商品项目"]
        values = [float(service["amount_sum"]), float(product["amount_sum"])]
        if chart_type == "pie":
            data["charts"] = [
                {
                    "type": "pie",
                    "title": "项目流水对比",
                    "categories": categories,
                    "series": [{"name": "金额(元)", "data": values}],
                }
            ]
        else:
            data["charts"] = [
                {
                    "type": "bar" if chart_type == "bar" else "line",
                    "title": "项目流水对比",
                    "categories": categories,
                    "series": [{"name": "金额(元)", "data": values}],
                }
            ]
    return {
        "block_type": "statistics",
        "summary": content,
        "content": content,
        "data": data,
    }


_CANCELLED_ORDER_STATUS = ("取消", "已取消", "作废")


def _order_effective_day(row) -> str:
    """历史数据常无 ORM created_at，回退 data.paidAt / data.createdAt。"""
    if getattr(row, "created_at", None):
        try:
            return row.created_at.date().isoformat()
        except Exception:  # noqa: BLE001
            pass
    data = row.data if isinstance(getattr(row, "data", None), dict) else {}
    for key in ("paidAt", "createdAt", "date"):
        raw = str(data.get(key) or "").strip()
        if len(raw) >= 10 and raw[4] == "-" and raw[7] == "-":
            return raw[:10]
    return ""


def _orders_in_period(model, date_from: str, date_to: str) -> list:
    rows = list(model.objects.filter(is_deleted=False).exclude(status__in=_CANCELLED_ORDER_STATUS))
    if not date_from and not date_to:
        return rows
    matched = []
    for row in rows:
        day = _order_effective_day(row)
        if not day:
            continue
        if date_from and day < date_from:
            continue
        if date_to and day > date_to:
            continue
        matched.append(row)
    return matched


def _sum_order_rows(rows: list) -> tuple[int, Decimal]:
    total = Decimal("0.00")
    for row in rows:
        total += Decimal(str(getattr(row, "amount", 0) or 0))
    return len(rows), total


def _daily_amounts_from_rows(rows: list) -> dict[str, float]:
    daily: dict[str, float] = {}
    for row in rows:
        day = _order_effective_day(row)
        if not day:
            continue
        daily[day] = daily.get(day, 0.0) + float(getattr(row, "amount", 0) or 0)
    return daily


def _invoice_effective_day(row) -> str:
    raw = str(getattr(row, "invoice_date", "") or "").strip()
    if len(raw) >= 10 and raw[4] == "-" and raw[7] == "-":
        return raw[:10]
    data = row.data if isinstance(getattr(row, "data", None), dict) else {}
    for key in ("invoiceDate", "date", "createdAt"):
        value = str(data.get(key) or "").strip()
        if len(value) >= 10 and value[4] == "-" and value[7] == "-":
            return value[:10]
    return _order_effective_day(row)


def _invoices_in_period(
    date_from: str,
    date_to: str,
    *,
    statuses: tuple[str, ...] | None = None,
) -> list:
    qs = InvoiceRecord.objects.filter(is_deleted=False).exclude(status="作废")
    if statuses:
        qs = qs.filter(status__in=statuses)
    rows = list(qs)
    if not date_from and not date_to:
        return rows
    matched = []
    for row in rows:
        day = _invoice_effective_day(row)
        if not day:
            continue
        if date_from and day < date_from:
            continue
        if date_to and day > date_to:
            continue
        matched.append(row)
    return matched


def _sales_overview(*, params: dict[str, Any], user_data: dict) -> dict[str, Any]:
    """经营概览：销售/采购订单金额 + 已确认发票 + 收款流水；仅显式 chart_type 时附带图表。"""
    del user_data
    period = str(params.get("relative_period") or "").strip()
    chart_type = resolve_chart_type(params)
    date_from, date_to = _resolve_tx_period(params)
    if not date_from and not date_to and period not in {"all", "全部", "累计", "all_time"}:
        # 「销售情况」默认本月；显式 all/累计则扫全部
        date_from, date_to = _resolve_tx_period({"relative_period": "this_month"})

    sales_rows = _orders_in_period(SalesOrderRecord, date_from, date_to)
    purchase_rows = _orders_in_period(PurchaseOrderRecord, date_from, date_to)
    service_rows = _orders_in_period(ServiceOrderRecord, date_from, date_to)
    # 「已经开完发票」按已确认口径
    invoice_rows = _invoices_in_period(date_from, date_to, statuses=(CONFIRMED_INVOICE_STATUS,))
    sales_count, sales_amount = _sum_order_rows(sales_rows)
    purchase_count, purchase_amount = _sum_order_rows(purchase_rows)
    service_count, service_amount = _sum_order_rows(service_rows)
    invoice_count, invoice_amount = _sum_order_rows(invoice_rows)
    order_total = sales_amount + service_amount

    # 收款：复用流水统计口径（嵌套调用不传 chart_type，避免多余图表）
    tx_result = _transaction_stats(
        params={
            "date_from": date_from,
            "date_to": date_to,
            "type": "",
        },
        user_data={},
    )
    tx_data = tx_result.get("data") if isinstance(tx_result.get("data"), dict) else {}
    service_rx = (tx_data.get("service_project") or {}).get("amount_sum") or "0.00"
    product_rx = (tx_data.get("product_project") or {}).get("amount_sum") or "0.00"
    receipt_total = Decimal(str(service_rx)) + Decimal(str(product_rx))

    period_label = f"{date_from} ~ {date_to}" if date_from and date_to else "全部时间"
    content = (
        f"{period_label} 经营概览："
        f"商品销售订单 {sales_amount:.2f} 元（{sales_count} 笔），"
        f"采购订单 {purchase_amount:.2f} 元（{purchase_count} 笔），"
        f"服务订单 {service_amount:.2f} 元（{service_count} 笔），"
        f"已确认发票 {invoice_amount:.2f} 元（{invoice_count} 张）；"
        f"收款/后返流水 {receipt_total:.2f} 元。"
    )
    items = [
        {"label": "时间范围", "value": period_label},
        {"label": "商品销售订单", "value": f"{sales_amount:.2f} 元（{sales_count} 笔）"},
        {"label": "采购订单", "value": f"{purchase_amount:.2f} 元（{purchase_count} 笔）"},
        {"label": "服务订单", "value": f"{service_amount:.2f} 元（{service_count} 笔）"},
        {"label": "销售+服务订单合计", "value": f"{order_total:.2f} 元"},
        {"label": "已确认发票（已开完）", "value": f"{invoice_amount:.2f} 元（{invoice_count} 张）"},
        {"label": "收款/后返流水", "value": f"{receipt_total:.2f} 元"},
        {"label": "服务项目收款", "value": f"{service_rx} 元"},
        {"label": "商品项目收款", "value": f"{product_rx} 元"},
    ]
    data: dict[str, Any] = {
        "title": "经营概览",
        "date_from": date_from or None,
        "date_to": date_to or None,
        "items": items,
        "sales_order": {"count": sales_count, "amount_sum": f"{sales_amount:.2f}"},
        "purchase_order": {"count": purchase_count, "amount_sum": f"{purchase_amount:.2f}"},
        "service_order": {"count": service_count, "amount_sum": f"{service_amount:.2f}"},
        "invoice_confirmed": {"count": invoice_count, "amount_sum": f"{invoice_amount:.2f}"},
        "receipt_total": f"{receipt_total:.2f}",
    }
    if chart_type:
        categories = ["商品销售订单", "采购订单", "服务订单", "已确认发票", "收款/后返"]
        values = [
            float(sales_amount),
            float(purchase_amount),
            float(service_amount),
            float(invoice_amount),
            float(receipt_total),
        ]
        charts: list[dict[str, Any]] = []
        if chart_type == "line":
            daily_sales = _daily_amounts_from_rows(sales_rows)
            daily_service = _daily_amounts_from_rows(service_rows)
            day_keys = sorted(set(daily_sales) | set(daily_service))
            daily_total = [
                round(float(daily_sales.get(day, 0) + daily_service.get(day, 0)), 2) for day in day_keys
            ]
            day_labels = [day[5:] if len(day) >= 10 else day for day in day_keys]
            if day_labels:
                charts.append(
                    {
                        "type": "line",
                        "title": "每日订单金额趋势",
                        "categories": day_labels,
                        "series": [{"name": "订单金额(元)", "data": daily_total}],
                    }
                )
            else:
                charts.append(
                    {
                        "type": "line",
                        "title": "订单 / 发票 / 收款对比",
                        "categories": categories,
                        "series": [{"name": "金额(元)", "data": values}],
                    }
                )
        elif chart_type == "pie":
            charts.append(
                {
                    "type": "pie",
                    "title": "订单 / 发票 / 收款对比",
                    "categories": categories,
                    "series": [{"name": "金额(元)", "data": values}],
                }
            )
        else:
            charts.append(
                {
                    "type": "bar",
                    "title": "订单 / 发票 / 收款对比",
                    "categories": categories,
                    "series": [{"name": "金额(元)", "data": values}],
                }
            )
        data["charts"] = charts
    return {
        "block_type": "statistics",
        "summary": content,
        "content": content,
        "data": data,
    }


def _resolve_invoice(*, invoice_id: str = "", invoice_no: str = "") -> InvoiceRecord | None:
    if invoice_id:
        found = InvoiceRecord.objects.filter(id=invoice_id, is_deleted=False).first()
        if found:
            return found
    number = (invoice_no or "").strip()
    if not number:
        return None
    exact = InvoiceRecord.objects.filter(is_deleted=False, invoice_no=number).first()
    if exact:
        return exact
    return InvoiceRecord.objects.filter(is_deleted=False, invoice_no__iexact=number).first()


def _invoice_delete(*, params: dict[str, Any], user_data: dict) -> dict[str, Any]:
    """软删除发票；已确认发票拒绝删除（与后台列表规则一致）。"""
    from apps.data_store.views import _soft_delete_queryset

    invoice_id = str(params.get("invoice_id") or "").strip()
    invoice_no = str(params.get("invoice_no") or "").strip()
    record = _resolve_invoice(invoice_id=invoice_id, invoice_no=invoice_no)
    if not record:
        return {
            "block_type": "error",
            "summary": "未找到发票",
            "content": f"未找到发票号「{invoice_no or invoice_id}」，请核对后重试。",
            "data": {"invoice_no": invoice_no, "invoice_id": invoice_id},
        }
    if (record.status or "") == CONFIRMED_INVOICE_STATUS:
        return {
            "block_type": "error",
            "summary": "已确认发票不可删除",
            "content": f"发票「{record.invoice_no or record.id}」状态为已确认，不可删除。",
            "data": {
                "invoice_id": record.id,
                "invoice_no": record.invoice_no,
                "status": record.status,
            },
        }

    deleted_by = str(user_data.get("name") or user_data.get("id") or "assistant")[:100]
    _soft_delete_queryset(InvoiceRecord.objects.filter(id=record.id), deleted_by)
    label = record.invoice_no or record.id
    return {
        "block_type": "tool_result",
        "summary": f"已删除发票 {label}",
        "content": f"已删除发票「{label}」。",
        "data": {
            "invoice_id": record.id,
            "invoice_no": record.invoice_no,
            "status": record.status,
            "deleted": True,
        },
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
            name="erp.invoice.delete",
            description="删除发票（需确认；已确认发票不可删）",
            input_schema={
                "type": "object",
                "properties": {
                    "invoice_no": {"type": "string"},
                    "invoice_id": {"type": "string"},
                },
                "required": ["invoice_no"],
            },
            permission="invoice.manage",
            risk_level="write",
            requires_confirmation=True,
            handler=_invoice_delete,
        )
    )
    register_tool(
        ToolDefinition(
            name="erp.sales_order.search",
            description="查询销售订单（可按客户名称）",
            input_schema={
                "type": "object",
                "properties": {
                    "keyword": {"type": "string"},
                    "customer": {"type": "string"},
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
    register_tool(
        ToolDefinition(
            name="erp.service_order.search",
            description="查询客户服务订单",
            input_schema={
                "type": "object",
                "properties": {
                    "keyword": {"type": "string"},
                    "customer": {"type": "string"},
                    "status": {"type": "string"},
                    "page": {"type": "integer"},
                    "page_size": {"type": "integer"},
                },
            },
            permission="serviceOrder.view",
            risk_level="read",
            handler=_service_order_search,
        )
    )
    register_tool(
        ToolDefinition(
            name="erp.transaction.stats",
            description="按服务项目/商品项目统计交易流水金额（收款/后返；默认仅数字，要图表才传 chart_type）",
            input_schema={
                "type": "object",
                "properties": {
                    "relative_period": {"type": "string"},
                    "date_from": {"type": "string"},
                    "date_to": {"type": "string"},
                    "project_type": {"type": "string", "description": "服务项目|商品项目|空=全部"},
                    "type": {"type": "string", "description": "流水类型，默认收款/后返"},
                    "chart_type": {
                        "type": "string",
                        "description": "仅用户明确要图表时传 bar|line|pie；默认不传",
                    },
                },
            },
            permission="finance.view",
            risk_level="read",
            handler=_transaction_stats,
        )
    )
    register_tool(
        ToolDefinition(
            name="erp.sales.overview",
            description="经营/销售概览：销售/采购/服务订单与已确认发票总金额、收款流水（默认仅数字；要图表才传 chart_type）。统计订单或发票总金额用此工具，勿用订单列表搜索",
            input_schema={
                "type": "object",
                "properties": {
                    "relative_period": {
                        "type": "string",
                        "description": "this_month|last_month|all|last_N_days；未指定时间的总金额用 all",
                    },
                    "date_from": {"type": "string"},
                    "date_to": {"type": "string"},
                    "chart_type": {
                        "type": "string",
                        "description": "仅用户明确要图表时传 bar|line|pie；默认不传",
                    },
                },
            },
            permission="salesOrder.view",
            risk_level="read",
            handler=_sales_overview,
        )
    )
    register_tool(
        ToolDefinition(
            name="erp.customer.expiry",
            description="查询客户/服务项目到期时间",
            input_schema={
                "type": "object",
                "properties": {
                    "customer": {"type": "string"},
                    "keyword": {"type": "string"},
                    "within_months": {"type": "integer"},
                    "within_days": {"type": "integer"},
                    "include_overdue": {"type": "boolean"},
                    "page": {"type": "integer"},
                    "page_size": {"type": "integer"},
                },
            },
            permission="project.view",
            risk_level="read",
            handler=_customer_expiry,
        )
    )
    register_tool(
        ToolDefinition(
            name="erp.project.status",
            description="按项目编号查询开票/付款/到期状态",
            input_schema={
                "type": "object",
                "properties": {
                    "project_no": {"type": "string"},
                    "keyword": {"type": "string"},
                },
            },
            permission="project.view",
            risk_level="read",
            handler=_project_status,
        )
    )
