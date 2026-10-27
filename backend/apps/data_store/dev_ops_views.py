from __future__ import annotations

import json

from django.db import transaction
from django.db.models import Q
from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from .dev_ops_catalog import get_script, list_scripts
from .dev_ops_defaults import ensure_default_dev_ops_jobs
from .dev_ops_models import DevOpsJob, DevOpsJobRun
from .dev_ops_schedule import next_run_at
from .dev_ops_tasks import enqueue_job_run
from .views import _require_permission


def _page(request) -> tuple[int, int]:
    try:
        page = max(int(request.GET.get("page") or 1), 1)
    except ValueError:
        page = 1
    try:
        page_size = int(request.GET.get("page_size") or 20)
    except ValueError:
        page_size = 20
    return page, min(max(page_size, 1), 50)


def _serialize_job(job: DevOpsJob) -> dict:
    script = get_script(job.script_key) or {}
    return {
        "id": job.id,
        "scriptKey": job.script_key,
        "scriptLabel": script.get("label") or job.script_key,
        "kind": script.get("kind") or "",
        "queue": script.get("queue") or "default",
        "name": job.name,
        "enabled": job.enabled,
        "scheduleType": job.schedule_type,
        "intervalSeconds": job.interval_seconds,
        "cronExpr": job.cron_expr,
        "args": job.args_json if isinstance(job.args_json, dict) else {},
        "lastRunAt": job.last_run_at.isoformat() if job.last_run_at else "",
        "nextRunAt": job.next_run_at.isoformat() if job.next_run_at else "",
        "updatedBy": job.updated_by,
        "updatedAt": job.updated_at.isoformat() if job.updated_at else "",
    }


def _serialize_run(run: DevOpsJobRun) -> dict:
    return {
        "id": run.id,
        "jobId": run.job_id,
        "jobName": run.job.name if run.job_id else "",
        "scriptKey": run.job.script_key if run.job_id else "",
        "trigger": run.trigger,
        "status": run.status,
        "celeryTaskId": run.celery_task_id,
        "startedAt": run.started_at.isoformat() if run.started_at else "",
        "finishedAt": run.finished_at.isoformat() if run.finished_at else "",
        "stdout": run.stdout,
        "stderr": run.stderr,
        "createdAt": run.created_at.isoformat() if run.created_at else "",
    }


def _parse_body(request) -> dict:
    try:
        payload = json.loads(request.body or b"{}")
    except json.JSONDecodeError:
        return {}
    return payload if isinstance(payload, dict) else {}


def _apply_job_payload(job: DevOpsJob, payload: dict, operator: str) -> str | None:
    script_key = str(payload.get("scriptKey") or job.script_key or "").strip()
    script = get_script(script_key)
    if not script:
        return "请选择白名单内的脚本。"
    schedule_type = str(payload.get("scheduleType") or job.schedule_type or "manual").strip()
    if schedule_type not in {"manual", "interval", "cron"}:
        return "调度类型不正确。"
    interval_seconds = payload.get("intervalSeconds", job.interval_seconds)
    cron_expr = str(payload.get("cronExpr") if "cronExpr" in payload else job.cron_expr or "").strip()
    if schedule_type == "interval":
        try:
            interval_seconds = int(interval_seconds or 0)
        except (TypeError, ValueError):
            return "间隔秒数不正确。"
        if interval_seconds < 60:
            return "间隔至少 60 秒。"
        cron_expr = ""
    elif schedule_type == "cron":
        if len(cron_expr.split()) != 5:
            return "cron 需为五段：分 时 日 月 周。"
        interval_seconds = None
    else:
        interval_seconds = None
        cron_expr = ""
    name = str(payload.get("name") or script["label"]).strip()[:128]
    args = payload.get("args") if isinstance(payload.get("args"), dict) else (job.args_json if isinstance(job.args_json, dict) else {})
    enabled = bool(payload["enabled"]) if "enabled" in payload else job.enabled
    now = timezone.now()
    job.script_key = script_key
    job.name = name or script["label"]
    job.enabled = enabled
    job.schedule_type = schedule_type
    job.interval_seconds = interval_seconds
    job.cron_expr = cron_expr
    job.args_json = args
    job.updated_by = operator[:100]
    job.next_run_at = next_run_at(
        schedule_type=schedule_type,
        interval_seconds=interval_seconds,
        cron_expr=cron_expr,
        now=now,
        last_run_at=job.last_run_at,
    )
    return None


@csrf_exempt
@require_http_methods(["GET"])
def dev_ops_scripts(request):
    _user, error = _require_permission(request, "dev.ops.view")
    if error:
        return error
    return JsonResponse({"items": list_scripts()})


@csrf_exempt
@require_http_methods(["GET", "POST"])
def dev_ops_jobs(request):
    permission = "dev.ops.manage" if request.method == "POST" else "dev.ops.view"
    user, error = _require_permission(request, permission)
    if error:
        return error
    if request.method == "POST":
        payload = _parse_body(request)
        job = DevOpsJob(script_key="", name="", schedule_type="manual", args_json={})
        detail = _apply_job_payload(job, payload, str((user or {}).get("name") or ""))
        if detail:
            return JsonResponse({"detail": detail}, status=400)
        job.save()
        return JsonResponse(_serialize_job(job), status=201)
    ensure_default_dev_ops_jobs()
    search = (request.GET.get("search") or "").strip()
    page, page_size = _page(request)
    qs = DevOpsJob.objects.all().order_by("-updated_at", "-id")
    if search:
        qs = qs.filter(Q(name__icontains=search) | Q(script_key__icontains=search))
    total = qs.count()
    items = [_serialize_job(job) for job in qs[(page - 1) * page_size : page * page_size]]
    return JsonResponse({"items": items, "total": total, "page": page, "pageSize": page_size})


@csrf_exempt
@require_http_methods(["GET", "PATCH", "DELETE"])
def dev_ops_job_detail(request, job_id: int):
    permission = "dev.ops.view" if request.method == "GET" else "dev.ops.manage"
    user, error = _require_permission(request, permission)
    if error:
        return error
    job = DevOpsJob.objects.filter(id=job_id).first()
    if not job:
        return JsonResponse({"detail": "任务不存在。"}, status=404)
    if request.method == "GET":
        return JsonResponse(_serialize_job(job))
    if request.method == "DELETE":
        job.delete()
        return JsonResponse({"ok": True})
    payload = _parse_body(request)
    detail = _apply_job_payload(job, payload, str((user or {}).get("name") or ""))
    if detail:
        return JsonResponse({"detail": detail}, status=400)
    job.save()
    return JsonResponse(_serialize_job(job))


@csrf_exempt
@require_http_methods(["POST"])
def dev_ops_job_run(request, job_id: int):
    _user, error = _require_permission(request, "dev.ops.manage")
    if error:
        return error
    job = DevOpsJob.objects.filter(id=job_id).first()
    if not job:
        return JsonResponse({"detail": "任务不存在。"}, status=404)
    if not get_script(job.script_key):
        return JsonResponse({"detail": "脚本不在白名单内。"}, status=400)
    if DevOpsJobRun.objects.filter(job=job, status__in=["pending", "running"]).exists():
        return JsonResponse({"detail": "该任务已有执行中的记录。"}, status=409)
    with transaction.atomic():
        run = DevOpsJobRun.objects.create(job=job, trigger="manual", status="pending")
    try:
        enqueue_job_run(run.id, job.script_key)
    except Exception as exc:  # noqa: BLE001
        run.status = "failed"
        run.stderr = f"无法入队：{exc}"
        run.finished_at = timezone.now()
        run.save(update_fields=["status", "stderr", "finished_at"])
        return JsonResponse({"detail": run.stderr}, status=503)
    run.refresh_from_db()
    return JsonResponse(_serialize_run(run), status=202)


@csrf_exempt
@require_http_methods(["GET"])
def dev_ops_runs(request):
    _user, error = _require_permission(request, "dev.ops.view")
    if error:
        return error
    page, page_size = _page(request)
    qs = DevOpsJobRun.objects.select_related("job").order_by("-id")
    job_id = request.GET.get("job_id")
    if job_id:
        qs = qs.filter(job_id=job_id)
    search = (request.GET.get("search") or "").strip()
    if search:
        qs = qs.filter(Q(job__name__icontains=search) | Q(job__script_key__icontains=search))
    total = qs.count()
    items = [_serialize_run(run) for run in qs[(page - 1) * page_size : page * page_size]]
    return JsonResponse({"items": items, "total": total, "page": page, "pageSize": page_size})
