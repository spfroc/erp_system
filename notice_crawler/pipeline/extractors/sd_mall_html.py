"""山东网上商城 HTML 规则抽取（移植自 new-bidding/Clinch.py）。

核心：详情 content 里的 <p>/<h2> + .contractTable，不是纯文本正则。
"""

from __future__ import annotations

import copy
import re
from typing import Any, Dict, List, Optional

from bs4 import BeautifulSoup

from pipeline.extractors.base import EXTRACT_SCHEMA


def _remove_all_letters(text: str) -> str:
    """去掉中文标签，留下项目编号等。"""
    return (
        re.sub(r"[\u4e00-\u9fa5]", "", text or "")
        .replace("：", "")
        .replace("、", "")
        .replace("（）", "")
        .replace(":", "")
    )


def _remove_ignore_character(text: str) -> str:
    """去掉段落前缀标签（对齐 new-bidding/Common.remove_ignore_character）。"""
    text = text or ""
    if text:
        text = text.replace(text[0], re.sub(r"[一二三四五六七八九十]+", "", text[0]), 1)
    for token in (
        "电话：",
        "：",
        "采购单位",
        "、",
        "供应商地址",
        "成交金额",
        "联系人",
        "联系方式",
        "项目名称",
        "预算金额",
        "采购计划编号",
        "（二）",
        " ",
        "成交供应商",
        "供应商名称",
        "供应商：",
        "供应商",
        "（一）",
        "（三）",
        "（）",
        "项目:",
        "采购人名称:",
        "名称:",
        "成交:",
        "采购人地址:",
        "采购人:",
    ):
        text = text.replace(token, "")
    return text.strip()


def _money(value: Any) -> Optional[float]:
    if value is None or value == "":
        return None
    s = str(value).replace("￥", "").replace("¥", "").replace(",", "").replace("，", "")
    s = re.sub(r"[^\d.]", "", s)
    if not s:
        return None
    try:
        return float(s)
    except ValueError:
        return None


def _qty(value: Any) -> Optional[float]:
    if value is None or value == "":
        return None
    s = str(value).replace(",", "").strip()
    try:
        return float(s)
    except ValueError:
        return None


def _cell_money(td_text: str) -> Optional[float]:
    return _money((td_text or "").replace("\n", "").replace(" ", ""))


def _parse_contract_tables(soup: BeautifulSoup) -> tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """解析 .contractTable → (商品列表, 报价名单)。"""
    goods: List[Dict[str, Any]] = []
    quotes: List[Dict[str, Any]] = []
    for table in soup.select(".contractTable"):
        rows = table.find_all("tr", recursive=False) or table.find_all("tr")
        if not rows:
            continue
        headers = [th.get_text(strip=True) for th in rows[0].find_all("th")]
        if not headers:
            # 有的表头也在 td
            headers = [td.get_text(strip=True) for td in rows[0].find_all("td")]
        for tr in rows[1:]:
            tds = tr.find_all("td")
            if not tds or len(headers) != len(tds):
                continue
            product: Dict[str, Any] = {}
            for i, td in enumerate(tds):
                title = headers[i]
                cell = td.get_text("\n", strip=True)
                if "商品品目" in title:
                    product["category"] = cell
                elif "供应商名称" in title:
                    product["supplier_name"] = cell
                elif "名称" in title:
                    product["name"] = cell
                elif "品牌" in title:
                    product["brand"] = cell
                elif "型号" in title:
                    product["model"] = cell
                elif "技术指标" in title or "参数" in title:
                    product["params"] = cell
                elif "数量" in title:
                    product["number"] = cell.replace(",", "")
                elif "供应商报价" in title or "报价金额" in title:
                    product["total_price"] = _cell_money(cell)
                elif "单价" in title:
                    product["price"] = _cell_money(cell)
                elif "费用小计" in title:
                    product["total_price"] = _cell_money(cell)
                    product["price"] = product.get("price") or product["total_price"]
                elif "小计" in title or ("金额" in title and "报价" not in title):
                    product["total_price"] = _cell_money(cell)
                elif "是否中标" in title:
                    product["successful"] = cell.replace("\n", "").replace(" ", "")
                elif "报价时间" in title:
                    product["quote_time"] = cell
                elif "供应商" in title:
                    product["supplier_name"] = cell
                elif "排名" in title:
                    product["rank"] = cell

            if not product:
                continue

            # 有报价时间 → 报价名单；否则当商品
            if product.get("quote_time") or (
                product.get("supplier_name") and product.get("total_price") is not None and not product.get("name")
            ):
                amount = product.get("total_price") or product.get("price")
                rank_raw = product.get("rank")
                try:
                    rank = int(str(rank_raw)) if rank_raw not in (None, "") else None
                except ValueError:
                    rank = None
                quotes.append(
                    {
                        "supplier_name": product.get("supplier_name") or product.get("name"),
                        "quote_amount": amount,
                        "rank": rank,
                        "is_winner": rank == 1 if rank is not None else False,
                        "phone": None,
                        "address": None,
                    }
                )
                continue

            if product.get("successful") and "是" not in str(product.get("successful")):
                # 定点服务表里未中标行不当商品
                if product.get("supplier_name"):
                    quotes.append(
                        {
                            "supplier_name": product.get("supplier_name"),
                            "quote_amount": product.get("total_price") or product.get("price"),
                            "rank": None,
                            "is_winner": False,
                            "phone": None,
                            "address": None,
                        }
                    )
                continue

            qty = _qty(product.get("number"))
            price = product.get("price")
            amount = product.get("total_price")
            if price is not None and amount is None and qty is not None:
                amount = round(float(price) * float(qty), 2)
            goods.append(
                {
                    "name": (product.get("name") or "").strip()[:512] or None,
                    "category": (product.get("category") or None),
                    "quantity": qty,
                    "unit": None,
                    "brand": (product.get("brand") or None),
                    "model": (product.get("model") or None),
                    "unit_price": price,
                    "spec": (product.get("params") or None),
                    "amount": amount,
                }
            )
    return goods, quotes


def extract_sd_mall_html(
    html: str,
    *,
    title: str = "",
    text: str = "",
    detail: Optional[dict] = None,
    list_item: Optional[dict] = None,
) -> Dict[str, Any]:
    """从商城详情 HTML 抽取字段（对齐 new-bidding Clinch 规则）。"""
    out = copy.deepcopy(EXTRACT_SCHEMA)
    out["goods"] = []
    out["quotes"] = []
    out["suppliers"] = []
    out["notice_title"] = title or None
    out["extra"] = {"extractor": "sd_mall_html"}

    detail = detail or {}
    list_item = list_item or {}
    soup = BeautifulSoup(html or "", "lxml")

    for h2 in soup.select("h2"):
        h2_text = h2.get_text(" ", strip=True)
        if "项目编号" in h2_text:
            code = _remove_all_letters(h2_text).replace(" ", "").replace("\n", "").replace("，A", "")
            if code:
                out["project_code"] = code.strip()

    for p in soup.select("p"):
        p_text = p.get_text(" ", strip=True)
        if not p_text:
            continue
        if "项目编号" in p_text and not out.get("project_code"):
            code = _remove_all_letters(p_text).replace(" ", "").replace("\n", "").replace("，A", "")
            # 直购常见「订单：SCZG-xxx，于：...」
            m = re.search(r"((?:SCJJ|ECJJ|SCZG|SCDZ|SDGP)[\w\-]+)", p_text)
            out["project_code"] = (m.group(1) if m else code).strip() or None
        if "项目名称" in p_text and not out.get("project_name"):
            out["project_name"] = _remove_ignore_character(p_text) or None
        if "供应商地址" in p_text:
            out["deal_supplier_address"] = _remove_ignore_character(p_text) or None
        if "供应商名称" in p_text or re.search(r"供应商\s*[:：]", p_text):
            name = _remove_ignore_character(p_text)
            if name and not name.startswith("地址"):
                out["deal_supplier"] = name
        if "成交供应商" in p_text and not out.get("deal_supplier"):
            out["deal_supplier"] = _remove_ignore_character(p_text) or None
        if "采购单位" in p_text or "采购人" in p_text:
            out["buyer_name"] = _remove_ignore_character(p_text) or out.get("buyer_name")
        if "成交金额" in p_text:
            m = re.search(r"成交金额\s*[:：]?\s*([0-9,.]+)", p_text)
            if m:
                out["deal_amount"] = _money(m.group(1))
        if "预算金额" in p_text:
            m = re.search(r"预算金额\s*[:：]?\s*([0-9,.]+)", p_text)
            if m:
                out["budget_amount"] = _money(m.group(1))
        if "联系人" in p_text and "联系方式" not in p_text:
            out["buyer_contact_name"] = _remove_ignore_character(p_text) or None
        if "联系方式" in p_text:
            phone = _remove_ignore_character(p_text)
            # 「田野 15066375463」或纯电话
            m = re.search(r"(1[3-9]\d{9}|[0-9\-]{7,20})", p_text)
            if m:
                out["buyer_phone"] = m.group(1)
            if phone and not out.get("buyer_contact_name"):
                name = re.sub(r"(1[3-9]\d{9}|[0-9\-]{7,20})", "", phone).strip()
                if name:
                    out["buyer_contact_name"] = name

    goods, quotes = _parse_contract_tables(soup)
    out["goods"] = goods
    if quotes:
        out["quotes"] = quotes
        out["suppliers"] = [q["supplier_name"] for q in quotes if q.get("supplier_name")]
        out["quote_count"] = len(quotes)
        if not out.get("deal_supplier"):
            winner = next((q for q in quotes if q.get("is_winner")), None) or (
                quotes[0] if quotes else None
            )
            if winner:
                out["deal_supplier"] = winner.get("supplier_name")
                if out.get("deal_amount") is None:
                    out["deal_amount"] = winner.get("quote_amount")

    # 详情/列表结构化补洞
    if not out.get("region_name"):
        out["region_name"] = detail.get("regionName") or list_item.get("regionName")
    if not out.get("end_time"):
        out["end_time"] = detail.get("endTime") or list_item.get("endTime")
    if not out.get("publish_time"):
        out["publish_time"] = (
            detail.get("publishTime")
            or detail.get("createDate")
            or list_item.get("publishTime")
            or list_item.get("createDate")
        )
    if out.get("budget_amount") is None:
        out["budget_amount"] = _money(list_item.get("budgetAmount") or detail.get("budgetAmount"))
    if out.get("deal_amount") is None:
        out["deal_amount"] = _money(list_item.get("tradingAmount") or detail.get("tradingAmount"))

    # 公告种类：优先列表/详情 noticeType（与抓取分类一致），避免正文套话
    # 如「反拍项目终止」误命中「终止」
    nt = list_item.get("noticeType")
    if nt in (None, ""):
        nt = detail.get("noticeType")
    nt_s = str(nt).strip() if nt not in (None, "") else ""
    sd_kind = {
        "0": "采购公告",
        "1": "成交公告",
        "5": "终止公告",
        "10": "终止公告",
        "13": "公示公告",
    }
    if nt_s in sd_kind:
        out["notice_kind"] = sd_kind[nt_s]
    else:
        # 仅看标题，不用正文（正文常有「项目终止」规则说明）
        title_blob = title or ""
        for key, kind in (
            ("废标公告", "废标公告"),
            ("终止公告", "终止公告"),
            ("失败公告", "失败公告"),
            ("成交结果", "成交结果公告"),
            ("成交公告", "成交公告"),
            ("结果公告", "成交公告"),
            ("采购公告", "采购公告"),
            ("公示公告", "公示公告"),
        ):
            if key in title_blob:
                out["notice_kind"] = kind
                break

    blob = f"{title}\n{text}\n{(html or '')[:500]}"
    for key, mode in (
        ("反拍", "反拍"),
        ("直购", "直接采购"),
        ("直接采购", "直接采购"),
        ("议价", "议价"),
        ("定点", "定点竞价"),
        ("竞价", "普通竞价"),
    ):
        if key in blob:
            out["procurement_mode"] = mode
            break

    if out.get("buyer_contact_name") or out.get("buyer_phone"):
        out["buyer_contact"] = " ".join(
            x for x in (out.get("buyer_contact_name"), out.get("buyer_phone")) if x
        )

    filled = sum(
        1
        for k in ("project_code", "buyer_name", "deal_supplier", "deal_amount", "budget_amount")
        if out.get(k) not in (None, "", [])
    )
    out["confidence"] = 0.85 if (filled >= 3 or out["goods"]) else 0.6
    return out
