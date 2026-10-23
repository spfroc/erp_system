"""山东网上商城 HTML 规则抽取（移植自 new-bidding/Clinch.py）。

核心：详情 content 里的 <p>/<h2> + .contractTable，不是纯文本正则。
"""

from __future__ import annotations

import copy
import re
from typing import Any, Dict, List, Optional

from bs4 import BeautifulSoup

from pipeline.extractors.base import EXTRACT_SCHEMA
from utils import (
    END_TIME_KEYS,
    START_TIME_KEYS,
    extract_time_window,
    normalize_region_name,
    pick_time_value,
)


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


_FW_DIGIT_TRANS = str.maketrans(
    {
        "０": "0",
        "１": "1",
        "２": "2",
        "３": "3",
        "４": "4",
        "５": "5",
        "６": "6",
        "７": "7",
        "８": "8",
        "９": "9",
        "－": "-",
        "—": "-",
        "–": "-",
        "　": " ",
        "（": "(",
        "）": ")",
    }
)
# 手机优先；固话次之。允许中间空格：150 6637 5463
_MOBILE_RE = re.compile(r"(?:\+?86[-\s]*)?(1[3-9](?:[\s-]?\d){9})")
_LANDLINE_RE = re.compile(r"(0\d{2,3}[-\s]?\d{7,8}|\(\d{3,4}\)\s*\d{7,8})")
_PHONE_RE = re.compile(
    r"(?:\+?86[-\s]*)?(1[3-9](?:[\s-]?\d){9})|(0\d{2,3}[-\s]?\d{7,8}|\(\d{3,4}\)\s*\d{7,8})"
)
_CONTACT_NAME_RE = re.compile(
    r"(?:项目|采购人|采购单位)?联系人\s*[:：]\s*([^\n\r，,；;。/｜|<>{}]{1,20})"
)
_CONTACT_PHONE_LABEL_RE = re.compile(
    r"(?:项目|采购人|采购单位)?(?:联系方式|联系电话|联系号码|电话|手机号?|Tel|TEL|手机)"
)
# 标签与号码可跨空白/换行
_CONTACT_PHONE_NEAR_RE = re.compile(
    r"(?:项目|采购人|采购单位)?(?:联系方式|联系电话|联系号码|电话|手机号?|Tel|TEL|手机)"
    r"\s*[:：]?\s*"
    r"(?:\n|\r|<br\s*/?>|\s)*"
    r"((?:\+?86[-\s]*)?1[3-9](?:[\s-]?\d){9}|0\d{2,3}[-\s]?\d{7,8}|\(\d{3,4}\)\s*\d{7,8}|[0-9\-\s]{7,20})",
    re.I,
)
_COMBINED_CONTACT_RE = re.compile(
    r"(?:项目|采购人)?联系人\s*[:：]\s*([^\n\r，,；;：:<>{}]{1,16}?)\s*"
    r"(?:联系方式|联系电话|电话|手机)\s*[:：]?\s*"
    r"((?:\+?86[-\s]*)?1[3-9](?:[\s-]?\d){9}|0\d{2,3}[-\s]?\d{7,8}|[0-9\-\s]{7,20})"
)
_PHONE_LABEL_ONLY_RE = re.compile(
    r"^(?:项目|采购人|采购单位)?(?:联系方式|联系电话|联系号码|电话|手机号?)\s*[:：]?\s*$",
    re.I,
)
# 「四、项目联系方式」这类章节标题，不能当联系人或电话标签行抽姓名
_SECTION_HEADER_RE = re.compile(
    r"^[（(]?[一二三四五六七八九十百千零\d]+[、.．)）]"
    r"|^(?:项目|采购人|采购单位)?联系方式\s*$"
)
_SUPPLIER_CONTACT_HINT = ("供应商联系", "成交供应商联系", "中标供应商联系", "报价供应商")
_BAD_NAME_TOKENS = frozenset(
    {"联系", "方式", "电话", "手机", "号码", "项目", "采购人", "采购单位", "供应商", "联系人"}
)


def _is_supplier_contact_line(text: str) -> bool:
    t = text or ""
    return any(h in t for h in _SUPPLIER_CONTACT_HINT) or (
        "供应商" in t and ("联系人" in t or "联系方式" in t or "电话" in t or "手机" in t)
    )


def _is_section_header_line(text: str) -> bool:
    t = (text or "").strip()
    if not t:
        return False
    # 「四、…」「（三）…」或纯「项目联系方式」章节标题
    if _SECTION_HEADER_RE.match(t):
        return True
    return bool(re.fullmatch(r".{0,8}项目联系方式\s*", t))


def _normalize_phone(raw: str | None) -> Optional[str]:
    if not raw:
        return None
    text = str(raw).translate(_FW_DIGIT_TRANS)
    text = text.replace(" ", "").replace("　", "")
    text = re.sub(r"^\+?86", "", text)
    # 优先完整手机号
    m = re.search(r"(1[3-9]\d{9})", text)
    if m:
        return m.group(1)
    m = re.search(r"(0\d{2,3}-?\d{7,8})", text)
    if m:
        return m.group(1)
    digits = re.sub(r"\D", "", text)
    if re.fullmatch(r"1[3-9]\d{9}", digits or ""):
        return digits
    if 7 <= len(digits or "") <= 12 and digits.startswith("0"):
        return digits
    return None


def _find_phone_in(text: str) -> Optional[str]:
    blob = (text or "").translate(_FW_DIGIT_TRANS)
    m = _MOBILE_RE.search(blob)
    if m:
        return _normalize_phone(m.group(1))
    m = _LANDLINE_RE.search(blob)
    if m:
        return _normalize_phone(m.group(1))
    return None


def _clean_contact_name(raw: str | None) -> Optional[str]:
    if not raw:
        return None
    name = str(raw).translate(_FW_DIGIT_TRANS).strip()
    name = re.sub(
        r"(?:项目|采购人|采购单位)?(?:联系人|联系方式|联系电话|联系号码|电话|手机号?|Tel|TEL)\s*[:：]?",
        "",
        name,
        flags=re.I,
    )
    name = re.sub(r"<[^>]*>", "", name)
    name = re.sub(r"[：:\s]+$", "", name).strip(" ，,；;|/｜<>")
    name = _PHONE_RE.sub("", name).strip(" ，,；;|/｜<>")
    if not name or len(name) > 20:
        return None
    if re.fullmatch(r"[\d\-\s]+", name):
        return None
    if "、" in name or "。" in name or "<" in name or ">" in name:
        return None
    if _SECTION_HEADER_RE.match(name):
        return None
    if name in _BAD_NAME_TOKENS or all(ch in "联系方式电话手机号码项目" for ch in name):
        return None
    return name


def _extract_buyer_contact_from_text(blob: str) -> tuple[Optional[str], Optional[str]]:
    """从正文抽项目联系人/电话，避开供应商联系信息。

    兼容：
    - 同行「联系人：张三 联系方式：138…」
    - 标签与号码分行「联系方式：\\n150…」/「电话：0631-7567118」
    - 「四、项目联系方式」章节标题下的分行联系人
    - 全角数字、手机号中间空格
    """
    text = (blob or "").translate(_FW_DIGIT_TRANS)
    # 统一 br
    text = re.sub(r"<br\s*/?>", "\n", text, flags=re.I)
    if not text.strip():
        return None, None
    name: Optional[str] = None
    phone: Optional[str] = None

    lines = [ln.strip() for ln in re.split(r"[\n\r]+", text) if ln.strip()]
    for i, line in enumerate(lines):
        if _is_supplier_contact_line(line):
            continue
        # 章节标题本身不抽姓名；但其后若干行常是联系人/电话
        if _is_section_header_line(line):
            if not phone:
                for nxt in lines[i + 1 : i + 5]:
                    if _is_supplier_contact_line(nxt) or _is_section_header_line(nxt):
                        break
                    if not name:
                        m = _CONTACT_NAME_RE.search(nxt)
                        if m:
                            name = _clean_contact_name(m.group(1)) or name
                    found = _find_phone_in(nxt)
                    if not found:
                        m = _CONTACT_PHONE_NEAR_RE.search(nxt)
                        if m:
                            found = _normalize_phone(m.group(1))
                    if found:
                        phone = found
                        break
            continue
        m = _COMBINED_CONTACT_RE.search(line)
        if m:
            name = _clean_contact_name(m.group(1)) or name
            phone = phone or _normalize_phone(m.group(2))
            continue
        # 显式「联系人：」优先，可覆盖误抽姓名
        m = _CONTACT_NAME_RE.search(line)
        if m and "供应商" not in line:
            cleaned = _clean_contact_name(m.group(1))
            if cleaned:
                name = cleaned
        if not phone:
            m = _CONTACT_PHONE_NEAR_RE.search(line)
            if m and "供应商" not in line:
                phone = _normalize_phone(m.group(1))
        # 标签独占一行，号码在后续 1~3 行
        if not phone and _PHONE_LABEL_ONLY_RE.match(line) and "供应商" not in line:
            for nxt in lines[i + 1 : i + 4]:
                if _is_supplier_contact_line(nxt) or _is_section_header_line(nxt):
                    break
                found = _find_phone_in(nxt)
                if found:
                    phone = found
                    if not name:
                        maybe = _PHONE_RE.sub("", nxt).strip(" ：:，,；;")
                        name = _clean_contact_name(maybe) or name
                    break
        # 「联系方式：张三 150xxxx」——跳过章节标题行
        if (
            _CONTACT_PHONE_LABEL_RE.search(line)
            and (not name or not phone)
            and "供应商" not in line
            and not _is_section_header_line(line)
        ):
            found = _find_phone_in(line)
            if found and not phone:
                phone = found
            if not name:
                maybe = re.sub(
                    r"(?:项目|采购人|采购单位)?(?:联系方式|联系电话|联系号码|电话|手机号?|Tel)\s*[:：]?",
                    "",
                    line,
                    flags=re.I,
                )
                maybe = _PHONE_RE.sub("", maybe).strip(" ，,；;")
                name = _clean_contact_name(maybe) or name

    # 全文：标签后允许跨行空白再跟号码
    if not name or not phone:
        safe = text
        for bad in _SUPPLIER_CONTACT_HINT:
            safe = re.sub(rf".{{0,40}}{re.escape(bad)}.{{0,120}}", " ", safe)
        if not name:
            m = _CONTACT_NAME_RE.search(safe)
            if m:
                name = _clean_contact_name(m.group(1))
        if not phone:
            m = _CONTACT_PHONE_NEAR_RE.search(safe) or _COMBINED_CONTACT_RE.search(safe)
            if m:
                # COMBINED: g1 name g2 phone; NEAR: g1 phone
                if m.re is _COMBINED_CONTACT_RE:
                    phone = _normalize_phone(m.group(2))
                    name = name or _clean_contact_name(m.group(1))
                else:
                    phone = _normalize_phone(m.group(1))
        # 联系人附近的手机/固话
        if not phone:
            m = re.search(
                r"(?:项目|采购人)?联系人\s*[:：]\s*[^\n]{0,30}?"
                r"((?:\+?86[-\s]*)?1[3-9](?:[\s-]?\d){9}|0\d{2,3}[-\s]?\d{7,8})",
                safe,
            )
            if m:
                phone = _normalize_phone(m.group(1))
        if not phone:
            m = re.search(
                r"(?:电话|手机|联系电话)\s*[:：]\s*"
                r"((?:\+?86[-\s]*)?1[3-9](?:[\s-]?\d){9}|0\d{2,3}[-\s]?\d{7,8})",
                safe,
            )
            if m:
                phone = _normalize_phone(m.group(1))
    return name, phone


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
        # 段落内「报价时间：A至B」或开始/结束时间
        if any(k in p_text for k in ("报价时间", "竞价时间", "开始时间", "结束时间", "截止时间")):
            p_start, p_end = extract_time_window(p_text)
            if p_start and not out.get("start_time"):
                out["start_time"] = p_start
            if p_end and not out.get("end_time"):
                out["end_time"] = p_end

    # 项目联系人/电话：优先整页文本（保留换行，兼容「联系方式：」与号码分行）
    contact_blob = "\n".join(
        part
        for part in (
            text,
            soup.get_text("\n", strip=True),
            html,
        )
        if part
    )
    c_name, c_phone = _extract_buyer_contact_from_text(contact_blob)
    if c_name:
        out["buyer_contact_name"] = c_name
    if c_phone:
        out["buyer_phone"] = c_phone
    # JSON 兜底（字段名因接口版本不一）
    if not out.get("buyer_contact_name"):
        out["buyer_contact_name"] = (
            detail.get("contactName")
            or detail.get("linkMan")
            or detail.get("linkman")
            or detail.get("buyerContactName")
            or detail.get("projectContactName")
            or list_item.get("contactName")
            or list_item.get("linkMan")
            or list_item.get("linkman")
        )
    if not out.get("buyer_phone"):
        raw_phone = (
            detail.get("contactPhone")
            or detail.get("linkPhone")
            or detail.get("linkTel")
            or detail.get("buyerPhone")
            or detail.get("mobile")
            or detail.get("tel")
            or detail.get("phone")
            or detail.get("projectContactPhone")
            or list_item.get("contactPhone")
            or list_item.get("linkPhone")
            or list_item.get("linkTel")
            or list_item.get("mobile")
            or list_item.get("tel")
            or list_item.get("phone")
        )
        out["buyer_phone"] = _normalize_phone(raw_phone) if raw_phone else None

    goods, quotes = _parse_contract_tables(soup)
    # 去掉「未报价供应商」等空行误入的商品
    goods = [
        g
        for g in goods
        if g.get("name") or g.get("amount") is not None or g.get("brand") or g.get("model")
    ]
    out["goods"] = goods
    if quotes:
        out["quotes"] = quotes
        out["suppliers"] = [q["supplier_name"] for q in quotes if q.get("supplier_name")]
        out["quote_count"] = len(quotes)
        # 定点竞价成交公告正文常有「成交供应商」但无「成交金额」，金额在报价表
        winner = next((q for q in quotes if q.get("is_winner")), None)
        if not winner and out.get("deal_supplier"):
            ds = str(out["deal_supplier"]).strip()
            winner = next(
                (q for q in quotes if (q.get("supplier_name") or "").strip() == ds),
                None,
            )
        if not winner:
            # 表通常已按价格从低到高排序，第一条为成交
            winner = quotes[0]
        if winner:
            if not out.get("deal_supplier"):
                out["deal_supplier"] = winner.get("supplier_name")
            if out.get("deal_amount") is None and winner.get("quote_amount") is not None:
                out["deal_amount"] = winner.get("quote_amount")
    # 成交金额仍空时：用中标商品小计合计
    if out.get("deal_amount") is None and goods:
        amounts = [g.get("amount") for g in goods if g.get("amount") is not None]
        if amounts:
            out["deal_amount"] = round(sum(float(a) for a in amounts), 2)

    # 详情/列表结构化补洞；区域统一为地级市短名
    if not out.get("region_name"):
        out["region_name"] = detail.get("regionName") or list_item.get("regionName")
    out["region_name"] = normalize_region_name(
        "sd-ggzyjyzx", out.get("region_name")
    )
    # 报价开始/结束：JSON 字段 + 全文「报价时间：A至B」
    if not out.get("start_time"):
        out["start_time"] = pick_time_value(detail, list_item, keys=START_TIME_KEYS)
    if not out.get("end_time"):
        out["end_time"] = pick_time_value(detail, list_item, keys=END_TIME_KEYS)
    if not out.get("start_time") or not out.get("end_time"):
        t_start, t_end = extract_time_window(text, html)
        if t_start and not out.get("start_time"):
            out["start_time"] = t_start
        if t_end and not out.get("end_time"):
            out["end_time"] = t_end
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
