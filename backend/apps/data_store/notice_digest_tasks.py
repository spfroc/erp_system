"""公告订阅日汇总 Celery 任务。"""

from __future__ import annotations

from celery import shared_task

from .notice_digest import default_digest_date, run_notice_digest


@shared_task(name="apps.data_store.notice_digest_tasks.run_daily_notice_digest")
def run_daily_notice_digest() -> dict:
    return run_notice_digest(digest_date=default_digest_date(), dry_run=False)
