from __future__ import annotations

from typing import Any

from apps.assistant.services.tool_registry import ToolDefinition, register_tool


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
