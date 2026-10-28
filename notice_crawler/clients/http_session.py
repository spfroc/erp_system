from __future__ import annotations

import os
import time
from typing import Callable, Optional

import requests

RETRYABLE_STATUS = frozenset({408, 425, 429, 500, 502, 503, 504})
RETRYABLE_EXCEPTIONS = (
    requests.ConnectionError,
    requests.Timeout,
    requests.exceptions.ChunkedEncodingError,
)


def proxy_url() -> str:
    for key in ("NOTICE_HTTP_PROXY", "HTTPS_PROXY", "HTTP_PROXY", "ALL_PROXY", "https_proxy", "http_proxy", "all_proxy"):
        value = (os.getenv(key) or "").strip()
        if value:
            return value
    return ""


def apply_proxies(session: requests.Session, explicit: Optional[str] = None) -> requests.Session:
    url = (explicit or proxy_url()).strip()
    if not url:
        return session
    session.proxies.update({"http": url, "https": url})
    return session


def build_session(*, headers: Optional[dict] = None, verify: bool = True) -> requests.Session:
    session = requests.Session()
    session.verify = verify
    if headers:
        session.headers.update(headers)
    return apply_proxies(session)


def request_with_retries(
    session: requests.Session,
    method: str,
    url: str,
    *,
    retries: int = 6,
    backoff: float = 2.0,
    timeout: float | tuple = 30,
    on_retry: Optional[Callable[[int, int, str, float], None]] = None,
    **kwargs,
) -> requests.Response:
    """对网关抖动（502/503 等）与网络超时做指数退避重试。"""
    attempts = max(1, int(retries))
    last_error = ""
    for attempt in range(1, attempts + 1):
        try:
            resp = session.request(method, url, timeout=timeout, **kwargs)
            if resp.status_code in RETRYABLE_STATUS and attempt < attempts:
                wait = min(120.0, backoff ** attempt)
                last_error = f"HTTP {resp.status_code}"
                if on_retry:
                    on_retry(attempt, attempts, last_error, wait)
                time.sleep(wait)
                continue
            return resp
        except RETRYABLE_EXCEPTIONS as exc:
            last_error = f"{type(exc).__name__}: {exc}"
            if attempt >= attempts:
                raise
            wait = min(120.0, backoff ** attempt)
            if on_retry:
                on_retry(attempt, attempts, last_error, wait)
            time.sleep(wait)
    raise RuntimeError(f"request retries exhausted ({last_error}): {method} {url}")
