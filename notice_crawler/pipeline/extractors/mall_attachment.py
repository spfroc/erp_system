"""山东网上商城「采购清单」PDF 规则抽取。

版式常见两种（PDF 抽字时常粘连表头、拆散单元格）：
1. 定点竞价/反拍等：编号 / 服务分项名称 / 数量 / 计量单位 / 技术指标
2. 批量集采：序号 / 商品名称 / 品牌 / 型号 / 数量 / 单价 / …
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

from pipeline.extractors.jd_attachment import _UNITS, _UNITS_CORE, _is_unit_token

# 商城 PDF 字体偶发映射到康熙部首，解析前尽量还原常见字
_RADICAL_MAP = str.maketrans(
    {
        "\u2f00": "一",
        "\u2f08": "人",
        "\u2f24": "大",
        "\u2f29": "小",
        "\u2f2f": "工",
        "\u2f3a": "手",
        "\u2f3c": "心",
        "\u2f46": "日",
        "\u2f4a": "木",
        "\u2f54": "水",
        "\u2f55": "火",
        "\u2f57": "网",
        "\u2f63": "目",
        "\u2f65": "矢",
        "\u2f66": "示",
        "\u2f67": "禾",
        "\u2f6e": "竹",
        "\u2f70": "米",
        "\u2f8f": "言",
        "\u2f97": "贝",
        "\u2f9c": "车",
        "\u2fa4": "金",
        "\u2fa7": "长",
        "\u2fa8": "门",
        "\u2fba": "页",
        "\u2fc1": "风",
        "\u2fc5": "飞",
        "\u2fce": "齿",
        "\u2ebe": "网",
        "\u2ecf": "言",
        "\u2ed6": "金",
        "\u2eda": "长",
        "\u2ee9": "页",
    }
)

_UNIT_ALT = _UNITS_CORE
_SERVICE_ROW = re.compile(
    rf"(?<!\d)(\d{{1,4}})\s+"
    rf"(.{{1,80}}?)\s+"
    rf"([0-9]+(?:\.[0-9]+)?)\s+"
    rf"({_UNIT_ALT})"
    rf"(?:\s+|$)(.*)$",
    re.S,
)
_STOP_TAIL = re.compile(
    r"(其他服务要求|其他要求|需求内容|参数\s*[:：]|合计|小计|第\s*\d+\s*页)"
)
_HEADER_GLUE = re.compile(
    r"(?:编号|序号|服务分项名称|货物名称|商品名称|产品名称|品牌|型号|"
    r"数量|单价|折扣率|优惠后小计|小计|计量单位|单位|技术指标){2,}"
)
_SEQ = re.compile(r"^\d{1,4}$")
_MONEY = re.compile(r"^\d{1,3}(?:,\d{3})*(?:\.\d+)?$|^\d+(?:\.\d+)?$")
_MODEL_TOKEN = re.compile(
    r"^[A-Za-z0-9][A-Za-z0-9\-_/]{1,30}$|^[\u4e00-\u9fffA-Za-z0-9]{0,20}[\-_/][A-Za-z0-9\-_/]+$"
)


def normalize_mall_pdf_text(text: str) -> str:
    raw = (text or "").translate(_RADICAL_MAP)
    raw = raw.replace("\u3000", " ")
    # 单字间异常空格：算 力 → 算力
    raw = re.sub(r"(?<=[\u4e00-\u9fff])\s+(?=[\u4e00-\u9fff])", "", raw)
    return raw


def parse_mall_acceptance_goods(text: str) -> List[Dict[str, Any]]:
    body = normalize_mall_pdf_text(text)
    if not body.strip():
        return []
    compact = re.sub(r"\s+", "", body)
    if not any(
        k in compact
        for k in ("采购清单", "采购凭证", "服务分项名称", "商品名称", "货物名称")
    ):
        return []

    lines = _prepare_lines(body)
    # 批量集采商品表优先
    goods_tbl = _filter_goods(_parse_goods_vertical(lines))
    if goods_tbl:
        return _dedupe_goods(goods_tbl)

    # 服务/定点：展平行正则更稳；有结果就不再混入技术指标里的竖排噪声
    flat = _filter_goods(_parse_service_collapsed(body))
    if flat:
        return _dedupe_goods(flat)

    vertical = _filter_goods(_parse_service_vertical(lines))
    return _dedupe_goods(vertical)


def _prepare_lines(text: str) -> List[str]:
    raw_lines = [re.sub(r"[ \t]+", " ", ln).strip() for ln in text.splitlines()]
    raw_lines = [ln for ln in raw_lines if ln]
    out: List[str] = []
    for ln in raw_lines:
        out.extend(_explode_glued(ln))
    # 去连续重复
    deduped: List[str] = []
    for ln in out:
        if deduped and deduped[-1] == ln:
            continue
        deduped.append(ln)
    return deduped


def _explode_glued(ln: str) -> List[str]:
    """把粘在一起的表头/单位+正文拆开。"""
    # 表头字段粘连：编号编号服务分项名称...
    if _HEADER_GLUE.search(re.sub(r"\s+", "", ln)) and len(ln) > 20:
        parts = re.findall(
            r"编号|序号|服务分项名称|货物名称|商品名称|产品名称|品牌|型号|"
            r"数量|单价|折扣率|优惠后小计|小计|计量单位|单位|技术指标",
            ln,
        )
        if len(parts) >= 4:
            # 保留表头前的供应商等前缀
            head = re.split(
                r"(?:编号|序号|服务分项名称|商品名称)", ln, maxsplit=1
            )[0].strip()
            tokens = []
            if head and len(head) < 80:
                tokens.append(head.rstrip("：:"))
            # 去重连续
            prev = None
            for p in parts:
                if p != prev:
                    tokens.append(p)
                prev = p
            return tokens or [ln]

    # 单位粘正文：张一张办公椅其他服务要求...
    m = re.match(rf"^({_UNIT_ALT})(.+)$", ln)
    if m and not _is_unit_token(ln):
        unit, rest = m.group(1), m.group(2).strip()
        chunks = [unit]
        stop = _STOP_TAIL.search(rest)
        if stop and stop.start() > 0:
            chunks.append(rest[: stop.start()].strip())
            chunks.append(rest[stop.start() :])
        elif rest:
            chunks.append(rest)
        return [c for c in chunks if c]

    # 其他服务要求粘在行尾
    stop = _STOP_TAIL.search(ln)
    if stop and stop.start() > 0 and stop.start() < len(ln):
        left = ln[: stop.start()].strip()
        right = ln[stop.start() :].strip()
        if left and right:
            return [left, right]
    return [ln]


def _parse_service_collapsed(text: str) -> List[Dict[str, Any]]:
    """在展平正文上抓「序号 名称 数量 单位」。"""
    flat = re.sub(r"\s+", " ", text)
    # 截到清单表区域
    start = -1
    for key in ("服务分项名称", "货物名称", "技术指标"):
        i = flat.find(key)
        if i >= 0:
            start = i if start < 0 else min(start, i)
    if start < 0:
        return []
    segment = flat[start:]
    end_m = _STOP_TAIL.search(segment)
    # 不要在第一个「参数」就切太狠；服务表用其他服务要求
    end_m = re.search(r"其他服务要求|其他要求", segment)
    if end_m:
        segment = segment[: end_m.start()]

    goods: List[Dict[str, Any]] = []
    for m in _SERVICE_ROW.finditer(segment):
        name = _clean(m.group(2))
        if not name or len(name) < 2:
            continue
        if any(k in name for k in ("服务分项名称", "技术指标", "计量单位", "编号")):
            continue
        try:
            qty = float(m.group(3))
        except ValueError:
            qty = m.group(3)
        spec = _clean(m.group(5) or "")
        if spec:
            spec = _STOP_TAIL.split(spec, maxsplit=1)[0].strip()
        item: Dict[str, Any] = {
            "name": name[:120],
            "quantity": qty,
            "unit": m.group(4),
            "category": "服务" if "服务" in name else None,
            "extra": {"seq": m.group(1), "source": "mall_service_flat"},
        }
        if spec and len(spec) >= 2:
            item["spec"] = spec[:500]
        goods.append(item)
    return goods


def _parse_service_vertical(lines: List[str]) -> List[Dict[str, Any]]:
    header_at = -1
    for i, ln in enumerate(lines):
        if ln in {"服务分项名称", "货物名称"} or (
            "服务分项名称" in ln and len(ln) < 40
        ):
            header_at = i
            break
    if header_at < 0:
        return []

    # 跳过表头字段
    fields = {
        "编号",
        "序号",
        "服务分项名称",
        "货物名称",
        "数量",
        "计量单位",
        "单位",
        "技术指标",
    }
    i = header_at
    while i < len(lines) and lines[i] in fields:
        i += 1

    goods: List[Dict[str, Any]] = []
    while i < len(lines):
        if lines[i].startswith("其他服务要求") or lines[i] in {"需求内容", "参数"}:
            break
        if not _SEQ.match(lines[i]):
            i += 1
            continue
        seq = lines[i]
        i += 1
        name_parts: List[str] = []
        while i < len(lines) and not _SEQ.match(lines[i]):
            if lines[i] in fields or lines[i].startswith("其他服务要求"):
                break
            if _is_qty_unit_pair(lines, i):
                break
            name_parts.append(lines[i])
            i += 1
            if len(name_parts) >= 4:
                break
        if not name_parts:
            continue
        qty = None
        unit = None
        if i < len(lines) and _MONEY.match(lines[i].replace(",", "")):
            try:
                qty = float(lines[i].replace(",", ""))
            except ValueError:
                qty = lines[i]
            i += 1
        if i < len(lines) and _is_unit_token(lines[i]):
            unit = lines[i]
            i += 1
        spec_parts: List[str] = []
        while i < len(lines) and not _SEQ.match(lines[i]):
            if lines[i].startswith("其他服务要求") or lines[i] == "需求内容":
                break
            spec_parts.append(lines[i])
            i += 1
            if sum(len(x) for x in spec_parts) > 600:
                break
        name = _clean("".join(name_parts))
        if not name:
            continue
        item: Dict[str, Any] = {
            "name": name[:120],
            "quantity": qty,
            "unit": unit,
            "category": "服务" if "服务" in name else None,
            "extra": {"seq": seq, "source": "mall_service_vertical"},
        }
        spec = _clean(" ".join(spec_parts))
        if spec:
            item["spec"] = spec[:500]
        goods.append(item)
    return goods


def _parse_goods_vertical(lines: List[str]) -> List[Dict[str, Any]]:
    header_at = -1
    for i, ln in enumerate(lines):
        if ln == "商品名称" or (ln.startswith("商品名称") and len(ln) < 20):
            header_at = i
            break
        if "商品名称" in ln and "品牌" in ln:
            header_at = i
            break
    if header_at < 0:
        return []

    fields = {
        "序号",
        "编号",
        "商品名称",
        "产品名称",
        "品牌",
        "型号",
        "数量",
        "单价",
        "折扣率",
        "优惠后小计",
        "小计",
        "单位",
        "计量单位",
        "技术指标",
    }
    i = header_at
    while i < len(lines) and (
        lines[i] in fields or re.sub(r"\s+", "", lines[i]) in fields
    ):
        i += 1

    goods: List[Dict[str, Any]] = []
    while i < len(lines):
        if lines[i].startswith("参数") or lines[i].startswith("其他"):
            # 参数区不再解析新商品行
            break
        if not _SEQ.match(lines[i]):
            i += 1
            continue
        if i + 1 >= len(lines) or lines[i + 1] in fields:
            i += 1
            continue
        if _is_unit_token(lines[i + 1]) or lines[i + 1].startswith("参数"):
            i += 1
            continue
        if _MONEY.match(lines[i + 1].replace(",", "")) and "." in lines[i + 1]:
            i += 1
            continue

        seq = lines[i]
        i += 1
        name_parts: List[str] = []
        while i < len(lines) and not _looks_brand_line(lines, i):
            if _SEQ.match(lines[i]) and name_parts:
                # HM740-0 / 91 → 型号被拆行，数字是型号后缀不是新序号
                prev = name_parts[-1]
                if re.search(r"[A-Za-z0-9\-]$", prev):
                    name_parts.append(lines[i])
                    i += 1
                    continue
                break
            if lines[i].startswith("参数") or lines[i] in fields:
                break
            name_parts.append(lines[i])
            i += 1
            if len(name_parts) >= 8:
                break
        brand = None
        if i < len(lines) and _looks_brand_line(lines, i):
            brand_parts = [lines[i]]
            i += 1
            if i < len(lines) and lines[i].startswith("/"):
                brand_parts.append(lines[i])
                i += 1
            brand = _clean("".join(brand_parts))
        model_parts: List[str] = []
        while i < len(lines) and not _MONEY.match(lines[i].replace(",", "")):
            if (
                _SEQ.match(lines[i])
                or lines[i].startswith("参数")
                or _is_unit_token(lines[i])
                or lines[i] in fields
            ):
                break
            if _looks_brand_line(lines, i):
                break
            model_parts.append(lines[i])
            i += 1
            if len(model_parts) >= 6:
                break
        qty = None
        unit = None
        if i < len(lines) and _MONEY.match(lines[i].replace(",", "")):
            raw_q = lines[i].replace(",", "")
            try:
                qty = float(raw_q)
            except ValueError:
                qty = raw_q
            i += 1
        if i < len(lines) and _is_unit_token(lines[i]):
            unit = lines[i]
            i += 1
        money_run = 0
        while i < len(lines) and money_run < 6:
            tok = lines[i].replace(",", "")
            if _MONEY.match(tok) or re.match(r"^0\.\d+$", tok):
                i += 1
                money_run += 1
            else:
                break

        name = _clean("".join(name_parts))
        model = _clean("".join(model_parts)) or None
        if not name:
            continue
        if not model and len(name_parts) > 1:
            head, tail = name_parts[0], _clean("".join(name_parts[1:]))
            if tail and re.search(r"[A-Za-z0-9]", tail):
                name = _clean(head)
                model = tail
        item: Dict[str, Any] = {
            "name": name[:120],
            "brand": brand or None,
            "model": model[:80] if model else None,
            "quantity": qty,
            "unit": unit,
            "category": "货物",
            "extra": {"seq": seq, "source": "mall_goods_vertical"},
        }
        goods.append(item)
        # 表体通常一行商品后接参数，下一轮若不是清晰新品名则由参数 break
    return goods


def _is_qty_unit_pair(lines: List[str], i: int) -> bool:
    if i >= len(lines):
        return False
    if _is_unit_token(lines[i]):
        return True
    if _MONEY.match(lines[i].replace(",", "")):
        if i + 1 < len(lines) and _is_unit_token(lines[i + 1]):
            return True
    return False


def _looks_brand_line(lines: List[str], i: int) -> bool:
    """品牌行：华为 + /HUAWEI，或 华为/HUAWEI。不要把「华为擎云」品名当成品牌。"""
    t = lines[i]
    if not t or t.startswith("参数"):
        return False
    if t.startswith("/"):
        return True
    if "/" in t and re.search(r"[A-Za-z]{2,}", t):
        return True
    nxt = lines[i + 1] if i + 1 < len(lines) else ""
    # 仅当下一行是 /英文 时，当前短中文才是品牌
    if re.fullmatch(r"[\u4e00-\u9fffA-Za-z]{2,12}", t) and nxt.startswith("/"):
        return True
    return False


def _clean(value: str) -> str:
    text = re.sub(r"\s+", " ", (value or "").strip())
    text = text.strip(" -/、，,;；")
    return text


def _filter_goods(goods: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for item in goods:
        name = str(item.get("name") or "")
        if not name or len(name) < 2:
            continue
        if name in {"长", "页", "门", "网", "项", "目"}:
            continue
        if re.fullmatch(r"[\d,\.]+", name):
            continue
        if any(
            k in name
            for k in (
                "升级服务",
                "具体规格",
                "光驱",
                "以采购人",
                "GB/T",
                "SQuaRE",
                "测试实施",
                "℃",
                "H.26",
                "接⼝",
                "接口数量",
            )
        ):
            continue
        src = (
            (item.get("extra") or {}).get("source")
            if isinstance(item.get("extra"), dict)
            else ""
        )
        qty = item.get("quantity")
        unit = item.get("unit")
        if src == "mall_goods_vertical":
            if qty in (None, ""):
                continue
            if not item.get("brand") and not item.get("model") and len(name) <= 2:
                continue
            # 数量像年份/单价
            try:
                qf = float(qty)
                if qf >= 1000 or (0 < qf < 1 and not unit):
                    continue
            except (TypeError, ValueError):
                pass
        elif src in {"mall_service_flat", "mall_service_vertical"}:
            if qty in (None, "") or not unit:
                continue
            if len(name) > 60:
                continue
            if re.search(r"[（(：《%]|Lux|Smart", name):
                continue
        out.append(item)
    return out


def _dedupe_goods(goods: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    seen = set()
    out: List[Dict[str, Any]] = []
    for item in goods:
        key = (
            str(item.get("name") or ""),
            str(item.get("brand") or ""),
            str(item.get("model") or ""),
            str(item.get("quantity") or ""),
            str(item.get("unit") or ""),
        )
        if key in seen:
            continue
        seen.add(key)
        out.append(item)
    return out
