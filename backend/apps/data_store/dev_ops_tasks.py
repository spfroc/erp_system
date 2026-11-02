from __future__ import annotations

from datetime import timedelta

from celery import shared_task
from django.db import transaction
from django.utils import timezone

from .dev_ops_catalog import get_script
from .dev_ops_models import DevOpsJob, DevOpsJobRun
from .dev_ops_runner import run_script
from .dev_ops_schedule import next_run_at

# pending 超过此时长仍未变成 running，视为队列丢失
PENDING_STALE_SECONDS = 2 * 3600
# running 超过脚本 timeout 后再宽限此时长，仍无结束则收尸
RUNNING_GRACE_SECONDS = 10 * 60

PREEMPT_NOTE = (
    "[系统] 被公告采集一轮抢占暂停（once run#{once_id}）。"
    "全量不会自动恢复，如需请手动再跑全量。"
)


@shared_task(name="apps.data_store.dev_ops_tasks.run_dev_ops_job")
def run_dev_ops_job(run_id: int):
    return _execute_run(run_id)


@shared_task(name="apps.data_store.dev_ops_tasks.run_crawler_script", queue="crawler")
def run_crawler_script(run_id: int):
    return _execute_run(run_id)


def preempt_notice_crawl_all(*, by_run_id: int) -> list[int]:
    """一轮采集优先：暂停/取消同队列上的全量任务。

    - running：置 cancel_requested，由全量任务进程内 watcher SIGTERM 其 devops 子进程
      （不杀 notice-crawler 常驻容器）
    - pending：直接标 failed 并尝试 revoke Celery 任务，避免挡在一轮前面
    默认不自动恢复全量。
    """
    now = timezone.now()
    note = PREEMPT_NOTE.format(once_id=by_run_id)
    preempted: list[int] = []

    qs = (
        DevOpsJobRun.objects.select_related("job")
        .filter(job__script_key="notice_crawl_all", status__in=["pending", "running"])
        .exclude(id=by_run_id)
    )
    for run in qs:
        if run.status == "running":
            run.cancel_requested = True
            run.preempted_by_run_id = by_run_id
            # 先写标志供 watcher 读取；最终 status 由执行进程收尾时写成 failed
            existing = (run.stderr or "").rstrip()
            run.stderr = f"{existing}\n{note}".strip() if existing else note
            run.save(update_fields=["cancel_requested", "preempted_by_run_id", "stderr"])
            preempted.append(run.id)
            continue

        # pending：立刻失败并尽量从队列摘掉
        run.status = "failed"
        run.finished_at = now
        run.cancel_requested = True
        run.preempted_by_run_id = by_run_id
        existing = (run.stderr or "").rstrip()
        run.stderr = f"{existing}\n{note}".strip() if existing else note
        run.save(
            update_fields=[
                "status",
                "finished_at",
                "cancel_requested",
                "preempted_by_run_id",
                "stderr",
            ]
        )
        if run.celery_task_id:
            try:
                from config.celery import app as celery_app

                celery_app.control.revoke(run.celery_task_id, terminate=False)
            except Exception:  # noqa: BLE001
                pass
        preempted.append(run.id)
    return preempted


def _execute_run(run_id: int) -> dict:
    run = DevOpsJobRun.objects.select_related("job").filter(id=run_id).first()
    if not run:
        return {"detail": "run missing"}
    if run.status in {"success", "failed"}:
        return {"detail": "run already finished", "status": run.status, "runId": run.id}

    # 入队后、真正开跑前若已被抢占（pending 全量），直接收尾
    if run.cancel_requested and run.job.script_key == "notice_crawl_all":
        run.status = "failed"
        run.finished_at = timezone.now()
        if not (run.stderr or "").strip():
            run.stderr = PREEMPT_NOTE.format(once_id=run.preempted_by_run_id or "?")
        run.save(update_fields=["status", "finished_at", "stderr"])
        return {"status": run.status, "runId": run.id, "preempted": True}

    job = run.job
    preempted_ids: list[int] = []
    if job.script_key == "notice_crawl_once":
        # 开跑前再抢一次，覆盖「入队后全量才变成 running」的窗口
        preempted_ids = preempt_notice_crawl_all(by_run_id=run.id)

    run.status = "running"
    run.started_at = timezone.now()
    # 不要写 celery_task_id：入队后 worker 抢跑时若用空值覆盖，会丢掉真实 task id
    run.save(update_fields=["status", "started_at"])
    try:
        output = run_script(
            job.script_key,
            job.args_json if isinstance(job.args_json, dict) else {},
            run_id=run.id,
        )
        run.refresh_from_db()
        stdout = output.get("stdout") or ""
        stderr = output.get("stderr") or ""
        preempted = bool(output.get("preempted")) or run.cancel_requested

        if preempted and job.script_key == "notice_crawl_all":
            run.stdout = stdout
            # 保留抢占说明（入队时写入的 stderr 可能已被 runner 覆盖成带 once id 的版本）
            run.stderr = stderr or run.stderr or PREEMPT_NOTE.format(
                once_id=run.preempted_by_run_id or "?"
            )
            run.status = "failed"
        else:
            if job.script_key == "notice_crawl_once" and preempted_ids:
                hint = (
                    f"[提示] 全量采集 run#{','.join(str(i) for i in preempted_ids)} "
                    "已被暂停，不会自动恢复，如需请手动再跑全量。"
                )
                stdout = f"{stdout}\n{hint}".strip() if stdout else hint
            run.stdout = stdout
            run.stderr = stderr
            run.status = "success" if output.get("ok", True) else "failed"
    except Exception as exc:  # noqa: BLE001
        run.refresh_from_db()
        if run.cancel_requested and job.script_key == "notice_crawl_all":
            run.stderr = (run.stderr or "").strip() or PREEMPT_NOTE.format(
                once_id=run.preempted_by_run_id or "?"
            )
            run.status = "failed"
        else:
            run.stderr = str(exc)
            run.status = "failed"
    run.finished_at = timezone.now()
    run.save(update_fields=["stdout", "stderr", "status", "finished_at"])
    now = timezone.now()
    job.last_run_at = now
    job.next_run_at = next_run_at(
        schedule_type=job.schedule_type,
        interval_seconds=job.interval_seconds,
        cron_expr=job.cron_expr,
        now=now,
        last_run_at=now,
    )
    job.save(update_fields=["last_run_at", "next_run_at", "updated_at"])
    return {"status": run.status, "runId": run.id}


def reap_stale_dev_ops_runs(now=None) -> dict:
    """回收僵尸 pending/running，避免挡住手动重跑与定时入队。"""
    now = now or timezone.now()
    reaped = 0
    notes: list[str] = []

    pending_cutoff = now - timedelta(seconds=PENDING_STALE_SECONDS)
    for run in DevOpsJobRun.objects.select_related("job").filter(status="pending", created_at__lte=pending_cutoff):
        run.status = "failed"
        run.finished_at = now
        run.stderr = ((run.stderr or "").rstrip() + "\n[系统] 排队超时，任务可能已从 Celery 队列丢失。").strip()
        run.save(update_fields=["status", "finished_at", "stderr"])
        reaped += 1
        notes.append(f"pending#{run.id}")

    for run in DevOpsJobRun.objects.select_related("job").filter(status="running"):
        script = get_script(run.job.script_key) or {}
        timeout = int(script.get("timeout") or 7200)
        started = run.started_at or run.created_at
        if not started:
            continue
        limit = timeout + RUNNING_GRACE_SECONDS
        if (now - started).total_seconds() <= limit:
            continue
        run.status = "failed"
        run.finished_at = now
        run.stderr = (
            (run.stderr or "").rstrip()
            + f"\n[系统] 执行超时未结束（已超过 {timeout}s），判定为僵尸 running，已自动收尸。"
        ).strip()
        run.save(update_fields=["status", "finished_at", "stderr"])
        # 同步推进 next_run，避免 interval 任务卡在过去
        job = run.job
        job.last_run_at = now
        job.next_run_at = next_run_at(
            schedule_type=job.schedule_type,
            interval_seconds=job.interval_seconds,
            cron_expr=job.cron_expr,
            now=now,
            last_run_at=now,
        )
        job.save(update_fields=["last_run_at", "next_run_at", "updated_at"])
        reaped += 1
        notes.append(f"running#{run.id}")

    return {"reaped": reaped, "runs": notes}


@shared_task(name="apps.data_store.dev_ops_tasks.tick_scheduled_jobs")
def tick_scheduled_jobs():
    now = timezone.now()
    reaped = reap_stale_dev_ops_runs(now=now)
    due = list(
        DevOpsJob.objects.filter(enabled=True)
        .exclude(schedule_type="manual")
        .filter(next_run_at__isnull=False, next_run_at__lte=now)
        .order_by("next_run_at")[:50]
    )
    enqueued = 0
    for job in due:
        if DevOpsJobRun.objects.filter(job=job, status__in=["pending", "running"]).exists():
            continue
        with transaction.atomic():
            run = DevOpsJobRun.objects.create(job=job, trigger="schedule", status="pending")
            # 先推后下次，避免同一分钟重复入队
            job.next_run_at = next_run_at(
                schedule_type=job.schedule_type,
                interval_seconds=job.interval_seconds,
                cron_expr=job.cron_expr,
                now=now,
                last_run_at=now,
            )
            job.save(update_fields=["next_run_at", "updated_at"])
        enqueue_job_run(run.id, job.script_key)
        enqueued += 1
    return {"enqueued": enqueued, "reaped": reaped.get("reaped", 0)}


def enqueue_job_run(run_id: int, script_key: str) -> str:
    if script_key == "notice_crawl_once":
        preempt_notice_crawl_all(by_run_id=run_id)
    script = get_script(script_key)
    queue = (script or {}).get("queue") or "default"
    if queue == "crawler":
        async_result = run_crawler_script.delay(run_id)
    else:
        async_result = run_dev_ops_job.delay(run_id)
    DevOpsJobRun.objects.filter(id=run_id).update(celery_task_id=async_result.id)
    return async_result.id
