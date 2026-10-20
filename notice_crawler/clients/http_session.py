from __future__ import annotations

import os
from typing import Optional

import requests


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
