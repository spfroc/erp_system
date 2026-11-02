"""OpenAI-compatible 本地/云端模型适配器。不在 Gunicorn Worker 内加载权重。"""

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
    timeout = max(1, int(os.getenv("ASSISTANT_LLM_TIMEOUT") or "20"))
    # 意图解析单独限时，避免规则未命中时干等过久才降级
    intent_timeout = max(3, int(os.getenv("ASSISTANT_LLM_INTENT_TIMEOUT") or min(25, timeout)))
    model = (os.getenv("ASSISTANT_LLM_MODEL") or "").strip()
    stream_env = (os.getenv("ASSISTANT_LLM_STREAM") or "").strip().lower()
    if stream_env in {"1", "true", "yes"}:
        stream = True
    elif stream_env in {"0", "false", "no"}:
        stream = False
    else:
        # NVIDIA MiniMax 等托管端点官方示例默认 stream=true；非流式常挂起
        stream = _should_default_stream(base_url, model)
    return {
        "enabled": enabled,
        "fallback_enabled": fallback,
        "base_url": base_url,
        "model": model,
        "timeout": timeout,
        "intent_timeout": intent_timeout,
        "max_output_tokens": max(32, int(os.getenv("ASSISTANT_LLM_MAX_OUTPUT_TOKENS") or "384")),
        "api_key": (os.getenv("ASSISTANT_LLM_API_KEY") or "local").strip(),
        "stream": stream,
    }


def _should_default_stream(base_url: str, model: str) -> bool:
    host = (base_url or "").lower()
    name = (model or "").lower()
    if "integrate.api.nvidia.com" in host or "api.nvidia.com" in host:
        return True
    if "minimax" in name:
        return True
    return False


def _is_nvidia_minimax(cfg: dict[str, Any]) -> bool:
    host = str(cfg.get("base_url") or "").lower()
    name = str(cfg.get("model") or "").lower()
    return ("api.nvidia.com" in host and "minimax" in name) or name.startswith("minimaxai/")


def _is_deepseek(cfg: dict[str, Any]) -> bool:
    host = str(cfg.get("base_url") or "").lower()
    name = str(cfg.get("model") or "").lower()
    return "deepseek.com" in host or name.startswith("deepseek")


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
            "stream": cfg["stream"],
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
            # 小模型冷启动可能略慢；过短超时会被误判离线并整段降级
            with urllib.request.urlopen(req, timeout=min(8, max(3, cfg["timeout"]))) as resp:
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
        "stream": cfg["stream"],
    }


def chat_completion_json(
    *,
    system_prompt: str,
    user_prompt: str,
    temperature: float = 0.1,
    timeout: int | None = None,
    max_tokens: int | None = None,
) -> dict[str, Any]:
    """调用 /v1/chat/completions，期望返回可解析 JSON 对象。"""
    cfg = llm_config()
    if not cfg["enabled"] or not cfg["base_url"]:
        raise LlmUnavailable("llm_disabled", "本地模型未启用或未配置")
    call_timeout = max(3, int(timeout if timeout is not None else cfg["timeout"]))
    out_tokens = max(32, int(max_tokens if max_tokens is not None else cfg["max_output_tokens"]))
    use_stream = bool(cfg["stream"])

    # MiniMax 官方推荐采样；其它端点沿用调用方温度
    call_temperature = 1.0 if _is_nvidia_minimax(cfg) else temperature
    top_p = 0.95 if _is_nvidia_minimax(cfg) else None
    deepseek = _is_deepseek(cfg)

    base_payload: dict[str, Any] = {
        "model": cfg["model"] or "local",
        "temperature": call_temperature,
        "max_tokens": out_tokens,
        "messages": [
            {"role": "system", "content": system_prompt[:1800]},
            {"role": "user", "content": user_prompt[:1600]},
        ],
    }
    if top_p is not None:
        base_payload["top_p"] = top_p
    if deepseek:
        # 意图路由要快、只要 JSON；关闭思考模式避免多段 reasoning
        base_payload["thinking"] = {"type": "disabled"}
    if use_stream:
        base_payload["stream"] = True
        if deepseek:
            # DeepSeek / OpenAI：最终 SSE 块可带回 usage
            base_payload["stream_options"] = {"include_usage": True}
        if _is_nvidia_minimax(cfg):
            base_payload["seed"] = 0
            # 降低推理力度，缩短免费端点排队后的生成时间
            base_payload["chat_template_kwargs"] = {"reasoning_effort": "low"}

    # 多数本地小模型支持 json_object；不支持时自动降级重试（Ollama 等）
    # 流式场景默认一枪；若带了 chat_template_kwargs，400 时再退回无该字段
    payloads: list[dict[str, Any]]
    if use_stream:
        payloads = [base_payload]
        if "chat_template_kwargs" in base_payload:
            plain = {k: v for k, v in base_payload.items() if k != "chat_template_kwargs"}
            payloads.append(plain)
    elif deepseek or call_timeout > 25:
        payloads = [
            {**base_payload, "response_format": {"type": "json_object"}},
            base_payload,
        ]
    else:
        payloads = [base_payload]

    acquired = _LOCK.acquire(timeout=min(call_timeout + 1, 8))
    if not acquired:
        raise LlmUnavailable("llm_busy", "模型请求队列已满，请稍后重试")
    started = time.perf_counter()
    last_error: Exception | None = None
    try:
        # 流式免费端点首包常要 60s+；兼容重试不要把超时对半砍
        for index, payload in enumerate(payloads):
            remaining = max(5, call_timeout - int(time.perf_counter() - started))
            if use_stream:
                attempt_timeout = remaining
            elif len(payloads) == 1:
                attempt_timeout = call_timeout
            else:
                attempt_timeout = max(5, call_timeout // len(payloads))
            try:
                content, usage = _request_chat_content(cfg, payload, attempt_timeout)
                if not usage.get("total_tokens"):
                    usage = _estimate_usage(
                        system_prompt=system_prompt[:1800],
                        user_prompt=user_prompt[:1600],
                        completion=str(content),
                    )
                parsed = _parse_json_content(str(content))
                return {
                    "ok": True,
                    "data": parsed,
                    "duration_ms": int((time.perf_counter() - started) * 1000),
                    "raw_content": str(content)[:500],
                    "json_mode": "response_format" in payload,
                    "stream": bool(payload.get("stream")),
                    "usage": usage,
                }
            except LlmUnavailable:
                raise
            except urllib.error.HTTPError as exc:
                last_error = exc
                # 仅对首包（json_object / chat_template_kwargs）做兼容重试
                if index == 0 and exc.code in {400, 422} and len(payloads) > 1:
                    logger.info("assistant llm optional payload unsupported, retry plain chat")
                    continue
                raise LlmUnavailable("llm_http", f"模型 HTTP {exc.code}") from exc
            except urllib.error.URLError as exc:
                raise LlmUnavailable("llm_unreachable", f"模型服务不可达：{exc}") from exc
            except Exception as exc:  # noqa: BLE001
                last_error = exc
                # 流式超时不要立刻再打第二枪，避免 120s×2
                if use_stream:
                    logger.warning("assistant llm call failed: %s", exc)
                    raise LlmUnavailable("llm_error", f"模型调用失败：{exc}") from exc
                if index == 0 and len(payloads) > 1:
                    logger.info("assistant llm first attempt failed, retry plain chat: %s", exc)
                    continue
                logger.warning("assistant llm call failed: %s", exc)
                raise LlmUnavailable("llm_error", f"模型调用失败：{exc}") from exc
        raise LlmUnavailable("llm_error", f"模型调用失败：{last_error}")
    finally:
        _LOCK.release()


def _normalize_usage(raw: Any) -> dict[str, Any]:
    if not isinstance(raw, dict):
        return {}
    prompt = int(raw.get("prompt_tokens") or raw.get("input_tokens") or 0)
    completion = int(raw.get("completion_tokens") or raw.get("output_tokens") or 0)
    total = int(raw.get("total_tokens") or (prompt + completion) or 0)
    if total <= 0:
        return {}
    return {
        "prompt_tokens": prompt,
        "completion_tokens": completion,
        "total_tokens": total,
        "source": "exact",
    }


def _estimate_tokens(text: str) -> int:
    """粗估：汉字约 1.5 字/token，其它约 4 字符/token。"""
    cjk = 0
    other = 0
    for ch in text or "":
        code = ord(ch)
        if 0x4E00 <= code <= 0x9FFF or 0x3400 <= code <= 0x4DBF:
            cjk += 1
        elif not ch.isspace():
            other += 1
    return max(1, int(cjk / 1.5 + other / 4))


def _estimate_usage(*, system_prompt: str, user_prompt: str, completion: str) -> dict[str, Any]:
    prompt_tokens = _estimate_tokens(f"{system_prompt}\n{user_prompt}")
    completion_tokens = _estimate_tokens(completion)
    return {
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "total_tokens": prompt_tokens + completion_tokens,
        "source": "estimated",
    }


def _request_chat_content(cfg: dict[str, Any], payload: dict[str, Any], timeout: int) -> tuple[str, dict[str, Any]]:
    body = json.dumps(payload).encode("utf-8")
    url = f"{cfg['base_url']}/chat/completions"
    stream = bool(payload.get("stream"))
    headers = {
        "Authorization": f"Bearer {cfg['api_key']}",
        "Content-Type": "application/json",
        "Accept": "text/event-stream" if stream else "application/json",
    }
    req = urllib.request.Request(url, data=body, headers=headers, method="POST")
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        if stream:
            return _read_sse_content(resp)
        raw = resp.read().decode("utf-8", errors="replace")
    data = json.loads(raw)
    content = str((((data.get("choices") or [{}])[0].get("message") or {}).get("content")) or "")
    return content, _normalize_usage(data.get("usage"))


def _read_sse_content(resp: Any) -> tuple[str, dict[str, Any]]:
    """聚合 OpenAI 兼容 SSE：拼接 choices[].delta.content，直到 [DONE]。"""
    content_parts: list[str] = []
    reasoning_parts: list[str] = []
    usage: dict[str, Any] = {}
    deadline = time.perf_counter() + 180
    while True:
        if time.perf_counter() > deadline:
            raise TimeoutError("SSE read exceeded safety deadline")
        line = resp.readline()
        if not line:
            break
        if isinstance(line, bytes):
            text = line.decode("utf-8", errors="replace")
        else:
            text = str(line)
        text = text.strip()
        if not text or text.startswith(":"):
            continue
        if not text.startswith("data:"):
            continue
        data_str = text[5:].strip()
        if not data_str or data_str == "[DONE]":
            break
        try:
            chunk = json.loads(data_str)
        except json.JSONDecodeError:
            continue
        usage = _normalize_usage(chunk.get("usage")) or usage
        for choice in chunk.get("choices") or []:
            delta = choice.get("delta") or {}
            if delta.get("content"):
                content_parts.append(str(delta["content"]))
            for key in ("reasoning_content", "reasoning", "thinking"):
                if delta.get(key):
                    reasoning_parts.append(str(delta[key]))
            message = choice.get("message") or {}
            if message.get("content"):
                content_parts.append(str(message["content"]))
            for key in ("reasoning_content", "reasoning"):
                if message.get(key):
                    reasoning_parts.append(str(message[key]))
    content = "".join(content_parts).strip()
    if not content:
        # MiniMax 偶发只在 reasoning 通道给出最终答案
        content = "".join(reasoning_parts).strip()
    return content, usage


def _parse_json_content(content: str) -> dict[str, Any]:
    text = (content or "").strip()
    # 推理模型偶发带上 think / 代码围栏
    text = re.sub(r"<think>[\s\S]*?</think>", "", text, flags=re.IGNORECASE).strip()
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
