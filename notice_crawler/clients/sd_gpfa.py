from __future__ import annotations

import time
from typing import Any, Dict, Iterable, List, Optional, Tuple

from clients.http_session import build_session
from config import settings

SITE_ID = "sd-gpfa-frame"

# (projectType, noticeType, label) — 按需求：采购公告/成交结果单笔/终止
CATEGORIES: List[Tuple[int, int, str]] = [
    (17, 0, "采购公告-二次竞价"),
    (17, 1, "成交结果单笔-二次竞价"),
    (33, 1, "成交结果单笔-顺序轮候"),
    (17, 10, "终止公告-二次竞价"),
    (33, 10, "终止公告-顺序轮候"),
]


class SdGpfaClient:
    def __init__(self) -> None:
        self.base = "https://ggzyjyzx.shandong.gov.cn:8182"
        self.session = build_session(
            headers={
                "Accept": "application/json",
                "siteCode": settings.sd_site_code,
                "regionGuid": settings.sd_region_guid,
                "User-Agent": "Mozilla/5.0 notice-crawler",
            }
        )

    def _sleep(self) -> None:
        time.sleep(settings.request_interval)

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
        self._sleep()
        resp = self.session.get(
            f"{self.base}/gateway/gpfa-bpoc/notice/v1/ignore/getNoticeList",
            params=params,
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()
        if not data.get("success"):
            raise RuntimeError(data.get("message") or str(data))
        return data.get("data") or {}

    def get_detail(self, notice_guid: str) -> Dict[str, Any]:
        self._sleep()
        resp = self.session.get(
            f"{self.base}/gateway/gpfa-bpoc/api/notice/other/v1/ignore/getNoticeDetailExceptGD",
            params={"noticeGuid": notice_guid},
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()
        if not data.get("success"):
            raise RuntimeError(data.get("message") or str(data))
        return data.get("data") or {}

    def iter_categories(self) -> Iterable[Tuple[int, int, str]]:
        return CATEGORIES
