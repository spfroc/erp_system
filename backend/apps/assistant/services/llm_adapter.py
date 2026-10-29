"""OpenAI-compatible 本地模型适配器。不在 Gunicorn Worker 内加载权重。"""

from __future__ import annotations

import json
import logging
import os
import re
import threading
import time
import urllib.error
import urllib.request
from typing import Any

logger = logging.getLogger(__name__)

_LOCK = threading.BoundedSemaphore(1)
_LAST_HEALTH: dict[str, Any] = {"checked_at": 0.0, "online": False, "detail": ""}


def llm_config() -> dict[str, Any]:
    enabled = (os.getenv("ASSISTANT_LLM_ENABLED") or "false").strip().lower() in {"1", "true", "yes"}
    fallback = (os.getenv("ASSISTANT_FALLBACK_ENABLED") or "true").strip().lower() not in {"0", "false", "no"}
    base_url = (os.getenv("ASSISTANT_LLM_BASE_URL") or "").strip().rstrip("/")
    return {
        "enabled": enabled,
        "fallback_enabled": fallback,
        "base_url": base_url,
        "model": (os.getenv("ASSISTANT_LLM_MODEL") or "").strip(),
        "timeout": max(1, int(os.getenv("ASSISTANT_LLM_TIMEOUT") or "20")),
        "max_output_tokens": max(32, int(os.getenv("ASSISTANT_LLM_MAX_OUTPUT_TOKENS") or "384")),
        "api_key": (os.getenv("ASSISTANT_LLM_API_KEY") or "local").strip(),
    }


def probe_llm(*, force: bool = False) -> dict[str, Any]:
    """轻量探活；结果短缓存，避免聊天请求打爆模型服务。"""
    cfg = llm_config()
    now = time.time()
    if not force and now - float(_LAST_HEALTH.get("checked_at") or 0) < 15:
        return {
            "enabled": cfg["enabled"],
            "configured": bool(cfg["base_url"]),
            "online": bool(_LAST_HEALTH.get("online")),
            "detail": str(_LAST_HEALTH.get("detail") or ""),
            "baseUrl": cfg["base_url"] or None,
            "model": cfg["model"] or None,
            "fallbackEnabled": cfg["fallback_enabled"],
        }

    online = False
    detail = ""
    if not cfg["enabled"]:
        detail = "ASSISTANT_LLM_ENABLED=false"
    elif not cfg["base_url"]:
        detail = "未配置 ASSISTANT_LLM_BASE_URL"
    else:
        url = f"{cfg['base_url']}/models"
        try:
            req = urllib.request.Request(
                url,
                headers={"Authorization": f"Bearer {cfg['api_key']}"},
                method="GET",
            )
            with urllib.request.urlopen(req, timeout=min(3, cfg["timeout"])) as resp:
                online = 200 <= getattr(resp, "status", 200) < 300
                detail = "ok" if online else f"status={getattr(resp, 'status', '?')}"
        except Exception as exc:  # noqa: BLE001
            online = False
            detail = str(exc)[:200]

    _LAST_HEALTH.update({"checked_at": now, "online": online, "detail": detail})
    return {
        "enabled": cfg["enabled"],
        "configured": bool(cfg["base_url"]),
        "online": online,
        "detail": detail,
        "baseUrl": cfg["base_url"] or None,
        "model": cfg["model"] or None,
        "fallbackEnabled": cfg["fallback_enabled"],
    }


def chat_completion_json(
    *,
    system_prompt: str,
    user_prompt: str,
    temperature: float = 0.1,
) -> dict[str, Any]:
    """调用 /v1/chat/completions，期望返回可解析 JSON 对象。"""
    cfg = llm_config()
    if not cfg["enabled"] or not cfg["base_url"]:
        raise LlmUnavailable("llm_disabled", "本地模型未启用或未配置")

    payload = {
        "model": cfg["model"] or "local",
        "temperature": temperature,
        "max_tokens": cfg["max_output_tokens"],
        "messages": [
            {"role": "system", "content": system_prompt[:4000]},
            {"role": "user", "content": user_prompt[:3000]},
        ],
        "response_format": {"type": "json_object"},
    }
    body = json.dumps(payload).encode("utf-8")
    url = f"{cfg['base_url']}/chat/completions"
    req = urllib.request.Request(
        url,
        data=body,
        headers={
            "Authorization": f"Bearer {cfg['api_key']}",
            "Content-Type": "application/json",
        },
        method="POST",
    )

    acquired = _LOCK.acquire(timeout=cfg["timeout"] + 1)
    if not acquired:
        raise LlmUnavailable("llm_busy", "模型请求队列已满，请稍后重试")
    started = time.perf_counter()
    try:
        with urllib.request.urlopen(req, timeout=cfg["timeout"]) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
        data = json.loads(raw)
        content = (((data.get("choices") or [{}])[0].get("message") or {}).get("content")) or ""
        parsed = _parse_json_content(str(content))
        return {
            "ok": True,
            "data": parsed,
            "duration_ms": int((time.perf_counter() - started) * 1000),
            "raw_content": str(content)[:500],
        }
    except LlmUnavailable:
        raise
    except urllib.error.URLError as exc:
        raise LlmUnavailable("llm_unreachable", f"模型服务不可达：{exc}") from exc
    except Exception as exc:  # noqa: BLE001
        logger.warning("assistant llm call failed: %s", exc)
        raise LlmUnavailable("llm_error", f"模型调用失败：{exc}") from exc
    finally:
        _LOCK.release()


def _parse_json_content(content: str) -> dict[str, Any]:
    text = (content or "").strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        match = re.search(r"\{[\s\S]*\}", text)
        if not match:
            raise LlmUnavailable("invalid_json", "模型未返回合法 JSON") from exc
        data = json.loads(match.group(0))
    if not isinstance(data, dict):
        raise LlmUnavailable("invalid_json", "模型 JSON 必须是对象")
    return data


class LlmUnavailable(Exception):
    def __init__(self, code: str, message: str):
        self.code = code
        self.message = message
        super().__init__(message)
