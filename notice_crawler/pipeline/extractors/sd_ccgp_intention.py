"""山东政府采购网「意向公开 / 采购需求公示」规则抽取。

版式多为 Word 表转 HTML，text 扁平后形如：
序号 / 采购项目名称 / 采购需求概况 / 预算金额（万元）/ … / 1 / 项目名 / 概况 / 3.008 / 是 / 2026年11月
"""

from __future__ import annotations

import calendar
import re
from copy import deepcopy
from datetime import datetime
from typing import Any, Dict, List, Optional

from pipeline.extractors.base import EXTRACT_SCHEMA

HEADER_NOISE = frozenset(
    {
        "序号",
        "采购项目名称",
        "采购需求概况",
        "预算金额",
        "（万元）",
        "(万元)",
        "万元",
        "拟面向中小企业预留",
        "预计采购时间",
        "（填写到月）",
        "(填写到月)",
        "备注",
        "地址",
        "名称",
        "单位",
    }
)

_MONTH_RE = re.compile(r"(\d{4})\s*年\s*(\d{1,2})\s*月")
_BUDGET_LINE_RE = re.compile(r"^([0-9]{1,8}(?:\.[0-9]+)?)\s*$")
_SME_RE = re.compile(r"^(是|否)$")
_SERIAL_RE = re.compile(r"^\d{1,4}$")
_FOOTER_RE = re.compile(r"本次公开的采购意向|以上意向|特此公告|特此公开")
_TITLE_BUYER_RE = re.compile(
    r"^(?:【[^】]+】)?\s*([\u4e00-\u9fffA-Za-z0-9（）()·\-、]{4,60}?)"
    r"(?=\d{4}\s*年|\d{4}\s*年度|本级|\d{4}\s*月|政府采购意向|采购需求|采购意向)"
)


def looks_like_intention(
    *,
    title: str = "",
    text: str = "",
    notice_type: str = "",
    list_item: Optional[dict] = None,
) -> bool:
    nt = str(notice_type or "").strip()
    if nt in {"2500", "2504"}:
        return True
    col = str((list_item or {}).get("colCode") or "").strip()
    if col in {"2500", "2504"}:
        return True
    blob = f"{title}\n{text[:800]}"
    return bool(
        re.search(r"政府采购意向|意向公开|采购需求公示|采购需求概况", blob)
        or ("预算金额" in blob and "预计采购时间" in blob and "采购项目名称" in blob)
    )


def is_header_noise(value: Optional[str]) -> bool:
    text = re.sub(r"\s+", "", str(value or "").strip())
    if not text:
        return True
    if text in HEADER_NOISE:
        return True
    if text.startswith("预算金额") or text.startswith("预计采购时间"):
        return True
    return False


def is_synthetic_project_code(value: Optional[str]) -> bool:
    code = str(value or "").strip()
    return code.startswith(("tp:", "id:")) or code.startswith("BN") and len(code) > 40


def _month_end(year: int, month: int) -> datetime:
    last = calendar.monthrange(year, month)[1]
    return datetime(year, month, last, 23, 59, 59)


def _month_start(year: int, month: int) -> datetime:
    return datetime(year, month, 1, 0, 0, 0)


def _parse_months(values: List[str]) -> List[tuple[int, int]]:
    out: List[tuple[int, int]] = []
    for raw in values:
        m = _MONTH_RE.search(raw or "")
        if not m:
            continue
        year, month = int(m.group(1)), int(m.group(2))
        if 1 <= month <= 12:
            out.append((year, month))
    return out


def _buyer_from_title(title: str) -> Optional[str]:
    title = (title or "").strip()
    if not title:
        return None
    m = _TITLE_BUYER_RE.match(title)
    if not m:
        return None
    buyer = re.sub(r"\s+", "", m.group(1)).strip("，,。；;、-—_")
    if len(buyer) < 4 or is_header_noise(buyer):
        return None
    # 标题里偶发「本级」前缀单位，保留
    return buyer[:256]


def _buyer_from_footer(text: str) -> Optional[str]:
    lines = [ln.strip() for ln in (text or "").splitlines() if ln.strip()]
    date_re = re.compile(r"^\d{4}\s*年\s*\d{1,2}\s*月\s*\d{1,2}\s*日$")
    for i in range(len(lines) - 1, -1, -1):
        if date_re.match(lines[i]) and i > 0:
            cand = re.sub(r"\s+", "", lines[i - 1])
            if 4 <= len(cand) <= 60 and not is_header_noise(cand) and "采购意向" not in cand:
                return cand[:256]
    return None


def _extract_demand_publicity(text: str, title: str = "") -> Dict[str, Any]:
    """「采购需求公示」条目式版式。"""
    out = deepcopy(EXTRACT_SCHEMA)
    out["goods"] = []
    out["quotes"] = []
    out["suppliers"] = []
    out["notice_title"] = title or None
    out["notice_kind"] = "意向公开"

    def _field(*labels: str) -> Optional[str]:
        for label in labels:
            m = re.search(
                rf"(?:^|\n)\s*(?:[一二三四五六七八九十]+、)?{label}\s*[:：]?\s*\n?\s*([^\n\r]+)",
                text,
                flags=re.M,
            )
            if m:
                val = re.sub(r"\s+", " ", m.group(1).strip())
                if val and not is_header_noise(val):
                    return val[:512]
        return None

    project_name = _field("项目名称", "采购项目名称")
    buyer = _field("采购单位", "采购人", "采购人名称")
    overview = _field("项目概况", "采购需求概况", "需求概况")
    budget_raw = _field("总预算", "预算金额", "预算")
    budget = None
    if budget_raw:
        wan = re.search(r"([0-9,.]+)\s*万", budget_raw)
        yuan = re.search(r"([0-9,.]+)\s*元", budget_raw)
        try:
            if wan:
                budget = round(float(wan.group(1).replace(",", "")) * 10000, 2)
            elif yuan:
                budget = float(yuan.group(1).replace(",", ""))
            else:
                num = re.search(r"([0-9,.]+)", budget_raw)
                if num:
                    budget = float(num.group(1).replace(",", ""))
        except ValueError:
            budget = None

    out["project_name"] = project_name or (title[:256] if title else None)
    out["buyer_name"] = buyer or _buyer_from_title(title)
    out["budget_amount"] = budget
    compile_time = _field("编制时间")
    months = _parse_months([compile_time or "", title or ""])
    if months:
        out["start_time"] = _month_start(*months[0]).strftime("%Y-%m-%d %H:%M:%S")
        out["end_time"] = _month_end(*months[-1]).strftime("%Y-%m-%d %H:%M:%S")
    if project_name:
        out["goods"] = [
            {
                "name": project_name[:512],
                "category": "服务" if any(x in (project_name + (overview or "")) for x in ("服务", "租赁", "维保", "运维")) else None,
                "quantity": 1,
                "unit": None,
                "brand": None,
                "model": None,
                "unit_price": None,
                "spec": (overview or "")[:2000] or None,
                "amount": budget,
            }
        ]
    out["extra"] = {"extractor": "sd_ccgp_intention_publicity", "intention_rows": len(out["goods"])}
    out["confidence"] = 0.82 if out["goods"] else 0.5
    return out


_ROW_TAIL_RE = re.compile(
    r"(?m)^([0-9]{1,12}(?:\.[0-9]+)?)\s*\n\s*(是|否)\s*\n\s*(\d{4}\s*年\s*\d{1,2}\s*月)\s*$"
)


def _extract_intention_table(text: str, title: str = "") -> Dict[str, Any]:
    out = deepcopy(EXTRACT_SCHEMA)
    out["goods"] = []
    out["quotes"] = []
    out["suppliers"] = []
    out["notice_title"] = title or None
    out["notice_kind"] = "意向公开"

    body = text or ""
    # 去掉表头前的说明段，尽量从「序号」后开始
    header = re.search(
        r"序号\s*\n\s*采购项目名称\s*\n\s*采购需求概况[\s\S]{0,120}?备注\s*\n",
        body,
    )
    if header:
        body = body[header.end() :]
    body = _FOOTER_RE.split(body, maxsplit=1)[0]

    lines = [re.sub(r"\s+", " ", ln).strip() for ln in body.splitlines()]
    lines = [ln for ln in lines if ln and ln not in {"（万元）", "(万元)", "（填写到月）", "(填写到月)"}]

    # 按序号切块，再从块尾识别「预算 + 是/否 + 年月」，避免概况正文里的数字干扰
    chunks: List[List[str]] = []
    current: List[str] = []
    for ln in lines:
        if _SERIAL_RE.match(ln):
            if current:
                chunks.append(current)
            current = []
            continue
        if _FOOTER_RE.search(ln):
            break
        current.append(ln)
    if current:
        chunks.append(current)

    rows: List[Dict[str, Any]] = []
    for chunk in chunks:
        if not chunk:
            continue
        joined = "\n".join(chunk)
        tails = list(_ROW_TAIL_RE.finditer(joined))
        budget = sme = when = None
        head = joined
        if tails:
            tail = tails[-1]
            budget = float(tail.group(1))
            sme = tail.group(2)
            when = tail.group(3)
            head = joined[: tail.start()].rstrip()
        head_lines = [x for x in head.splitlines() if x.strip()]
        if not head_lines:
            continue
        name = head_lines[0].strip()
        if is_header_noise(name) or _SERIAL_RE.match(name):
            continue
        overview = "\n".join(head_lines[1:]).strip() or None
        amount = round(budget * 10000, 2) if budget is not None else None
        rows.append(
            {
                "name": name[:512],
                "category": None,
                "quantity": 1,
                "unit": None,
                "brand": None,
                "model": None,
                "unit_price": None,
                "spec": (overview or "")[:2000] or None,
                "amount": amount,
                "expected_month": when,
                "sme_reserved": sme,
            }
        )

    goods = []
    months: List[str] = []
    total = 0.0
    has_amount = False
    for row in rows:
        goods.append(
            {
                "name": row["name"],
                "category": row["category"],
                "quantity": row["quantity"],
                "unit": row["unit"],
                "brand": row["brand"],
                "model": row["model"],
                "unit_price": row["unit_price"],
                "spec": row["spec"],
                "amount": row["amount"],
            }
        )
        if row.get("expected_month"):
            months.append(str(row["expected_month"]))
        if row.get("amount") is not None:
            total += float(row["amount"])
            has_amount = True

    out["goods"] = goods
    if goods:
        out["project_name"] = goods[0]["name"] if len(goods) == 1 else f"{goods[0]['name']}等{len(goods)}项"
    else:
        # 不要用表头；退回标题
        out["project_name"] = title[:256] if title else None
    out["budget_amount"] = round(total, 2) if has_amount else None

    parsed_months = _parse_months(months) or _parse_months([title or ""])
    if parsed_months:
        start = min(_month_start(y, m) for y, m in parsed_months)
        end = max(_month_end(y, m) for y, m in parsed_months)
        out["start_time"] = start.strftime("%Y-%m-%d %H:%M:%S")
        out["end_time"] = end.strftime("%Y-%m-%d %H:%M:%S")

    out["buyer_name"] = _buyer_from_title(title) or _buyer_from_footer(text)
    out["extra"] = {
        "extractor": "sd_ccgp_intention_table",
        "intention_rows": len(goods),
        "expected_months": months,
    }
    out["confidence"] = 0.9 if goods else 0.4
    return out


def extract_ccgp_intention(
    text: str,
    title: str = "",
    *,
    html: Optional[str] = None,
    list_item: Optional[dict] = None,
    detail: Optional[dict] = None,
) -> Dict[str, Any]:
    body = text or ""
    if (not body or len(body) < 40) and html:
        from utils import html_to_text

        body = html_to_text(html)

    if re.search(r"(?:^|\n)\s*一、\s*项目名称", body) or "采购需求公示" in (title or ""):
        parsed = _extract_demand_publicity(body, title=title)
    else:
        parsed = _extract_intention_table(body, title=title)

    # list_json.userName 常是采购单位
    user_name = str((list_item or {}).get("userName") or "").strip()
    if user_name and (
        not parsed.get("buyer_name")
        or len(str(parsed.get("buyer_name"))) < len(user_name)
        or is_header_noise(parsed.get("buyer_name"))
    ):
        parsed["buyer_name"] = user_name[:256]

    area = str((list_item or {}).get("areaName") or "").strip()
    if area and not parsed.get("region_name"):
        parsed["region_name"] = area

    # 意向公开通常无项目编号
    parsed["project_code"] = None
    if not isinstance(parsed.get("extra"), dict):
        parsed["extra"] = {}
    if detail and isinstance(detail, dict):
        parsed["extra"]["has_detail_json"] = True
    return parsed
