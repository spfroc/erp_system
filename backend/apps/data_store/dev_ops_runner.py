"""白名单脚本实际执行（Django 命令或采集 CLI）。"""

from __future__ import annotations

import io
import os
import subprocess
import sys
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from typing import Any

from django.conf import settings
from django.core.management import call_command

from .dev_ops_catalog import get_script

OUTPUT_LIMIT = 32_000


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


def run_script(script_key: str, args: dict | None = None) -> dict[str, str]:
    script = get_script(script_key)
    if not script:
        raise ValueError(f"未知脚本：{script_key}")
    options = _normalize_args(script, args)
    if script["kind"] == "django":
        return _run_django(script["command"], options, int(script.get("timeout") or 600))
    if script["kind"] == "crawler":
        return _run_crawler(script, options)
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


def _run_crawler(script: dict[str, Any], options: dict[str, Any]) -> dict[str, str]:
    root = Path(getattr(settings, "NOTICE_CRAWLER_DIR", "") or "")
    cli = root / "cli.py"
    if not cli.is_file():
        raise FileNotFoundError(f"找不到采集目录或 cli.py：{root}")
    cmd = [sys.executable, str(cli), *list(script.get("cli") or [])]
    if script["key"] in {"notice_crawl_once", "notice_crawl_all"}:
        cmd += _build_notice_crawl_cli_args(script["key"], options)
    env = os.environ.copy()
    timeout = int(script.get("timeout") or 7200)
    completed = subprocess.run(
        cmd,
        cwd=str(root),
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
        env=env,
    )
    result = {
        "ok": completed.returncode == 0,
        "stdout": _clip(completed.stdout or ""),
        "stderr": _clip(completed.stderr or ""),
    }
    if completed.returncode != 0 and not result["stderr"]:
        result["stderr"] = f"采集命令退出码 {completed.returncode}"
    return result
