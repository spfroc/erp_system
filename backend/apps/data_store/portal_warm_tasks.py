"""定时预热门户热路径，避免长时间闲置后首屏冷查库。"""

from __future__ import annotations

import hashlib
import logging

from celery import shared_task
from django.core.cache import cache
from django.utils import timezone

logger = logging.getLogger(__name__)


def _stats_cache_key(*, include_notice: bool, include_tags: bool) -> str:
    raw = "|".join(
        [
            "*",
            "all",
            "last_30_days",
            "",
            "",
            "1" if include_notice else "0",
            "1" if include_tags else "0",
            "0",
            "",
            "",
            "",
        ]
    )
    return "portal_stats_v2:" + hashlib.md5(raw.encode("utf-8")).hexdigest()


@shared_task(name="apps.data_store.portal_warm_tasks.warm_portal_hot_paths")
def warm_portal_hot_paths() -> dict:
    from apps.data_store.notice_tagging import period_bounds, safe_stats
    from apps.data_store.notice_views import _cached_raw_total, query_crawled_notices
    from apps.data_store.portal import (
        PORTAL_NOTICE_KINDS,
        PORTAL_NOTICES_DEFAULT_CACHE_SECONDS,
        PORTAL_STATS_CACHE_SECONDS,
        _empty_notice_stats,
        _portal_swr_pack,
        build_notice_stats,
        site_options,
    )

    started = timezone.now()
    result: dict = {"ok": True, "steps": {}}

    try:
        result["steps"]["raw_total"] = _cached_raw_total()
    except Exception as exc:
        logger.exception("warm raw_total failed")
        result["ok"] = False
        result["steps"]["raw_total"] = str(exc)

    try:
        body = query_crawled_notices(page=1, page_size=20)
        body["sites"] = site_options(None)
        body["noticeKinds"] = PORTAL_NOTICE_KINDS + ["意向公开", "结果公告", "成交结果公告"]
        cache.set(
            "portal_notices_default_v2:all",
            _portal_swr_pack(body),
            PORTAL_NOTICES_DEFAULT_CACHE_SECONDS,
        )
        result["steps"]["notices_default"] = body.get("total")
    except Exception as exc:
        logger.exception("warm notices failed")
        result["ok"] = False
        result["steps"]["notices_default"] = str(exc)

    try:
        bound_start, bound_end = period_bounds("last_30_days")
        range_start = bound_start.date()
        range_end = bound_end.date()
        notice_stats = build_notice_stats(site_ids=None, start=range_start, end=range_end)
        notice_stats.pop("_siteMaps", None)
        notice_stats["sites"] = site_options(None)
        cache.set(
            _stats_cache_key(include_notice=True, include_tags=False),
            _portal_swr_pack({"period": "last_30_days", **notice_stats, "tagStats": {}}),
            PORTAL_STATS_CACHE_SECONDS,
        )

        empty = _empty_notice_stats(None, start=range_start, end=range_end)
        empty["sites"] = site_options(None)
        tag_stats = safe_stats(period="last_30_days", site_ids=None)
        cache.set(
            _stats_cache_key(include_notice=False, include_tags=True),
            _portal_swr_pack({"period": "last_30_days", **empty, "tagStats": tag_stats}),
            PORTAL_STATS_CACHE_SECONDS,
        )
        result["steps"]["stats_notice"] = notice_stats.get("publicNoticeTotal")
        result["steps"]["stats_tags"] = tag_stats.get("noticeCount")
    except Exception as exc:
        logger.exception("warm stats failed")
        result["ok"] = False
        result["steps"]["stats"] = str(exc)

    result["elapsedMs"] = int((timezone.now() - started).total_seconds() * 1000)
    return result
