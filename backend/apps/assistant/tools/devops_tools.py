from __future__ import annotations

from typing import Any

from django.db import transaction
from django.utils import timezone

from apps.assistant.services.tool_registry import ToolDefinition, register_tool

# 仅开放低风险、已明确副作用的任务给助手执行；采集/全量/外部系统任务一律不开放。
ASSISTANT_SAFE_SCRIPT_KEYS = frozenset({"tag_notice_results"})


def _devops_get_status(*, params: dict[str, Any], user_data: dict) -> dict[str, Any]:
    del user_data
    limit = min(max(int(params.get("limit") or 20), 1), 50)
    failed_only = bool(params.get("failed_only") or params.get("failedOnly"))
    try:
        from apps.data_store.dev_ops_models import DevOpsJob, DevOpsJobRun
        from apps.data_store.dev_ops_views import _serialize_job, _serialize_run
    except Exception as exc:  # noqa: BLE001
        return {
            "block_type": "error",
            "summary": "定时任务模块不可用",
            "content": str(exc),
            "data": {},
        }

    jobs = [_serialize_job(job) for job in DevOpsJob.objects.all().order_by("-updated_at", "-id")[:limit]]
    run_qs = DevOpsJobRun.objects.select_related("job").order_by("-id")
    if failed_only:
        run_qs = run_qs.filter(status="failed")
    runs = [_serialize_run(run) for run in run_qs[:limit]]
    return {
        "block_type": "statistics",
        "summary": f"任务 {len(jobs)} 个，最近运行 {len(runs)} 条。",
        "content": f"任务 {len(jobs)} 个，最近运行 {len(runs)} 条。",
        "data": {"jobs": jobs, "runs": runs, "total": len(runs)},
    }


def _devops_run_safe_job(*, params: dict[str, Any], user_data: dict) -> dict[str, Any]:
    """执行助手白名单内的已注册任务（真实入队，需确认）。"""
    del user_data
    from apps.data_store.dev_ops_catalog import get_script
    from apps.data_store.dev_ops_models import DevOpsJob, DevOpsJobRun
    from apps.data_store.dev_ops_tasks import enqueue_job_run
    from apps.data_store.dev_ops_views import _serialize_run

    job_id = int(params.get("job_id") or 0)
    job = DevOpsJob.objects.filter(id=job_id).first()
    if not job:
        return {
            "block_type": "error",
            "summary": "任务不存在",
            "content": "未找到指定定时任务。",
            "data": {"job_id": job_id},
        }
    script = get_script(job.script_key)
    if not script:
        return {
            "block_type": "error",
            "summary": "脚本不在白名单",
            "content": "该任务脚本不在运维白名单内。",
            "data": {"job_id": job_id, "script_key": job.script_key},
        }
    if job.script_key not in ASSISTANT_SAFE_SCRIPT_KEYS:
        return {
            "block_type": "navigation",
            "summary": "该任务不可由助手直接执行",
            "content": (
                f"任务「{job.name}」({job.script_key}) 可能影响采集/外部系统，"
                "V1.1 仅提供导航入口，请到「定时任务」页面人工执行。"
            ),
            "data": {
                "items": [{"id": "devOps", "viewId": "devOps", "label": "定时任务"}],
                "total": 1,
                "job_id": job_id,
                "script_key": job.script_key,
            },
        }

    if DevOpsJobRun.objects.filter(job=job, status__in=["pending", "running"]).exists():
        return {
            "block_type": "error",
            "summary": "任务执行中",
            "content": "该任务已有执行中的记录，请稍后再试。",
            "data": {"job_id": job_id},
        }

    with transaction.atomic():
        run = DevOpsJobRun.objects.create(job=job, trigger="assistant", status="pending")
    try:
        celery_id = enqueue_job_run(run.id, job.script_key)
    except Exception as exc:  # noqa: BLE001
        run.status = "failed"
        run.stderr = f"无法入队：{exc}"
        run.finished_at = timezone.now()
        run.save(update_fields=["status", "stderr", "finished_at"])
        return {
            "block_type": "error",
            "summary": "入队失败",
            "content": run.stderr,
            "data": {"job_id": job_id, "run_id": run.id},
        }

    run.refresh_from_db()
    payload = _serialize_run(run)
    payload["celeryTaskId"] = celery_id or payload.get("celeryTaskId")
    return {
        "block_type": "tool_result",
        "summary": f"已触发任务「{job.name}」，运行 ID={run.id}",
        "content": f"已触发安全任务「{job.name}」（script={job.script_key}），运行 ID={run.id}，状态={run.status}。",
        "data": {"job_id": job_id, "run": payload, "script_key": job.script_key},
    }


def register() -> None:
    register_tool(
        ToolDefinition(
            name="devops.get_status",
            description="查看定时任务与最近运行状态",
            input_schema={
                "type": "object",
                "properties": {
                    "limit": {"type": "integer"},
                    "failed_only": {"type": "boolean"},
                },
            },
            permission="dev.ops.view",
            risk_level="read",
            handler=_devops_get_status,
        )
    )
    register_tool(
        ToolDefinition(
            name="devops.run_safe_job",
            description="运行助手白名单内的已授权安全定时任务（需确认）",
            input_schema={
                "type": "object",
                "properties": {
                    "job_id": {"type": "integer", "description": "DevOpsJob.id"},
                },
                "required": ["job_id"],
            },
            permission="dev.ops.manage",
            risk_level="write",
            requires_confirmation=True,
            handler=_devops_run_safe_job,
        )
    )
