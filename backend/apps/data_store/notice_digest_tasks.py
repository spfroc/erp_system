"""公告订阅推送 Celery 任务。"""

from __future__ import annotations

from celery import shared_task
from django.utils import timezone
from zoneinfo import ZoneInfo

from .notice_digest import run_notice_digest

SHANGHAI = ZoneInfo("Asia/Shanghai")


@shared_task(name="apps.data_store.notice_digest_tasks.run_daily_notice_digest")
def run_daily_notice_digest() -> dict:
    """每分钟调度：仅推送当前时刻命中自定义 pushTimes 的账号。"""
    now = timezone.localtime(timezone.now(), SHANGHAI)
    slot = now.strftime("%H:%M")
    return run_notice_digest(digest_date=now.date(), push_slot=slot, dry_run=False)
