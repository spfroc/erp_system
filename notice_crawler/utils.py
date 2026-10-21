from __future__ import annotations

import re
from datetime import datetime
from typing import Any, Optional
from zoneinfo import ZoneInfo

from bs4 import BeautifulSoup

# 公告业务时区：网站展示与入库墙钟统一用上海时间（naive DATETIME）
APP_TZ = ZoneInfo("Asia/Shanghai")


def now() -> datetime:
    """当前上海墙钟（naive），写入 MySQL DATETIME。"""
    return datetime.now(APP_TZ).replace(tzinfo=None)


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
    """解析为上海墙钟 naive datetime。

    - 秒/毫秒时间戳：按绝对时刻转上海本地
    - 无时区字符串（网站常用）：视为已是上海本地时间
    """
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        if value.tzinfo is not None:
            return value.astimezone(APP_TZ).replace(tzinfo=None)
        return value
    if isinstance(value, (int, float)) or (isinstance(value, str) and str(value).strip().isdigit()):
        # JD createTime 常为毫秒时间戳
        ts = float(value)
        if ts > 1e12:
            ts /= 1000.0
        try:
            return datetime.fromtimestamp(ts, tz=APP_TZ).replace(tzinfo=None)
        except (OverflowError, OSError, ValueError):
            return None
    s = str(value).strip().replace("T", " ")
    for fmt, n in (
        ("%Y-%m-%d %H:%M:%S", 19),
        ("%Y/%m/%d %H:%M:%S", 19),
        ("%Y-%m-%d", 10),
        ("%Y/%m/%d", 10),
    ):
        try:
            return datetime.strptime(s[:n], fmt)
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
