from __future__ import annotations

import json
import re
from decimal import Decimal, InvalidOperation
from typing import Any, Dict, Optional  # noqa: F401

import requests
from sqlalchemy import delete, select
from tqdm import tqdm

from clients.jd_quan import is_jd_site
from config import settings
from db import NoticeGoods, NoticeParsed, NoticeRaw, dumps, get_session
from utils import now as now_shanghai
from utils import parse_dt

PARSE_SCHEMA_HINT = {
    "project_code": "项目编号/公告编号/订单号",
    "project_name": "项目名称",
    "notice_title": "公告标题",
    "buyer_name": "采购单位/采购人",
    "buyer_contact_name": "项目联系人姓名",
    "buyer_phone": "项目联系电话",
    "buyer_address": "采购人/项目地址",
    "buyer_contact": "兼容字段：联系人及电话合并串",
    "region_name": "区域",
    "budget_amount": "预算金额数字，无币种符号",
    "deal_amount": "成交金额数字",
    "deal_supplier": "成交供应商名称",
    "deal_supplier_phone": "成交供应商电话",
    "deal_supplier_address": "成交供应商地址",
    "quote_count": "报价供应商数量整数",
    "notice_kind": "竞价公告/询比公告/采购公告/成交公告/终止公告/废标公告/失败公告/公示公告",
    "procurement_mode": "普通竞价/反拍/询比/二次竞价/顺序轮候/直购/议价/批量采购等",
    "publish_time": "YYYY-MM-DD HH:MM:SS 或 null",
    "start_time": "竞价/报价开始时间 YYYY-MM-DD HH:MM:SS",
    "end_time": "截止时间 YYYY-MM-DD HH:MM:SS",
    "delivery_address": "交货地点",
    "goods": [
        {
            "name": "产品名称",
            "category": "分类",
            "quantity": "购买数量（数字）",
            "unit": "单位",
            "brand": "品牌",
            "model": "型号",
            "unit_price": "单价（数字）",
            "spec": "参数/规格",
            "amount": "金额小计（数字，可空）",
        }
    ],
    "quotes": [
        {
            "supplier_name": "供应商",
            "quote_amount": "报价金额",
            "rank": "名次",
            "is_winner": True,
            "phone": "电话",
            "address": "地址",
        }
    ],
    "suppliers": ["相关供应商名称"],
    "extra": {},
    "confidence": 0.0,
}

SYSTEM_PROMPT = """你是政府采购公告信息抽取助手。
只根据给定正文抽取字段，不要编造。
不确定的字段填 null 或空数组。
金额、单价、数量输出纯数字（可带小数），不要货币符号和千分位。
时间统一为 YYYY-MM-DD HH:MM:SS；若只有日期则 YYYY-MM-DD。
goods 必须是数组：有几条产品就输出几条，不要合并。
必须只输出一个 JSON 对象，不要 Markdown。
字段说明如下：
""" + json.dumps(PARSE_SCHEMA_HINT, ensure_ascii=False, indent=2)


def _to_decimal(v: Any) -> Optional[Decimal]:
    if v is None or v == "":
        return None
    try:
        s = str(v).replace(",", "").replace("¥", "").replace("元", "").strip()
        return Decimal(s)
    except (InvalidOperation, ValueError):
        return None


def _to_dt(v: Any):
    """兼容旧调用；统一走上海墙钟解析。"""
    return parse_dt(v)


def normalize_goods(goods: Any) -> list:
    """统一商品明细字段；兼容旧版 unit_price_limit / amount_limit。"""
    if not isinstance(goods, list):
        return []
    out = []
    for item in goods:
        if not isinstance(item, dict):
            continue
        unit_price = item.get("unit_price")
        if unit_price in (None, "") and item.get("unit_price_limit") not in (None, ""):
            unit_price = item.get("unit_price_limit")
        amount = item.get("amount")
        if amount in (None, "") and item.get("amount_limit") not in (None, ""):
            amount = item.get("amount_limit")
        row = {
            "name": item.get("name") or item.get("product_name"),
            "category": item.get("category") or item.get("catalog") or item.get("class_name"),
            "quantity": item.get("quantity"),
            "unit": item.get("unit"),
            "brand": item.get("brand"),
            "model": item.get("model"),
            "unit_price": unit_price,
            "spec": item.get("spec") or item.get("params") or item.get("parameter"),
            "amount": amount,
        }
        if any(v not in (None, "", []) for v in row.values()):
            out.append(row)
    return out


def call_llm(text: str, title: str = "") -> Dict[str, Any]:
    if not settings.llm_api_key:
        raise RuntimeError("未配置 LLM_API_KEY，无法解析")

    payload = {
        "model": settings.llm_model,
        "temperature": 0.1,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {
                "role": "user",
                "content": f"公告标题: {title}\n\n正文:\n{text[:28000]}",
            },
        ],
        "response_format": {"type": "json_object"},
    }
    resp = requests.post(
        settings.llm_base_url.rstrip("/") + "/chat/completions",
        headers={
            "Authorization": f"Bearer {settings.llm_api_key}",
            "Content-Type": "application/json",
        },
        json=payload,
        timeout=120,
    )
    resp.raise_for_status()
    content = resp.json()["choices"][0]["message"]["content"]
    content = content.strip()
    if content.startswith("```"):
        content = re.sub(r"^```(?:json)?\s*", "", content)
        content = re.sub(r"\s*```$", "", content)
    return json.loads(content)


def extract_fields(
    text: str,
    title: str = "",
    *,
    html: Optional[str] = None,
    site_id: Optional[str] = None,
    detail: Optional[dict] = None,
    list_item: Optional[dict] = None,
) -> Dict[str, Any]:
    """按站点/后端抽取。山东商城优先走 HTML 表格规则（new-bidding Clinch）。"""
    # 商城：有 HTML 时强制规则（秒级，对齐线上 Clinch）
    if site_id == "sd-ggzyjyzx" and html and html.strip():
        from pipeline.extractors.sd_mall_html import extract_sd_mall_html

        return extract_sd_mall_html(
            html,
            title=title,
            text=text,
            detail=detail,
            list_item=list_item,
        )
    # 京东：详情 JSON 结构化映射（对齐 xiaoyihuicai JdBusinessOpportunityService）
    if is_jd_site(site_id):
        from pipeline.extractors.jd_json import extract_jd_json

        return extract_jd_json(detail, list_item, title=title)

    backend = (settings.extractor_backend or "local_gguf").lower().strip()
    if backend in {"api", "openai", "llm", "remote"}:
        return call_llm(text, title=title)
    if backend in {"heuristic", "rule", "rules", "sd_mall"}:
        from pipeline.extractors.heuristic import HeuristicExtractor

        return HeuristicExtractor().extract(text, title=title)

    from pipeline.extractors import get_extractor

    return get_extractor(backend).extract(text, title=title)


def _raw_html_and_meta(raw: NoticeRaw) -> tuple[str, dict, dict]:
    detail = raw.detail_json if isinstance(raw.detail_json, dict) else {}
    list_item = raw.list_json if isinstance(raw.list_json, dict) else {}
    html = (raw.content_html or "").strip() or str(detail.get("content") or "").strip()
    return html, detail, list_item


def _jd_goods_from_detail(nested: dict) -> list:
    goods: list = []
    for group in nested.get("skuGroupList") or []:
        if not isinstance(group, dict):
            continue
        category = group.get("categoryName") or group.get("groupName")
        for sku in group.get("skuList") or []:
            if not isinstance(sku, dict):
                continue
            goods.append(
                {
                    "name": sku.get("skuName"),
                    "category": category,
                    "quantity": sku.get("skuNum") or sku.get("num"),
                    "unit": sku.get("unit") or None,
                    "brand": sku.get("brandName"),
                    "model": sku.get("skuModel") or sku.get("model"),
                    "unit_price": sku.get("sellPrice") or sku.get("price"),
                    "spec": None,
                    "amount": None,
                }
            )
    return goods


def _jd_deal_from_detail(nested: dict) -> Dict[str, Any]:
    deal = nested.get("auctionNoticeDealResult")
    if not isinstance(deal, dict):
        return {}
    suppliers = [s for s in (deal.get("supplierList") or []) if isinstance(s, dict)]
    if not suppliers:
        return {}
    # 反拍/竞价：成交价最低者优先；否则取第一条
    ranked = sorted(
        suppliers,
        key=lambda s: (
            s.get("dealPrice") is None,
            float(s.get("dealPrice") or 0),
        ),
    )
    winner = ranked[0]
    quotes = []
    for i, s in enumerate(ranked, start=1):
        quotes.append(
            {
                "supplier_name": s.get("supplierName"),
                "quote_amount": s.get("dealPrice"),
                "rank": i,
                "is_winner": i == 1,
                "phone": s.get("phone") or s.get("mobile"),
                "address": s.get("address"),
            }
        )
    return {
        "deal_supplier": winner.get("supplierName"),
        "deal_amount": winner.get("dealPrice"),
        "deal_supplier_phone": winner.get("phone") or winner.get("mobile"),
        "deal_supplier_address": winner.get("address"),
        "quote_count": len(suppliers),
        "quotes": quotes,
        "suppliers": [s.get("supplierName") for s in ranked if s.get("supplierName")],
    }


def enrich_from_raw(parsed: Dict[str, Any], raw: NoticeRaw) -> Dict[str, Any]:
    """用 notice_raw / detail_json / list_json 结构化字段补洞。"""
    detail = raw.detail_json if isinstance(raw.detail_json, dict) else None
    list_item = raw.list_json if isinstance(raw.list_json, dict) else None

    def _pick(*vals):
        for v in vals:
            if v not in (None, "", []):
                return v
        return None

    nested = (detail or {}).get("detail") if isinstance((detail or {}).get("detail"), dict) else {}
    jd_base = (
        nested.get("auctionNoticeBaseInfo")
        if isinstance(nested.get("auctionNoticeBaseInfo"), dict)
        else {}
    )

    if not parsed.get("notice_title"):
        parsed["notice_title"] = _pick(
            raw.title,
            (detail or {}).get("noticeTitle"),
            (detail or {}).get("auctionName"),
            (list_item or {}).get("noticeTitle"),
            (list_item or {}).get("title"),
            jd_base.get("auctionName"),
        )
    if not parsed.get("project_name"):
        parsed["project_name"] = _pick(
            (detail or {}).get("auctionName"),
            (list_item or {}).get("auctionName"),
            jd_base.get("auctionName"),
            parsed.get("notice_title"),
        )
    if not parsed.get("region_name"):
        parsed["region_name"] = _pick(
            raw.region_name,
            (detail or {}).get("regionFullName"),
            (detail or {}).get("regionName"),
            (list_item or {}).get("regionFullName"),
            (list_item or {}).get("regionName"),
        )
    if not parsed.get("publish_time"):
        parsed["publish_time"] = _pick(
            raw.publish_time,
            (detail or {}).get("publishTime"),
            (detail or {}).get("createDate"),
            (detail or {}).get("createTime"),
            (list_item or {}).get("publishTime"),
            (list_item or {}).get("createDate"),
            (list_item or {}).get("createTime"),
        )

    # 时间：启发式坏串可被结构化字段覆盖
    if not _to_dt(parsed.get("end_time")):
        picked = _pick(
            (detail or {}).get("endTime"),
            (detail or {}).get("closeTime"),
            (list_item or {}).get("endTime"),
            (list_item or {}).get("closeTime"),
            jd_base.get("endTime"),
            jd_base.get("closeTime"),
        )
        if picked is not None:
            parsed["end_time"] = picked
    if not _to_dt(parsed.get("start_time")):
        picked = _pick(
            (detail or {}).get("startTime"),
            (detail or {}).get("beginTime"),
            (list_item or {}).get("startTime"),
            (list_item or {}).get("beginTime"),
            jd_base.get("startTime"),
            jd_base.get("beginTime"),
        )
        if picked is not None:
            parsed["start_time"] = picked

    # 采购单位 / 预算
    if not parsed.get("buyer_name"):
        parsed["buyer_name"] = _pick(
            (detail or {}).get("buyerName"),
            (detail or {}).get("purchaseUnitName"),
            (detail or {}).get("purchaserName"),
            (list_item or {}).get("purchaseUnitName"),
            (list_item or {}).get("buyerName"),
            jd_base.get("purchaseUnitName"),
        )
    if parsed.get("budget_amount") in (None, "", []):
        picked = _pick(
            (list_item or {}).get("budgetAmount"),
            (detail or {}).get("budgetAmount"),
            (detail or {}).get("budgetPrice"),
            jd_base.get("budgetPrice"),
            (list_item or {}).get("budgetPrice"),
        )
        if picked is not None:
            parsed["budget_amount"] = picked

    # 项目编号
    if not parsed.get("project_code"):
        if raw.title:
            m = re.search(r"【((?:SDGP|SDKJXY|SCJJ|ECJJ)[\w\-]+)】", raw.title)
            if m:
                parsed["project_code"] = m.group(1)
        if not parsed.get("project_code"):
            parsed["project_code"] = _pick(
                (list_item or {}).get("projectCode"),
                (detail or {}).get("noticeCode"),
                (list_item or {}).get("noticeCode"),
                (detail or {}).get("auctionNo"),
                (list_item or {}).get("auctionNo"),
                jd_base.get("auctionNo"),
                (list_item or {}).get("noticeGuid"),
                raw.notice_key,
            )

    # 公告种类：有站点 noticeType 映射时强制对齐（纠正正文套话误判）
    nt = str(
        (detail or {}).get("noticeType")
        or (list_item or {}).get("noticeType")
        or raw.notice_type
        or ""
    )
    if is_jd_site(raw.site_id):
        jd_kind = {
            "1": "竞价公告",
            "2": "成交公告",
            "3": "终止公告",
            "4": "失败公告",
            "5": "询比公告",
            "6": "废标公告",
        }
        if nt in jd_kind:
            parsed["notice_kind"] = jd_kind[nt]
    elif raw.site_id == "sd-ggzyjyzx":
        sd_kind = {
            "0": "采购公告",
            "1": "成交公告",
            "5": "终止公告",
            "10": "终止公告",
            "13": "公示公告",
        }
        if nt in sd_kind:
            parsed["notice_kind"] = sd_kind[nt]
    elif raw.site_id == "sd-gpfa-frame":
        gpfa_kind = {"0": "采购公告", "1": "成交公告", "10": "终止公告"}
        if nt in gpfa_kind:
            parsed["notice_kind"] = gpfa_kind[nt]
    else:
        kind = str(parsed.get("notice_kind") or "").strip()
        if not kind or kind.isdigit():
            title = (raw.title or "") + " " + (parsed.get("notice_title") or "")
            for token, label in (
                ("废标公告", "废标公告"),
                ("终止公告", "终止公告"),
                ("成交结果", "成交结果公告"),
                ("成交公告", "成交公告"),
                ("失败公告", "失败公告"),
                ("采购公告", "采购公告"),
            ):
                if token in title:
                    parsed["notice_kind"] = label
                    break

    # 采购方式
    if not parsed.get("procurement_mode"):
        if is_jd_site(raw.site_id):
            parsed["procurement_mode"] = _pick(
                (list_item or {}).get("procurementName"),
                {
                    "1": "普通竞价",
                    "2": "反拍",
                    "3": "询比",
                }.get(
                    str(
                        (detail or {}).get("auctionType")
                        or (list_item or {}).get("auctionType")
                        or raw.auction_type
                        or ""
                    )
                ),
            )
        elif raw.site_id == "sd-gpfa-frame":
            title = raw.title or ""
            if "顺序轮候" in title:
                parsed["procurement_mode"] = "顺序轮候"
            elif "二次竞价" in title or "二次竞价" in (raw.content_text or ""):
                parsed["procurement_mode"] = "二次竞价"
            else:
                parsed["procurement_mode"] = "框架协议"
        elif raw.site_id == "sd-ggzyjyzx":
            title = (raw.title or "") + " " + (parsed.get("notice_title") or "")
            for token, label in (
                ("反拍", "反拍"),
                ("竞价", "竞价"),
                ("直购", "直购"),
                ("议价", "议价"),
            ):
                if token in title:
                    parsed["procurement_mode"] = label
                    break

    # 京东成交 / 商品
    if is_jd_site(raw.site_id) and nested:
        deal_info = _jd_deal_from_detail(nested)
        for k, v in deal_info.items():
            if k in {"quotes", "suppliers"}:
                if not parsed.get(k):
                    parsed[k] = v
            elif parsed.get(k) in (None, "", []):
                parsed[k] = v
        if not parsed.get("goods"):
            goods = _jd_goods_from_detail(nested)
            if goods:
                parsed["goods"] = goods

    if not isinstance(parsed.get("extra"), dict):
        parsed["extra"] = {}
    parsed["extra"]["enriched_from_raw"] = True
    return parsed


def parsed_row_to_dict(row: NoticeParsed, goods_rows: Optional[list] = None) -> Dict[str, Any]:
    """把已有 notice_parsed（+商品行）还原成可再 enrich/save 的 dict。"""
    raw_json = row.model_raw_json if isinstance(row.model_raw_json, dict) else {}
    goods = []
    if goods_rows:
        for g in goods_rows:
            goods.append(
                {
                    "name": g.product_name,
                    "category": g.category,
                    "quantity": g.quantity,
                    "unit": g.unit,
                    "brand": g.brand,
                    "model": g.model,
                    "unit_price": g.unit_price,
                    "spec": g.spec,
                    "amount": g.amount,
                }
            )
    elif isinstance(raw_json.get("goods"), list):
        goods = raw_json["goods"]
    return {
        "project_code": row.project_code,
        "project_name": row.project_name,
        "notice_title": row.notice_title,
        "buyer_name": row.buyer_name,
        "buyer_contact_name": row.buyer_contact_name,
        "buyer_phone": row.buyer_phone,
        "buyer_address": row.buyer_address,
        "buyer_contact": row.buyer_contact,
        "region_name": row.region_name,
        "budget_amount": row.budget_amount,
        "deal_amount": row.deal_amount,
        "deal_supplier": row.deal_supplier,
        "deal_supplier_phone": row.deal_supplier_phone,
        "deal_supplier_address": row.deal_supplier_address,
        "quote_count": row.quote_count,
        "notice_kind": row.notice_kind,
        "procurement_mode": row.procurement_mode,
        "publish_time": row.publish_time,
        "start_time": row.start_time,
        "end_time": row.end_time,
        "delivery_address": row.delivery_address,
        "goods": goods,
        "quotes": row.quotes_json if isinstance(row.quotes_json, list) else (raw_json.get("quotes") or []),
        "suppliers": row.suppliers_json
        if isinstance(row.suppliers_json, list)
        else (raw_json.get("suppliers") or []),
        "extra": row.extra_json if isinstance(row.extra_json, dict) else {},
        "confidence": row.confidence,
    }


def reenrich_parsed(*, limit: int = 500, site_id: Optional[str] = None) -> int:
    """不跑模型：用 list/detail JSON 把已解析但缺字段的公告补全。"""
    session = get_session()
    ok = 0
    try:
        stmt = select(NoticeRaw).where(NoticeRaw.crawl_status == "detail_ok")
        if site_id:
            stmt = stmt.where(NoticeRaw.site_id == site_id)
        stmt = stmt.order_by(NoticeRaw.id.asc()).limit(limit)
        rows = session.execute(stmt).scalars().all()
        for raw in tqdm(rows, desc="enrich"):
            parsed_row = session.execute(
                select(NoticeParsed).where(NoticeParsed.notice_raw_id == raw.id)
            ).scalar_one_or_none()
            goods_rows = list(
                session.execute(
                    select(NoticeGoods).where(NoticeGoods.notice_raw_id == raw.id)
                ).scalars().all()
            )
            if parsed_row:
                parsed = parsed_row_to_dict(parsed_row, goods_rows)
            else:
                parsed = {
                    "notice_title": raw.title,
                    "goods": [],
                    "quotes": [],
                    "suppliers": [],
                    "extra": {},
                    "confidence": 0.0,
                }
            before = (
                parsed.get("end_time"),
                parsed.get("budget_amount"),
                parsed.get("buyer_name"),
                parsed.get("deal_supplier"),
                len(parsed.get("goods") or []),
                parsed.get("notice_kind"),
            )
            parsed = enrich_from_raw(parsed, raw)
            after = (
                parsed.get("end_time"),
                parsed.get("budget_amount"),
                parsed.get("buyer_name"),
                parsed.get("deal_supplier"),
                len(parsed.get("goods") or []),
                parsed.get("notice_kind"),
            )
            save_parsed(session, raw, parsed)
            if before != after or parsed_row is None:
                ok += 1
            session.commit()
    finally:
        session.close()
    return ok


def save_parsed(session, raw: NoticeRaw, parsed: Dict[str, Any]) -> NoticeParsed:
    row = session.execute(
        select(NoticeParsed).where(NoticeParsed.notice_raw_id == raw.id)
    ).scalar_one_or_none()
    if row is None:
        row = NoticeParsed(notice_raw_id=raw.id, site_id=raw.site_id, notice_key=raw.notice_key)
        session.add(row)

    buyer_name = parsed.get("buyer_contact_name")
    buyer_phone = parsed.get("buyer_phone")
    buyer_address = parsed.get("buyer_address")
    buyer_contact = parsed.get("buyer_contact")
    if not buyer_contact and (buyer_name or buyer_phone):
        buyer_contact = " ".join(x for x in (buyer_name, buyer_phone) if x)

    goods = normalize_goods(parsed.get("goods") or [])

    row.project_code = (parsed.get("project_code") or None)
    row.project_name = parsed.get("project_name")
    row.notice_title = parsed.get("notice_title") or raw.title
    row.buyer_name = parsed.get("buyer_name")
    row.buyer_contact_name = buyer_name
    row.buyer_phone = buyer_phone
    row.buyer_address = buyer_address
    row.buyer_contact = buyer_contact
    row.region_name = parsed.get("region_name") or raw.region_name
    row.budget_amount = _to_decimal(parsed.get("budget_amount"))
    row.deal_amount = _to_decimal(parsed.get("deal_amount"))
    row.deal_supplier = parsed.get("deal_supplier")
    row.deal_supplier_phone = parsed.get("deal_supplier_phone")
    row.deal_supplier_address = parsed.get("deal_supplier_address")
    row.quote_count = parsed.get("quote_count")
    row.notice_kind = parsed.get("notice_kind")
    row.procurement_mode = parsed.get("procurement_mode")
    row.publish_time = _to_dt(parsed.get("publish_time")) or raw.publish_time
    row.start_time = _to_dt(parsed.get("start_time"))
    row.end_time = _to_dt(parsed.get("end_time"))
    row.delivery_address = parsed.get("delivery_address")
    row.quotes_json = dumps(parsed.get("quotes") or [])
    row.suppliers_json = dumps(parsed.get("suppliers") or [])
    row.extra_json = dumps(parsed.get("extra") or {})
    backend = (settings.extractor_backend or "").strip()
    extra = parsed.get("extra") if isinstance(parsed.get("extra"), dict) else {}
    if extra.get("extractor"):
        row.model_name = str(extra["extractor"])[:128]
    elif backend in {"api", "openai", "llm", "remote"}:
        row.model_name = settings.llm_model
    else:
        row.model_name = backend or settings.local_model_path
    row.model_raw_json = dumps(parsed)
    conf = parsed.get("confidence")
    try:
        row.confidence = Decimal(str(conf)) if conf is not None else None
    except (InvalidOperation, ValueError):
        row.confidence = None
    row.parsed_at = now_shanghai()
    raw.parse_status = "parsed"
    session.flush()
    replace_goods(session, raw=raw, parsed_row=row, goods=goods)
    return row


def replace_goods(
    session,
    *,
    raw: NoticeRaw,
    parsed_row: NoticeParsed,
    goods: list,
) -> None:
    """按公告重写产品明细行。"""
    session.execute(delete(NoticeGoods).where(NoticeGoods.notice_raw_id == raw.id))
    for i, item in enumerate(goods, start=1):
        session.add(
            NoticeGoods(
                notice_raw_id=raw.id,
                notice_parsed_id=parsed_row.id,
                site_id=raw.site_id,
                notice_key=raw.notice_key,
                line_no=i,
                product_name=_clip(item.get("name"), 512),
                category=_clip(item.get("category"), 256),
                quantity=_to_decimal(item.get("quantity")),
                unit=_clip(item.get("unit"), 64),
                brand=_clip(item.get("brand"), 128),
                model=_clip(item.get("model"), 256),
                unit_price=_to_decimal(item.get("unit_price")),
                spec=_clip(item.get("spec"), 2000),
                amount=_to_decimal(item.get("amount")),
            )
        )


def _clip(v: Any, n: int) -> Optional[str]:
    if v is None or v == "":
        return None
    return str(v).strip()[:n] or None


def parse_pending(
    *,
    limit: int = 100,
    site_id: Optional[str] = None,
    force: bool = False,
) -> int:
    """按 .env 的 EXTRACTOR_BACKEND（默认 local_gguf）解析公告。

    force=False：只处理 pending / parse_fail
    force=True：已解析的也会用本地模型重抽并覆盖（版式不固定时用这个）
    """
    session = get_session()
    ok = 0
    try:
        stmt = select(NoticeRaw).where(NoticeRaw.crawl_status == "detail_ok")
        if not force:
            stmt = stmt.where(NoticeRaw.parse_status.in_(["pending", "parse_fail"]))
        if site_id:
            stmt = stmt.where(NoticeRaw.site_id == site_id)
        stmt = stmt.order_by(NoticeRaw.id.asc()).limit(limit)
        rows = session.execute(stmt).scalars().all()
        for raw in tqdm(rows, desc="parse"):
            html, detail, list_item = _raw_html_and_meta(raw)
            text = raw.content_text or html_fallback(raw)
            # 商城：即使 content_text 短，只要 detail 里有 HTML 也能规则抽
            if (not text or len(text.strip()) < 20) and not html:
                if is_jd_site(raw.site_id):
                    continue
                raw.parse_status = "skipped"
                session.commit()
                continue
            try:
                parsed = extract_fields(
                    text or "",
                    title=raw.title or "",
                    html=html,
                    site_id=raw.site_id,
                    detail=detail,
                    list_item=list_item,
                )
                parsed = enrich_from_raw(parsed, raw)
                save_parsed(session, raw, parsed)
                ok += 1
                session.commit()
            except Exception as exc:  # noqa: BLE001
                raw.parse_status = "parse_fail"
                raw.error_message = str(exc)[:1000]
                session.commit()
    finally:
        session.close()
    return ok


def _merge_parsed(base: Dict[str, Any], fresh: Dict[str, Any]) -> Dict[str, Any]:
    """用新抽取结果补空字段；商品/报价在原为空时整表替换。"""
    out = dict(base or {})
    for k, v in (fresh or {}).items():
        if k == "extra":
            extra = out.get("extra") if isinstance(out.get("extra"), dict) else {}
            if isinstance(v, dict):
                extra = {**extra, **v}
            out["extra"] = extra
            continue
        if k in {"goods", "quotes", "suppliers"}:
            if not out.get(k) and v:
                out[k] = v
            continue
        if out.get(k) in (None, "", []) and v not in (None, "", []):
            out[k] = v
    return out


def reparse_existing(
    *,
    limit: int = 200,
    site_id: Optional[str] = None,
    force: bool = False,
    backend: Optional[str] = None,
) -> int:
    """对已抓取公告重新抽取。

    backend=None 时跟 .env 的 EXTRACTOR_BACKEND（本地模型）；
    显式传 heuristic 才走纯规则。
    """
    from pipeline.extractors import get_extractor

    session = get_session()
    ok = 0
    # None / 空 → extract_fields（读 .env）；指定则用对应后端
    use_env = not (backend or "").strip()
    extractor = None if use_env else get_extractor(backend)
    try:
        stmt = select(NoticeRaw).where(NoticeRaw.crawl_status == "detail_ok")
        if site_id:
            stmt = stmt.where(NoticeRaw.site_id == site_id)
        stmt = stmt.order_by(NoticeRaw.id.asc()).limit(limit)
        rows = session.execute(stmt).scalars().all()
        for raw in tqdm(rows, desc="reparse"):
            html, detail, list_item = _raw_html_and_meta(raw)
            text = raw.content_text or html_fallback(raw)
            if (not text or len(text.strip()) < 20) and not html:
                continue
            try:
                if extractor is not None and not (
                    raw.site_id == "sd-ggzyjyzx" and html and not (backend or "").strip()
                ):
                    fresh = extractor.extract(text or "", title=raw.title or "")
                else:
                    fresh = extract_fields(
                        text or "",
                        title=raw.title or "",
                        html=html,
                        site_id=raw.site_id,
                        detail=detail,
                        list_item=list_item,
                    )
                parsed_row = session.execute(
                    select(NoticeParsed).where(NoticeParsed.notice_raw_id == raw.id)
                ).scalar_one_or_none()
                goods_rows = list(
                    session.execute(
                        select(NoticeGoods).where(NoticeGoods.notice_raw_id == raw.id)
                    ).scalars().all()
                )
                if force or parsed_row is None:
                    parsed = enrich_from_raw(fresh, raw)
                else:
                    base = parsed_row_to_dict(parsed_row, goods_rows)
                    parsed = enrich_from_raw(_merge_parsed(base, fresh), raw)
                before_deal = (parsed_row.deal_supplier if parsed_row else None, len(goods_rows))
                save_parsed(session, raw, parsed)
                session.commit()
                after_goods = session.execute(
                    select(NoticeGoods).where(NoticeGoods.notice_raw_id == raw.id)
                ).scalars().all()
                after_deal = (
                    session.execute(
                        select(NoticeParsed).where(NoticeParsed.notice_raw_id == raw.id)
                    ).scalar_one().deal_supplier
                )
                if force or before_deal != (after_deal, len(after_goods)) or parsed_row is None:
                    ok += 1
            except Exception as exc:  # noqa: BLE001
                raw.error_message = str(exc)[:1000]
                session.commit()
    finally:
        session.close()
    return ok


def html_fallback(raw: NoticeRaw) -> str:
    from utils import html_to_text

    if raw.content_html:
        return html_to_text(raw.content_html)
    if raw.detail_json:
        return json.dumps(raw.detail_json, ensure_ascii=False)
    return ""
