"""山东政府采购网通用公告规则抽取（结果/合同/验收/采购/单一来源等）。

意向公开仍走 sd_ccgp_intention；本模块覆盖其余常见版式。
"""

from __future__ import annotations

import re
from copy import deepcopy
from typing import Any, Dict, List, Optional, Tuple

from pipeline.extractors.base import EXTRACT_SCHEMA, strip_deal_supplier_if_pre_result

MAX_SANE_AMOUNT = 1_000_000_000.0

_KIND_BY_TYPE = {
    "2500": "意向公开",
    "0301": "采购公告",
    "0305": "更正公告",
    "0302": "结果公告",
    "0306": "终止公告",
    "2502": "合同公告",
    "2503": "验收公告",
    "2102": "单一来源公示",
}


def _clean(text: Optional[str], limit: int = 256) -> Optional[str]:
    if text is None:
        return None
    val = re.sub(r"\s+", " ", str(text)).strip()
    if not val or val in {"无", "/", "-", "—", "详见附件", "详见招标文件", "详见磋商文件"}:
        return None
    return val[:limit]


def _sane_amount(value: Optional[float]) -> Optional[float]:
    if value is None:
        return None
    try:
        amount = float(value)
    except (TypeError, ValueError):
        return None
    if amount < 0 or amount > MAX_SANE_AMOUNT:
        return None
    return round(amount, 2)


def _parse_amount(raw: Optional[str], *, wan: bool = False) -> Optional[float]:
    if raw is None:
        return None
    text = str(raw).replace(",", "").replace("，", "").replace("￥", "").replace("¥", "")
    text = text.replace("元", "").replace("万元", "").strip()
    m = re.search(r"([0-9]+(?:\.[0-9]+)?)", text)
    if not m:
        return None
    try:
        amount = float(m.group(1))
    except ValueError:
        return None
    if wan or ("万" in str(raw) and "万元" not in str(raw).replace(m.group(0), "")):
        # 调用方可显式传 wan=True；正文带「万元」时也按万元
        pass
    if wan:
        amount *= 10000
    return _sane_amount(amount)


def _label_value(labels: List[str], text: str) -> Optional[str]:
    for label in labels:
        m = re.search(
            rf"{label}\s*[:：]?\s*\n?\s*([^\n\r]+)",
            text,
            flags=re.M,
        )
        if m:
            val = _clean(m.group(1))
            if val and not val.startswith(("地", "联系方式", "供应商名称", "供应商地址")):
                return val
    return None


def _first_money(patterns: List[str], text: str, *, wan_default: bool = False) -> Optional[float]:
    for pat in patterns:
        m = re.search(pat, text, flags=re.M)
        if not m:
            continue
        raw = m.group(1)
        wan = wan_default or ("万" in (m.group(0) or ""))
        amount = _parse_amount(raw, wan=wan)
        if amount is not None:
            return amount
    return None


def _extract_result_deal_table(text: str) -> Tuple[Dict[str, Any], List[Dict[str, Any]], List[Dict[str, Any]]]:
    """六、成交情况：标包/采购内容/供应商/数量/成交金额。"""
    out: Dict[str, Any] = {}
    goods: List[Dict[str, Any]] = []
    quotes: List[Dict[str, Any]] = []
    m = re.search(r"成交情况\s*[:：]?\s*([\s\S]+?)(?=\n七、|\n八、|\n公告期限|$)", text)
    if not m:
        return out, goods, quotes
    section = m.group(1)
    section = re.sub(
        r"^\s*标包\s*\n?\s*采购内容\s*\n?\s*供应商名称\s*\n?\s*采购数量\s*\n?\s*成交金额\s*",
        "",
        section,
        count=1,
    )
    total = 0.0
    for row in re.finditer(
        r"(?m)^([A-Za-z0-9\-]+)\n"
        r"([^\n]{1,200})\n"
        r"([^\n]{2,120})\n"
        r"([0-9]+(?:\.[0-9]+)?)\n"
        r"([0-9,.]+)\s*元?",
        section,
    ):
        pkg, content, supplier, qty_raw, amt_raw = row.groups()
        supplier = _clean(supplier, 256)
        content = _clean(content, 512) or f"标包{pkg}"
        amount = _parse_amount(amt_raw, wan=False)
        qty = None
        try:
            qty = float(qty_raw)
        except ValueError:
            qty = None
        if supplier:
            quotes.append(
                {
                    "supplier_name": supplier,
                    "quote_amount": amount,
                    "rank": len(quotes) + 1,
                    "is_winner": True,
                    "phone": None,
                    "address": None,
                }
            )
            if not out.get("deal_supplier"):
                out["deal_supplier"] = supplier
        if amount is not None:
            total += amount
        goods.append(
            {
                "name": content,
                "category": None,
                "quantity": qty if qty is not None else 1,
                "unit": None,
                "brand": None,
                "model": None,
                "spec": f"标包{pkg}",
                "unit_price": None,
                "amount": amount,
            }
        )
        if len(goods) >= 40:
            break
    if total > 0:
        out["deal_amount"] = _sane_amount(total)
    return out, goods, quotes


def _append_winner(
    out: Dict[str, Any],
    quotes: List[Dict[str, Any]],
    goods: List[Dict[str, Any]],
    *,
    supplier: Optional[str],
    amount: Optional[float],
    addr: Optional[str] = None,
    pkg: Optional[str] = None,
) -> float:
    """追加中标供应商；返回计入合计的金额（无则 0）。"""
    supplier = _clean(supplier)
    addr = _clean(addr, 512)
    added = 0.0
    if supplier:
        quotes.append(
            {
                "supplier_name": supplier,
                "quote_amount": amount,
                "rank": len(quotes) + 1,
                "is_winner": True,
                "phone": None,
                "address": addr,
            }
        )
        if not out.get("deal_supplier"):
            out["deal_supplier"] = supplier
            if addr:
                out["deal_supplier_address"] = addr
    if amount is not None:
        added = float(amount)
        goods.append(
            {
                "name": f"采购包{pkg}" if pkg else (supplier or "成交标的"),
                "category": None,
                "quantity": 1,
                "unit": None,
                "brand": None,
                "model": None,
                "spec": None,
                "unit_price": amount,
                "amount": amount,
            }
        )
    return added


def _parse_amount_unit(raw: Optional[str], unit: Optional[str] = None) -> Optional[float]:
    wan = (unit or "") == "万元" or (raw is not None and "万" in str(raw) and "元" not in str(raw).replace("万", ""))
    if unit == "元":
        wan = False
    return _parse_amount(raw, wan=wan)


def _extract_result_packages(text: str) -> Tuple[Dict[str, Any], List[Dict[str, Any]], List[Dict[str, Any]]]:
    """采购结果 / 中标（成交）信息：多采购包供应商+金额。"""
    out: Dict[str, Any] = {}
    goods: List[Dict[str, Any]] = []
    quotes: List[Dict[str, Any]] = []
    total = 0.0

    # 版式 A：采购包X: 表头后供应商/地址/金额（可能夹「评审价格」等表头行；地址可能为 /）
    package_blocks = list(
        re.finditer(
            r"(?:采购包|合同包|标包)\s*([0-9A-Za-z\-包]+)[^\n]{0,40}:\s*\n"
            r"供应商名称\s*\n"
            r"供应商地址\s*\n"
            r"中标[（(]成交[)）]金额\s*\n"
            r"(?:(?:执行标准|评审总得分|评审价格|评审报价|报价)\s*\n){0,4}"
            r"([^\n]{2,120})\n"
            r"([^\n]{1,200})\n"
            r"([0-9,.]+)\s*(?:\(元\)|元)",
            text,
        )
    )
    for block in package_blocks:
        pkg, supplier, addr, amt_raw = block.groups()
        total += _append_winner(
            out,
            quotes,
            goods,
            supplier=supplier,
            amount=_parse_amount(amt_raw, wan=False),
            addr=addr,
            pkg=pkg,
        )

    if not quotes:
        # 版式 B：中标（成交）信息表（金额可能是万元）
        m = re.search(
            r"中标（成交）信息\s*[:：]?\s*([\s\S]+?)(?=\n四、|\n五、|\n主要标的|\n公告期限|$)",
            text,
        )
        section = m.group(1) if m else ""
        for row in re.finditer(
            r"(?m)^((?:SDGP)?[A-Za-z0-9][\w\-]*)\n"
            r"([^\n]{2,120})\n"
            r"([^\n]{2,200})\n"
            r"([0-9]+(?:\.[0-9]+)?)\s*$",
            section,
        ):
            pkg, supplier, addr, amt_raw = row.groups()
            wan = "万元" in section[:80] or "（万元）" in section[:80] or "(万元)" in section[:80]
            total += _append_winner(
                out,
                quotes,
                goods,
                supplier=supplier,
                amount=_parse_amount(amt_raw, wan=wan),
                addr=addr,
                pkg=pkg,
            )

    if not quotes:
        # 版式 A2：无采购包前缀的「供应商名称/地址/金额」竖表
        for row in re.finditer(
            r"供应商名称\s*\n"
            r"供应商地址\s*\n"
            r"中标[（(]成交[)）]金额\s*\n"
            r"(?:(?:执行标准|评审总得分|评审价格|评审报价|报价)\s*\n){0,4}"
            r"([^\n]{2,120})\n"
            r"([^\n]{1,200})\n"
            r"([0-9,.]+)\s*(?:\(元\)|元)",
            text,
        ):
            total += _append_winner(
                out,
                quotes,
                goods,
                supplier=row.group(1),
                amount=_parse_amount(row.group(3), wan=False),
                addr=row.group(2),
            )

    if not quotes:
        # 版式 C/D：供应商名称：…（可多行地址）+ 中标金额/中标价（金额可换行，单位可单独一行）
        for row in re.finditer(
            r"(?:成交)?供应商\s*名称\s*[:：]\s*\n?\s*([^\n\r]{2,120})\s*"
            r"(?:供应商\s*地址\s*[:：]\s*\n?\s*([\s\S]{0,220}?)\s*)?"
            r"(?:中标[（(]\s*成交\s*[)）]\s*金额|成交金额|中标价|中标金额)"
            r"[^\n]{0,80}[:：]?\s*(?:\n\s*[:：]\s*)?\n?\s*"
            r"(?:大写[^\n]{0,40}\n\s*小写\s*[:：]\s*)?"
            r"(?:人民币)?\s*([0-9,.]+)\s*(?:\n\s*)?(万元|元)?",
            text,
        ):
            unit = row.group(4)
            # 若金额行后紧跟「万元」在后续短文本里
            if not unit:
                tail = text[row.end() : row.end() + 12]
                if re.match(r"\s*万元", tail):
                    unit = "万元"
                elif re.match(r"\s*元", tail):
                    unit = "元"
            total += _append_winner(
                out,
                quotes,
                goods,
                supplier=row.group(1),
                amount=_parse_amount_unit(row.group(3), unit),
                addr=row.group(2),
            )

    if not quotes:
        # 版式 E：中标情况表（序号 / 中标供应商名称 / 地址 / 金额）
        for row in re.finditer(
            r"(?:中标情况|中标信息)\s*[:：]?\s*\n"
            r"(?:序号\s*\n)?"
            r"中标供应商名称\s*\n"
            r"中标供应商地址\s*\n"
            r"中标金额[^\n]*\n"
            r"(?:\d+\n)?"
            r"([^\n]{2,120})\n"
            r"([^\n]{2,200})\n"
            r"([0-9,.]+)",
            text,
        ):
            total += _append_winner(
                out,
                quotes,
                goods,
                supplier=row.group(1),
                amount=_parse_amount(row.group(3), wan=False),
                addr=row.group(2),
            )

    if not quotes:
        # 版式 F：中标人/投标人名称：xxx … 中标金额：xxx元
        for row in re.finditer(
            r"(?:中标人|投标人)\s*名称\s*[:：]\s*\n?\s*([^\n\r]{2,120})\s*"
            r"(?:[\s\S]{0,160}?(?:中标人|投标人)\s*地址\s*[:：]\s*\n?\s*([\s\S]{0,200}?)\s*)?"
            r"[\s\S]{0,120}?中标金额\s*[:：]\s*\n?\s*(?:人民币)?"
            r"[^\n]{0,40}?(?:￥|¥)?\s*([0-9,.]+)\s*元?",
            text,
        ):
            total += _append_winner(
                out,
                quotes,
                goods,
                supplier=row.group(1),
                amount=_parse_amount(row.group(3), wan=False),
                addr=row.group(2),
            )
        # 中标人\n名称\n:xxx（旧竖排）
        if not quotes:
            for row in re.finditer(
                r"中标人\s*\n?\s*名称\s*[:：]\s*([^\n\r]{2,120})\s*"
                r"(?:[\s\S]{0,120}?中标人\s*\n?\s*地址\s*[:：]\s*([^\n\r]{0,200})\s*)?"
                r"[\s\S]{0,80}?中标金额\s*[:：]\s*\n?\s*([0-9,.]+)\s*元?",
                text,
            ):
                total += _append_winner(
                    out,
                    quotes,
                    goods,
                    supplier=row.group(1),
                    amount=_parse_amount(row.group(3), wan=False),
                    addr=row.group(2),
                )

    if not quotes:
        # 版式 G：入围供应商信息表（排名/名称/地址/折扣或单价）
        m = re.search(
            r"(?:入围供应商信息|入围信息|入围（成交）信息)\s*[:：]?\s*([\s\S]+?)(?=\n四、|\n五、|\n主要标的|\n公告期限|$)",
            text,
        )
        section = m.group(1) if m else ""
        for row in re.finditer(
            r"(?m)^(\d+)\n([^\n]{2,120})\n([^\n]{2,200})\n",
            section,
        ):
            name = _clean(row.group(2))
            if not name or name in {"供应商名称", "地址", "排名", "入围供应商", "排序"}:
                continue
            total += _append_winner(
                out, quotes, goods, supplier=name, amount=None, addr=row.group(3)
            )
            if len(quotes) >= 30:
                break

    if not quotes:
        # 版式 H：入围/多中标单位名称：xxx（无明确成交额时只取供应商）
        for row in re.finditer(
            r"(?:单位名称|供应商名称)\s*[:：]\s*([^\n\r]{2,120})",
            text,
        ):
            name = _clean(row.group(1))
            if not name or name in {"地址", "联系方式"}:
                continue
            if re.search(r"(采购人|代理|财政)", name):
                continue
            head = text[max(0, row.start() - 80) : row.start()]
            if not re.search(r"(入围|中标|成交|供应商信息)", head):
                continue
            total += _append_winner(out, quotes, goods, supplier=name, amount=None)
            if len(quotes) >= 20:
                break

    if total > 0:
        out["deal_amount"] = _sane_amount(total)
    return out, goods, quotes


def _extract_result_goods(text: str) -> List[Dict[str, Any]]:
    goods: List[Dict[str, Any]] = []
    # 货物类明细
    for row in re.finditer(
        r"(?m)^(?:\d+-\d+(?:-\d+)?)\n"
        r"([^\n]{2,80})\n"  # 品目名称
        r"([^\n]{2,120})\n"  # 采购标的
        r"([^\n]{0,80})\n"  # 品牌
        r"([^\n]{0,120})\n"  # 规格
        r"([0-9]+(?:\.[0-9]+)?)\s*[（(]?([^)）\n]*)[)）]?",
        text,
    ):
        category, name, brand, model, qty_raw, unit = row.groups()
        name = _clean(name, 512)
        if not name:
            continue
        try:
            qty = float(qty_raw)
        except ValueError:
            qty = 1
        goods.append(
            {
                "name": name,
                "category": _clean(category, 64),
                "quantity": qty,
                "unit": _clean(unit, 32),
                "brand": _clean(brand, 64),
                "model": _clean(model, 128),
                "spec": None,
                "unit_price": None,
                "amount": None,
            }
        )
        if len(goods) >= 40:
            break
    if goods:
        return goods

    # 服务类：采购标的一行
    for row in re.finditer(
        r"(?m)^(?:\d+-\d+(?:-\d+)?)\n"
        r"(?:[^\n]{2,100}\n)?"  # 品目编号及名称 或 品目名称
        r"([^\n]{2,120})\n",  # 采购标的
        text,
    ):
        name = _clean(row.group(1), 512)
        if not name or name in {"采购标的", "品目名称", "报价明细内容", "服务范围"}:
            continue
        goods.append(
            {
                "name": name,
                "category": "服务",
                "quantity": 1,
                "unit": None,
                "brand": None,
                "model": None,
                "spec": None,
                "unit_price": None,
                "amount": None,
            }
        )
        if len(goods) >= 20:
            break
    return goods


def _extract_contract(text: str) -> Tuple[Dict[str, Any], List[Dict[str, Any]]]:
    out: Dict[str, Any] = {}
    goods: List[Dict[str, Any]] = []

    out["deal_supplier"] = _label_value(["供应商（乙方）", "供应商\\(乙方\\)", "乙方"], text)
    # 乙方后地址/电话
    m = re.search(
        r"供应商（乙方）\s*[:：]?\s*\n?\s*([^\n\r]+)\s*\n\s*地\s*址\s*[:：]?\s*\n?\s*([^\n\r]+)\s*\n\s*联系方式\s*[:：]?\s*\n?\s*([^\n\r]+)",
        text,
    )
    if m:
        out["deal_supplier"] = _clean(m.group(1)) or out.get("deal_supplier")
        out["deal_supplier_address"] = _clean(m.group(2), 512)
        phone = _clean(m.group(3), 64)
        if phone and re.search(r"\d", phone):
            out["deal_supplier_phone"] = phone

    # 合同金额（万元）表
    section_m = re.search(
        r"合同主要信息\s*([\s\S]+?)(?=\n履约期限|\n七、|\n八、|\n采购方式|$)",
        text,
    )
    section = section_m.group(1) if section_m else text
    wan_table = "合同金额（万元）" in section or "主要标的单价（万元）" in section
    for row in re.finditer(
        r"(?m)^([^\n]{2,80})\n"
        r"([^\n]{1,120})\n"
        r"([0-9]+(?:\.[0-9]+)?)\n"
        r"([0-9]+(?:\.[0-9]+)?)\n"
        r"([0-9]+(?:\.[0-9]+)?)\s*$",
        re.sub(
            r"主要标的名称\s*\n?\s*规格型号[^\n]*\n?\s*主要标的数量\s*\n?\s*主要标的单价[^\n]*\n?\s*合同金额[^\n]*\s*",
            "",
            section,
            count=1,
        ),
    ):
        name, spec, qty_raw, price_raw, amt_raw = row.groups()
        name = _clean(name, 512)
        if not name or name.startswith("履约"):
            continue
        try:
            qty = float(qty_raw)
        except ValueError:
            qty = 1
        unit_price = _parse_amount(price_raw, wan=wan_table)
        amount = _parse_amount(amt_raw, wan=wan_table)
        goods.append(
            {
                "name": name,
                "category": None,
                "quantity": qty,
                "unit": None,
                "brand": None,
                "model": None,
                "spec": _clean(spec, 512),
                "unit_price": unit_price,
                "amount": amount,
            }
        )
        if len(goods) >= 40:
            break

    if goods:
        total = sum(g["amount"] for g in goods if g.get("amount") is not None)
        if total > 0:
            out["deal_amount"] = _sane_amount(total)
    if out.get("deal_amount") is None:
        out["deal_amount"] = _first_money(
            [
                r"合同金额\s*[（(]?万元[)）]?\s*[:：]?\s*\n?\s*([0-9,.]+)",
                r"合同金额\s*[:：]?\s*\n?\s*([0-9,.]+)\s*万元",
                r"合同金额\s*[:：]?\s*\n?\s*([0-9,.]+)\s*元",
            ],
            text,
        )

    mode = _label_value(["采购方式"], text)
    if mode and len(mode) <= 20 and "办法" not in mode and "法律" not in mode:
        out["procurement_mode"] = mode
    return out, goods


def _extract_acceptance(text: str) -> Dict[str, Any]:
    out: Dict[str, Any] = {}
    out["deal_supplier"] = _label_value(["供应商（乙方）", "乙方"], text)
    m = re.search(
        r"供应商（乙方）\s*[:：]?\s*\n?\s*([^\n\r]+)\s*\n\s*地\s*址\s*[:：]?\s*\n?\s*([^\n\r]+)",
        text,
    )
    if m:
        out["deal_supplier"] = _clean(m.group(1)) or out.get("deal_supplier")
        out["deal_supplier_address"] = _clean(m.group(2), 512)
    service = _label_value(["服务内容"], text)
    # 验收模板常把「合格」填进服务内容/要求，不能当标的名
    if service and service not in {"合格", "不合格", "同意验收", "详见合同"} and len(service) >= 4:
        out["_goods_name"] = service
    return out


def _extract_single_source(text: str) -> Dict[str, Any]:
    out: Dict[str, Any] = {}
    out["budget_amount"] = _first_money(
        [
            r"拟采购的货物或服务的预算金额\s*[:：]?\s*\n?\s*([0-9,.]+)\s*万元",
            r"拟采购的货物或服务的预算金额\s*[:：]?\s*\n?\s*([0-9,.]+)\s*元",
            r"采购预算\s*[（(]?元[)）]?\s*[:：]?\s*\n?\s*([0-9,.]+)",
            r"预算金额\s*[:：]?\s*\n?\s*([0-9,.]+)\s*万元",
            r"预算金额\s*[（(]?元[)）]?\s*[:：]?\s*\n?\s*([0-9,.]+)",
        ],
        text,
    )

    m = re.search(
        r"拟定唯一供应商[\s\S]{0,120}?供应商名称\s*[:：]?\s*\n?\s*([^\n\r]{2,120})",
        text,
    )
    if not m:
        m = re.search(
            r"拟定供应商(?:信息)?\s*[:：]?\s*\n?\s*名称\s*[:：]\s*([^\n\r]{2,120})",
            text,
        )
    if not m:
        # 单一来源采购邀请：现邀请 XXX 提交响应文件
        m = re.search(
            r"现邀请\s*\n?\s*([^\n\r]{2,120}?)\s*\n?\s*提交响应文件",
            text,
        )
    if m:
        out["deal_supplier"] = _clean(m.group(1))
    # 预算：本项目预算金额为 259849.0 元
    if out.get("budget_amount") is None:
        out["budget_amount"] = _first_money(
            [
                r"本项目预算金额为\s*([0-9,.]+)\s*元",
                r"预算金额\s*[:：]?\s*\n?\s*([0-9,.]+)\s*\n?\s*万元",
                r"最高限价\s*[:：]?\s*\n?\s*([0-9,.]+)\s*\n?\s*万元",
            ],
            text,
        )
    # 地址
    addr = None
    for anchor in ("拟定唯一供应商", "拟定供应商信息", "拟定供应商"):
        if anchor in text:
            chunk = text[text.find(anchor) : text.find(anchor) + 400]
            addr = _label_value(["地址", "供应商地址"], chunk)
            break
    if addr and out.get("deal_supplier"):
        out["deal_supplier_address"] = addr
    return out


def _extract_common(text: str, title: str = "") -> Dict[str, Any]:
    full = f"{title}\n{text}"
    out: Dict[str, Any] = {
        "notice_title": title or None,
        "project_code": None,
        "project_name": None,
        "buyer_name": None,
        "budget_amount": None,
        "procurement_mode": None,
    }
    title_code = re.search(r"【((?:SDGP)[\w\-]+)】", title or "")
    out["project_code"] = (title_code.group(1) if title_code else None) or _label_value(
        [
            "采购项目编号",
            "采购项目编码",
            "项目编号",
            "原公告的采购项目编号",
            "合同编号",
        ],
        full,
    )
    if not out["project_code"]:
        m = re.search(r"(SDGP[\w\-]+)", full)
        if m:
            out["project_code"] = m.group(1)

    out["project_name"] = _label_value(
        [
            "采购项目名称",
            "项目名称",
            "合同名称",
            "原公告的采购项目名称",
        ],
        full,
    )
    m = re.search(
        r"(?:采购人信息|采购单位信息)[\s\S]{0,60}?名称\s*[:：]?\s*\n?\s*([^\n\r]+)",
        full,
    )
    if m:
        out["buyer_name"] = _clean(m.group(1))
    if not out.get("buyer_name"):
        out["buyer_name"] = _label_value(["采购人", "采购单位"], full)
    # 避免「采购人：\n地址」把下一标签当值
    if out.get("buyer_name") and out["buyer_name"] in {"地址", "联系方式", "供应商（乙方）"}:
        out["buyer_name"] = None

    out["budget_amount"] = _first_money(
        [
            r"预算金额\s*[:：]?\s*\n?\s*([0-9,.]+)\s*元",
            r"采购包预算金额\s*[:：]?\s*\n?\s*([0-9,.]+)\s*元",
            r"采购预算\s*[（(]?元[)）]?\s*[:：]?\s*\n?\s*([0-9,.]+)",
        ],
        full,
    )
    mode = _label_value(["采购方式"], full)
    if mode and len(mode) <= 20 and "办法" not in mode and "法律" not in mode:
        out["procurement_mode"] = mode
    return out


def extract_ccgp_notice(
    text: str,
    *,
    title: str = "",
    notice_type: str = "",
    list_item: Optional[dict] = None,
    detail: Optional[dict] = None,
) -> Dict[str, Any]:
    """抽取山东政府采购网非意向公开类公告。"""
    out = deepcopy(EXTRACT_SCHEMA)
    out["goods"] = []
    out["quotes"] = []
    out["suppliers"] = []
    nt = str(
        notice_type
        or (list_item or {}).get("noticeType")
        or (list_item or {}).get("colCode")
        or (detail or {}).get("noticeType")
        or ""
    ).strip()
    kind = _KIND_BY_TYPE.get(nt)
    if not kind:
        blob = title or ""
        for token, label in (
            ("合同公示", "合同公告"),
            ("合同公告", "合同公告"),
            ("验收", "验收公告"),
            ("更正", "更正公告"),
            ("废标", "终止公告"),
            ("终止", "终止公告"),
            ("成交公告", "结果公告"),
            ("结果公告", "结果公告"),
            ("单一来源", "单一来源公示"),
            ("采购公告", "采购公告"),
        ):
            if token in blob:
                kind = label
                break
    out["notice_kind"] = kind

    common = _extract_common(text or "", title=title or "")
    for k, v in common.items():
        if v not in (None, "", []):
            out[k] = v

    goods: List[Dict[str, Any]] = []
    quotes: List[Dict[str, Any]] = []

    if kind == "结果公告" or nt == "0302":
        deal, g1, q1 = _extract_result_deal_table(text or "")
        if not deal.get("deal_supplier"):
            deal2, g2, q2 = _extract_result_packages(text or "")
            deal.update({k: v for k, v in deal2.items() if v not in (None, "", [])})
            g1 = g1 or g2
            q1 = q1 or q2
        for k, v in deal.items():
            if v not in (None, "", []):
                out[k] = v
        goods = g1 or _extract_result_goods(text or "")
        quotes = q1
    elif kind == "合同公告" or nt == "2502":
        deal, goods = _extract_contract(text or "")
        for k, v in deal.items():
            if v not in (None, "", []):
                out[k] = v
    elif kind == "验收公告" or nt == "2503":
        deal = _extract_acceptance(text or "")
        for k, v in deal.items():
            if k.startswith("_"):
                continue
            if v not in (None, "", []):
                out[k] = v
        goods_name = deal.get("_goods_name") or out.get("project_name")
        if goods_name:
            goods = [
                {
                    "name": str(goods_name)[:512],
                    "category": "服务",
                    "quantity": 1,
                    "unit": None,
                    "brand": None,
                    "model": None,
                    "spec": None,
                    "unit_price": None,
                    "amount": None,
                }
            ]
    elif kind == "单一来源公示" or nt == "2102":
        deal = _extract_single_source(text or "")
        for k, v in deal.items():
            if v not in (None, "", []):
                out[k] = v
    elif kind in {"采购公告", "更正公告"} or nt in {"0301", "0305"}:
        # 采购公告预算已在 common；再补采购标的
        for row in re.finditer(
            r"采购标的\s*\n数量[^\n]*\n[\s\S]{0,40}?\n([^\n]{2,120})\n([0-9]+(?:\.[0-9]+)?)\s*[（(]?([^)）\n]*)[)）]?",
            text or "",
        ):
            name = _clean(row.group(1), 512)
            if not name:
                continue
            try:
                qty = float(row.group(2))
            except ValueError:
                qty = 1
            goods.append(
                {
                    "name": name,
                    "category": None,
                    "quantity": qty,
                    "unit": _clean(row.group(3), 32),
                    "brand": None,
                    "model": None,
                    "spec": None,
                    "unit_price": None,
                    "amount": out.get("budget_amount"),
                }
            )
            break

    # 废标/终止：清空成交
    if kind == "终止公告" or re.search(r"废标理由|予以废标|本项目废标", text or ""):
        if "废标" in (title or "") or "废标理由" in (text or "") or kind == "终止公告":
            if re.search(r"废标理由|予以废标|本项目废标|无（废标）", text or ""):
                out["deal_amount"] = None
                out["deal_supplier"] = None
                out["deal_supplier_address"] = None
                out["deal_supplier_phone"] = None

    out["goods"] = goods
    out["quotes"] = quotes
    out["suppliers"] = [q["supplier_name"] for q in quotes if q.get("supplier_name")]
    if out.get("deal_supplier") and out["deal_supplier"] not in out["suppliers"]:
        out["suppliers"] = [out["deal_supplier"], *out["suppliers"]]
    if out.get("quote_count") is None and quotes:
        out["quote_count"] = len(quotes)

    if kind != "单一来源公示":
        strip_deal_supplier_if_pre_result(out)

    filled = sum(
        1
        for k in ("project_code", "buyer_name", "deal_supplier", "deal_amount", "budget_amount")
        if out.get(k) not in (None, "", [])
    )
    out["confidence"] = 0.75 if filled >= 3 else (0.55 if filled >= 2 else 0.4)
    out["extra"] = {"extractor": "sd_ccgp_notice", "notice_type": nt or None}
    return out
