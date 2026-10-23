from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

from pipeline.extractors.base import BaseExtractor, EXTRACT_SCHEMA


def _first(patterns: List[str], text: str, flags: int = 0) -> Optional[str]:
    for p in patterns:
        m = re.search(p, text, flags)
        if m:
            val = m.group(1).strip()
            val = re.sub(r"\s+", " ", val)
            return val[:256]
    return None


def _money(patterns: List[str], text: str) -> Optional[float]:
    for p in patterns:
        m = re.search(p, text)
        if not m:
            continue
        raw = m.group(1).replace(",", "").replace("，", "").replace(" ", "")
        try:
            return float(raw)
        except ValueError:
            continue
    return None


def _label_value(labels: List[str], text: str) -> Optional[str]:
    """支持「标签: 值」或「标签:\\n值」两种排版（框架协议常见）。"""
    for label in labels:
        m = re.search(
            rf"{label}\s*[:：]?\s*\n?\s*([^\n\r]+)",
            text,
            flags=re.M,
        )
        if m:
            val = re.sub(r"\s+", " ", m.group(1).strip())
            if val and val not in {"地址", "成交金额（元）", "成交金额(元)", "成交供应商"}:
                return val[:256]
    return None


def _extract_gpfa_deal(text: str) -> Dict[str, Any]:
    """框架协议结果公告：成交供应商表头在上一行，值在后续行。"""
    out: Dict[str, Any] = {}
    m = re.search(
        r"二、成交供应商\s+"
        r"成交供应商\s+"
        r"地址\s+"
        r"成交金额[^\n\r]*\s+"
        r"([^\n\r]{2,80})\s+"
        r"([^\n\r]{2,200})\s+"
        r"([0-9]+(?:\.[0-9]+)?)",
        text,
    )
    if m:
        out["deal_supplier"] = re.sub(r"\s+", " ", m.group(1).strip())[:256]
        addr = re.sub(r"\s+", " ", m.group(2).strip().replace("_", ""))
        out["deal_supplier_address"] = addr[:512]
        try:
            out["deal_amount"] = float(m.group(3))
        except ValueError:
            pass
        return out
    # 宽松：成交供应商段落后找公司名+金额
    m2 = re.search(
        r"成交供应商[\s\S]{0,120}?"
        r"([^\n\r]{2,40}?(?:公司|事务所|中心|医院|学校|厂|商行|研究院))"
        r"[\s\S]{0,160}?"
        r"([0-9]{2,}(?:\.[0-9]+)?)",
        text,
    )
    if m2:
        out["deal_supplier"] = m2.group(1).strip()[:256]
        try:
            out["deal_amount"] = float(m2.group(2))
        except ValueError:
            pass
    return out


def _extract_gpfa_goods(text: str) -> List[Dict[str, Any]]:
    """框架协议服务/商品分项。"""
    goods: List[Dict[str, Any]] = []
    for m in re.finditer(
        r"(?:服务分项名称|商品名称|标的名称)\s*[:：]\s*\n?\s*([^\n\r]+)"
        r"[\s\S]{0,80}?"
        r"(?:控制单价|报价单价|单价)\s*[（(]?元[)）]?\s*[:：]\s*\n?\s*([0-9,.]+)"
        r"[\s\S]{0,40}?"
        r"数量\s*[:：]\s*\n?\s*([0-9,.]+)"
        r"(?:[\s\S]{0,40}?服务内容\s*[:：]\s*\n?\s*([^\n\r]+))?",
        text,
    ):
        name = re.sub(r"\s+", " ", m.group(1).strip())
        try:
            unit_price = float(m.group(2).replace(",", ""))
        except ValueError:
            unit_price = None
        try:
            quantity = float(m.group(3).replace(",", ""))
        except ValueError:
            quantity = None
        spec = m.group(4).strip() if m.group(4) else None
        amount = None
        if unit_price is not None and quantity is not None:
            amount = round(unit_price * quantity, 2)
        goods.append(
            {
                "name": name[:512],
                "category": "服务" if "服务" in (name + (spec or "")) else None,
                "quantity": quantity,
                "unit": None,
                "brand": None,
                "model": None,
                "unit_price": unit_price,
                "spec": spec[:2000] if spec else None,
                "amount": amount,
            }
        )
    return goods[:50]


def _num(s: str) -> Optional[float]:
    if s is None:
        return None
    raw = str(s).replace(",", "").replace("，", "").replace("￥", "").replace("¥", "").strip()
    if not raw:
        return None
    try:
        return float(raw)
    except ValueError:
        return None


def _extract_mall_deal(text: str) -> Dict[str, Any]:
    """山东网上商城成交/结果公告：供应商名称 / 成交金额（可带大写）。"""
    out: Dict[str, Any] = {}
    supplier = _first(
        [
            r"供应商名称\s*[:：]\s*([^\n\r]+)",
            r"(?<!成交)供应商\s*[:：]\s*([^\n\r]+)",  # 「供应商：」且非「供应商地址」
            r"成交供应商\s*[:：]\s*([^\n\r]+)",
            r"中标(?:供应商|人|单位)\s*[:：]\s*([^\n\r]+)",
        ],
        text,
        flags=re.M,
    )
    # 避免把「供应商地址」误当成供应商名
    if supplier and (supplier.startswith("地址") or "地址：" in supplier[:4]):
        supplier = None
    if supplier:
        # 去掉尾部干扰
        supplier = re.split(r"\s{2,}|供应商地址", supplier)[0].strip()
        out["deal_supplier"] = supplier[:256]
    addr = _first(
        [
            r"供应商地址\s*[:：]\s*([^\n\r]+)",
            r"成交供应商地址\s*[:：]\s*([^\n\r]+)",
        ],
        text,
        flags=re.M,
    )
    if addr:
        out["deal_supplier_address"] = addr[:512]
    # 成交金额：464.00（大写…）元 / 7525.00，大写(人民币)：…
    m = re.search(
        r"成交金额\s*[:：]\s*([0-9]+(?:\.[0-9]+)?)",
        text,
    )
    if m:
        out["deal_amount"] = _num(m.group(1))
    m2 = re.search(r"(?:本次竞价)?共有\s*([0-9]+)\s*家供应商", text)
    if m2:
        out["quote_count"] = int(m2.group(1))
    else:
        m3 = re.search(r"有效报价供应商为\s*([0-9]+)\s*家", text)
        if m3:
            out["quote_count"] = int(m3.group(1))
    return out


def _extract_mall_goods(text: str) -> List[Dict[str, Any]]:
    """网上商城「主要标的信息」竖排表格（品目/名称/品牌/型号/[参数]/数量/单价/小计）。"""
    m = re.search(
        r"主要标的信息\s*[:：]?\s*(.*?)(?=\n(?:五、|六、|服务要求|备注[:：]|报价信息|项目联系方式|\Z))",
        text,
        flags=re.S,
    )
    if not m:
        return []
    block = m.group(1).strip()
    if not block or "详见附件" in block[:20]:
        return []
    lines = [ln.strip() for ln in block.splitlines() if ln.strip()]
    # 跳过表头
    header_tokens = {
        "编号",
        "序号",
        "商品品目",
        "商品名称",
        "品牌",
        "型号",
        "参数",
        "数量",
        "单价（元）",
        "单价(元)",
        "单价",
        "小计（元）",
        "小计(元)",
        "小计",
    }
    while lines and (lines[0] in header_tokens or lines[0].endswith("（元）") or lines[0].endswith("(元)")):
        lines.pop(0)

    goods: List[Dict[str, Any]] = []
    i = 0
    while i < len(lines):
        if not re.fullmatch(r"[0-9]+", lines[i]):
            i += 1
            continue
        # 至少：品目 名称 品牌 型号 数量 单价 小计 = 7 字段；带参数则 8
        rest = lines[i + 1 :]
        if len(rest) < 7:
            break
        # 判别有无「参数」列：第 5 个字段不像纯数字/金额时视为参数
        has_spec = False
        if len(rest) >= 8:
            fifth = rest[4]
            if _num(fifth) is None and not re.fullmatch(r"[￥¥]?[0-9]+(?:\.[0-9]+)?", fifth.replace(",", "")):
                has_spec = True
        if has_spec:
            category, name, brand, model, spec, qty_s, price_s, amt_s = rest[:8]
            consume = 9  # 含行号
        else:
            category, name, brand, model, qty_s, price_s, amt_s = rest[:7]
            spec = None
            consume = 8
        qty, price, amt = _num(qty_s), _num(price_s), _num(amt_s)
        if qty is None or price is None:
            i += 1
            continue
        goods.append(
            {
                "name": re.sub(r"\s+", " ", name)[:512],
                "category": category[:256] if category else None,
                "quantity": qty,
                "unit": None,
                "brand": brand[:128] if brand else None,
                "model": model[:256] if model else None,
                "unit_price": price,
                "spec": (spec[:2000] if spec else None),
                "amount": amt if amt is not None else round(qty * price, 2),
            }
        )
        i += consume
        if len(goods) >= 50:
            break
    return goods


def _extract_mall_quotes(text: str) -> List[Dict[str, Any]]:
    """结果公告「报价情况如下」排名表。"""
    m = re.search(
        r"报价情况如下\s*[:：]?\s*(.*?)(?=\n(?:采购单位|五、|六、|项目联系|\Z))",
        text,
        flags=re.S,
    )
    if not m:
        return []
    block = m.group(1).strip()
    lines = [ln.strip() for ln in block.splitlines() if ln.strip()]
    header = {
        "排名",
        "供应商",
        "商品名称",
        "品牌",
        "型号",
        "数量",
        "单价",
        "报价金额(元)",
        "报价金额（元）",
        "报价金额",
        "报价时间",
    }
    while lines and lines[0] in header:
        lines.pop(0)
    quotes: List[Dict[str, Any]] = []
    i = 0
    while i < len(lines):
        if not re.fullmatch(r"[0-9]+", lines[i]):
            i += 1
            continue
        # 排名 供应商 商品 品牌 型号 数量 单价 报价金额 报价时间
        rest = lines[i + 1 :]
        if len(rest) < 8:
            break
        rank = int(lines[i])
        supplier, _name, _brand, _model, _qty, _price, amount_s, _time = rest[:8]
        amount = _num(amount_s)
        quotes.append(
            {
                "supplier_name": supplier[:256],
                "quote_amount": amount,
                "rank": rank,
                "is_winner": rank == 1,
                "phone": None,
                "address": None,
            }
        )
        i += 9
        if len(quotes) >= 30:
            break
    return quotes


class HeuristicExtractor(BaseExtractor):
    """规则抽取：无 GPU、不开源权重也能跑，适合冷启动与对照。"""

    name = "heuristic"

    def extract(self, text: str, title: str = "") -> Dict[str, Any]:
        full = f"{title}\n{text}"
        out = json_deepcopy(EXTRACT_SCHEMA)
        out["goods"] = []
        out["quotes"] = []
        out["suppliers"] = []
        out["notice_title"] = title or None
        # 标题里的【SDGP…】通常是本次采购包编号，优先于框架协议总编号
        title_code = _first([r"【((?:SDGP|SDKJXY|SCJJ|ECJJ)[\w\-]+)】"], title or "")
        out["project_code"] = title_code or _first(
            [
                r"项目编号[:：]\s*([A-Za-z0-9\-_/]+)",
                r"框架协议项目编号[:：]?\s*\n?\s*([A-Za-z0-9\-_/]+)",
                r"公告编号[:：]\s*([A-Za-z0-9\-_/]+)",
                r"订单编号[:：]\s*([A-Za-z0-9\-_/]+)",
                r"【((?:SDGP|SDKJXY)[\w\-]+)】",
            ],
            full,
        )
        if out["project_code"] is None:
            m = re.search(r"(?:SCJJ|ECJJ|SDGP|SDKJXY|JJ\d{8,}|XB\d{8,})[\w\-]*", full)
            if m:
                out["project_code"] = m.group(0)

        out["project_name"] = _label_value(
            ["采购包名称", "项目名称", "采购项目名称", "框架协议项目名称"],
            full,
        ) or _first(
            [
                r"项目名称[:：]\s*(.+)",
                r"采购项目名称[:：]\s*(.+)",
            ],
            full,
            flags=re.M,
        )
        out["buyer_name"] = _label_value(
            ["采购人名称", "采购人单位", "采购单位", "采购人"],
            full,
        ) or _first(
            [
                r"采购人(?:单位)?[:：]\s*(.+)",
                r"采购单位[:：]\s*(.+)",
                r"采购人名称[:：]\s*(.+)",
            ],
            full,
            flags=re.M,
        )
        out["buyer_contact_name"] = _first(
            [
                r"(?:项目)?联系人[:：]\s*([^\n\r，,；;]{2,20})",
                r"采购人联系人[:：]\s*([^\n\r，,；;]{2,20})",
            ],
            full,
            flags=re.M,
        )
        out["buyer_phone"] = _first(
            [
                r"采购人联系方式[:：]?\s*\n?\s*([0-9\-－＋+\s]{7,20})",
                r"(?:联系)?电话[:：]\s*([0-9\-－]{7,20})",
                r"联系方式[:：]\s*([0-9\-－]{7,20})",
                r"(1[3-9]\d{9})",
            ],
            full,
        )
        out["buyer_address"] = _label_value(
            ["采购人地址", "单位地址", "项目地址"],
            full,
        ) or _first(
            [
                r"(?:采购人|项目)?地址[:：]\s*(.+)",
                r"单位地址[:：]\s*(.+)",
            ],
            full,
            flags=re.M,
        )
        if out["buyer_contact_name"] or out["buyer_phone"]:
            out["buyer_contact"] = " ".join(
                x for x in (out["buyer_contact_name"], out["buyer_phone"]) if x
            )
        else:
            out["buyer_contact"] = _first(
                [r"联系方式[:：]\s*(.+)"],
                full,
                flags=re.M,
            )
        out["budget_amount"] = _money(
            [
                r"预算金额[（(]?元[)）]?[:：]?\s*\n?\s*([0-9,.]+)",
                r"预算[:：]\s*([0-9,.]+)\s*元",
                r"最高限价[（(]?元[)）]?[:：]?\s*([0-9,.]+)",
            ],
            full,
        )
        out["deal_amount"] = _money(
            [
                r"成交金额\s*[:：]\s*([0-9,.]+)",
                r"成交金额\s*[（(]?元[)）]?\s*[:：]\s*([0-9,.]+)",
                r"成交总?价\s*[（(]?元[)）]?\s*[:：]?\s*([0-9,.]+)",
                r"成交供应商报价[:：]\s*([0-9,.]+)",
            ],
            full,
        )
        out["deal_supplier"] = _first(
            [
                r"供应商名称\s*[:：]\s*(.+)",
                r"(?<![成地])供应商\s*[:：]\s*(.+)",
                r"成交供应商[:：]\s*(.+)",
                r"中标(?:供应商|人|单位)[:：]\s*(.+)",
                r"成交单位[:：]\s*(.+)",
            ],
            full,
            flags=re.M,
        )
        if out["deal_supplier"] and str(out["deal_supplier"]).startswith("地址"):
            out["deal_supplier"] = None
        out["deal_supplier_phone"] = _first(
            [
                r"成交供应商[^\n\r]{0,40}?电话[:：]\s*([0-9\-]+)",
                r"供应商电话[:：]\s*([0-9\-]+)",
                r"中标(?:供应商|人|单位)[^\n\r]{0,40}?电话[:：]\s*([0-9\-]+)",
            ],
            full,
            flags=re.M,
        )
        out["deal_supplier_address"] = _first(
            [
                r"供应商地址\s*[:：]\s*([^\n\r]+)",
                r"成交供应商[^\n\r]{0,40}?地址[:：]\s*([^\n\r]+)",
                r"中标(?:供应商|人|单位)[^\n\r]{0,40}?地址[:：]\s*([^\n\r]+)",
            ],
            full,
            flags=re.M,
        )
        # 山东商城成交公告（供应商名称 / 主要标的竖表 / 报价排名）
        mall_deal = _extract_mall_deal(full)
        if mall_deal.get("deal_supplier"):
            out["deal_supplier"] = mall_deal["deal_supplier"]
        if mall_deal.get("deal_amount") is not None:
            out["deal_amount"] = mall_deal["deal_amount"]
        if mall_deal.get("deal_supplier_address"):
            out["deal_supplier_address"] = mall_deal["deal_supplier_address"]
        if mall_deal.get("quote_count") is not None:
            out["quote_count"] = mall_deal["quote_count"]
        mall_goods = _extract_mall_goods(full)
        mall_quotes = _extract_mall_quotes(full)
        # 框架协议结果公告表格（覆盖通用规则）
        gpfa_deal = _extract_gpfa_deal(full)
        if gpfa_deal.get("deal_supplier"):
            out["deal_supplier"] = gpfa_deal["deal_supplier"]
        if gpfa_deal.get("deal_amount") is not None:
            out["deal_amount"] = gpfa_deal["deal_amount"]
        if gpfa_deal.get("deal_supplier_address"):
            out["deal_supplier_address"] = gpfa_deal["deal_supplier_address"]
        out["goods"] = mall_goods or _extract_gpfa_goods(full) or out["goods"]
        if mall_quotes:
            out["quotes"] = mall_quotes
            out["suppliers"] = [q["supplier_name"] for q in mall_quotes if q.get("supplier_name")]
            if out.get("quote_count") is None:
                out["quote_count"] = len(mall_quotes)
        out["delivery_address"] = _first(
            [
                r"交货地点[:：]\s*(.+)",
                r"交付地点[:：]\s*(.+)",
            ],
            full,
            flags=re.M,
        )
        from utils import extract_time_window

        t_start, t_end = extract_time_window(full)
        out["start_time"] = t_start or _first(
            [
                r"(?:竞价|报价|报名|采购)?开始时间[:：]\s*([0-9\-/: ：]+)",
                r"开始时间[:：]\s*([0-9\-/: ：]+)",
            ],
            full,
            flags=re.M,
        )
        out["end_time"] = t_end or _first(
            [
                r"(?:竞价|报价|报名)?截止时间[:：]\s*([0-9\-/: ：]+)",
                r"结束时间[:：]\s*([0-9\-/: ：]+)",
                r"截止日期[:：]\s*([0-9\-/: ：]+)",
            ],
            full,
            flags=re.M,
        )
        out["region_name"] = _first(
            [r"(山东省|济南市|青岛市|淄博市|枣庄市|烟台市|潍坊市|济宁市|泰安市|威海市|日照市|临沂市|德州市|聊城市|滨州市|菏泽市|东营市)[^\n]{0,20}"],
            full,
        )

        # 公告种类 / 采购方式（标题启发）
        kind_map = [
            ("废标", "废标公告"),
            ("终止", "终止公告"),
            ("失败", "失败公告"),
            ("成交", "成交公告"),
            ("结果", "成交公告"),
            ("询比", "询比公告"),
            ("公示", "公示公告"),
            ("采购公告", "采购公告"),
            ("竞价公告", "竞价公告"),
        ]
        for key, kind in kind_map:
            if key in (title or "") or key in full[:200]:
                out["notice_kind"] = kind
                break

        mode_map = [
            ("反拍", "反拍"),
            ("询比", "询比"),
            ("二次竞价", "二次竞价"),
            ("顺序轮候", "顺序轮候"),
            ("框架协议", "框架协议"),
            ("直购", "直购"),
            ("议价", "议价"),
            ("批量", "批量采购"),
            ("竞价", "普通竞价"),
        ]
        for key, mode in mode_map:
            if key in (title or "") or key in full[:300]:
                out["procurement_mode"] = mode
                break

        # 若商城排名表未命中，再粗抽「供应商…报价」
        if not out.get("quotes"):
            quotes = []
            for m in re.finditer(
                r"([^\n\r，,。；;]{2,40}?(?:公司|事务所|中心|医院|学校|厂|商行|门市部|经营部)).{0,20}?报价[:：]?\s*([0-9,.]+)",
                full,
            ):
                quotes.append(
                    {
                        "supplier_name": m.group(1).strip(),
                        "quote_amount": float(m.group(2).replace(",", "")),
                        "rank": None,
                        "is_winner": False,
                        "phone": None,
                        "address": None,
                    }
                )
            if out["deal_supplier"]:
                quotes.insert(
                    0,
                    {
                        "supplier_name": out["deal_supplier"],
                        "quote_amount": out["deal_amount"],
                        "rank": 1,
                        "is_winner": True,
                        "phone": out.get("deal_supplier_phone"),
                        "address": out.get("deal_supplier_address"),
                    },
                )
            out["quotes"] = quotes[:30]
            if out.get("quote_count") is None:
                out["quote_count"] = len(quotes) or None
            out["suppliers"] = list({q["supplier_name"] for q in quotes if q.get("supplier_name")})
        filled = sum(
            1
            for k in ("project_code", "buyer_name", "deal_supplier", "deal_amount", "budget_amount")
            if out.get(k) not in (None, "", [])
        )
        out["confidence"] = 0.7 if (filled >= 3 and out["goods"]) else (0.55 if filled >= 3 or out["goods"] else 0.35)
        out["extra"] = {"extractor": self.name}
        return out


def json_deepcopy(obj: Dict[str, Any]) -> Dict[str, Any]:
    import copy

    return copy.deepcopy(obj)
