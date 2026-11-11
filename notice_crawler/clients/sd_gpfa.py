from __future__ import annotations

import time
from typing import Any, Dict, Iterable, List, Optional, Tuple

import requests

from clients.http_session import build_session, request_with_retries
from config import settings

try:
    from tqdm import tqdm
except ImportError:  # pragma: no cover
    tqdm = None

SITE_ID = "sd-gpfa-frame"
SITE_LABEL = "框架协议"
_CONN_HINTS = ("ConnectTimeout", "ConnectionError", "NewConnectionError", "ProxyError", "RemoteDisconnected")

# (projectType, noticeType, label)
# 三大类：采购公告(0) / 成交结果单笔(1) / 终止公告(10)
# 小类：二次竞价(17) / 直接选定服务(31) / 直接选定货物(32) / 顺序轮候(33)
# 页面「直接选定」常传拼接码 3132；这里拆开抓，便于每类限额与差异化解析
CATEGORIES: List[Tuple[int, int, str]] = [
    (17, 0, "采购公告-二次竞价"),
    (31, 0, "采购公告-直接选定服务"),
    (32, 0, "采购公告-直接选定货物"),
    (33, 0, "采购公告-顺序轮候"),
    (17, 1, "成交结果单笔-二次竞价"),
    (31, 1, "成交结果单笔-直接选定服务"),
    (32, 1, "成交结果单笔-直接选定货物"),
    (33, 1, "成交结果单笔-顺序轮候"),
    (17, 10, "终止公告-二次竞价"),
    (31, 10, "终止公告-直接选定服务"),
    (32, 10, "终止公告-直接选定货物"),
    (33, 10, "终止公告-顺序轮候"),
]

DETAIL_PATH = "/gateway/gpfa-bpoc/api/notice/other/v1/ignore/getNoticeDetailExceptGD"
LIST_PATH = "/gateway/gpfa-bpoc/notice/v1/ignore/getNoticeList"
PORTAL = "https://ggzyjyzx.shandong.gov.cn:8182"


def is_connection_failure(exc: BaseException) -> bool:
    text = f"{type(exc).__name__}: {exc}"
    return isinstance(exc, (requests.ConnectionError, requests.Timeout)) or any(
        h in text for h in _CONN_HINTS
    )


class SdGpfaClient:
    def __init__(self) -> None:
        self.base = PORTAL
        self._headers = {
            "Accept": "application/json",
            "siteCode": settings.sd_site_code,
            "regionGuid": settings.sd_region_guid,
            "User-Agent": "Mozilla/5.0 notice-crawler",
        }
        self.session = build_session(headers=self._headers)

    def reset_session(self) -> None:
        try:
            self.session.close()
        except Exception:  # noqa: BLE001
            pass
        self.session = build_session(headers=self._headers)

    def _sleep(self) -> None:
        time.sleep(settings.request_interval)

    def _on_retry(self, attempt: int, attempts: int, reason: str, wait: float) -> None:
        if any(h in reason for h in _CONN_HINTS):
            self.reset_session()
        message = f"{SITE_ID} 请求重试 {attempt}/{attempts - 1}（{reason}），等待 {wait:.0f}s"
        if tqdm is not None:
            tqdm.write(message)
        else:
            print(message)

    def _request(self, method: str, path: str, **kwargs) -> Any:
        self._sleep()
        resp = request_with_retries(
            self.session,
            method,
            f"{self.base}{path}",
            retries=6,
            backoff=2.0,
            timeout=(20, 60),
            on_retry=self._on_retry,
            **kwargs,
        )
        resp.raise_for_status()
        data = resp.json()
        if not data.get("success"):
            raise RuntimeError(data.get("message") or str(data))
        return data.get("data") or {}

    def probe(self) -> None:
        self.list_notices(project_type=17, notice_type=0, page_num=1, page_size=1)

    def list_notices(
        self,
        *,
        project_type: int,
        notice_type: int,
        page_num: int = 1,
        page_size: int = 50,
        region_guid: Optional[str] = None,
        region_code: Optional[str] = None,
        factor: str = "",
    ) -> Dict[str, Any]:
        params = {
            "regionCode": region_code or settings.sd_region_code,
            "regionGuid": region_guid or settings.sd_region_guid,
            "supplierName": "",
            "projectName": "",
            "projectCode": "",
            "agreementName": "",
            "agreementCode": "",
            "factor": factor or "",
            "projectTypeCode": "",
            "firstStageProjectName": "",
            "firstStageProjectCode": "",
            "pageSize": page_size,
            "pageNum": page_num,
            "projectType": project_type,
            "noticeType": notice_type,
        }
        return self._request("GET", LIST_PATH, params=params)

    def get_detail(self, notice_guid: str) -> Dict[str, Any]:
        return self._request("GET", DETAIL_PATH, params={"noticeGuid": notice_guid})

    @staticmethod
    def list_items(payload: Dict[str, Any]) -> List[Dict[str, Any]]:
        """列表接口实际记录在 data 字段（不是 records）。"""
        rows = payload.get("data")
        if isinstance(rows, list):
            return [r for r in rows if isinstance(r, dict)]
        for key in ("records", "list", "rows"):
            rows = payload.get(key)
            if isinstance(rows, list):
                return [r for r in rows if isinstance(r, dict)]
        return []

    @staticmethod
    def notice_detail_url(notice_guid: str) -> str:
        return f"{PORTAL}/gpfa-main-web/basic/noticeDetail?noticeGuid={notice_guid}"

    def iter_categories(self) -> Iterable[Tuple[int, int, str]]:
        return CATEGORIES
