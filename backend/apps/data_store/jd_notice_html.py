"""泉E采 / 青慧采结构化详情 → 官网可读 HTML。

上方信息网格已有的标题、编号、单位、金额、时间等字段不在此重复。
"""

from __future__ import annotations

import html
from datetime import datetime, timezone as dt_timezone
from decimal import Decimal
from typing import Any

from django.utils import timezone

JD_SITE_IDS = frozenset({"jd-quan-yicai", "jd-qing-huicai"})


def _esc(value: Any) -> str:
    return html.escape("" if value is None else str(value), quote=True)


def _dec(value: Any) -> float | None:
    if value is None:
        return None
    if isinstance(value, Decimal):
        return float(value)
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _fmt_money(value: Any) -> str:
    num = _dec(value)
    if num is None:
        return str(value or "").strip()
    if abs(num - int(num)) < 1e-9:
        return f"{int(num):,}"
    return f"{num:,.2f}"


def _fmt_time(value: Any) -> str:
    if value in (None, ""):
        return ""
    if isinstance(value, (int, float)):
        ts = float(value)
        if ts > 1e12:
            ts /= 1000.0
        try:
            dt = datetime.fromtimestamp(ts, tz=dt_timezone.utc).astimezone(
                timezone.get_default_timezone()
            )
            return dt.strftime("%Y-%m-%d %H:%M:%S")
        except (OverflowError, OSError, ValueError):
            return str(value)
    return str(value).strip()


def _abs_url(url: str) -> str:
    text = (url or "").strip()
    if not text:
        return ""
    if text.startswith("//"):
        return "https:" + text
    if text.startswith("http://") or text.startswith("https://"):
        return text
    return "https://" + text.lstrip("/")


def _section(title: str, body: str) -> str:
    body = (body or "").strip()
    if not body:
        return ""
    return (
        f'<section class="jd-notice-section">'
        f"<h2>{_esc(title)}</h2>"
        f'<div class="jd-section-body">{body}</div>'
        f"</section>"
    )


def _meta_grid(rows: list[tuple[str, Any]]) -> str:
    cells: list[str] = []
    for label, value in rows:
        text = "" if value is None else str(value).strip()
        if not text:
            continue
        cells.append(
            f"<div><span>{_esc(label)}</span><strong>{_esc(text)}</strong></div>"
        )
    if not cells:
        return ""
    return f'<div class="jd-meta-grid">{"".join(cells)}</div>'


def clean_jd_content_text(text: str) -> str:
    raw = (text or "").strip()
    if not raw:
        return ""
    marker = "详情结构化数据:"
    idx = raw.find(marker)
    if idx >= 0:
        raw = raw[:idx].rstrip()
    return raw[:50000]


def build_jd_notice_content_html(detail: dict[str, Any] | None) -> str:
    root = detail if isinstance(detail, dict) else {}
    if not root:
        return ""
    nested = root.get("detail") if isinstance(root.get("detail"), dict) else {}
    base = (
        nested.get("auctionNoticeBaseInfo")
        if isinstance(nested.get("auctionNoticeBaseInfo"), dict)
        else {}
    )
    demand = (
        nested.get("auctionDemandInfo")
        if isinstance(nested.get("auctionDemandInfo"), dict)
        else {}
    )
    parts: list[str] = []

    parts.append(
        _meta_grid(
            [
                ("竞价/询比编号", root.get("auctionNo") or base.get("auctionNo") or base.get("projectNo")),
                ("合同编号", base.get("contractNum")),
            ]
        )
    )

    demand_bits: list[str] = []
    requirement = (base.get("requirement") or "").strip()
    demand_remark = (demand.get("demandRemark") or "").strip()
    attach_remark = (demand.get("attachRequestedRemark") or "").strip()
    if requirement:
        demand_bits.append(
            f'<p class="jd-prose">{_esc(requirement).replace(chr(10), "<br/>")}</p>'
        )
    if demand_remark:
        demand_bits.append(
            "<p class=\"jd-prose\"><em>需求说明</em>"
            f"{_esc(demand_remark).replace(chr(10), '<br/>')}</p>"
        )
    if attach_remark:
        demand_bits.append(
            "<p class=\"jd-prose\"><em>附件要求</em>"
            f"{_esc(attach_remark).replace(chr(10), '<br/>')}</p>"
        )
    parts.append(_section("采购需求", "".join(demand_bits)))

    sku_rows: list[str] = []
    for group in nested.get("skuGroupList") or []:
        if not isinstance(group, dict):
            continue
        group_name = (group.get("groupName") or group.get("categoryName") or "").strip()
        for sku in group.get("skuList") or []:
            if not isinstance(sku, dict):
                continue
            name = (sku.get("skuName") or "").strip()
            if group_name and name:
                name = f"{group_name} / {name}"
            elif group_name:
                name = group_name
            sku_rows.append(
                "<tr>"
                f"<td data-label=\"商品\">{_esc(name)}</td>"
                f"<td data-label=\"品牌\">{_esc(sku.get('brandName') or '—')}</td>"
                f"<td data-label=\"型号\">{_esc(sku.get('skuModel') or '—')}</td>"
                f"<td data-label=\"数量\">{_esc(sku.get('skuNum') or '—')}</td>"
                f"<td data-label=\"单位\">{_esc(sku.get('unit') or '—')}</td>"
                f"<td data-label=\"单价\">{_esc(_fmt_money(sku.get('sellPrice')) or '—')}</td>"
                f"<td data-label=\"品类\">{_esc(sku.get('categoryName') or '—')}</td>"
                "</tr>"
            )
    if sku_rows:
        goods_html = (
            '<div class="jd-table-wrap"><table class="jd-goods-table">'
            "<thead><tr>"
            "<th>商品</th><th>品牌</th><th>型号</th><th>数量</th><th>单位</th><th>单价（元）</th><th>品类</th>"
            "</tr></thead><tbody>"
            + "".join(sku_rows)
            + "</tbody></table></div>"
        )
        parts.append(_section("商品清单", goods_html))

    deal = nested.get("auctionNoticeDealResult")
    if isinstance(deal, dict):
        supplier_rows: list[str] = []
        for item in deal.get("supplierList") or []:
            if not isinstance(item, dict):
                continue
            supplier_rows.append(
                "<tr>"
                f"<td data-label=\"供应商\">{_esc(item.get('supplierName') or '—')}</td>"
                f"<td data-label=\"成交/报价\">{_esc(_fmt_money(item.get('dealPrice')) or '—')}</td>"
                f"<td data-label=\"响应时间\">{_esc(_fmt_time(item.get('respTime')) or '—')}</td>"
                "</tr>"
            )
        if supplier_rows:
            deal_html = (
                '<div class="jd-table-wrap"><table class="jd-goods-table">'
                "<thead><tr><th>供应商</th><th>成交/报价（元）</th><th>响应时间</th></tr></thead>"
                "<tbody>"
                + "".join(supplier_rows)
                + "</tbody></table></div>"
            )
            parts.append(_section("成交结果", deal_html))

    pay_rows: list[str] = []
    for term in base.get("auctionPaymentTermList") or []:
        if not isinstance(term, dict):
            continue
        ratio = term.get("paymentRatio")
        ratio_text = f"{ratio}%" if ratio not in (None, "") else ""
        pay_rows.append(
            "<tr>"
            f"<td data-label=\"付款项\">{_esc(term.get('paymentType') or '—')}</td>"
            f"<td data-label=\"比例\">{_esc(ratio_text or '—')}</td>"
            f"<td data-label=\"预计时间\">{_esc(term.get('expectedTime') or '—')}</td>"
            "</tr>"
        )
    if pay_rows:
        pay_html = (
            '<div class="jd-table-wrap"><table class="jd-goods-table">'
            "<thead><tr><th>付款项</th><th>比例</th><th>预计时间</th></tr></thead>"
            "<tbody>"
            + "".join(pay_rows)
            + "</tbody></table></div>"
        )
        parts.append(_section("付款条件", pay_html))

    attach_items: list[str] = []
    for att in root.get("attachmentInfoList") or []:
        if not isinstance(att, dict):
            continue
        name = (att.get("attachmentName") or "附件").strip() or "附件"
        href = _abs_url(str(att.get("url") or ""))
        if href:
            attach_items.append(
                f'<li><a class="jd-attach-link" href="{_esc(href)}" '
                f'target="_blank" rel="noopener noreferrer">{_esc(name)}</a></li>'
            )
        else:
            attach_items.append(f"<li>{_esc(name)}</li>")
    if attach_items:
        parts.append(_section("附件", f'<ul class="jd-attach-list">{"".join(attach_items)}</ul>'))

    body = "".join(part for part in parts if part)
    if not body:
        return ""
    return f'<div class="jd-notice-body">{body}</div>'
