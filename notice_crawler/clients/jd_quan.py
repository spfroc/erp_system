from __future__ import annotations

import json
import time
from typing import Any, Dict, Iterable, List, Optional, Tuple

from curl_cffi import requests as cffi_requests

from clients.http_session import proxy_url
from config import settings
from utils import ensure_https

SITE_ID = "jd-quan-yicai"

# (auctionType, noticeType, label, businessType)
# 竞价/反拍 noticeType: 1/2/3/4/6；询比 noticeType: 5/2/3/4/6
CATEGORIES: List[Tuple[str, str, str, str]] = [
    ("1", "1", "普通竞价-竞价公告", "1"),
    ("1", "2", "普通竞价-成交公告", "1"),
    ("1", "3", "普通竞价-终止公告", "1"),
    ("1", "4", "普通竞价-失败公告", "1"),
    ("1", "6", "普通竞价-废标公告", "1"),
    ("2", "1", "反拍竞价-竞价公告", "1"),
    ("2", "2", "反拍竞价-成交公告", "1"),
    ("2", "3", "反拍竞价-终止公告", "1"),
    ("2", "4", "反拍竞价-失败公告", "1"),
    ("2", "6", "反拍竞价-废标公告", "1"),
    ("3", "5", "询比-询比公告", "2"),
    ("3", "2", "询比-成交公告", "2"),
    ("3", "3", "询比-终止公告", "2"),
    ("3", "4", "询比-失败公告", "2"),
    ("3", "6", "询比-废标公告", "2"),
]


class JdQuanClient:
    def __init__(
        self,
        contract_num: Optional[str] = None,
        app_source: Optional[str] = None,
    ) -> None:
        self.contract_num = contract_num or settings.jd_contract_num
        self.app_source = app_source or settings.jd_app_source
        self.origin = "https://zcy-auction-view-pro.pf.jd.com"
        self.headers = {
            "Accept": "application/json, text/plain, */*",
            "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
            "Origin": self.origin,
            "Referer": self.origin + "/",
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/131.0.0.0 Safari/537.36"
            ),
        }

    def _sleep(self) -> None:
        time.sleep(settings.request_interval)

    def request(self, function_id: str, body: Dict[str, Any]) -> Any:
        self._sleep()
        kwargs = {
            "params": {"functionId": function_id, "appid": "zcy-auction-view"},
            "data": {"body": json.dumps(body, ensure_ascii=False)},
            "headers": self.headers,
            "impersonate": settings.jd_impersonate,
            "timeout": 30,
        }
        proxy = proxy_url()
        if proxy:
            kwargs["proxies"] = {"http": proxy, "https": proxy}
        resp = cffi_requests.post("https://api.m.jd.com/api", **kwargs)
        if resp.status_code != 200:
            raise RuntimeError(f"HTTP {resp.status_code}: {resp.text[:300]}")
        data = resp.json()
        if str(data.get("code")) != "0":
            raise RuntimeError(data.get("msg") or str(data))
        return data.get("data")

    def list_notices(
        self,
        *,
        auction_type: str,
        notice_type: str,
        business_type: str = "1",
        page_num: int = 1,
        page_size: int = 50,
    ) -> Dict[str, Any]:
        body = {
            "pageNum": page_num,
            "pageSize": page_size,
            "auctionType": str(auction_type),
            "noticeType": "" if notice_type in (None, "全部") else str(notice_type),
            "businessType": str(business_type),
            "contractNum": self.contract_num,
            "appSource": self.app_source,
            "orderByCreateTime": "",
            "search": "",
            "noticeCodeSearch": "",
            "projectNoSearch": "",
            "auctionNameSearch": "",
        }
        return self.request("zcy_selectNoticePage", body) or {}

    def get_detail(self, auction_no: str, notice_type: int | str) -> Dict[str, Any]:
        return (
            self.request(
                "zcy_selectNoticeByAuctionNo",
                {"auctionNo": auction_no, "noticeType": int(notice_type)},
            )
            or {}
        )

    def extract_attachments(self, detail: Dict[str, Any]) -> List[Dict[str, str]]:
        files: List[Dict[str, str]] = []
        for item in detail.get("attachmentInfoList") or []:
            url = ensure_https(item.get("url") or "")
            if not url:
                continue
            files.append(
                {
                    "file_name": item.get("attachmentName") or url.rsplit("/", 1)[-1],
                    "file_url": url,
                }
            )
        return files

    def iter_categories(self) -> Iterable[Tuple[str, str, str, str]]:
        return CATEGORIES
