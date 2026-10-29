from __future__ import annotations

import json
import time
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Optional, Tuple

from curl_cffi import requests as cffi_requests

from clients.http_session import proxy_url
from config import settings
from utils import ensure_https

# 兼容旧引用：默认仍是泉易采
SITE_ID = "jd-quan-yicai"
SITE_ID_QING_HUICAI = "jd-qing-huicai"

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


@dataclass(frozen=True)
class JdSiteConfig:
    site_id: str
    label: str
    contract_num: str
    app_source: str = "CLT"


def jd_site_configs() -> List[JdSiteConfig]:
    """泉易采 + 青慧采（同一套京东公告接口，不同合同号）。"""
    sites = [
        JdSiteConfig(
            site_id=SITE_ID,
            label="京东泉易采",
            contract_num=settings.jd_contract_num,
            app_source=settings.jd_app_source,
        ),
    ]
    qhc = (settings.jd_qhc_contract_num or "").strip()
    if qhc:
        sites.append(
            JdSiteConfig(
                site_id=SITE_ID_QING_HUICAI,
                label="京东青慧采",
                contract_num=qhc,
                app_source=settings.jd_app_source,
            )
        )
    return sites


def is_jd_site(site_id: Optional[str]) -> bool:
    return bool(site_id) and (
        site_id.startswith("jd-")
        or site_id in {SITE_ID, SITE_ID_QING_HUICAI}
    )


def notice_path_for_business(business_type: str | int) -> str:
    """询比走 /xj，竞价/反拍走 /jj。"""
    return "xj" if str(business_type) == "2" else "jj"


class JdQuanClient:
    def __init__(
        self,
        *,
        site_id: Optional[str] = None,
        contract_num: Optional[str] = None,
        app_source: Optional[str] = None,
        label: Optional[str] = None,
    ) -> None:
        self.site_id = site_id or SITE_ID
        self.label = label or ("京东青慧采" if self.site_id == SITE_ID_QING_HUICAI else "京东泉易采")
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

    @classmethod
    def from_config(cls, cfg: JdSiteConfig) -> "JdQuanClient":
        return cls(
            site_id=cfg.site_id,
            contract_num=cfg.contract_num,
            app_source=cfg.app_source,
            label=cfg.label,
        )

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

    def notice_detail_url(
        self,
        auction_no: str,
        notice_type: Any,
        *,
        business_type: str | int = "1",
    ) -> str:
        path = notice_path_for_business(business_type)
        return (
            f"{self.origin}/{path}/notice/detail"
            f"?auctionNo={auction_no}&noticeType={notice_type}"
        )

    def extract_attachments(self, detail: Dict[str, Any]) -> List[Dict[str, str]]:
        files: List[Dict[str, str]] = []
        seen = set()

        def add(item: Any) -> None:
            if not isinstance(item, dict):
                return
            url = ensure_https(
                item.get("url") or item.get("fileUrl") or item.get("attachmentUrl") or ""
            )
            if not url or url in seen:
                return
            seen.add(url)
            files.append(
                {
                    "file_name": (
                        item.get("attachmentName")
                        or item.get("fileName")
                        or url.rsplit("/", 1)[-1]
                    ),
                    "file_url": url,
                }
            )

        for item in detail.get("attachmentInfoList") or []:
            add(item)
        nested = detail.get("detail")
        if isinstance(nested, dict):
            for item in nested.get("attachmentInfoList") or []:
                add(item)
        return files

    def iter_categories(self) -> Iterable[Tuple[str, str, str, str]]:
        return CATEGORIES
