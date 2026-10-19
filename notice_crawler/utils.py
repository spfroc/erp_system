from __future__ import annotations

import re
from datetime import datetime
from typing import Any, Optional

from bs4 import BeautifulSoup


def html_to_text(html: Optional[str]) -> str:
    if not html:
        return ""
    soup = BeautifulSoup(html, "lxml")
    for tag in soup(["script", "style"]):
        tag.decompose()
    text = soup.get_text("\n", strip=True)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def parse_dt(value: Any) -> Optional[datetime]:
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        return value
    if isinstance(value, (int, float)):
        # JD createTime often ms timestamp
        ts = float(value)
        if ts > 1e12:
            ts /= 1000.0
        try:
            return datetime.fromtimestamp(ts)
        except (OverflowError, OSError, ValueError):
            return None
    s = str(value).strip()
    for fmt in (
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d",
        "%Y/%m/%d %H:%M:%S",
        "%Y/%m/%d",
    ):
        try:
            return datetime.strptime(s[:19], fmt)
        except ValueError:
            continue
    return None


def ensure_https(url: str) -> str:
    url = (url or "").strip()
    if not url:
        return url
    if url.startswith("//"):
        return "https:" + url
    if url.startswith("http://") or url.startswith("https://"):
        return url
    return "https://" + url.lstrip("/")
