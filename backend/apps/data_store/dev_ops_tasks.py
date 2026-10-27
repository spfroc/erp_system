from __future__ import annotations

from celery import shared_task
from django.db import transaction
from django.utils import timezone

from .dev_ops_catalog import get_script
from .dev_ops_models import DevOpsJob, DevOpsJobRun
from .dev_ops_runner import run_script
from .dev_ops_schedule import next_run_at


@shared_task(name="apps.data_store.dev_ops_tasks.run_dev_ops_job")
def run_dev_ops_job(run_id: int):
    return _execute_run(run_id)


@shared_task(name="apps.data_store.dev_ops_tasks.run_crawler_script", queue="crawler")
def run_crawler_script(run_id: int):
    return _execute_run(run_id)


def _execute_run(run_id: int) -> dict:
    run = DevOpsJobRun.objects.select_related("job").filter(id=run_id).first()
    if not run:
        return {"detail": "run missing"}
    job = run.job
    run.status = "running"
    run.started_at = timezone.now()
    run.celery_task_id = run.celery_task_id or ""
    run.save(update_fields=["status", "started_at", "celery_task_id"])
    try:
        output = run_script(job.script_key, job.args_json if isinstance(job.args_json, dict) else {})
        run.stdout = output.get("stdout") or ""
        run.stderr = output.get("stderr") or ""
        run.status = "success" if output.get("ok", True) else "failed"
    except Exception as exc:  # noqa: BLE001
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


@shared_task(name="apps.data_store.dev_ops_tasks.tick_scheduled_jobs")
def tick_scheduled_jobs():
    now = timezone.now()
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
    return {"enqueued": enqueued}


def enqueue_job_run(run_id: int, script_key: str) -> str:
    script = get_script(script_key)
    queue = (script or {}).get("queue") or "default"
    if queue == "crawler":
        async_result = run_crawler_script.delay(run_id)
    else:
        async_result = run_dev_ops_job.delay(run_id)
    DevOpsJobRun.objects.filter(id=run_id).update(celery_task_id=async_result.id)
    return async_result.id
