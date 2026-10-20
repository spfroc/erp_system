from __future__ import annotations

import time
from typing import Any, Dict, Iterable, List, Optional, Tuple

from clients.http_session import build_session
from config import settings

SITE_ID = "sd-ggzyjyzx"

# (projectType, noticeType, label)
CATEGORIES: List[Tuple[int, int, str]] = [
    (21, 0, "标准品目竞价-采购公告"),
    (21, 1, "标准品目竞价-成交公告"),
    (21, 10, "标准品目竞价-终止公告"),
    (1, 0, "标准品目反拍-采购公告"),
    (1, 1, "标准品目反拍-成交公告"),
    (1, 10, "标准品目反拍-终止公告"),
    (5, 1, "标准品目直购-成交公告"),
    (5, 10, "标准品目直购-终止公告"),
    (3, 0, "定制品目竞价-采购公告"),
    (3, 1, "定制品目竞价-成交公告"),
    (3, 5, "定制品目竞价-终止公告"),
    (12, 0, "定制品目议价-采购公告"),
    (12, 1, "定制品目议价-成交公告"),
    (12, 5, "定制品目议价-终止公告"),
    (10, 1, "标准品目批量采购-成交公告"),
    (10, 5, "标准品目批量采购-终止公告"),
]


class SdMallClient:
    def __init__(self) -> None:
        self.base = "https://ggzyjyzx.shandong.gov.cn:8182"
        self.session = build_session(
            headers={
                "Content-Type": "application/json",
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
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        factor: str = "",
    ) -> Dict[str, Any]:
        body: Dict[str, Any] = {
            "pageNum": page_num,
            "pageSize": page_size,
            "projectType": project_type,
            "noticeType": notice_type,
            "factor": factor or "",
            "startDate": start_date,
            "endDate": end_date,
        }
        # 全省：不传 regionGuidList
        self._sleep()
        resp = self.session.post(
            f"{self.base}/gateway/gpmall-bpoc/notice/v1/ignore/getNoticeList",
            json=body,
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
            f"{self.base}/gateway/gpmall-bpoc/notice/v1/ignore/getNoticeDetail",
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
