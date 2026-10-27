"""预置定时任务，避免管理页空白。"""

from __future__ import annotations

from django.utils import timezone

from .dev_ops_catalog import SCRIPT_CATALOG
from .dev_ops_models import DevOpsJob
from .dev_ops_schedule import next_run_at

# 常驻采集由 notice-crawler 容器负责；这里预置可手动跑/改调度的任务行。
DEFAULT_JOB_SPECS = [
    {
        "script_key": "notice_crawl_once",
        "name": "公告采集一轮",
        "enabled": False,
        "schedule_type": "interval",
        "interval_seconds": 10800,
        "args": {"lookback_days": 2, "page_size": 20, "stop_dup": 5, "site": "all", "list_only": False},
    },
    {
        "script_key": "notice_crawl_all",
        "name": "公告全量采集",
        "enabled": False,
        "schedule_type": "manual",
        "interval_seconds": None,
        "args": {"page_size": 20, "site": "all", "list_only": False},
    },
    {
        "script_key": "tag_notice_results",
        "name": "结果公告规则打标",
        "enabled": False,
        "schedule_type": "manual",
        "interval_seconds": None,
        "args": {"limit": 200, "rebuild": False},
    },
    {
        "script_key": "notice_migrate_list_indexes",
        "name": "采集表列表索引迁移",
        "enabled": False,
        "schedule_type": "manual",
        "interval_seconds": None,
        "args": {},
    },
    {
        "script_key": "repair_transaction_projects",
        "name": "修复交易项目关联",
        "enabled": False,
        "schedule_type": "manual",
        "interval_seconds": None,
        "args": {},
    },
    {
        "script_key": "import_library_sms",
        "name": "导入资料库短信",
        "enabled": False,
        "schedule_type": "manual",
        "interval_seconds": None,
        "args": {},
    },
]


def ensure_default_dev_ops_jobs() -> int:
    created = 0
    now = timezone.now()
    for spec in DEFAULT_JOB_SPECS:
        script_key = spec["script_key"]
        if script_key not in SCRIPT_CATALOG:
            continue
        if DevOpsJob.objects.filter(script_key=script_key).exists():
            continue
        job = DevOpsJob(
            script_key=script_key,
            name=spec["name"],
            enabled=bool(spec.get("enabled")),
            schedule_type=spec.get("schedule_type") or "manual",
            interval_seconds=spec.get("interval_seconds"),
            cron_expr="",
            args_json=spec.get("args") or {},
            updated_by="system",
        )
        job.next_run_at = next_run_at(
            schedule_type=job.schedule_type,
            interval_seconds=job.interval_seconds,
            cron_expr=job.cron_expr,
            now=now,
            last_run_at=None,
        )
        job.save()
        created += 1
    return created
