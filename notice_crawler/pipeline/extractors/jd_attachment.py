"""京东公告附件里的采购清单。

详情 JSON 里商品名经常是「详见附件」，真正的名称、品牌、型号、数量在 PDF 表格中。
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

_PLACEHOLDERS = (
    "详见附件",
    "见附件",
    "详见采购需求",
    "详情见附件",
    "详见询比",
    "详见询比文件",
    "详见询比采购文件",
    "按附件",
    "以附件为准",
    "附件要求",
    "按采购需求",
)

# 单位放在数量前面，用来锚定一行。规格型号里允许空格。
# 更长的单位写前面，避免 m 抢先匹配 m2；支持「个/天」「张/天」「平米」等。
_UNITS_CORE = (
    "平方米|平米|平方|延长米|台班|工日|人次|m2|m²|㎡|ml|ML|kg|KG|"
    "个|只|台|套|件|支|把|盒|包|箱|桶|卷|本|张|米|批|条|双|辆|项|次|部|"
    "人|天|月|年|份|组|根|片|瓶|袋|令|升|公斤|千克|斤|吨|副|架|块|"
    "顶|面|盘|筒|听|提|打|捆|扎|枚|颗|粒|盏|具|扇|幅|间|座|栋|幢|处|"
    "车|孔|榀|樘|付|板|节|套装|位|名|点|m"
)
_UNITS = rf"(?:{_UNITS_CORE})(?:/[天日月年场次时])?"
_UNIT_FULLMATCH = re.compile(rf"^{_UNITS}$")


def _is_unit_token(token: str) -> bool:
    return bool(token and _UNIT_FULLMATCH.match(token.strip()))
_HEADER_HINT = re.compile(r"序号|货物名称|品名|项目名称|耗材名称|产品名称")

# 优先抓带清单语义的段落，避免长询比文件只喂封面/目录给模型
_FOCUS_KEYWORDS = (
    "采购清单",
    "货物一览",
    "货物清单",
    "标的清单",
    "工程量",
    "服务内容",
    "采购内容",
    "项目需求",
    "技术要求",
    "需求一览",
    "报价参数",
    "报价参考",
    "明细表",
    "一览表",
    "租赁",
    "采购需求",
    "实训耗材",
    "办公用品",
    "产品名称",
    "项目名称",
    "货物名称",
)

_EMPTY_TOKEN = {"", "/", "-", "—", "－", "无", "暂无", "无品牌", "不限"}


def goods_are_placeholder(goods: Optional[list]) -> bool:
    """详情/抽取结果是否只是占位，没有可入库的产品行。

    「详见附件」算占位；有真实名称的服务/工程/货物行不算占位
    （即使缺品牌型号，也不能再当壳丢掉）。
    """
    if not goods:
        return True
    rows = [g for g in goods if isinstance(g, dict)]
    if not rows:
        return True
    if all(_row_is_placeholder(g) for g in rows):
        return True
    return len(rows) == 1 and _is_shell(rows[0])


def should_replace_goods_with_attachment(
    existing: Optional[list],
    attachment_goods: Optional[list],
    *,
    detail: Optional[dict] = None,
) -> bool:
    """附件抽出有效标的时，是否覆盖详情里的商品行。

    京东常只有一行摘要 SKU（项目名/文体服务），明细在 PDF；只要附件有清单就覆盖。
    """
    if not attachment_goods or goods_are_placeholder(attachment_goods):
        return False
    if goods_are_placeholder(existing):
        return True
    rows = [g for g in (existing or []) if isinstance(g, dict)]
    if len(rows) <= 1:
        return True
    if len(attachment_goods) > len(rows):
        return True
    # 旧数据是粘连长句/政策杂文，附件是短品名清单时仍覆盖
    def _avg_name_len(items: list) -> float:
        names = [len(str((g or {}).get("name") or (g or {}).get("product_name") or "")) for g in items]
        return sum(names) / max(len(names), 1)

    if _avg_name_len(rows) >= 40 and _avg_name_len(attachment_goods) <= 24:
        return True
    nested = detail.get("detail") if isinstance(detail, dict) else None
    demand = (
        nested.get("auctionDemandInfo")
        if isinstance(nested, dict)
        else {}
    )
    if not isinstance(demand, dict):
        demand = {}
    remark = str(demand.get("demandRemark") or "") + str(
        demand.get("attachRequestedRemark") or ""
    )
    if demand.get("attachRequested") in (1, "1", True) or any(
        token in remark for token in _PLACEHOLDERS
    ):
        return True
    return False


def _has_qty_or_unit(item: Dict[str, Any]) -> bool:
    qty = item.get("quantity")
    if qty not in (None, "", [], 0, "0"):
        return True
    unit = str(item.get("unit") or "").strip()
    return bool(unit)


def _is_shell(item: Dict[str, Any]) -> bool:
    """API 摘要壳：详见附件、或整单项目名且无数量单位。"""
    if _row_is_placeholder(item):
        return True
    name = str(item.get("name") or item.get("product_name") or "").strip()
    if not name:
        return True
    # 有数量/单位的明确标的行，保留
    if _has_qty_or_unit(item):
        return False
    brand = str(item.get("brand") or "").strip()
    model = str(item.get("model") or "").strip()
    spec = str(item.get("spec") or "").strip()
    if brand not in _EMPTY_TOKEN or model not in _EMPTY_TOKEN or len(spec) >= 8:
        return False
    # 长项目名、无明细 → 常见摘要壳
    if len(name) >= 16 and any(
        token in name for token in ("项目", "采购", "询比", "服务", "工程")
    ):
        return True
    if "+" in name and len(name) >= 20:
        return True
    return False


def _row_is_placeholder(item: Dict[str, Any]) -> bool:
    blob = "".join(
        str(item.get(key) or "")
        for key in ("name", "product_name", "brand", "model", "spec")
    )
    blob = re.sub(r"\s+", "", blob)
    if not blob:
        return True
    return any(token in blob for token in _PLACEHOLDERS)


def focus_product_sections(text: str, *, max_chars: int = 12000) -> str:
    """从长附件正文里优先截取含清单/标的的段落，供本地模型使用。"""
    raw = (text or "").strip()
    if not raw:
        return ""
    if len(raw) <= max_chars:
        return raw
    lines = raw.splitlines()
    hits: List[int] = []
    for i, line in enumerate(lines):
        if any(key in line for key in _FOCUS_KEYWORDS):
            hits.append(i)
        elif _header_kind(line):
            hits.append(i)
    if not hits:
        # 无关键词：头尾各取一段，中间常见清单
        head = raw[: max_chars // 3]
        mid_start = max(0, len(raw) // 2 - max_chars // 3)
        mid = raw[mid_start : mid_start + max_chars // 3]
        tail = raw[-(max_chars // 3) :]
        return f"{head}\n\n...\n\n{mid}\n\n...\n\n{tail}"[:max_chars]

    chunks: List[str] = []
    used = 0
    window = 80
    for idx in hits:
        start = max(0, idx - 2)
        end = min(len(lines), idx + window)
        block = "\n".join(lines[start:end]).strip()
        if not block:
            continue
        if used + len(block) + 2 > max_chars:
            remain = max_chars - used - 2
            if remain > 200:
                chunks.append(block[:remain])
            break
        chunks.append(block)
        used += len(block) + 2
    return "\n\n".join(chunks).strip() or raw[:max_chars]


_UNIT_ROW = re.compile(
    rf"^(?:(\d+)\s+)?(.+?)\s+({_UNITS})\s+"
    rf"([0-9]+(?:\.[0-9]+)?)(?:\s+([0-9]+(?:\.[0-9]+)?))?(?:\s+(.*))?$"
)
# 数量在单位前：1 活动策划与设计 1 项
_QTY_UNIT_ROW = re.compile(
    rf"^(?:(\d+)\s+)?(.+?)\s+([0-9]+(?:\.[0-9]+)?)\s+({_UNITS})(?:\s+(.*))?$"
)
_UNIT_ONLY = re.compile(
    rf"^/?({_UNITS})\s+([0-9]+(?:\.[0-9]+)?)(?:\s+(.*))?$"
)
# 缺单位：序号 名称 规格 数量 备注（办公报价偶发）
_QTY_NO_UNIT_ROW = re.compile(
    r"^(\d+)\s+(\S+)\s+(.+?)\s+([0-9]+(?:\.[0-9]+)?)\s+(.*)$"
)
_SPEC_ROW = re.compile(
    r"^(\d+)\s+(\S+)\s+(.+?)\s+([0-9]+(?:\.[0-9]+)?)\s*(.*)$"
)
_SECTION_HEAD = re.compile(r"^\d{1,2}[\.、．][\u4e00-\u9fff].{0,20}$")
# 采购内容里的服务分项标题：1.活动服务内容概述 / 1.参会人才组织
_SERVICE_ITEM_HEAD = re.compile(
    r"^(\d{1,2})[\.、．]\s*([\u4e00-\u9fff][\u4e00-\u9fffA-Za-z0-9（）()\-、]{1,40})$"
)
_MAX_GOODS = 500
_FALSE_HEADER_TOKENS = (
    "注：",
    "注意：",
    "条款名称",
    "依据的标准",
    "资格要求",
    "证明材料",
    "保证金",
    "关系单位",
    "法定代表人",
    "供应商单位名称",
    "中小企业",
)


def parse_jd_attachment_goods(text: str) -> List[Dict[str, Any]]:
    """从附件正文抽出采购清单。多表合并去重，避免只拿到一部分。"""
    if not text or not text.strip():
        return []
    lines = _norm_lines(text)
    candidates = [
        _parse_goods_from_lines(lines),
        _parse_vertical_quote_goods(lines),
        _parse_tech_param_trailers(lines),
        _parse_service_section_items(lines),
    ]
    # PDF 竖排/倒序抽取时，反转行序常能还原报价单
    rev_lines = list(reversed(lines))
    candidates.append(_parse_goods_from_lines(rev_lines))
    candidates.append(_parse_vertical_quote_goods(rev_lines))

    best: List[Dict[str, Any]] = []
    best_score = -1
    for goods, score in candidates:
        goods = _filter_junk_goods(goods)
        if not goods:
            continue
        score = max(score, 0) + len(goods) * 8 + _goods_quality(goods) * 3
        if score > best_score:
            best_score = score
            best = goods
    return best


def _filter_junk_goods(goods: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    junk_tokens = (
        "微型企业",
        "中型企业",
        "履约担保",
        "报价有效期",
        "踏勘现场",
        "投标保证金",
        "残疾人福利",
        "划分标准所属行业",
        "可靠的数据支撑",
        "平台界面应在",
        "调节步长",
        "营业收入",
        "资格证明文件",
        "响应文件的签字",
        "采购人信息",
        "采购代理机构信息",
        "项目联系方式",
        "法定代表人或授权",
    )
    out: List[Dict[str, Any]] = []
    for item in goods:
        if not isinstance(item, dict):
            continue
        name = str(item.get("name") or "").strip()
        blob = name + str(item.get("spec") or "") + str(item.get("model") or "")
        if not name or _is_section_noise_name(name):
            continue
        if any(tok in blob for tok in junk_tokens):
            continue
        if len(name) >= 60:
            continue
        if name.startswith("人以下"):
            continue
        out.append(item)
    return out


def _goods_quality(goods: List[Dict[str, Any]]) -> int:
    """短品名+有数量的清单优先于粘连了技术说明的长行。"""
    if not goods:
        return 0
    score = 0
    for item in goods:
        name = str(item.get("name") or "")
        if item.get("quantity") not in (None, "", []):
            score += 3
        if 2 <= len(name) <= 24:
            score += 2
        elif len(name) <= 40:
            score += 1
        if item.get("unit"):
            score += 1
    return score


def _norm_lines(text: str) -> List[str]:
    lines = [re.sub(r"[ \t]+", " ", ln).strip() for ln in (text or "").splitlines()]
    return [ln for ln in lines if ln]


def _parse_goods_from_lines(lines: List[str]) -> tuple:
    headers: List[tuple] = []
    for i, line in enumerate(lines):
        detected = _header_kind(line)
        if detected:
            headers.append((i, detected[0], detected[1], detected[2], line))
    if not headers:
        # 无表头时仍尝试整篇工程量行（名称 单位 数量）
        goods = _parse_unit_table(lines, "qty_amt", split_mode="spec")
        return (goods, len(goods) * 8) if goods else ([], -1)

    segments: List[tuple] = []
    for hi, (idx, kind, roles, split_mode, header_line) in enumerate(headers):
        end = headers[hi + 1][0] if hi + 1 < len(headers) else len(lines)
        body = lines[idx + 1 : end]
        if kind == "spec_qty":
            goods = _parse_spec_qty(body)
        elif kind == "model_only":
            goods = _parse_model_only(body)
        elif kind == "qty_unit":
            goods = _parse_qty_unit_table(body)
        elif kind == "tech_param":
            goods = _parse_tech_param_trailers(body)[0]
        else:
            goods = _parse_unit_table(body, roles, split_mode=split_mode)
            # 常规单位表为空时，再试数量在前
            if len(goods) < 2:
                alt = _parse_qty_unit_table(body)
                if len(alt) > len(goods):
                    goods = alt
        score = _table_score(header_line, goods)
        segments.append((score, goods, header_line))

    if not segments:
        return [], -1

    # 报价明细/服务项目表一旦像样，直接用它（避免和技术要求段合并脏数据）
    quote_segs = []
    for score, goods, header_line in segments:
        compact = re.sub(r"\s+", "", header_line or "")
        goods = _filter_junk_goods(goods)
        if not goods:
            continue
        if "服务项目" in compact or "报价明细" in compact:
            quote_segs.append((len(goods) * 20 + _goods_quality(goods), goods, header_line))
        elif score >= 40:
            quote_segs.append((score + _goods_quality(goods), goods, header_line))
    if not quote_segs:
        return [], -1

    # 优先：真正的报价明细（有单价/合计），排除「详细技术要求」需求表
    def _is_quote_header(header_line: str) -> bool:
        compact = re.sub(r"\s+", "", header_line or "")
        if "详细技术要求" in compact or "技术要求" in compact:
            return False
        return "服务项目" in compact and (
            "单价" in compact or "合计" in compact or "报价" in compact
        )

    service_quotes = [
        x for x in quote_segs if _is_quote_header(x[2]) and len(x[1]) >= 3
    ]
    if service_quotes:
        # 品名更短、带单位的更像报价行
        _sc, best, _h = max(
            service_quotes,
            key=lambda x: (_goods_quality(x[1]), len(x[1]), x[0]),
        )
        return best, _sc

    best_score, best, best_header = max(quote_segs, key=lambda x: (x[0], len(x[1])))
    # 仅合并「质量接近」的多表，避免长技术说明污染报价清单
    merged: List[Dict[str, Any]] = []
    seen: set = set()
    best_q = _goods_quality(best)
    merge_score = best_score
    for score, goods, header_line in sorted(quote_segs, key=lambda x: x[0], reverse=True):
        compact = re.sub(r"\s+", "", header_line or "")
        if any(k in compact for k in ("认证证书", "节能标志", "环境标志")):
            continue
        if _goods_quality(goods) < max(4, best_q * 0.4) and len(goods) < len(best):
            continue
        merge_score += score
        for item in goods:
            key = (
                str(item.get("name") or "").strip(),
                str(item.get("unit") or "").strip(),
                str(item.get("quantity") or "").strip(),
                str(item.get("model") or item.get("spec") or "").strip()[:48],
            )
            if not key[0] or key in seen:
                continue
            seen.add(key)
            merged.append(item)
            if len(merged) >= _MAX_GOODS:
                break
        if len(merged) >= _MAX_GOODS:
            break

    if _goods_quality(merged) >= _goods_quality(best) and len(merged) > len(best):
        return merged, merge_score
    return best, best_score


def _parse_vertical_quote_goods(lines: List[str]) -> tuple:
    """处理「序号/名称/规格/单位/数量」各占一行的报价单（常见于 PDF 列阅读顺序错乱）。"""
    header_at = -1
    for i in range(len(lines) - 4):
        window = "".join(lines[i : i + 6])
        if (
            "序号" in window
            and "名称" in window
            and ("规格" in window or "型号" in window)
            and "数量" in window
        ):
            # 表头本身是连续短行
            if lines[i] in {"序号", "名称"} or (
                lines[i] == "序号" or (i + 1 < len(lines) and lines[i + 1] == "名称")
            ):
                header_at = i
                break
    if header_at < 0:
        return [], -1

    # 跳过表头字段行
    body_start = header_at
    while body_start < len(lines) and lines[body_start] in {
        "序号",
        "名称",
        "规格型号",
        "规格",
        "型号",
        "单位",
        "数量",
        "单价",
        "总价",
        "金额",
        "备注",
    }:
        body_start += 1

    goods: List[Dict[str, Any]] = []
    stop_names = {"合计", "小计", "报价人：", "联系电话：", "报价单位（盖章）："}
    last_seq = 0
    # 倒序 PDF 时常把后半页行堆在表头前，表头前后两段都要扫
    scan_ranges = [(0, header_at), (body_start, len(lines))]

    def _looks_seq(idx: int) -> bool:
        if idx >= len(lines) or not re.fullmatch(r"\d{1,3}", lines[idx]):
            return False
        nxt = lines[idx + 1] if idx + 1 < len(lines) else ""
        if not nxt or _is_unit_token(nxt) or nxt in stop_names:
            return False
        if re.fullmatch(r"\d+(?:\.\d+)?", nxt):
            return False
        return True

    def _looks_name(idx: int) -> bool:
        if idx >= len(lines):
            return False
        token = lines[idx]
        if _is_unit_token(token) or token in stop_names or token.startswith("日期"):
            return False
        if re.fullmatch(r"\d+(?:\.\d+)?", token):
            return False
        if _looks_seq(idx):
            return False
        # 至少一个中文，避免英文噪声行当品名
        return bool(re.search(r"[\u4e00-\u9fff]", token))

    def _number_is_next_seq(idx: int) -> bool:
        """单位后的数字若刚好是 last_seq+1 且后接品名，则是下一序号而非数量。"""
        if not _looks_seq(idx):
            return False
        try:
            n = int(lines[idx])
        except ValueError:
            return False
        return last_seq > 0 and n == last_seq + 1

    def _consume_item(start: int) -> tuple:
        """从品名开始读 model/unit/qty，返回 (goods_item_or_None, next_index)。"""
        j = start
        name = lines[j]
        j += 1
        model = None
        unit = None
        qty = None
        if (
            j < len(lines)
            and not _is_unit_token(lines[j])
            and not re.fullmatch(r"\d+(?:\.\d+)?", lines[j])
            and lines[j] not in stop_names
            and not _looks_seq(j)
        ):
            model = lines[j]
            j += 1
        if j < len(lines) and _is_unit_token(lines[j]):
            unit = lines[j]
            j += 1
        if j < len(lines) and re.fullmatch(r"\d+(?:\.\d+)?", lines[j]):
            if _number_is_next_seq(j):
                # PDF 漏抽数量：默认 1
                qty = 1.0
            else:
                qty = _num(lines[j])
                j += 1
        for _ in range(2):
            if (
                j < len(lines)
                and re.fullmatch(r"\d+(?:\.\d+)?", lines[j])
                and not _looks_seq(j)
            ):
                j += 1
            else:
                break
        if name and qty is not None:
            return _goods(name, None, model, unit, qty, None, None, None), j
        return None, j

    for range_start, range_end in scan_ranges:
        i = range_start
        while i < range_end:
            if _looks_seq(i):
                try:
                    last_seq = int(lines[i])
                except ValueError:
                    last_seq = last_seq + 1
                i += 1
                if i >= range_end or not _looks_name(i):
                    continue
                item, next_i = _consume_item(i)
                i = min(next_i, range_end)
                if item and item.get("name"):
                    goods.append(item)
            elif _looks_name(i) and goods:
                # 缺序号的续行（PDF 抽字常见）
                item, next_i = _consume_item(i)
                if item and item.get("name"):
                    goods.append(item)
                    i = min(next_i, range_end)
                else:
                    i += 1
            else:
                i += 1
            if len(goods) >= _MAX_GOODS:
                break
        if len(goods) >= _MAX_GOODS:
            break
    # 去重（前后两段可能重叠）
    deduped: List[Dict[str, Any]] = []
    seen: set = set()
    for item in goods:
        key = (
            str(item.get("name") or "").strip(),
            str(item.get("unit") or "").strip(),
            str(item.get("quantity") or "").strip(),
            str(item.get("model") or "").strip()[:40],
        )
        if not key[0] or key in seen:
            continue
        seen.add(key)
        deduped.append(item)
    score = len(deduped) * 10 + (50 if len(deduped) >= 3 else 0)
    return deduped, score


def _table_score(header_line: str, goods: List[Dict[str, Any]]) -> int:
    compact = re.sub(r"\s+", "", header_line or "")
    score = len(goods) * 10
    if any(k in compact for k in ("认证证书", "节能标志", "环境标志", "制造商")):
        score -= 80
    if any(k in compact for k in _FALSE_HEADER_TOKENS):
        score -= 100
    if "服务项目" in compact or "报价明细" in compact:
        score += 60
    if "单位" in compact and "数量" in compact:
        score += 40
    if any(
        k in compact
        for k in ("货物名称", "项目名称", "耗材名称", "产品名称", "品名", "服务项目")
    ):
        score += 30
    if "材质" in compact or "规格" in compact:
        score += 10
    if "技术参数" in compact:
        score += 20
    return score


def _header_kind(line: str) -> Optional[tuple]:
    """返回 (kind, number_roles, split_mode)。"""
    raw = (line or "").strip()
    compact = re.sub(r"\s+", "", raw)
    if any(tok in raw[:6] or tok in compact[:8] for tok in ("注：", "注意：", "注:")):
        return None
    if any(tok in compact for tok in _FALSE_HEADER_TOKENS):
        # 技术参数清单本身要保留
        if "技术参数" not in compact:
            return None
    has_name = any(
        k in compact
        for k in ("货物名称", "品名", "项目名称", "产品名称", "服务项目", "名称", "耗材名称")
    )
    if "序号" not in compact and not has_name:
        return None
    if not has_name and "序号" in compact and "数量" not in compact:
        return None

    split_mode = (
        "spec"
        if ("材质" in compact or "规格" in compact) and "品牌" not in compact
        else "brand_model"
    )
    # 名称 + 技术参数 + 单位 + 数量：按块末「套 1」收口
    if "技术参数" in compact and "数量" in compact:
        return "tech_param", _number_roles(compact), split_mode
    # 数量在单位前，或服务项目报价明细
    if "服务项目" in compact and "数量" in compact:
        return "qty_unit", _number_roles(compact), split_mode
    if "数量" in compact and "单位" in compact and compact.find("数量") < compact.find("单位"):
        return "qty_unit", _number_roles(compact), split_mode
    if "品名" in compact and "数量" in compact and "单位" not in compact:
        return "spec_qty", _number_roles(compact), split_mode
    if "单位" in compact and ("数量" in compact or has_name):
        return "unit_qty", _number_roles(compact), split_mode
    if ("型号" in compact or "规格" in compact) and "单位" not in compact and has_name:
        return "model_only", "qty_amt", split_mode
    if "序号" in compact and has_name:
        # 有数量无单位时仍按 数量+单位 行试解析
        if "数量" in compact and "单位" not in compact:
            return "qty_unit", _number_roles(compact), split_mode
        return "unit_qty", _number_roles(compact), split_mode
    return None


def _parse_qty_unit_table(lines: List[str]) -> List[Dict[str, Any]]:
    """解析「名称 数量 单位」列序（报价明细常见）。"""
    goods: List[Dict[str, Any]] = []
    for line in lines:
        if _stop_line(line, started=bool(goods)):
            break
        if _SECTION_HEAD.match(line) or _is_page_footer(line):
            continue
        if line.startswith("总报价") or line.startswith("合计"):
            break
        match = _QTY_UNIT_ROW.match(line)
        if not match:
            # 再试常规 单位+数量
            item = _parse_unit_row(line, "qty_amt", split_mode="spec")
            if item:
                goods.append(item)
            continue
        name = match.group(2).strip()
        qty = _num(match.group(3))
        unit = match.group(4).strip()
        remark = (match.group(5) or "").strip()
        if not name or name in {"合计", "小计", "名称", "服务项目"}:
            continue
        if _row_is_placeholder({"name": name}):
            continue
        goods.append(_goods(name, None, None, unit, qty, None, None, remark or None))
        if len(goods) >= _MAX_GOODS:
            break
    return [g for g in goods if g.get("name")]


def _parse_tech_param_trailers(lines: List[str]) -> tuple:
    """技术参数表：分项标题在前，块末出现「套 1 / 个 1」收口。"""
    goods: List[Dict[str, Any]] = []
    # 优先一级/二级标题，避免收成「1.3.1 病案管理」过细条目
    title_re = re.compile(
        r"^(\d+(?:\.\d+){0,1})\s+([\u4e00-\u9fff（）()][\u4e00-\u9fffA-Za-z0-9（）()\-+、/]{1,40})$"
    )
    titles: List[tuple] = []  # (index, depth, title)
    for i, line in enumerate(lines):
        if _is_page_footer(line):
            continue
        m = title_re.match(line.strip())
        if not m:
            continue
        title = m.group(2).strip()
        if len(title) < 2 or title.endswith(("：", ":")):
            continue
        if any(tok in title for tok in ("总体要求", "技术标准", "功能要求", "核心功能", "硬件要求")):
            continue
        depth = m.group(1).count(".")
        titles.append((i, depth, title))

    for i, line in enumerate(lines):
        only = _UNIT_ONLY.match(line)
        if not only:
            continue
        # 向回找最近标题，优先 depth 更小者
        cand = [t for t in titles if t[0] < i and i - t[0] <= 80]
        if not cand:
            continue
        cand.sort(key=lambda t: (t[1], -t[0]))
        _idx, _depth, title = cand[0]
        goods.append(
            _goods(title, None, None, only.group(1), _num(only.group(2)), None, None, None)
        )
        if len(goods) >= _MAX_GOODS:
            break
    score = len(goods) * 12 + (40 if len(goods) >= 3 else 0)
    return goods, score


def _parse_service_section_items(lines: List[str]) -> tuple:
    """从「采购内容/项目要求」章节抽服务分项标题。"""
    start = -1
    for i, line in enumerate(lines):
        # 跳过目录行（大量点号）
        if line.count(".") >= 8 or line.count("…") >= 2:
            continue
        if re.search(r"第[四五六七八九十\d]+章.*采购内容", line):
            start = i
            break
        if line.strip() in {"采购内容及项目要求", "三、项目需求", "二、项目需求"}:
            start = i
            break
        if line.startswith("1.活动服务") or line.startswith("1.服务内容"):
            start = i
            break
    if start < 0:
        return [], -1
    goods: List[Dict[str, Any]] = []
    seen: set = set()
    for line in lines[start : start + 250]:
        if goods and re.match(r"^第[一二三四五六七八九十百零\d]+章", line):
            break
        if line.count(".") >= 8:
            continue
        m = _SERVICE_ITEM_HEAD.match(line.strip())
        if not m:
            continue
        name = m.group(2).strip()
        if name in seen:
            continue
        if any(
            tok in name
            for tok in (
                "交付",
                "付款",
                "售后",
                "其他商务",
                "采购项目的其他",
                "拟采购标的",
                "采购人信息",
                "代理机构",
                "联系方式",
                "资格证明",
                "技术文件",
                "商务文件",
                "报价函",
            )
        ):
            continue
        item = _goods(name, None, None, "项", 1.0, None, None, None)
        if not item.get("name"):
            continue
        item["category"] = "服务"
        seen.add(name)
        goods.append(item)
        if len(goods) >= 40:
            break
    if len(goods) < 3:
        return [], -1
    score = len(goods) * 15 + 30
    return goods, score


def _parse_unit_table(
    lines: List[str], roles: str, *, split_mode: str = "brand_model"
) -> List[Dict[str, Any]]:
    goods: List[Dict[str, Any]] = []
    buf: List[str] = []
    for line in lines:
        if _stop_line(line, started=bool(goods)):
            break
        # 工程量分节标题（如「2.屋面防水维修」）跳过，不中断整表
        if _SECTION_HEAD.match(line) or _is_page_footer(line):
            buf = []
            continue
        if _HEADER_HINT.search(line) and ("名称" in line or "品名" in line):
            roles = _number_roles(re.sub(r"\s+", "", line))
            if "材质" in line or ("规格" in line and "品牌" not in line):
                split_mode = "spec"
            buf = []
            continue
        # 材质/规格清单勿启用「无单位」兜底，否则续行「1 桌 4 椅…」会打断缓冲
        allow_no_unit = split_mode != "spec"
        item = _parse_unit_row(
            line, roles, split_mode=split_mode, allow_no_unit=allow_no_unit
        )
        if item:
            goods.append(item)
            buf = []
        else:
            only = _UNIT_ONLY.match(line)
            if only and buf:
                goods.append(
                    _goods_from_block(
                        buf, only.group(1), only.group(2), only.group(3) or ""
                    )
                )
                buf = []
            else:
                buf.append(line)
                # 缓冲过长时丢掉噪声，避免跨到下一张无关表
                if len(buf) > 12:
                    buf = buf[-6:]
        if len(goods) >= _MAX_GOODS:
            break
    return [g for g in goods if g.get("name")]


def _parse_unit_row(
    line: str,
    roles: str,
    *,
    split_mode: str = "brand_model",
    allow_no_unit: bool = True,
) -> Optional[Dict[str, Any]]:
    match = _UNIT_ROW.match(line)
    if match:
        middle = match.group(2).strip()
        unit = match.group(3).strip()
        numbers = [match.group(4)]
        if match.group(5):
            numbers.append(match.group(5))
        remark = (match.group(6) or "").strip()
        name, brand, model, spec = _split_middle(middle, split_mode)
        if not name or name in {"合计", "小计", "名称", "货物名称", "品名", "项目名称"}:
            return None
        if _row_is_placeholder({"name": name, "brand": brand, "model": model, "spec": spec}):
            return None
        qty, price, amount = _assign_numbers(numbers, roles)
        if qty is None:
            return None
        if remark:
            spec = f"{spec}\n{remark}".strip() if spec else remark
        return _goods(name, brand, model, unit, qty, price, amount, spec)

    if not allow_no_unit:
        return None
    # 缺单位行：21 磁吸键盘 华为平板原装磁吸键盘 1 原装…
    m2 = _QTY_NO_UNIT_ROW.match(line)
    if not m2:
        return None
    name = m2.group(2).strip()
    middle = m2.group(3).strip()
    qty = _num(m2.group(4))
    remark = (m2.group(5) or "").strip()
    if not name or qty is None:
        return None
    # 尺寸续行勿当商品：含 84*64*94 / 1 桌 4 椅
    if "*" in middle or "×" in middle or "桌" in name and "椅" in (remark + middle):
        return None
    brand, model, spec = None, None, None
    if split_mode == "spec":
        spec = middle
    else:
        parts = middle.split()
        brand = parts[0] if parts else None
        model = " ".join(parts[1:]) if len(parts) > 1 else None
    if remark:
        spec = f"{spec}\n{remark}".strip() if spec else remark
    if _row_is_placeholder({"name": name, "brand": brand, "model": model, "spec": spec}):
        return None
    return _goods(name, brand, model, None, qty, None, None, spec)


def _split_middle(middle: str, split_mode: str) -> tuple:
    parts = middle.split()
    if not parts:
        return "", None, None, None
    name = parts[0]
    rest_parts = parts[1:]
    # 「X 展架」「LED 背墙」：短英文/型号词并进品名，避免被当成噪声丢掉
    if (
        rest_parts
        and (len(name) <= 3 or name.isascii())
        and re.search(r"[\u4e00-\u9fff]", rest_parts[0] or "")
    ):
        name = f"{name} {rest_parts[0]}"
        rest_parts = rest_parts[1:]
    rest = " ".join(rest_parts).strip()
    if split_mode == "spec":
        return name, None, None, rest or None
    brand = rest_parts[0] if rest_parts else None
    model = " ".join(rest_parts[1:]) if len(rest_parts) > 1 else None
    return name, brand, model, None


def _split_name_brand_model(middle: str) -> tuple:
    name, brand, model, _spec = _split_middle(middle, "brand_model")
    return name, brand, model


def _goods_from_block(buf: List[str], unit: str, qty_s: str, remark: str) -> Dict[str, Any]:
    first = re.sub(r"^\d+\s+", "", (buf[0] if buf else "")).strip()
    parts = first.split()
    name = parts[0] if parts else first
    brand = None
    model = None
    if len(parts) >= 2:
        brand = parts[1]
    if len(parts) >= 3:
        model = " ".join(parts[2:])
    spec_lines = []
    for line in buf[1:]:
        if _SECTION_HEAD.match(line):
            continue
        m = re.match(r"品牌\s*[:：]\s*(.+)", line)
        if m and not brand:
            brand = m.group(1).strip()
        else:
            # 去掉行首单独的 /套 之类残片
            cleaned = re.sub(rf"^/?({_UNITS})$", "", line).strip()
            if cleaned:
                spec_lines.append(cleaned)
    qty, price, amount = _assign_numbers([qty_s], "qty_amt")
    spec = "\n".join(spec_lines).strip()
    if model and spec:
        spec = f"{model}\n{spec}".strip()
        model = None
    elif model and not spec:
        spec = model
        model = None
    if remark:
        spec = f"{spec}\n{remark}".strip() if spec else remark
    return _goods(name, brand, model, unit, qty, price, amount, spec)


def _parse_spec_qty(lines: List[str]) -> List[Dict[str, Any]]:
    goods: List[Dict[str, Any]] = []
    for line in lines:
        if _stop_line(line, started=bool(goods)):
            break
        if _SECTION_HEAD.match(line):
            continue
        match = _SPEC_ROW.match(line)
        if not match:
            continue
        name = match.group(2).strip()
        spec = match.group(3).strip()
        qty = _num(match.group(4))
        remark = (match.group(5) or "").strip()
        if _row_is_placeholder({"name": name}):
            continue
        goods.append(_goods(name, None, spec, None, qty, None, None, remark or None))
        if len(goods) >= _MAX_GOODS:
            break
    return goods


def _parse_model_only(lines: List[str]) -> List[Dict[str, Any]]:
    goods: List[Dict[str, Any]] = []
    for line in lines:
        if _stop_line(line, started=bool(goods)):
            break
        if _SECTION_HEAD.match(line):
            continue
        if not re.match(r"^\d+\s+\S", line):
            continue
        parts = line.split()
        rest = parts[1:]
        if not rest:
            continue
        name = rest[0]
        model = rest[1] if len(rest) >= 3 else None
        spec = " ".join(rest[2:] if len(rest) >= 3 else rest[1:])
        if _row_is_placeholder({"name": name, "model": model}):
            continue
        goods.append(_goods(name, None, model, None, None, None, None, spec))
        if len(goods) >= _MAX_GOODS:
            break
    return goods


def _is_page_footer(line: str) -> bool:
    compact = re.sub(r"\s+", "", line or "")
    if re.fullmatch(r"\d{1,3}", compact or ""):
        # PDF 抽字常见的纯页码行，不能进缓冲否则会吃掉下一品名
        return True
    return bool(re.match(r"^第?\d+页[，,／/]?共?\d+页$", compact)) or bool(
        re.match(r"^第\d+页", compact)
    )


def _stop_line(line: str, *, started: bool) -> bool:
    """只在真正的表尾停；续行/分节/页码不能截断整张清单。"""
    compact = re.sub(r"\s+", "", line)
    if _is_page_footer(line):
        return False
    if compact.startswith(("合计", "合计金额", "总计", "注：", "注:", "注意：", "注意:")):
        return True
    if compact.startswith(("报价人", "联系电话")):
        return True
    # 供应商响应格式等大段说明
    if started and compact.startswith(("本人", "本单位", "法定代表人")):
        return True
    return False


def _number_roles(header: str) -> str:
    compact = re.sub(r"\s+", "", header)
    has_price = "单价" in compact
    has_amount = "小计" in compact or "金额" in compact or "总价" in compact
    if has_price and has_amount:
        return "qty_price_amt"
    if has_price:
        return "qty_price"
    return "qty_amt"


def _is_section_noise_name(name: str) -> bool:
    """技术要求章节标题误匹配，如「1 平台架构」「1.1.1 平台应采用」。"""
    text = (name or "").strip()
    if not text:
        return True
    if len(text) <= 1:
        return True
    if text in {"一", "二", "三", "四", "五", "六", "七", "八", "九", "十"}:
        return True
    if re.match(r"^\d+(\.\d+){0,4}\s+\S+$", text) and len(text) <= 40:
        return True
    if text in {"平台架构", "技术标准", "总体要求", "服务内容", "采购内容"}:
        return True
    return False


def _goods(
    name: str,
    brand: Optional[str],
    model: Optional[str],
    unit: Optional[str],
    qty: Optional[float],
    price: Optional[float],
    amount: Optional[float],
    spec: Optional[str],
) -> Dict[str, Any]:
    clean_name = (name or "").strip()
    if _is_section_noise_name(clean_name):
        return {
            "name": "",
            "category": None,
            "quantity": None,
            "unit": None,
            "brand": None,
            "model": None,
            "unit_price": None,
            "spec": None,
            "amount": None,
        }
    spec_text = (spec or "").strip()
    # 超长「规格」塞进 name 的技术描述不当品名
    if len(spec_text) > 800 and len(clean_name) <= 20:
        spec_text = spec_text[:800]
    return {
        "name": clean_name[:512],
        "category": None,
        "quantity": qty,
        "unit": (unit or "").strip()[:64] or None,
        "brand": (brand or "").strip()[:128] or None,
        "model": (model or "").strip()[:256] or None,
        "unit_price": price,
        "spec": spec_text[:2000] or None,
        "amount": amount,
    }


def _assign_numbers(numbers: List[str], roles: str) -> tuple:
    values = [_num(n) for n in numbers]
    values = [v for v in values if v is not None]
    if not values:
        return None, None, None
    if roles == "qty_price_amt" and len(values) >= 3:
        qty, price, amount = values[0], values[1], values[2]
    elif roles == "qty_price" and len(values) >= 2:
        qty, price, amount = values[0], values[1], None
    else:
        qty, price = values[0], None
        amount = values[1] if len(values) > 1 else None
    if price == 0:
        price = None
    if amount == 0:
        amount = None
    return qty, price, amount


def _num(value: str) -> Optional[float]:
    try:
        return float(value.replace(",", ""))
    except (TypeError, ValueError):
        return None
