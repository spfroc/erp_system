from __future__ import annotations

from datetime import date
from typing import Optional

from tqdm import tqdm

from clients.jd_quan import SITE_ID as JD_SITE
from clients.jd_quan import JdQuanClient
from clients.sd_mall import SITE_ID as MALL_SITE
from clients.sd_mall import SdMallClient
from sqlalchemy import select

from db import NoticeAttachment, NoticeRaw, get_session, raw_exists, save_cursor, upsert_raw
from pipeline.parse_llm import enrich_from_raw, extract_fields, save_parsed
from utils import html_to_text, parse_dt


def _as_day(value: Optional[str]) -> Optional[date]:
    if not value:
        return None
    parsed = parse_dt(value)
    if parsed is None:
        raise ValueError(f"日期格式应为 YYYY-MM-DD：{value}")
    return parsed.date()


def _day_of(value) -> Optional[date]:
    parsed = parse_dt(value)
    return parsed.date() if parsed else None


class _DupStop:
    """同一类型列表里连续命中已入库公告达到阈值后停止该类。"""

    def __init__(self, limit: Optional[int]) -> None:
        self.limit = limit if limit and limit > 0 else None
        self.streak = 0

    def hit(self, duplicated: bool) -> bool:
        if not self.limit:
            return False
        if duplicated:
            self.streak += 1
            return self.streak >= self.limit
        self.streak = 0
        return False


def _parse_after_detail(session, raw: NoticeRaw, *, html: str = "", text: str = "") -> None:
    """抓到详情后立刻规则/模型解析并写入 notice_parsed。"""
    body = (text or raw.content_text or html_to_text(html) or "").strip()
    detail = raw.detail_json if isinstance(raw.detail_json, dict) else {}
    list_item = raw.list_json if isinstance(raw.list_json, dict) else {}
    page_html = (html or raw.content_html or "").strip() or str(detail.get("content") or "").strip()
    if len(body) < 20 and not page_html:
        return
    parsed = extract_fields(
        body,
        title=raw.title or "",
        html=page_html,
        site_id=raw.site_id,
        detail=detail,
        list_item=list_item,
    )
    parsed = enrich_from_raw(parsed, raw)
    save_parsed(session, raw, parsed)


def crawl_sd_mall(
    *,
    max_pages: Optional[int] = None,
    page_size: int = 50,
    with_detail: bool = True,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    stop_dup: Optional[int] = None,
) -> None:
    start_day = _as_day(start_date)
    end_day = _as_day(end_date)
    start_arg = start_day.isoformat() if start_day else None
    end_arg = end_day.isoformat() if end_day else None
    client = SdMallClient()
    session = get_session()
    try:
        for project_type, notice_type, label in client.iter_categories():
            cursor_key = f"{project_type}:{notice_type}"
            page = 1
            total_pages = None
            dup = _DupStop(stop_dup)
            stop_category = False
            pbar = tqdm(desc=f"{MALL_SITE}/{label}", unit="page")
            while True:
                if max_pages and page > max_pages:
                    break
                data = client.list_notices(
                    project_type=project_type,
                    notice_type=notice_type,
                    page_num=page,
                    page_size=page_size,
                    start_date=start_arg,
                    end_date=end_arg,
                )
                items = data.get("data") or []
                total = int(data.get("total") or 0)
                if total_pages is None:
                    total_pages = max(1, (total + page_size - 1) // page_size)
                    pbar.total = min(total_pages, max_pages or total_pages)

                for item in items:
                    notice_guid = str(item.get("noticeGuid") or "")
                    if not notice_guid:
                        continue
                    published = _day_of(item.get("publishTime") or item.get("createDate"))
                    if start_day and published and published < start_day:
                        stop_category = True
                        tqdm.write(f"{label} 早于 {start_day.isoformat()}，停止该类")
                        break
                    if end_day and published and published > end_day:
                        continue
                    if dup.hit(raw_exists(session, MALL_SITE, notice_guid)):
                        stop_category = True
                        tqdm.write(f"{label} 连续重复 {dup.limit} 条，停止该类")
                        break
                    if dup.streak:
                        continue
                    row = upsert_raw(
                        session,
                        site_id=MALL_SITE,
                        notice_key=notice_guid,
                        auction_type=str(project_type),
                        notice_type=str(notice_type),
                        title=item.get("title"),
                        region_name=item.get("regionName"),
                        publish_time=parse_dt(item.get("publishTime") or item.get("createDate")),
                        list_json=item,
                        source_url=(
                            "https://ggzyjyzx.shandong.gov.cn:8182/gpmall-main-web/basic/"
                            f"noticeDetail?noticeGuid={notice_guid}"
                        ),
                        crawl_status="list_only",
                    )
                    if with_detail:
                        try:
                            detail = client.get_detail(notice_guid)
                            html = detail.get("content") or ""
                            text = html_to_text(html)
                            raw = upsert_raw(
                                session,
                                site_id=MALL_SITE,
                                notice_key=notice_guid,
                                detail_json=detail,
                                content_html=html,
                                content_text=text,
                                title=detail.get("title") or item.get("title"),
                                crawl_status="detail_ok",
                            )
                            try:
                                _parse_after_detail(session, raw, html=html, text=text)
                            except Exception as exc:  # noqa: BLE001
                                raw.parse_status = "parse_fail"
                                raw.error_message = str(exc)[:1000]
                        except Exception as exc:  # noqa: BLE001
                            upsert_raw(
                                session,
                                site_id=MALL_SITE,
                                notice_key=notice_guid,
                                crawl_status="detail_fail",
                                error_message=str(exc),
                            )
                    _ = row

                session.commit()
                save_cursor(session, MALL_SITE, cursor_key, page, total)
                session.commit()
                pbar.update(1)
                if stop_category or page >= total_pages or not items:
                    break
                page += 1
            pbar.close()
    finally:
        session.close()


def crawl_jd(
    *,
    max_pages: Optional[int] = None,
    page_size: int = 50,
    with_detail: bool = True,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    stop_dup: Optional[int] = None,
) -> None:
    # 列表按创建时间倒序，接口本身没有日期参数，按 createTime 在本地截断
    start_day = _as_day(start_date)
    end_day = _as_day(end_date)
    client = JdQuanClient()
    session = get_session()
    try:
        for auction_type, notice_type, label, business_type in client.iter_categories():
            cursor_key = f"{auction_type}:{notice_type}"
            page = 1
            total_pages = None
            dup = _DupStop(stop_dup)
            stop_category = False
            pbar = tqdm(desc=f"{JD_SITE}/{label}", unit="page")
            while True:
                if max_pages and page > max_pages:
                    break
                data = client.list_notices(
                    auction_type=auction_type,
                    notice_type=notice_type,
                    business_type=business_type,
                    page_num=page,
                    page_size=page_size,
                )
                items = data.get("result") or []
                total = int(data.get("totalCount") or 0)
                if total_pages is None:
                    total_pages = max(1, (total + page_size - 1) // page_size) if total else 1
                    pbar.total = min(total_pages, max_pages or total_pages)

                for item in items:
                    auction_no = str(item.get("auctionNo") or "")
                    item_notice_type = item.get("noticeType")
                    if not auction_no:
                        continue
                    created = _day_of(item.get("createTime"))
                    if end_day and created and created > end_day:
                        continue
                    if start_day and created and created < start_day:
                        stop_category = True
                        tqdm.write(f"{label} 早于 {start_day.isoformat()}，停止该类")
                        break
                    notice_key = f"{auction_no}:{item_notice_type}"
                    if dup.hit(raw_exists(session, JD_SITE, notice_key)):
                        stop_category = True
                        tqdm.write(f"{label} 连续重复 {dup.limit} 条，停止该类")
                        break
                    if dup.streak:
                        continue
                    upsert_raw(
                        session,
                        site_id=JD_SITE,
                        notice_key=notice_key,
                        auction_type=str(item.get("auctionType") or auction_type),
                        notice_type=str(item_notice_type if item_notice_type is not None else notice_type),
                        title=item.get("noticeTitle") or item.get("auctionName"),
                        region_name=None,
                        publish_time=parse_dt(item.get("createTime")),
                        list_json=item,
                        source_url=(
                            f"{client.origin}/jj/notice/detail?auctionNo={auction_no}"
                            f"&noticeType={item_notice_type}"
                        ),
                        crawl_status="list_only",
                    )
                    if with_detail:
                        try:
                            detail = client.get_detail(auction_no, item_notice_type or notice_type)
                            # JD 详情多为结构化 JSON，无整页 HTML；拼可读文本供规则/模型
                            content_text = json_detail_to_text(detail)
                            raw = upsert_raw(
                                session,
                                site_id=JD_SITE,
                                notice_key=notice_key,
                                detail_json=detail,
                                content_html=None,
                                content_text=content_text,
                                title=detail.get("noticeTitle") or item.get("noticeTitle"),
                                crawl_status="detail_ok",
                            )
                            try:
                                _parse_after_detail(session, raw, text=content_text)
                            except Exception as exc:  # noqa: BLE001
                                raw.parse_status = "parse_fail"
                                raw.error_message = str(exc)[:1000]
                            raw = session.execute(
                                select(NoticeRaw).where(
                                    NoticeRaw.site_id == JD_SITE,
                                    NoticeRaw.notice_key == notice_key,
                                )
                            ).scalar_one()
                            for att in client.extract_attachments(detail):
                                exists = session.execute(
                                    select(NoticeAttachment).where(
                                        NoticeAttachment.notice_raw_id == raw.id,
                                        NoticeAttachment.file_url == att["file_url"],
                                    )
                                ).scalar_one_or_none()
                                if exists:
                                    continue
                                session.add(
                                    NoticeAttachment(
                                        notice_raw_id=raw.id,
                                        site_id=JD_SITE,
                                        notice_key=notice_key,
                                        file_name=att.get("file_name"),
                                        file_url=att["file_url"],
                                        download_status="pending",
                                        parse_status="pending",
                                    )
                                )
                        except Exception as exc:  # noqa: BLE001
                            upsert_raw(
                                session,
                                site_id=JD_SITE,
                                notice_key=notice_key,
                                crawl_status="detail_fail",
                                error_message=str(exc),
                            )
                session.commit()
                save_cursor(session, JD_SITE, cursor_key, page, total)
                session.commit()
                pbar.update(1)
                if stop_category or page >= total_pages or not items:
                    break
                page += 1
            pbar.close()
    finally:
        session.close()


def json_detail_to_text(detail: dict) -> str:
    """把京东结构化详情压成可读文本，便于 LLM 抽取。"""
    import json
    from datetime import datetime

    def _fmt_ts(v):
        if v in (None, ""):
            return ""
        try:
            num = float(v)
            if num > 1e12:
                num /= 1000.0
            if num > 1e9:
                return datetime.fromtimestamp(num).strftime("%Y-%m-%d %H:%M:%S")
        except (TypeError, ValueError, OSError, OverflowError):
            pass
        return str(v)

    nested = detail.get("detail") or {}
    base = nested.get("auctionNoticeBaseInfo") if isinstance(nested, dict) else {}
    if not isinstance(base, dict):
        base = {}

    parts = [
        f"标题: {detail.get('noticeTitle') or detail.get('auctionName') or ''}",
        f"项目名称: {detail.get('auctionName') or base.get('auctionName') or ''}",
        f"公告编号: {detail.get('noticeCode') or ''}",
        f"拍卖编号: {detail.get('auctionNo') or base.get('auctionNo') or ''}",
        f"公告类型: {detail.get('noticeType')}",
        f"竞价类型: {detail.get('auctionType')}",
        f"采购单位: {base.get('purchaseUnitName') or detail.get('purchaseUnitName') or ''}",
        f"预算金额: {base.get('budgetPrice') or detail.get('budgetPrice') or ''}",
        f"发布时间: {_fmt_ts(detail.get('createTime') or detail.get('publishTime'))}",
        f"开始时间: {_fmt_ts(base.get('startTime') or detail.get('startTime'))}",
        f"截止时间: {_fmt_ts(base.get('endTime') or detail.get('endTime'))}",
    ]
    # 商品摘要
    for group in (nested.get("skuGroupList") or []) if isinstance(nested, dict) else []:
        if not isinstance(group, dict):
            continue
        for sku in group.get("skuList") or []:
            if not isinstance(sku, dict):
                continue
            parts.append(
                "商品: "
                f"{sku.get('skuName') or ''} "
                f"品牌:{sku.get('brandName') or ''} "
                f"型号:{sku.get('skuModel') or ''} "
                f"数量:{sku.get('skuNum') or ''} "
                f"单价:{sku.get('sellPrice') or ''}"
            )
    deal = nested.get("auctionNoticeDealResult") if isinstance(nested, dict) else None
    if isinstance(deal, dict):
        for s in deal.get("supplierList") or []:
            if isinstance(s, dict):
                parts.append(
                    f"成交供应商: {s.get('supplierName') or ''} 成交价:{s.get('dealPrice') or ''}"
                )
    if nested:
        parts.append("详情结构化数据:")
        parts.append(json.dumps(nested, ensure_ascii=False, indent=2)[:20000])
    return "\n".join(parts)
