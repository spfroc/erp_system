"""白名单脚本实际执行（Django 命令或采集 CLI）。"""

from __future__ import annotations

import io
import os
import signal
import subprocess
import sys
import threading
import time
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from typing import Any

from django.conf import settings
from django.core.management import call_command

from .dev_ops_catalog import get_script

OUTPUT_LIMIT = 32_000
CANCEL_POLL_SECONDS = 1.0
PREEMPT_STDERR = "[系统] 被公告采集一轮抢占暂停。全量不会自动恢复，如需请手动再跑全量。"


def _clip(text: str) -> str:
    text = text or ""
    if len(text) <= OUTPUT_LIMIT:
        return text
    return text[:OUTPUT_LIMIT] + "\n…(已截断)"


def _normalize_args(script: dict[str, Any], args: dict | None) -> dict[str, Any]:
    raw = dict(args or {})
    normalized: dict[str, Any] = {}
    for field in script.get("argSchema") or []:
        key = field["key"]
        if key not in raw or raw[key] in (None, ""):
            if field.get("optional") and key not in raw:
                continue
            value = field.get("default")
        else:
            value = raw[key]
        if field.get("type") == "int" and value is not None and value != "":
            value = int(value)
        if field.get("type") == "str" and value is not None:
            value = str(value)
        if field.get("type") == "bool":
            value = bool(value)
        if value is None and field.get("optional"):
            continue
        normalized[key] = value
    return normalized


def run_script(script_key: str, args: dict | None = None, *, run_id: int | None = None) -> dict[str, Any]:
    script = get_script(script_key)
    if not script:
        raise ValueError(f"未知脚本：{script_key}")
    options = _normalize_args(script, args)
    if script["kind"] == "django":
        return _run_django(script["command"], options, int(script.get("timeout") or 600))
    if script["kind"] == "crawler":
        return _run_crawler(script, options, run_id=run_id)
    raise ValueError(f"不支持的脚本类型：{script['kind']}")


def _run_django(command: str, options: dict[str, Any], timeout: int) -> dict[str, str]:
    stdout_buf = io.StringIO()
    stderr_buf = io.StringIO()
    kwargs = {}
    for key, value in options.items():
        if isinstance(value, bool):
            if value:
                kwargs[key] = True
        else:
            kwargs[key] = value
    try:
        with redirect_stdout(stdout_buf), redirect_stderr(stderr_buf):
            call_command(command, **kwargs)
    except Exception as exc:  # noqa: BLE001 - surface to job run
        return {
            "ok": False,
            "stdout": _clip(stdout_buf.getvalue()),
            "stderr": _clip(f"{stderr_buf.getvalue()}\n{exc}".strip()),
        }
    return {"ok": True, "stdout": _clip(stdout_buf.getvalue()), "stderr": _clip(stderr_buf.getvalue())}


def _build_notice_crawl_cli_args(script_key: str, options: dict[str, Any]) -> list[str]:
    """组装 crawl 子命令参数。一轮=按回溯日期；全量=不设日期窗口。"""
    args: list[str] = []
    if script_key == "notice_crawl_once":
        from datetime import date, timedelta

        lookback = int(options.get("lookback_days") or 2)
        end = date.today()
        start = end - timedelta(days=max(lookback, 0))
        args += ["--start-date", start.isoformat(), "--end-date", end.isoformat()]
        if options.get("stop_dup") is not None:
            args += ["--stop-dup", str(options["stop_dup"])]
    elif script_key == "notice_crawl_all":
        # 全量：不传 start/end；仅当显式配置 stop_dup 时才提前停止
        if options.get("stop_dup") is not None:
            args += ["--stop-dup", str(options["stop_dup"])]
    if options.get("page_size") is not None:
        args += ["--page-size", str(options["page_size"])]
    if options.get("max_pages") is not None:
        args += ["--max-pages", str(options["max_pages"])]
    if options.get("site"):
        args += ["--site", str(options["site"])]
    if options.get("list_only"):
        args.append("--list-only")
    return args


def _run_crawler(script: dict[str, Any], options: dict[str, Any], *, run_id: int | None = None) -> dict[str, str]:
    cli_args = list(script.get("cli") or [])
    if script["key"] in {"notice_crawl_once", "notice_crawl_all"}:
        cli_args += _build_notice_crawl_cli_args(script["key"], options)
    timeout = int(script.get("timeout") or 7200)
    container = (getattr(settings, "NOTICE_CRAWLER_DOCKER_CONTAINER", "") or "").strip()
    if container:
        result = _run_crawler_docker_exec(container, cli_args, timeout, run_id=run_id)
    else:
        result = _run_crawler_local(cli_args, timeout, run_id=run_id)
    # 采集成功后批量补标签（全量/一轮都需要；解析写入 notice_parsed 后才能识别）
    if result["ok"] and script["key"] in {"notice_crawl_once", "notice_crawl_all"}:
        tag_summary = _tag_after_crawl(batch_size=500, max_batches=200)
        result["stdout"] = _clip((result["stdout"] or "") + "\n" + tag_summary)
    return result


def _run_crawler_local(cli_args: list[str], timeout: int, *, run_id: int | None = None) -> dict[str, str]:
    root = Path(getattr(settings, "NOTICE_CRAWLER_DIR", "") or "")
    cli = root / "cli.py"
    if not cli.is_file():
        raise FileNotFoundError(f"找不到采集目录或 cli.py：{root}")
    cmd = [sys.executable, str(cli), *cli_args]
    return _run_subprocess(cmd, cwd=str(root), timeout=timeout, env=os.environ.copy(), run_id=run_id)


def _run_crawler_docker_exec(
    container: str, cli_args: list[str], timeout: int, *, run_id: int | None = None
) -> dict[str, str]:
    """在已具备依赖/代理的 notice-crawler 容器内跑 cli（生产 SOCKS 需 host 网络）。"""
    cmd = ["docker", "exec", "-w", "/app", container, "python", "cli.py", *cli_args]
    return _run_subprocess(cmd, cwd=None, timeout=timeout, env=os.environ.copy(), run_id=run_id)


def _is_cancel_requested(run_id: int | None) -> bool:
    if not run_id:
        return False
    from .dev_ops_models import DevOpsJobRun

    return DevOpsJobRun.objects.filter(id=run_id, cancel_requested=True).exists()


def _terminate_process(proc: subprocess.Popen) -> None:
    """只终止 devops 拉起的采集子进程（本地 python cli / docker exec），不碰常驻 notice-crawler。"""
    if proc.poll() is not None:
        return
    try:
        if os.name == "nt":
            proc.terminate()
        else:
            # start_new_session=True 时整组发送，覆盖 cli 可能再拉的子进程
            try:
                os.killpg(proc.pid, signal.SIGTERM)
            except (ProcessLookupError, PermissionError, OSError):
                proc.send_signal(signal.SIGTERM)
    except ProcessLookupError:
        return
    deadline = time.monotonic() + 8
    while time.monotonic() < deadline:
        if proc.poll() is not None:
            return
        time.sleep(0.2)
    try:
        if os.name == "nt":
            proc.kill()
        else:
            try:
                os.killpg(proc.pid, signal.SIGKILL)
            except (ProcessLookupError, PermissionError, OSError):
                proc.kill()
    except ProcessLookupError:
        pass


def _run_subprocess(
    cmd: list[str],
    *,
    cwd: str | None,
    timeout: int,
    env: dict[str, str],
    run_id: int | None = None,
) -> dict[str, str]:
    if _is_cancel_requested(run_id):
        return {"ok": False, "stdout": "", "stderr": PREEMPT_STDERR, "preempted": True}

    popen_kwargs: dict[str, Any] = {
        "cwd": cwd,
        "stdout": subprocess.PIPE,
        "stderr": subprocess.PIPE,
        "text": True,
        "env": env,
    }
    if os.name != "nt":
        popen_kwargs["start_new_session"] = True

    try:
        proc = subprocess.Popen(cmd, **popen_kwargs)
    except FileNotFoundError as exc:
        return {
            "ok": False,
            "stdout": "",
            "stderr": _clip(f"无法执行采集命令（缺少可执行文件）：{exc}"),
        }

    stop_watch = threading.Event()
    cancel_hit = threading.Event()

    def _watch_cancel() -> None:
        while not stop_watch.wait(CANCEL_POLL_SECONDS):
            if _is_cancel_requested(run_id):
                cancel_hit.set()
                _terminate_process(proc)
                return

    watcher: threading.Thread | None = None
    if run_id:
        watcher = threading.Thread(target=_watch_cancel, name=f"devops-cancel-{run_id}", daemon=True)
        watcher.start()

    timed_out = False
    try:
        try:
            stdout, stderr = proc.communicate(timeout=timeout)
        except subprocess.TimeoutExpired:
            timed_out = True
            _terminate_process(proc)
            stdout, stderr = proc.communicate(timeout=30)
    finally:
        stop_watch.set()
        if watcher is not None:
            watcher.join(timeout=2)

    stdout = stdout or ""
    stderr = stderr or ""

    if cancel_hit.is_set() or _is_cancel_requested(run_id):
        note = PREEMPT_STDERR
        if run_id:
            from .dev_ops_models import DevOpsJobRun

            preempted_by = (
                DevOpsJobRun.objects.filter(id=run_id)
                .values_list("preempted_by_run_id", flat=True)
                .first()
            )
            if preempted_by:
                note = (
                    f"[系统] 被公告采集一轮抢占暂停（once run#{preempted_by}）。"
                    "全量不会自动恢复，如需请手动再跑全量。"
                )
        return {
            "ok": False,
            "stdout": _clip(stdout),
            "stderr": _clip(f"{stderr}\n{note}".strip() if stderr else note),
            "preempted": True,
        }

    if timed_out:
        return {
            "ok": False,
            "stdout": _clip(stdout),
            "stderr": _clip(f"采集超时（限制 {timeout}s）\n{stderr}".strip()),
        }

    result = {
        "ok": proc.returncode == 0,
        "stdout": _clip(stdout),
        "stderr": _clip(stderr),
    }
    if proc.returncode not in (0, None) and not result["stderr"]:
        result["stderr"] = f"采集命令退出码 {proc.returncode}"
    return result


def _tag_after_crawl(*, batch_size: int = 500, max_batches: int = 200) -> str:
    """采集完成后循环打标，直到本轮无可处理或达到上限。"""
    from .notice_tagging import tag_result_notices

    tagged_total = 0
    skipped_total = 0
    batches = 0
    try:
        for _ in range(max_batches):
            batches += 1
            outcome = tag_result_notices(limit=batch_size, rebuild=False)
            tagged = int(outcome.get("tagged") or 0)
            skipped = int(outcome.get("skipped") or 0)
            tagged_total += tagged
            skipped_total += skipped
            if tagged <= 0:
                break
    except Exception as exc:  # noqa: BLE001
        return f"[打标] 失败：{exc}（已打标 {tagged_total}）"
    return f"[打标] 完成：新增/更新 {tagged_total}，跳过 {skipped_total}，批次 {batches}"
