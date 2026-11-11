"""公告订阅日汇总推送。"""

from __future__ import annotations

import logging
from datetime import date, datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from django.db import IntegrityError, transaction
from django.db.models import Q
from django.utils import timezone

from .models import CustomerAccountRecord
from .notice_inbox_models import PortalNoticeInbox
from .notice_models import NoticeParsed, NoticeRaw
from .notice_push_models import NoticePushLog
from .notice_subscription import (
    notice_matches_subscription,
    normalize_subscription,
    subscription_has_filters,
)
from .notice_tag_models import NoticeResultTag
from .portal import account_site_scope, normalize_portal_permissions, public_account
from . import wechat_mp

logger = logging.getLogger(__name__)
SHANGHAI = ZoneInfo("Asia/Shanghai")
CHANNEL = "wechat_mp"


def digest_day_bounds(digest_date: date) -> tuple[datetime, datetime]:
    start = datetime(digest_date.year, digest_date.month, digest_date.day, tzinfo=SHANGHAI)
    end = start + timedelta(days=1)
    return start, end


def default_digest_date(*, now: datetime | None = None) -> date:
    """默认推送「上一自然日」。"""
    current = timezone.localtime(now or timezone.now(), SHANGHAI)
    return (current - timedelta(days=1)).date()


def _account_wechat(record: CustomerAccountRecord) -> dict[str, Any]:
    data = record.data if isinstance(record.data, dict) else {}
    wechat = data.get("wechat") if isinstance(data.get("wechat"), dict) else {}
    return {
        "openid": str(wechat.get("openid") or "").strip(),
        "followStatus": str(wechat.get("followStatus") or "unknown").strip() or "unknown",
        "boundAt": str(wechat.get("boundAt") or "").strip(),
    }


def _iter_eligible_accounts():
    qs = CustomerAccountRecord.objects.filter(is_deleted=False, status="启用")
    for record in qs.iterator(chunk_size=200):
        account = public_account(record)
        perms = set(normalize_portal_permissions(account.get("permissions")))
        if "portal.notice.subscribe" not in perms:
            continue
        sub = normalize_subscription(account.get("subscription"))
        if not sub.get("enabled") or not subscription_has_filters(sub):
            continue
        wechat = _account_wechat(record)
        if not wechat["openid"]:
            continue
        if wechat["followStatus"] == "unsubscribed":
            continue
        yield record, account, sub, wechat


def _load_day_notices(digest_date: date, *, site_ids: list[str] | None) -> list[dict[str, Any]]:
    start, end = digest_day_bounds(digest_date)
    parsed_qs = NoticeParsed.objects.filter(publish_time__gte=start, publish_time__lt=end)
    rows = list(
        parsed_qs.values(
            "notice_raw_id",
            "notice_title",
            "project_name",
            "buyer_name",
            "region_name",
            "publish_time",
        )
    )
    if not rows:
        return []
    raw_ids = [int(row["notice_raw_id"]) for row in rows]
    raw_map = {
        item.id: item
        for item in NoticeRaw.objects.filter(id__in=raw_ids).only("id", "site_id", "title", "region_name")
    }
    if site_ids is not None:
        allowed = set(site_ids)
        rows = [row for row in rows if (raw_map.get(int(row["notice_raw_id"])) and raw_map[int(row["notice_raw_id"])].site_id in allowed)]
        raw_ids = [int(row["notice_raw_id"]) for row in rows]
        if not raw_ids:
            return []
    tags = {
        tag.notice_raw_id: tag
        for tag in NoticeResultTag.objects.select_related("buyer_profile").filter(notice_raw_id__in=raw_ids)
    }
    result: list[dict[str, Any]] = []
    for row in rows:
        rid = int(row["notice_raw_id"])
        raw = raw_map.get(rid)
        tag = tags.get(rid)
        profile = tag.buyer_profile if tag and tag.buyer_profile_id else None
        title = (row.get("notice_title") or (raw.title if raw else "") or "").strip()
        result.append(
            {
                "id": rid,
                "title": title,
                "projectName": (row.get("project_name") or "").strip(),
                "buyerName": (row.get("buyer_name") or (profile.buyer_name if profile else "") or "").strip(),
                "regionName": (row.get("region_name") or (raw.region_name if raw else "") or "").strip(),
                "contentTag": ((tag.content_tag if tag else "") or "").strip(),
                "orgType": ((profile.org_type if profile else "") or "").strip(),
                "province": ((profile.province if profile else "") or "").strip(),
                "city": ((profile.city if profile else "") or "").strip(),
                "district": ((profile.district if profile else "") or "").strip(),
                "siteId": (raw.site_id if raw else "") or "",
            }
        )
    return result


def match_notices_for_subscription(notices: list[dict[str, Any]], subscription: dict[str, Any]) -> list[dict[str, Any]]:
    hits: list[dict[str, Any]] = []
    for item in notices:
        if notice_matches_subscription(
            subscription=subscription,
            title=item.get("title") or "",
            project_name=item.get("projectName") or "",
            buyer_name=item.get("buyerName") or "",
            content_tag=item.get("contentTag") or "",
            org_type=item.get("orgType") or "",
            province=item.get("province") or "",
            city=item.get("city") or "",
            district=item.get("district") or "",
            region_name=item.get("regionName") or "",
        ):
            hits.append(item)
    return hits


def _clip(value: str, limit: int) -> str:
    text = str(value or "").strip()
    if len(text) <= limit:
        return text
    return text[: max(limit - 1, 1)] + "…"


def _template_data(
    *,
    digest_date: date,
    hits: list[dict[str, Any]],
    now: datetime | None = None,
) -> dict[str, dict[str, str]]:
    """汇总通知：有 N 条公告更新了 → 点击进消息列表。"""
    del digest_date  # 保留参数兼容旧调用
    count = max(len(hits), 0)
    current = timezone.localtime(now or timezone.now(), SHANGHAI)
    return {
        "thing1": {"value": _clip(f"有{count}条公告更新了", 20)},
        "time2": {"value": current.strftime("%Y-%m-%d %H:%M:%S")},
        "thing3": {"value": _clip("点击查看消息列表", 20)},
        "character_string5": {"value": _clip(str(count or "0"), 32)},
    }


def _upsert_inbox_messages(
    *,
    account_id: str,
    digest_date: date,
    hits: list[dict[str, Any]],
    push_log_id: int | None = None,
) -> list[int]:
    notice_ids: list[int] = []
    for item in hits:
        notice_id = int(item.get("id") or 0)
        if notice_id <= 0:
            continue
        notice_ids.append(notice_id)
        PortalNoticeInbox.objects.update_or_create(
            customer_account_id=account_id,
            notice_raw_id=notice_id,
            digest_date=digest_date,
            defaults={
                "push_log_id": push_log_id,
                "title": str(item.get("title") or "")[:500],
                "project_name": str(item.get("projectName") or "")[:255],
                "buyer_name": str(item.get("buyerName") or "")[:255],
                "region_name": str(item.get("regionName") or "")[:128],
                "site_id": str(item.get("siteId") or "")[:64],
            },
        )
    return notice_ids


def build_notice_template_data(
    *,
    project: str,
    bid_time: str,
    initiator: str,
    project_code: str,
) -> dict[str, dict[str, str]]:
    return {
        "thing1": {"value": _clip(project, 20)},
        "time2": {"value": _clip(bid_time, 40)},
        "thing3": {"value": _clip(initiator, 20)},
        "character_string5": {"value": _clip(project_code, 32)},
    }


def send_manual_template_for_account(
    *,
    account_id: str,
    project: str,
    bid_time: str,
    initiator: str,
    project_code: str,
    jump_url: str = "",
) -> dict[str, Any]:
    """开发手动推送：按模板字段直发，不走日汇总匹配。"""
    record = CustomerAccountRecord.objects.filter(id=account_id, is_deleted=False).first()
    if not record:
        return {"accountId": account_id, "status": "failed", "reason": "not_found"}
    if (record.status or "") != "启用":
        return {"accountId": account_id, "status": "failed", "reason": "disabled"}
    account = public_account(record)
    wechat = _account_wechat(record)
    if not wechat["openid"]:
        return {"accountId": account_id, "status": "failed", "reason": "wechat_unbound"}
    if wechat["followStatus"] == "unsubscribed":
        return {"accountId": account_id, "status": "failed", "reason": "wechat_unsubscribed"}
    if not wechat_mp.mp_configured():
        return {"accountId": account_id, "status": "failed", "reason": "wechat_not_configured"}
    project = str(project or "").strip()
    bid_time = str(bid_time or "").strip()
    initiator = str(initiator or "").strip()
    project_code = str(project_code or "").strip()
    if not project or not bid_time or not initiator or not project_code:
        return {"accountId": account_id, "status": "failed", "reason": "invalid_fields"}
    result = wechat_mp.send_template_message(
        openid=wechat["openid"],
        data=build_notice_template_data(
            project=project,
            bid_time=bid_time,
            initiator=initiator,
            project_code=project_code,
        ),
        url=(jump_url or wechat_mp.portal_notice_url() or "").strip(),
        client_msg_id=f"notice-manual-{record.id}-{int(timezone.now().timestamp())}",
    )
    return {
        "accountId": record.id,
        "accountName": account.get("name") or "",
        "phone": account.get("phone") or "",
        "status": "sent" if result.get("ok") else "failed",
        "errcode": result.get("errcode"),
        "errmsg": result.get("errmsg"),
    }


def _already_sent(account_id: str, digest_date: date) -> bool:
    return NoticePushLog.objects.filter(
        customer_account_id=account_id,
        channel=CHANNEL,
        digest_date=digest_date,
        status="sent",
    ).exists()


def send_digest_for_account(
    *,
    record: CustomerAccountRecord,
    account: dict[str, Any],
    subscription: dict[str, Any],
    wechat: dict[str, Any],
    digest_date: date,
    day_notices: list[dict[str, Any]] | None = None,
    dry_run: bool = False,
    force: bool = False,
    allow_empty: bool = False,
) -> dict[str, Any]:
    if not force and _already_sent(record.id, digest_date):
        return {"accountId": record.id, "status": "skipped", "reason": "already_sent"}

    scope = account_site_scope(account)
    notices = day_notices
    if notices is None:
        notices = _load_day_notices(digest_date, site_ids=scope)
    elif scope is not None:
        allowed = set(scope)
        notices = [item for item in notices if item.get("siteId") in allowed]

    hits = match_notices_for_subscription(notices, subscription)
    empty_test = False
    if not hits:
        if not allow_empty:
            return {"accountId": record.id, "status": "skipped", "reason": "no_match", "matched": 0}
        empty_test = True
        hits = [{"id": 0, "title": "手动测试推送"}]

    notice_ids = [int(item["id"]) for item in hits[:200] if int(item.get("id") or 0) > 0]
    filter_snapshot = normalize_subscription(subscription)
    if dry_run:
        return {
            "accountId": record.id,
            "status": "dry_run",
            "matched": 0 if empty_test else len(hits),
            "noticeIds": notice_ids,
            "emptyTest": empty_test,
        }

    try:
        with transaction.atomic():
            log, created = NoticePushLog.objects.get_or_create(
                customer_account_id=record.id,
                channel=CHANNEL,
                digest_date=digest_date,
                defaults={
                    "openid": wechat["openid"],
                    "filter_snapshot": filter_snapshot,
                    "notice_ids": notice_ids,
                    "status": "pending",
                },
            )
            if not created and log.status == "sent" and not force:
                return {"accountId": record.id, "status": "skipped", "reason": "already_sent"}
            if not created:
                log.openid = wechat["openid"]
                log.filter_snapshot = filter_snapshot
                log.notice_ids = notice_ids
                log.status = "pending"
                log.errcode = 0
                log.errmsg = ""
                log.save(update_fields=["openid", "filter_snapshot", "notice_ids", "status", "errcode", "errmsg", "updated_at"])
            if not empty_test:
                _upsert_inbox_messages(
                    account_id=record.id,
                    digest_date=digest_date,
                    hits=hits,
                    push_log_id=log.id,
                )
    except IntegrityError:
        return {"accountId": record.id, "status": "skipped", "reason": "race"}

    client_msg_id = f"notice-digest-{record.id}-{digest_date.isoformat()}"
    if force or empty_test:
        client_msg_id = f"{client_msg_id}-m{int(timezone.now().timestamp())}"

    result = wechat_mp.send_template_message(
        openid=wechat["openid"],
        data=_template_data(digest_date=digest_date, hits=hits),
        url=wechat_mp.portal_messages_url(),
        client_msg_id=client_msg_id,
    )
    log = NoticePushLog.objects.filter(
        customer_account_id=record.id, channel=CHANNEL, digest_date=digest_date
    ).first()
    if log:
        log.status = "sent" if result.get("ok") else "failed"
        log.errcode = int(result.get("errcode") or 0)
        log.errmsg = str(result.get("errmsg") or "")[:255]
        log.notice_ids = notice_ids
        log.filter_snapshot = filter_snapshot
        log.save(update_fields=["status", "errcode", "errmsg", "notice_ids", "filter_snapshot", "updated_at"])

    return {
        "accountId": record.id,
        "status": "sent" if result.get("ok") else "failed",
        "matched": 0 if empty_test else len(hits),
        "emptyTest": empty_test,
        "errcode": result.get("errcode"),
        "errmsg": result.get("errmsg"),
    }


def send_manual_digest_for_account(
    *,
    account_id: str,
    digest_date: date | None = None,
    dry_run: bool = False,
    force: bool = True,
    allow_empty: bool = True,
) -> dict[str, Any]:
    """开发手动推送：不要求订阅已开启，只要已绑定微信即可。"""
    record = CustomerAccountRecord.objects.filter(id=account_id, is_deleted=False).first()
    if not record:
        return {"accountId": account_id, "status": "failed", "reason": "not_found"}
    if (record.status or "") != "启用":
        return {"accountId": account_id, "status": "failed", "reason": "disabled"}
    account = public_account(record)
    wechat = _account_wechat(record)
    if not wechat["openid"]:
        return {"accountId": account_id, "status": "failed", "reason": "wechat_unbound"}
    if wechat["followStatus"] == "unsubscribed":
        return {"accountId": account_id, "status": "failed", "reason": "wechat_unsubscribed"}
    if not wechat_mp.mp_configured():
        return {"accountId": account_id, "status": "failed", "reason": "wechat_not_configured"}
    subscription = normalize_subscription(account.get("subscription"))
    day = digest_date or default_digest_date()
    outcome = send_digest_for_account(
        record=record,
        account=account,
        subscription=subscription,
        wechat=wechat,
        digest_date=day,
        dry_run=dry_run,
        force=force,
        allow_empty=allow_empty,
    )
    outcome["date"] = day.isoformat()
    outcome["accountName"] = account.get("name") or ""
    outcome["phone"] = account.get("phone") or ""
    return outcome


def run_notice_digest(*, digest_date: date | None = None, dry_run: bool = False, limit: int = 0) -> dict[str, Any]:
    day = digest_date or default_digest_date()
    # 全量日公告先按「不限站点」加载；各账号再按 allowedSiteIds 过滤
    all_notices = _load_day_notices(day, site_ids=None)
    stats = {"date": day.isoformat(), "accounts": 0, "sent": 0, "failed": 0, "skipped": 0, "matchedAccounts": 0}
    details: list[dict[str, Any]] = []
    for record, account, subscription, wechat in _iter_eligible_accounts():
        if limit and stats["accounts"] >= limit:
            break
        stats["accounts"] += 1
        # 按账号站点裁剪缓存列表
        scope = account_site_scope(account)
        if scope is None:
            day_notices = all_notices
        else:
            allowed = set(scope)
            day_notices = [item for item in all_notices if item.get("siteId") in allowed]
        outcome = send_digest_for_account(
            record=record,
            account=account,
            subscription=subscription,
            wechat=wechat,
            digest_date=day,
            day_notices=day_notices,
            dry_run=dry_run,
        )
        details.append(outcome)
        status = outcome.get("status")
        if status == "sent":
            stats["sent"] += 1
            stats["matchedAccounts"] += 1
        elif status == "failed":
            stats["failed"] += 1
            stats["matchedAccounts"] += 1
        elif status == "dry_run":
            stats["matchedAccounts"] += 1
            stats["skipped"] += 1
        else:
            stats["skipped"] += 1
    stats["details"] = details
    logger.info("notice digest done %s", {k: v for k, v in stats.items() if k != "details"})
    return stats
