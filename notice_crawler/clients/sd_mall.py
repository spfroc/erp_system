from __future__ import annotations

import json
import time
from typing import Any, Dict, Iterable, List, Optional, Tuple

import requests

from clients.http_session import build_session, request_with_retries
from config import settings
from utils import ensure_https

try:
    from tqdm import tqdm
except ImportError:  # pragma: no cover
    tqdm = None

SITE_ID = "sd-ggzyjyzx"
_CONN_HINTS = ("ConnectTimeout", "ConnectionError", "NewConnectionError", "ProxyError", "RemoteDisconnected")

# 详情页「采购清单」按钮实际走 ExceptGD（含 orderGuid/projectType）
DETAIL_EXCEPT_GD = "/gateway/gpmall-bpoc/api/notice/other/v1/ignore/getNoticeDetailExceptGD"
# projectType!=10：普通订单；=10：批量集采
ACCEPTANCE_ORDERS = "/gateway/gpmall-bpoc/api/orders/v1/ignore/downloadAcceptanceFrom/{order_guid}"
ACCEPTANCE_CENTRAL = (
    "/gateway/gpmall-gpm/api/centralOrder/v1/ignore/downloadAcceptanceFrom/{order_guid}"
)

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


def is_connection_failure(exc: BaseException) -> bool:
    text = f"{type(exc).__name__}: {exc}"
    return isinstance(exc, (requests.ConnectionError, requests.Timeout)) or any(h in text for h in _CONN_HINTS)


class SdMallClient:
    def __init__(self) -> None:
        self.base = "https://ggzyjyzx.shandong.gov.cn:8182"
        self._headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "siteCode": settings.sd_site_code,
            "regionGuid": settings.sd_region_guid,
            "User-Agent": "Mozilla/5.0 notice-crawler",
        }
        self.session = build_session(headers=self._headers)

    def reset_session(self) -> None:
        """SOCKS 超时后连接池易脏，重建 session 再试。"""
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
        # connect/read 分开：代理抖动时尽快失败并重建，读响应可稍长
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
        """轻量探活：确认 SOCKS→商城网关可用。"""
        self.list_notices(project_type=5, notice_type=1, page_num=1, page_size=1)

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
        return self._request(
            "POST",
            "/gateway/gpmall-bpoc/notice/v1/ignore/getNoticeList",
            json=body,
        )

    def get_detail(self, notice_guid: str) -> Dict[str, Any]:
        return self._request(
            "GET",
            "/gateway/gpmall-bpoc/notice/v1/ignore/getNoticeDetail",
            params={"noticeGuid": notice_guid},
        )

    def get_detail_except_gd(self, notice_guid: str) -> Dict[str, Any]:
        """公告详情扩展字段：orderGuid / projectType / pdfPath 等（采购清单依赖）。"""
        return self._request(
            "GET",
            DETAIL_EXCEPT_GD,
            params={"noticeGuid": notice_guid},
        )

    def merge_except_gd(
        self, notice_guid: str, detail: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """把 ExceptGD 关键字段并入详情；失败时原样返回。"""
        base = dict(detail or {})
        try:
            extra = self.get_detail_except_gd(notice_guid)
        except Exception:  # noqa: BLE001
            return base
        if not isinstance(extra, dict):
            return base
        for key, value in extra.items():
            if value in (None, "", [], {}):
                continue
            if key == "content" and base.get("content"):
                continue
            if key == "noticeFileList" and base.get("noticeFileList"):
                continue
            base[key] = value
        return base

    def resolve_acceptance_file(
        self, order_guid: str, project_type: Any = None
    ) -> Optional[Dict[str, str]]:
        """调用采购清单接口，返回 {file_name, file_url}。"""
        og = str(order_guid or "").strip()
        if not og:
            return None
        try:
            pt = int(project_type) if project_type not in (None, "") else 0
        except (TypeError, ValueError):
            pt = 0
        path = (ACCEPTANCE_CENTRAL if pt == 10 else ACCEPTANCE_ORDERS).format(
            order_guid=og
        )
        raw = self._request("GET", path)
        info: Any = raw
        if isinstance(raw, str):
            try:
                info = json.loads(raw)
            except json.JSONDecodeError:
                return None
        if not isinstance(info, dict):
            return None
        url = ensure_https(str(info.get("filePath") or info.get("url") or "").strip())
        if not url:
            return None
        name = str(info.get("name") or info.get("fileName") or "").strip()
        if not name:
            name = f"采购清单-{og}.pdf"
        elif not name.lower().endswith((".pdf", ".xls", ".xlsx", ".doc", ".docx")):
            name = f"{name}.pdf"
        return {"file_name": name, "file_url": url}

    def extract_attachments(self, detail: Dict[str, Any]) -> List[Dict[str, str]]:
        """登记 noticeFileList + 采购清单（downloadAcceptanceFrom）。"""
        files: List[Dict[str, str]] = []
        seen = set()

        def add(name: Any, url: Any) -> None:
            file_url = ensure_https(str(url or "").strip())
            if not file_url or file_url in seen:
                return
            seen.add(file_url)
            file_name = str(name or "").strip() or file_url.rsplit("/", 1)[-1].split("?", 1)[0]
            files.append({"file_name": file_name, "file_url": file_url})

        if not isinstance(detail, dict):
            return files

        for item in detail.get("noticeFileList") or []:
            if isinstance(item, dict):
                add(
                    item.get("fileName") or item.get("name") or item.get("file_name"),
                    item.get("filePath")
                    or item.get("fileUrl")
                    or item.get("url")
                    or item.get("file_url"),
                )
            elif isinstance(item, str):
                add("", item)

        notice_file = detail.get("noticeFile")
        if isinstance(notice_file, dict):
            add(
                notice_file.get("fileName") or notice_file.get("name"),
                notice_file.get("filePath")
                or notice_file.get("fileUrl")
                or notice_file.get("url"),
            )
        elif isinstance(notice_file, str) and notice_file.startswith("http"):
            add("", notice_file)

        pdf_path = detail.get("pdfPath")
        if isinstance(pdf_path, str) and pdf_path.startswith("http"):
            add(detail.get("title") or "公告PDF", pdf_path)

        order_guid = str(detail.get("orderGuid") or "").strip()
        if order_guid:
            try:
                acc = self.resolve_acceptance_file(
                    order_guid, detail.get("projectType")
                )
            except Exception:  # noqa: BLE001
                acc = None
            if acc:
                # 采购清单优先靠前，便于解析
                files = [acc] + [f for f in files if f["file_url"] != acc["file_url"]]

        return files

    def iter_categories(self) -> Iterable[Tuple[int, int, str]]:
        return CATEGORIES
