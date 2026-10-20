"""京东泉易采 / 青慧采结构化解析（对齐 xiaoyihuicai JdBusinessOpportunityService）。

字段来自详情 JSON，不走模型：
- auctionNoticeBaseInfo：预算、起止时间、采购单位
- skuGroupList：商品
- auctionNoticeDealResult / auctionNoticeDealDetailList：成交供应商与成交价
- auctionAddressGoodsList：询比收货地址与商品
"""

from __future__ import annotations

import copy
from typing import Any, Dict, List, Optional

from pipeline.extractors.base import EXTRACT_SCHEMA

# 与京东公告页 tab 一致（竞价页叫「竞价公告」，询比页叫「询比公告」）
NOTICE_KIND = {
    1: "竞价公告",
    2: "成交公告",
    3: "终止公告",
    4: "失败公告",
    5: "询比公告",
    6: "废标公告",
}
PROCUREMENT_MODE = {
    1: "普通竞价",
    2: "反拍",
    3: "询比",
}


def _num(value: Any) -> Optional[float]:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _ms(value: Any) -> Optional[int]:
    """毫秒时间戳原样返回，交给 _to_dt。"""
    if value in (None, ""):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _goods_from_groups(groups: list) -> List[Dict[str, Any]]:
    goods: List[Dict[str, Any]] = []
    for group in groups or []:
        if not isinstance(group, dict):
            continue
        category = group.get("categoryName") or group.get("groupName")
        for sku in group.get("skuList") or []:
            if not isinstance(sku, dict):
                continue
            goods.append(
                {
                    "name": sku.get("skuName"),
                    "category": sku.get("categoryName") or sku.get("threeCategoryName") or category,
                    "quantity": _num(sku.get("skuNum")),
                    "unit": sku.get("unit") or None,
                    "brand": sku.get("brandName"),
                    "model": sku.get("skuModel"),
                    "unit_price": _num(sku.get("sellPrice")),
                    "spec": None,
                    "amount": None,
                    "_sku_id": sku.get("skuId"),
                }
            )
    return goods


def _apply_deal_details(goods: List[Dict[str, Any]], deal_details: list) -> None:
    """成交公告：按 skuId 回写成交单价/金额/品牌型号。"""
    by_id = {}
    for item in deal_details or []:
        if isinstance(item, dict) and item.get("skuId") is not None:
            by_id[item.get("skuId")] = item
    for g in goods:
        detail = by_id.get(g.get("_sku_id"))
        if not detail:
            continue
        if detail.get("brandName"):
            g["brand"] = detail.get("brandName")
        if detail.get("respModel"):
            g["model"] = detail.get("respModel")
        unit = _num(detail.get("dealUnitPrice"))
        total = _num(detail.get("dealTotalPrice"))
        qty = _num(detail.get("dealNum"))
        if unit is not None:
            g["unit_price"] = unit
        if qty is not None:
            g["quantity"] = qty
        if total is not None:
            g["amount"] = total
        elif unit is not None and g.get("quantity"):
            g["amount"] = round(unit * float(g["quantity"]), 2)


def extract_jd_json(
    detail: Optional[dict] = None,
    list_item: Optional[dict] = None,
    *,
    title: str = "",
) -> Dict[str, Any]:
    detail = detail if isinstance(detail, dict) else {}
    list_item = list_item if isinstance(list_item, dict) else {}
    nested = detail.get("detail") if isinstance(detail.get("detail"), dict) else {}
    base = nested.get("auctionNoticeBaseInfo") if isinstance(nested.get("auctionNoticeBaseInfo"), dict) else {}
    demand = nested.get("auctionDemandInfo") if isinstance(nested.get("auctionDemandInfo"), dict) else {}
    survey = nested.get("surveyRequirement") if isinstance(nested.get("surveyRequirement"), dict) else {}
    deal = nested.get("auctionNoticeDealResult") if isinstance(nested.get("auctionNoticeDealResult"), dict) else {}

    out = copy.deepcopy(EXTRACT_SCHEMA)
    out["goods"] = []
    out["quotes"] = []
    out["suppliers"] = []
    out["extra"] = {"extractor": "jd_json"}

    notice_type = detail.get("noticeType")
    if notice_type is None:
        notice_type = list_item.get("noticeType")
    auction_type = detail.get("auctionType")
    if auction_type is None:
        auction_type = list_item.get("auctionType") or base.get("auctionType")
    try:
        notice_type_i = int(notice_type) if notice_type not in (None, "") else None
    except (TypeError, ValueError):
        notice_type_i = None
    try:
        auction_type_i = int(auction_type) if auction_type not in (None, "") else None
    except (TypeError, ValueError):
        auction_type_i = None

    out["notice_title"] = (
        title
        or detail.get("noticeTitle")
        or list_item.get("noticeTitle")
        or base.get("auctionName")
        or list_item.get("auctionName")
    )
    out["project_name"] = (
        detail.get("auctionName")
        or list_item.get("auctionName")
        or base.get("auctionName")
        or out["notice_title"]
    )
    out["project_code"] = (
        detail.get("noticeCode")
        or list_item.get("noticeCode")
        or detail.get("auctionNo")
        or list_item.get("auctionNo")
        or base.get("auctionNo")
    )
    out["buyer_name"] = (
        base.get("purchaseUnitName")
        or detail.get("purchaseUnitName")
        or list_item.get("purchaseUnitName")
    )
    out["budget_amount"] = _num(
        base.get("budgetPrice") or detail.get("budgetPrice") or list_item.get("budgetPrice")
    )
    out["start_time"] = _ms(base.get("startTime") or detail.get("startTime") or list_item.get("startTime"))
    out["end_time"] = _ms(base.get("endTime") or detail.get("endTime") or list_item.get("endTime"))
    out["publish_time"] = _ms(
        detail.get("createTime") or list_item.get("createTime") or detail.get("publishTime")
    )
    if notice_type_i in NOTICE_KIND:
        out["notice_kind"] = NOTICE_KIND[notice_type_i]
    mode = list_item.get("procurementName")
    if auction_type_i in PROCUREMENT_MODE:
        out["procurement_mode"] = PROCUREMENT_MODE[auction_type_i]
    elif mode:
        out["procurement_mode"] = mode

    if survey:
        out["buyer_contact_name"] = survey.get("contactsName")
        out["buyer_phone"] = survey.get("contactTel")
        out["delivery_address"] = survey.get("scoutAddr")
        if out["buyer_contact_name"] or out["buyer_phone"]:
            out["buyer_contact"] = " ".join(
                x for x in (out["buyer_contact_name"], out["buyer_phone"]) if x
            )

    goods = _goods_from_groups(nested.get("skuGroupList") or [])
    _apply_deal_details(goods, nested.get("auctionNoticeDealDetailList") or [])

    # 询比：商品可能在收货地址下
    addresses = nested.get("auctionAddressGoodsList") or []
    if isinstance(addresses, list) and addresses:
        first = addresses[0] if isinstance(addresses[0], dict) else {}
        addr = first.get("detailAddress") or first.get("address")
        if addr and not out.get("delivery_address"):
            parts = [
                first.get("provinceName"),
                first.get("cityName"),
                first.get("countyName"),
                addr,
            ]
            out["delivery_address"] = "".join(p for p in parts if p)
        if first.get("receiverName") and not out.get("buyer_contact_name"):
            out["buyer_contact_name"] = first.get("receiverName")
        if first.get("mobile") and not out.get("buyer_phone"):
            out["buyer_phone"] = first.get("mobile")
        if not goods:
            for block in addresses:
                if not isinstance(block, dict):
                    continue
                goods.extend(_goods_from_groups([{"skuList": block.get("addressGoodsList") or []}]))

    for g in goods:
        g.pop("_sku_id", None)
        if g.get("amount") is None and g.get("unit_price") is not None and g.get("quantity"):
            g["amount"] = round(float(g["unit_price"]) * float(g["quantity"]), 2)
    out["goods"] = goods

    suppliers = [s for s in (deal.get("supplierList") or []) if isinstance(s, dict)]
    deal_details = [d for d in (nested.get("auctionNoticeDealDetailList") or []) if isinstance(d, dict)]
    winner_name = next((d.get("supplierName") for d in deal_details if d.get("supplierName")), None)
    if suppliers:
        quotes = []
        names = []
        for i, s in enumerate(suppliers, start=1):
            name = s.get("supplierName")
            if name:
                names.append(name)
            quotes.append(
                {
                    "supplier_name": name,
                    "quote_amount": _num(s.get("dealPrice")),
                    "rank": i,
                    "is_winner": name == winner_name if winner_name else i == 1,
                    "phone": None,
                    "address": None,
                }
            )
        out["quotes"] = quotes
        out["suppliers"] = names
        out["quote_count"] = _num(deal.get("supplierTotalNum")) or len(suppliers)
        out["deal_supplier"] = winner_name or suppliers[0].get("supplierName")
        out["deal_amount"] = _num(deal.get("dealTotalPrice")) or _num(suppliers[0].get("dealPrice"))
    elif winner_name:
        out["deal_supplier"] = winner_name
        out["deal_amount"] = _num(deal_details[0].get("dealTotalPrice"))

    if demand.get("demandRemark"):
        out["extra"]["demand_remark"] = demand.get("demandRemark")

    filled = sum(
        1
        for k in ("project_code", "buyer_name", "budget_amount", "deal_supplier", "end_time")
        if out.get(k) not in (None, "", [])
    )
    out["confidence"] = 0.9 if filled >= 3 or out["goods"] else 0.7
    return out
