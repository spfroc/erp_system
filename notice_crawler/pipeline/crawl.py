from __future__ import annotations

import time
from datetime import date
from typing import Optional

from tqdm import tqdm

from clients.jd_quan import JdQuanClient, jd_site_configs
from clients.sd_ccgp import SITE_ID as CCGP_SITE
from clients.sd_ccgp import SdCcgpClient, decode_notice_body
from clients.sd_mall import SITE_ID as MALL_SITE
from clients.sd_mall import SdMallClient, is_connection_failure
from clients.sd_gpfa import SITE_ID as GPFA_SITE
from clients.sd_gpfa import SdGpfaClient
from clients.sd_gpfa import is_connection_failure as is_gpfa_connection_failure
from sqlalchemy import select

from db import (
    NoticeRaw,
    _ensure_notice_key_width,
    dumps,
    extract_project_code,
    find_ccgp_raw,
    get_session,
    mall_has_project_code,
    raw_exists,
    save_cursor,
    upsert_raw,
)
from pipeline.attachments import (
    ingest_attachments,
    parse_attachments,
    sync_missing_jd_attachments,
    sync_missing_mall_attachments,
)
from pipeline.parse_llm import enrich_from_raw, extract_fields, save_parsed
from utils import extract_district_name, html_to_text, normalize_region_name, parse_dt


def _ccgp_region_fields(item: dict) -> tuple[Optional[str], Optional[str], Optional[str]]:
    """areaName/areaCode → region_name / district_name / region_guid。"""
    raw_region = (item.get("areaName") or item.get("regionName") or "").strip() or None
    area_code = str(item.get("areaCode") or item.get("regionGuid") or "").strip() or None
    if area_code == "370000" or (raw_region or "").startswith("山东"):
        if raw_region in (None, "", "山东省本级", "省本级"):
            return "山东省", None, area_code or "370000"
    region_name = normalize_region_name(CCGP_SITE, raw_region)
    district = extract_district_name(raw_region)
    if district in ("本级", "市本级"):
        district = None
    return region_name, district, area_code


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


def _mall_wait_proxy(client: SdMallClient, *, rounds: int = 3) -> bool:
    """全量/增量开始前探活 SOCKS；失败则退避重试，避免连续空跑各类别。"""
    for i in range(1, rounds + 1):
        try:
            client.probe()
            if i > 1:
                tqdm.write(f"{MALL_SITE} 代理探活成功（第 {i} 次）")
            return True
        except Exception as exc:  # noqa: BLE001
            wait = min(180.0, 30.0 * i)
            tqdm.write(f"{MALL_SITE} 代理探活失败 {i}/{rounds}：{exc}；{wait:.0f}s 后重试")
            client.reset_session()
            time.sleep(wait)
    return False


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
    if not _mall_wait_proxy(client):
        tqdm.write(f"{MALL_SITE} 代理不可用，跳过本轮商城采集")
        return
    session = get_session()
    conn_skip_streak = 0
    try:
        for project_type, notice_type, label in client.iter_categories():
            if conn_skip_streak >= 3:
                tqdm.write(f"{MALL_SITE} 连续 {conn_skip_streak} 类因连接失败跳过，中止本轮剩余类别")
                break
            cursor_key = f"{project_type}:{notice_type}"
            page = 1
            total_pages = None
            dup = _DupStop(stop_dup)
            stop_category = False
            page1_retries = 0
            pbar = tqdm(desc=f"{MALL_SITE}/{label}", unit="page")
            try:
                while True:
                    if max_pages and page > max_pages:
                        break
                    try:
                        data = client.list_notices(
                            project_type=project_type,
                            notice_type=notice_type,
                            page_num=page,
                            page_size=page_size,
                            start_date=start_arg,
                            end_date=end_arg,
                        )
                    except Exception as exc:  # noqa: BLE001
                        # 首页遇 SOCKS 抖动：重建会话后再试，避免整类直接跳过
                        if page == 1 and is_connection_failure(exc) and page1_retries < 2:
                            page1_retries += 1
                            wait = 45.0 * page1_retries
                            tqdm.write(
                                f"{MALL_SITE}/{label} 第 1 页连接失败，"
                                f"{wait:.0f}s 后重试该类 ({page1_retries}/2)：{exc}"
                            )
                            client.reset_session()
                            time.sleep(wait)
                            continue
                        # 列表接口重试耗尽后跳过该类，避免整次全量任务中断
                        tqdm.write(f"{MALL_SITE}/{label} 第 {page} 页列表失败，跳过该类：{exc}")
                        if is_connection_failure(exc):
                            conn_skip_streak += 1
                        else:
                            conn_skip_streak = 0
                        break
                    conn_skip_streak = 0
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
                        raw_region = item.get("regionName")
                        upsert_raw(
                            session,
                            site_id=MALL_SITE,
                            notice_key=notice_guid,
                            auction_type=str(project_type),
                            notice_type=str(notice_type),
                            title=item.get("title"),
                            region_name=normalize_region_name(MALL_SITE, raw_region),
                            district_name=extract_district_name(raw_region),
                            region_guid=item.get("regionGuid"),
                            publish_time=parse_dt(item.get("publishTime") or item.get("createDate")),
                            list_json=item,
                            source_url=(
                                "https://ggzyjyzx.shandong.gov.cn:8182/gpmall-main-web/basic/"
                                f"noticeDetail?noticeGuid={notice_guid}"
                            ),
                            crawl_status="list_only",
                        )
                        session.commit()
                        if with_detail:
                            try:
                                detail = client.get_detail(notice_guid)
                                detail = client.merge_except_gd(notice_guid, detail)
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
                                    auction_type=str(
                                        detail.get("projectType")
                                        if detail.get("projectType") not in (None, "")
                                        else project_type
                                    ),
                                    crawl_status="detail_ok",
                                )
                                try:
                                    _parse_after_detail(session, raw, html=html, text=text)
                                except Exception as exc:  # noqa: BLE001
                                    raw.parse_status = "parse_fail"
                                    raw.error_message = str(exc)[:1000]
                                files = client.extract_attachments(detail)
                                session.commit()
                                if files:
                                    raw = session.execute(
                                        select(NoticeRaw).where(
                                            NoticeRaw.site_id == MALL_SITE,
                                            NoticeRaw.notice_key == notice_guid,
                                        )
                                    ).scalar_one()
                                    ingest_attachments(session, raw, files)
                                    session.commit()
                            except Exception as exc:  # noqa: BLE001
                                session.rollback()
                                upsert_raw(
                                    session,
                                    site_id=MALL_SITE,
                                    notice_key=notice_guid,
                                    crawl_status="detail_fail",
                                    error_message=str(exc),
                                )
                                session.commit()

                    save_cursor(session, MALL_SITE, cursor_key, page, total)
                    session.commit()
                    pbar.update(1)
                    if stop_category or page >= total_pages or not items:
                        break
                    page += 1
            finally:
                pbar.close()
    finally:
        session.close()

    if with_detail:
        import os

        limit = int(os.getenv("CRAWL_ATT_LIMIT", "100") or "100")
        synced = sync_missing_mall_attachments(limit=max(limit, 1), use_llm=False)
        if synced:
            tqdm.write(f"商城历史采购清单已补下载 {synced} 个")
        flag = (os.getenv("CRAWL_PARSE_ATT") or "0").strip().lower()
        if flag in {"1", "true", "yes", "on"}:
            parsed_n = parse_attachments(
                limit=max(limit, 1), site_id=MALL_SITE, use_llm=True
            )
            if parsed_n:
                tqdm.write(f"商城采购清单本地模型已解析 {parsed_n} 个")


def _gpfa_wait_proxy(client: SdGpfaClient, *, rounds: int = 3) -> bool:
    for i in range(1, rounds + 1):
        try:
            client.probe()
            if i > 1:
                tqdm.write(f"{GPFA_SITE} 代理探活成功（第 {i} 次）")
            return True
        except Exception as exc:  # noqa: BLE001
            wait = min(180.0, 30.0 * i)
            tqdm.write(f"{GPFA_SITE} 代理探活失败 {i}/{rounds}：{exc}；{wait:.0f}s 后重试")
            client.reset_session()
            time.sleep(wait)
    return False


def crawl_sd_gpfa(
    *,
    max_pages: Optional[int] = None,
    page_size: int = 50,
    with_detail: bool = True,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    stop_dup: Optional[int] = None,
    max_items: Optional[int] = 500,
) -> None:
    """框架协议专区：采购/成交/终止 × 二次竞价/直接选定/顺序轮候；每类默认最多 500 条。"""
    start_day = _as_day(start_date)
    end_day = _as_day(end_date)
    client = SdGpfaClient()
    if not _gpfa_wait_proxy(client):
        tqdm.write(f"{GPFA_SITE} 代理不可用，跳过本轮框架协议采集")
        return
    session = get_session()
    conn_skip_streak = 0
    item_cap = max_items if max_items and max_items > 0 else None
    try:
        for project_type, notice_type, label in client.iter_categories():
            if conn_skip_streak >= 3:
                tqdm.write(f"{GPFA_SITE} 连续 {conn_skip_streak} 类因连接失败跳过，中止本轮剩余类别")
                break
            cursor_key = f"{project_type}:{notice_type}"
            page = 1
            total_pages = None
            fetched = 0
            dup = _DupStop(stop_dup)
            stop_category = False
            page1_retries = 0
            pbar = tqdm(desc=f"{GPFA_SITE}/{label}", unit="page")
            try:
                while True:
                    if max_pages and page > max_pages:
                        break
                    if item_cap is not None and fetched >= item_cap:
                        break
                    try:
                        data = client.list_notices(
                            project_type=project_type,
                            notice_type=notice_type,
                            page_num=page,
                            page_size=page_size,
                        )
                    except Exception as exc:  # noqa: BLE001
                        if page == 1 and is_gpfa_connection_failure(exc) and page1_retries < 2:
                            page1_retries += 1
                            wait = 45.0 * page1_retries
                            tqdm.write(
                                f"{GPFA_SITE}/{label} 第 1 页连接失败，"
                                f"{wait:.0f}s 后重试该类 ({page1_retries}/2)：{exc}"
                            )
                            client.reset_session()
                            time.sleep(wait)
                            continue
                        tqdm.write(f"{GPFA_SITE}/{label} 第 {page} 页列表失败，跳过该类：{exc}")
                        if is_gpfa_connection_failure(exc):
                            conn_skip_streak += 1
                        else:
                            conn_skip_streak = 0
                        break
                    conn_skip_streak = 0
                    items = client.list_items(data)
                    total = int(data.get("total") or 0)
                    if total_pages is None:
                        total_pages = max(1, (total + page_size - 1) // page_size) if total else 1
                        pbar.total = min(total_pages, max_pages or total_pages)

                    for item in items:
                        if item_cap is not None and fetched >= item_cap:
                            stop_category = True
                            break
                        notice_guid = str(item.get("noticeGuid") or "").strip()
                        if not notice_guid:
                            continue
                        published = _day_of(item.get("publishTime") or item.get("createDate"))
                        if start_day and published and published < start_day:
                            stop_category = True
                            tqdm.write(f"{label} 早于 {start_day.isoformat()}，停止该类")
                            break
                        if end_day and published and published > end_day:
                            continue
                        if dup.hit(raw_exists(session, GPFA_SITE, notice_guid)):
                            stop_category = True
                            tqdm.write(f"{label} 连续重复 {dup.limit} 条，停止该类")
                            break
                        if dup.streak:
                            continue
                        fetched += 1
                        raw_region = item.get("regionFullName") or item.get("regionName")
                        item_pt = item.get("projectType")
                        auction_type = str(
                            item_pt if item_pt not in (None, "") else project_type
                        )
                        upsert_raw(
                            session,
                            site_id=GPFA_SITE,
                            notice_key=notice_guid,
                            auction_type=auction_type,
                            notice_type=str(notice_type),
                            title=item.get("title"),
                            region_name=normalize_region_name(GPFA_SITE, raw_region),
                            district_name=extract_district_name(raw_region),
                            region_guid=item.get("regionGuid"),
                            publish_time=parse_dt(item.get("publishTime") or item.get("createDate")),
                            list_json=item,
                            source_url=client.notice_detail_url(notice_guid),
                            crawl_status="list_only",
                        )
                        session.commit()
                        if with_detail:
                            try:
                                detail = client.get_detail(notice_guid)
                                html = detail.get("content") or ""
                                text = html_to_text(html)
                                detail_pt = detail.get("projectType")
                                if detail_pt not in (None, ""):
                                    auction_type = str(detail_pt)
                                raw = upsert_raw(
                                    session,
                                    site_id=GPFA_SITE,
                                    notice_key=notice_guid,
                                    auction_type=auction_type,
                                    detail_json=detail,
                                    content_html=html,
                                    content_text=text,
                                    title=detail.get("title") or item.get("title"),
                                    region_name=normalize_region_name(
                                        GPFA_SITE,
                                        detail.get("regionFullName")
                                        or detail.get("regionName")
                                        or raw_region,
                                    ),
                                    district_name=extract_district_name(
                                        detail.get("regionFullName")
                                        or detail.get("regionName")
                                        or raw_region
                                    ),
                                    region_guid=detail.get("regionGuid") or item.get("regionGuid"),
                                    publish_time=parse_dt(
                                        detail.get("publishTime")
                                        or detail.get("createDate")
                                        or item.get("publishTime")
                                    ),
                                    crawl_status="detail_ok",
                                )
                                try:
                                    _parse_after_detail(session, raw, html=html, text=text)
                                except Exception as exc:  # noqa: BLE001
                                    raw.parse_status = "parse_fail"
                                    raw.error_message = str(exc)[:1000]
                                session.commit()
                            except Exception as exc:  # noqa: BLE001
                                session.rollback()
                                upsert_raw(
                                    session,
                                    site_id=GPFA_SITE,
                                    notice_key=notice_guid,
                                    crawl_status="detail_fail",
                                    error_message=str(exc),
                                )
                                session.commit()

                    save_cursor(session, GPFA_SITE, cursor_key, page, total)
                    session.commit()
                    pbar.update(1)
                    if stop_category or page >= total_pages or not items:
                        break
                    page += 1
            finally:
                pbar.close()
                tqdm.write(f"{GPFA_SITE}/{label} 本轮处理 {fetched} 条")
    finally:
        session.close()


def _looks_like_ccgp_b64(text: Optional[str]) -> bool:
    raw = (text or "").strip()
    if len(raw) < 64 or raw.lstrip().startswith("<"):
        return False
    compact = "".join(raw.split())
    return bool(compact) and all(ch.isalnum() or ch in "+/=" for ch in compact)


def repair_ccgp_bodies(*, limit: Optional[int] = None) -> int:
    """把已入库的 base64+GBK 正文解码回 HTML，并重置 parse_status 便于重解析。"""
    session = get_session()
    fixed = 0
    try:
        stmt = (
            select(NoticeRaw)
            .where(NoticeRaw.site_id == CCGP_SITE)
            .order_by(NoticeRaw.id.desc())
        )
        if limit:
            stmt = stmt.limit(limit)
        rows = session.execute(stmt).scalars().all()
        for raw in rows:
            html = raw.content_html or ""
            detail = raw.detail_json if isinstance(raw.detail_json, dict) else {}
            body = str(detail.get("body") or "")
            source = html if _looks_like_ccgp_b64(html) else (body if _looks_like_ccgp_b64(body) else "")
            if not source:
                # 即便 content_html 已是 HTML，detail.body 仍可能是 b64，统一清洗
                if body and _looks_like_ccgp_b64(body):
                    detail = {**detail, "body": decode_notice_body(body)}
                    raw.detail_json = detail
                    fixed += 1
                continue
            decoded = decode_notice_body(source)
            if decoded == source or not decoded.lstrip().startswith("<"):
                continue
            raw.content_html = decoded
            raw.content_text = html_to_text(decoded)
            if isinstance(detail, dict):
                detail = {**detail, "body": decoded}
                raw.detail_json = detail
            raw.parse_status = "pending"
            raw.error_message = None
            fixed += 1
        session.commit()
    finally:
        session.close()
    return fixed


def crawl_sd_ccgp(
    *,
    max_pages: Optional[int] = None,
    page_size: int = 20,
    with_detail: bool = True,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    stop_dup: Optional[int] = None,
) -> None:
    """中国山东政府采购网：省级 + 市区县；排除中小企业预留执行公告。"""
    _ensure_notice_key_width()
    repaired = repair_ccgp_bodies()
    if repaired:
        tqdm.write(f"sd-ccgp 已修复 base64 正文 {repaired} 条，将在抓取中重解析")
    start_day = _as_day(start_date)
    end_day = _as_day(end_date)
    start_arg = f"{start_day.isoformat()} 00:00:00" if start_day else ""
    end_arg = f"{end_day.isoformat()} 23:59:59" if end_day else ""
    client = SdCcgpClient()
    session = get_session()
    try:
        categories = list(client.iter_categories())
        for cat_idx, (scope_key, area, col_code, canonical, label) in enumerate(categories):
            if cat_idx > 0:
                client.pause_between_categories()
            cursor_key = f"{scope_key}:{canonical}"
            page = 1
            total_pages = None
            dup = _DupStop(stop_dup)
            stop_category = False
            pbar = tqdm(desc=f"{CCGP_SITE}/{label}", unit="page")
            while True:
                if max_pages and page > max_pages:
                    break
                data = None
                for attempt in range(8):
                    try:
                        data = client.list_notices(
                            col_code=col_code,
                            area=area,
                            page_num=page,
                            page_size=page_size,
                            start_time=start_arg,
                            end_time=end_arg,
                        )
                        break
                    except Exception as exc:  # noqa: BLE001
                        msg = str(exc)
                        retryable = any(
                            k in msg.lower()
                            for k in (
                                "captcha",
                                "验证码",
                                "blackip",
                                "http 400",
                                "http 429",
                                "http 502",
                                "http 503",
                                "http 504",
                                "list failed",
                            )
                        )
                        if not retryable:
                            raise
                        client.clear_captcha()
                        wait = 20.0 if "blackip" in msg.lower() else min(15.0, 2.0 * (attempt + 1))
                        tqdm.write(
                            f"{label} 第{page}页列表失败，{wait:.0f}s 后重试 ({attempt + 1}/8): {exc}"
                        )
                        time.sleep(wait)
                if data is None:
                    tqdm.write(f"{label} 第{page}页多次失败，跳过该类后续页")
                    break
                items = data.get("records") or []
                total = int(data.get("total") or 0)
                if total_pages is None:
                    total_pages = max(1, (total + page_size - 1) // page_size) if total else 1
                    pbar.total = min(total_pages, max_pages or total_pages)

                for item in items:
                    notice_id = str(item.get("id") or "").strip()
                    if not notice_id:
                        continue
                    item_col = str(item.get("colCode") or col_code)
                    publish_dt = parse_dt(item.get("date") or item.get("publishTime"))
                    published = _day_of(publish_dt or item.get("date") or item.get("publishTime"))
                    # 列表加密 id 会轮换；稳定键 = 标题 + 发布时间 + 栏目类型
                    notice_key = client.stable_notice_key(
                        title=item.get("title"),
                        publish_time=publish_dt or item.get("date") or item.get("publishTime"),
                        notice_type=canonical,
                        notice_id=notice_id,
                    )
                    if start_day and published and published < start_day:
                        stop_category = True
                        tqdm.write(f"{label} 早于 {start_day.isoformat()}，停止该类")
                        break
                    if end_day and published and published > end_day:
                        continue
                    existing = find_ccgp_raw(
                        session,
                        notice_key=notice_key,
                        title=item.get("title"),
                        publish_time=publish_dt,
                        notice_type=canonical,
                    )
                    if existing is not None:
                        # 旧数据仍是 id-hash 键时，顺带迁到稳定键，便于后续 raw_exists
                        if existing.notice_key != notice_key:
                            clash = session.execute(
                                select(NoticeRaw.id).where(
                                    NoticeRaw.site_id == CCGP_SITE,
                                    NoticeRaw.notice_key == notice_key,
                                    NoticeRaw.id != existing.id,
                                )
                            ).scalar_one_or_none()
                            if clash is None:
                                existing.notice_key = notice_key
                        existing.list_json = dumps(item)
                        existing.source_url = client.notice_detail_url(
                            notice_id, item_col, old_data=item.get("oldData")
                        )
                        session.commit()
                        if dup.hit(True):
                            stop_category = True
                            tqdm.write(f"{label} 连续重复 {dup.limit} 条，停止该类")
                            break
                        continue
                    # 新公告：重置连续重复计数
                    dup.hit(False)

                    publisher = str(
                        item.get("userName") or item.get("publisher") or ""
                    ).strip()
                    # 发布人=网上商城：多为商城镜像；商城已有同项目编号则不再入库
                    skip_mall_mirror = False
                    prefetched_detail = None
                    prefetched_html = ""
                    prefetched_text = ""
                    if publisher == "网上商城" and with_detail:
                        try:
                            prefetched_detail = client.get_detail(
                                notice_id,
                                item_col,
                                old_data=item.get("oldData"),
                            )
                            prefetched_html = decode_notice_body(
                                (prefetched_detail or {}).get("body") or ""
                            )
                            if (
                                (prefetched_detail or {}).get("existNoticeBody")
                                and len(prefetched_html) < 40
                            ):
                                try:
                                    body_extra = client.get_notice_body(
                                        notice_id, item_col
                                    )
                                    extra_html = decode_notice_body(
                                        body_extra.get("body")
                                        or body_extra.get("content")
                                        or body_extra.get("value")
                                        or ""
                                    )
                                    if extra_html:
                                        prefetched_html = extra_html
                                        prefetched_detail = {
                                            **prefetched_detail,
                                            "noticeBody": body_extra,
                                        }
                                except Exception:  # noqa: BLE001
                                    pass
                            if isinstance(prefetched_detail, dict):
                                prefetched_detail = {
                                    **prefetched_detail,
                                    "body": prefetched_html,
                                }
                            prefetched_text = html_to_text(prefetched_html)
                            code = extract_project_code(
                                item.get("title"),
                                (prefetched_detail or {}).get("title"),
                                prefetched_text,
                                prefetched_html,
                            )
                            if code and mall_has_project_code(session, code):
                                skip_mall_mirror = True
                        except Exception as exc:  # noqa: BLE001
                            tqdm.write(
                                f"{label} 网上商城镜像预检失败，按普通公告处理："
                                f"{(item.get('title') or '')[:40]} {exc}"
                            )
                            prefetched_detail = None

                    if skip_mall_mirror:
                        if dup.hit(True):
                            stop_category = True
                            tqdm.write(
                                f"{label} 连续重复 {dup.limit} 条（含网上商城已镜像），停止该类"
                            )
                            break
                        continue

                    region_name, district_name, region_guid = _ccgp_region_fields(item)
                    upsert_raw(
                        session,
                        site_id=CCGP_SITE,
                        notice_key=notice_key,
                        auction_type=scope_key,
                        notice_type=canonical,
                        title=item.get("title"),
                        region_name=region_name,
                        district_name=district_name,
                        region_guid=region_guid,
                        publish_time=publish_dt,
                        list_json=item,
                        source_url=client.notice_detail_url(
                            notice_id, item_col, old_data=item.get("oldData")
                        ),
                        crawl_status="list_only",
                    )
                    session.commit()
                    if with_detail:
                        try:
                            if prefetched_detail is not None:
                                detail = prefetched_detail
                                html = prefetched_html
                                text = prefetched_text
                            else:
                                detail = client.get_detail(
                                    notice_id,
                                    item_col,
                                    old_data=item.get("oldData"),
                                )
                                html = decode_notice_body(detail.get("body") or "")
                                if detail.get("existNoticeBody") and len(html) < 40:
                                    try:
                                        body_extra = client.get_notice_body(
                                            notice_id, item_col
                                        )
                                        extra_html = decode_notice_body(
                                            body_extra.get("body")
                                            or body_extra.get("content")
                                            or body_extra.get("value")
                                            or ""
                                        )
                                        if extra_html:
                                            html = extra_html
                                            detail = {
                                                **detail,
                                                "noticeBody": body_extra,
                                            }
                                    except Exception:  # noqa: BLE001
                                        pass
                                if isinstance(detail, dict):
                                    detail = {**detail, "body": html}
                                text = html_to_text(html)
                            # 列表未标发布人时，详情也可能是网上商城镜像
                            detail_publisher = str(
                                (detail or {}).get("userName")
                                or (detail or {}).get("publisher")
                                or publisher
                                or ""
                            ).strip()
                            if detail_publisher == "网上商城":
                                code = extract_project_code(
                                    item.get("title"),
                                    (detail or {}).get("title"),
                                    text,
                                    html,
                                )
                                if code and mall_has_project_code(session, code):
                                    session.rollback()
                                    orphan = session.execute(
                                        select(NoticeRaw).where(
                                            NoticeRaw.site_id == CCGP_SITE,
                                            NoticeRaw.notice_key == notice_key,
                                        )
                                    ).scalar_one_or_none()
                                    if orphan is not None and orphan.crawl_status in (
                                        "list_only",
                                        "detail_fail",
                                    ):
                                        session.delete(orphan)
                                        session.commit()
                                    if dup.hit(True):
                                        stop_category = True
                                        tqdm.write(
                                            f"{label} 连续重复 {dup.limit} 条"
                                            f"（含网上商城已镜像），停止该类"
                                        )
                                        break
                                    continue
                            raw = upsert_raw(
                                session,
                                site_id=CCGP_SITE,
                                notice_key=notice_key,
                                detail_json=detail,
                                content_html=html,
                                content_text=text,
                                title=detail.get("title") or item.get("title"),
                                publish_time=parse_dt(
                                    detail.get("date") or item.get("date")
                                ),
                                crawl_status="detail_ok",
                            )
                            try:
                                _parse_after_detail(session, raw, html=html, text=text)
                            except Exception as exc:  # noqa: BLE001
                                raw.parse_status = "parse_fail"
                                raw.error_message = str(exc)[:1000]
                            files = client.extract_attachments(detail)
                            session.commit()
                            if files:
                                raw = session.execute(
                                    select(NoticeRaw).where(
                                        NoticeRaw.site_id == CCGP_SITE,
                                        NoticeRaw.notice_key == notice_key,
                                    )
                                ).scalar_one()
                                ingest_attachments(session, raw, files)
                                session.commit()
                        except Exception as exc:  # noqa: BLE001
                            session.rollback()
                            upsert_raw(
                                session,
                                site_id=CCGP_SITE,
                                notice_key=notice_key,
                                crawl_status="detail_fail",
                                error_message=str(exc),
                            )
                            session.commit()

                save_cursor(session, CCGP_SITE, cursor_key, page, total)
                session.commit()
                pbar.update(1)
                if stop_category or page >= total_pages or not items:
                    break
                page += 1
                client.pause_between_pages()
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
    # 泉易采 / 青慧采共用同一套接口，按合同号分 site_id 入库
    start_day = _as_day(start_date)
    end_day = _as_day(end_date)
    for site_cfg in jd_site_configs():
        _crawl_jd_site(
            JdQuanClient.from_config(site_cfg),
            max_pages=max_pages,
            page_size=page_size,
            with_detail=with_detail,
            start_day=start_day,
            end_day=end_day,
            stop_dup=stop_dup,
        )
    if with_detail:
        import os

        limit = int(os.getenv("CRAWL_ATT_LIMIT", "100") or "100")
        # 抓取阶段只补下载，避免本地模型拖慢列表
        synced = sync_missing_jd_attachments(limit=max(limit, 1), use_llm=False)
        if synced:
            tqdm.write(f"京东历史附件已补下载 {synced} 个")
        # 默认不在 crawl 末尾跑模型；设 CRAWL_PARSE_ATT=1 或单独 parse-att
        flag = (os.getenv("CRAWL_PARSE_ATT") or "0").strip().lower()
        if flag in {"1", "true", "yes", "on"}:
            parsed_n = 0
            for site in ("jd-quan-yicai", "jd-qing-huicai"):
                parsed_n += parse_attachments(limit=max(limit, 1), site_id=site, use_llm=True)
            if parsed_n:
                tqdm.write(f"京东附件本地模型已解析 {parsed_n} 个")


def _crawl_jd_site(
    client: JdQuanClient,
    *,
    max_pages: Optional[int] = None,
    page_size: int = 50,
    with_detail: bool = True,
    start_day: Optional[date] = None,
    end_day: Optional[date] = None,
    stop_dup: Optional[int] = None,
) -> None:
    site_id = client.site_id
    session = get_session()
    try:
        for auction_type, notice_type, label, business_type in client.iter_categories():
            cursor_key = f"{auction_type}:{notice_type}"
            page = 1
            total_pages = None
            dup = _DupStop(stop_dup)
            stop_category = False
            pbar = tqdm(desc=f"{site_id}/{label}", unit="page")
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
                        tqdm.write(f"{client.label}/{label} 早于 {start_day.isoformat()}，停止该类")
                        break
                    notice_key = f"{auction_no}:{item_notice_type}"
                    if dup.hit(raw_exists(session, site_id, notice_key)):
                        stop_category = True
                        tqdm.write(f"{client.label}/{label} 连续重复 {dup.limit} 条，停止该类")
                        break
                    if dup.streak:
                        continue
                    # 先只写列表并立刻提交，避免拉详情/下附件时长时间占锁
                    raw_region = item.get("regionName")
                    upsert_raw(
                        session,
                        site_id=site_id,
                        notice_key=notice_key,
                        auction_type=str(item.get("auctionType") or auction_type),
                        notice_type=str(item_notice_type if item_notice_type is not None else notice_type),
                        title=item.get("noticeTitle") or item.get("auctionName"),
                        region_name=normalize_region_name(site_id, raw_region),
                        district_name=extract_district_name(raw_region),
                        region_guid=item.get("regionGuid") or item.get("regionId"),
                        publish_time=parse_dt(item.get("createTime")),
                        list_json=item,
                        source_url=client.notice_detail_url(
                            auction_no,
                            item_notice_type,
                            business_type=business_type,
                        ),
                        crawl_status="list_only",
                    )
                    session.commit()
                    if with_detail:
                        files = []
                        try:
                            detail = client.get_detail(auction_no, item_notice_type or notice_type)
                            # JD 详情多为结构化 JSON，无整页 HTML；拼可读文本供规则/模型
                            content_text = json_detail_to_text(detail)
                            raw = upsert_raw(
                                session,
                                site_id=site_id,
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
                            files = client.extract_attachments(detail)
                            # 详情+解析先落库，再下附件，避免下载时占着 notice_goods 行锁
                            session.commit()
                            if files:
                                raw = session.execute(
                                    select(NoticeRaw).where(
                                        NoticeRaw.site_id == site_id,
                                        NoticeRaw.notice_key == notice_key,
                                    )
                                ).scalar_one()
                                ingest_attachments(session, raw, files)
                                session.commit()
                        except Exception as exc:  # noqa: BLE001
                            session.rollback()
                            upsert_raw(
                                session,
                                site_id=site_id,
                                notice_key=notice_key,
                                crawl_status="detail_fail",
                                error_message=str(exc),
                            )
                            session.commit()
                save_cursor(session, site_id, cursor_key, page, total)
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

    def _fmt_ts(v):
        if v in (None, ""):
            return ""
        parsed = parse_dt(v)
        if parsed is not None:
            return parsed.strftime("%Y-%m-%d %H:%M:%S")
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
