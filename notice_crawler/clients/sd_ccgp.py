from __future__ import annotations

import base64
import hashlib
import random
import re
import time
from typing import Any, Dict, Iterable, List, Optional, Tuple
from urllib.parse import quote, urlencode

from clients.http_session import build_session
from config import settings

SITE_ID = "sd-ccgp"
SITE_LABEL = "山东政府采购网"
PORTAL = "https://www.ccgp-shandong.gov.cn"
API_BASE = f"{PORTAL}:8087/api"

# 采购信息栏目：省级用 code，市区县用 code1。排除「中小企业预留执行公告」。
CATEGORIES: List[Tuple[str, str, str]] = [
    ("2500", "2504", "意向公开"),
    ("0301", "0303", "采购公告"),
    ("0305", "0305", "更正公告"),
    ("0302", "0304", "结果公告"),
    ("0306", "0306", "终止公告"),
    ("2502", "2505", "合同公告"),
    ("2503", "2506", "验收公告"),
    ("2102", "2106", "单一来源公示"),
]

AREA_PROVINCIAL = "370000"
AREA_MUNICIPAL = "!370000"

_SCOPES: List[Tuple[str, str, str]] = [
    ("provincial", AREA_PROVINCIAL, "省级"),
    ("municipal", AREA_MUNICIPAL, "市区县"),
]

_CAPTCHA_FAIL_RE = re.compile(r"验证码|captcha|请输入验证码", re.I)
# WAF / 限流：HTTP 400 + blackIp；偶发网关错误也重试
_RETRYABLE_RE = re.compile(
    r"验证码|captcha|请输入验证码|blackIp|blocked|forbidden|too many|限流|频繁|429|502|503|504|400",
    re.I,
)
_BASE64_BODY_RE = re.compile(r"^[A-Za-z0-9+/=\s]+$")


def decode_notice_body(body: Any) -> str:
    """详情 body：前端用 atob + TextDecoder('gbk')；已是 HTML 则原样返回。"""
    if body is None:
        return ""
    if isinstance(body, (bytes, bytearray)):
        raw = bytes(body)
        for enc in ("gbk", "gb18030", "utf-8"):
            try:
                return raw.decode(enc)
            except Exception:  # noqa: BLE001
                continue
        return raw.decode("utf-8", errors="replace")

    text = str(body).strip()
    if not text:
        return ""
    stripped = text.lstrip()
    if stripped.startswith("<") or stripped.startswith("<!"):
        return text
    if stripped.startswith("data:application/pdf") or stripped.startswith("JVBERi0"):
        return text

    compact = re.sub(r"\s+", "", text)
    if len(compact) < 32 or not _BASE64_BODY_RE.fullmatch(text):
        return text
    try:
        raw = base64.b64decode(compact, validate=False)
    except Exception:  # noqa: BLE001
        return text
    if raw.startswith(b"%PDF"):
        return text
    for enc in ("gbk", "gb18030", "utf-8"):
        try:
            decoded = raw.decode(enc)
        except Exception:  # noqa: BLE001
            continue
        if "<" in decoded or any(tok in decoded for tok in ("采购", "公告", "项目", "供应商")):
            return decoded
        if len(decoded) > 40:
            return decoded
    return text


class SdCcgpClient:
    """中国山东政府采购网（ccgp-shandong.gov.cn/xxgk）公开信息抓取。"""

    # 前 5 页通常不强制验证码；第 6 页起必须带对的 captchaCode+Uuid。
    CAPTCHA_PAGE_THRESHOLD = 6

    def __init__(self) -> None:
        self.site_id = SITE_ID
        self.label = SITE_LABEL
        self.base = API_BASE
        self.session = build_session(
            headers={
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/131.0.0.0 Safari/537.36"
                ),
                "Accept": "application/json, text/plain, */*",
                "Origin": PORTAL,
                "Referer": f"{PORTAL}/xxgk",
                "Content-Type": "application/json;charset=utf-8",
            }
        )
        self._dddd = None
        # 验证码在有效期内可复用同一组 code+uuid 继续翻页
        self._captcha_code: str = ""
        self._captcha_uuid: str = ""

    def _sleep(self, seconds: Optional[float] = None) -> None:
        if seconds is not None:
            time.sleep(max(0.0, seconds))
            return
        base = max(0.2, float(settings.ccgp_request_interval))
        jitter = max(0.0, float(settings.ccgp_request_jitter))
        time.sleep(random.uniform(base, base + jitter) if jitter else base)

    def pause_between_pages(self) -> None:
        lo = max(0.0, float(settings.ccgp_page_pause_min))
        hi = max(lo, float(settings.ccgp_page_pause_max))
        time.sleep(random.uniform(lo, hi))

    def pause_between_categories(self) -> None:
        lo = max(0.0, float(settings.ccgp_category_pause_min))
        hi = max(lo, float(settings.ccgp_category_pause_max))
        time.sleep(random.uniform(lo, hi))

    def iter_categories(self) -> Iterable[Tuple[str, str, str, str, str]]:
        """yield (scope_key, area, col_code, canonical_code, label)."""
        for scope_key, area, scope_label in _SCOPES:
            for code, code1, name in CATEGORIES:
                col = code if scope_key == "provincial" else code1
                yield scope_key, area, col, code, f"{scope_label}-{name}"

    def clear_captcha(self) -> None:
        self._captcha_code = ""
        self._captcha_uuid = ""

    def fetch_captcha(self) -> Tuple[bytes, str]:
        self._sleep()
        resp = self.session.get(f"{self.base}/website/captcha", timeout=30)
        resp.raise_for_status()
        uuid = (resp.headers.get("captcha-uuid") or "").strip()
        if not uuid:
            raise RuntimeError("captcha-uuid missing")
        return resp.content, uuid

    def _dddd_engine(self):
        if self._dddd is None:
            import ddddocr

            self._dddd = ddddocr.DdddOcr(show_ad=False)
        return self._dddd

    def recognize_captcha(self, image_bytes: bytes) -> str:
        """ddddocr 识别 4 位字母数字验证码（原图效果最好）。"""
        try:
            text = self._dddd_engine().classification(image_bytes)
        except Exception:  # noqa: BLE001
            return ""
        return re.sub(r"[^A-Za-z0-9]", "", str(text or ""))

    def solve_captcha(self, *, max_tries: int = 8) -> Tuple[str, str]:
        """拉新图并用 ddddocr 识别；要求恰好 4 位，否则换图。"""
        last = ""
        for _ in range(max(1, max_tries)):
            raw, uuid = self.fetch_captcha()
            code = self.recognize_captcha(raw)
            last = code
            if len(code) == 4:
                return code, uuid
        raise RuntimeError(f"captcha OCR failed (last={last!r})")

    def _unwrap(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """接口外层 timestamp/status + data:{code,message,data}。"""
        outer = payload.get("data") if isinstance(payload.get("data"), dict) else payload
        if not isinstance(outer, dict):
            raise RuntimeError(f"unexpected response: {payload!r}"[:500])
        code = outer.get("code")
        if code not in (None, 100, "100"):
            msg = str(outer.get("message") or outer)
            raise RuntimeError(msg)
        data = outer.get("data")
        return data if isinstance(data, dict) else {"value": data}

    def _is_captcha_error(self, exc: BaseException) -> bool:
        return bool(_CAPTCHA_FAIL_RE.search(str(exc)))

    def _is_retryable_error(self, exc: BaseException) -> bool:
        return bool(_RETRYABLE_RE.search(str(exc)))

    def _backoff(self, attempt: int, exc: BaseException) -> None:
        msg = str(exc)
        if re.search(r"blackIp|blocked|频繁|限流", msg, re.I):
            # WAF 拉黑：拉长等待，避免继续打爆
            delay = min(120.0, 15.0 * (attempt + 1))
        elif self._is_captcha_error(exc):
            delay = min(8.0, 0.8 * (attempt + 1))
        else:
            delay = min(30.0, 2.0 * (attempt + 1))
        self._sleep(delay)

    def _post_list(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        self._sleep()
        resp = self.session.post(
            f"{self.base}/website/site/getListByCode",
            json=payload,
            timeout=45,
        )
        # WAF 常以 HTTP 400 + JSON{code:999,message:blackIp_...} 返回，不能只 raise_for_status
        try:
            body = resp.json()
        except Exception:  # noqa: BLE001
            body = None
        if resp.status_code >= 400:
            msg = ""
            if isinstance(body, dict):
                msg = str(body.get("message") or body.get("msg") or "")
                nested = body.get("data")
                if not msg and isinstance(nested, dict):
                    msg = str(nested.get("message") or "")
            if not msg:
                msg = (resp.text or "")[:300] or f"HTTP {resp.status_code}"
            raise RuntimeError(f"HTTP {resp.status_code}: {msg}")
        if not isinstance(body, dict):
            raise RuntimeError(f"invalid list response HTTP {resp.status_code}")
        return self._unwrap(body)

    def list_notices(
        self,
        *,
        col_code: str,
        area: str,
        page_num: int = 1,
        page_size: int = 20,
        start_time: Optional[str] = None,
        end_time: Optional[str] = None,
        old_data: int = 0,
        captcha_retries: int = 15,
    ) -> Dict[str, Any]:
        """列表抓取。

        - 第 1～5 页：可无验证码。
        - 第 6 页起：必须正确 captcha；通过后同一 code+uuid 在有效期内可继续翻页。
        - 过期/错误/WAF 400：清缓存并退避重试。
        """
        last_err: Optional[BaseException] = None
        base_payload = {
            "colCode": col_code,
            "area": area,
            "title": "",
            "projectCode": "",
            "currentPage": page_num,
            "pageSize": page_size,
            "buyKind": "",
            "buyType": "",
            "startTime": start_time or "",
            "endTime": end_time or "",
            "oldData": old_data,
            "homePage": 0,
            "mergeType": 0,
            "unitName": "",
            "projectType": "",
        }
        need_captcha = page_num >= self.CAPTCHA_PAGE_THRESHOLD

        for attempt in range(max(1, captcha_retries)):
            # 1) 复用未过期的验证码（翻页关键路径）
            if self._captcha_code and self._captcha_uuid:
                payload = {
                    **base_payload,
                    "captchaCode": self._captcha_code,
                    "captchaUuid": self._captcha_uuid,
                }
                try:
                    return self._post_list(payload)
                except RuntimeError as exc:
                    last_err = exc
                    if not self._is_retryable_error(exc):
                        raise
                    self.clear_captcha()
                    if not self._is_captcha_error(exc):
                        self._backoff(attempt, exc)
                        continue

            # 2) 前 5 页先试空码
            if not need_captcha and attempt == 0:
                payload = {**base_payload, "captchaCode": "", "captchaUuid": ""}
                try:
                    return self._post_list(payload)
                except RuntimeError as exc:
                    last_err = exc
                    if not self._is_retryable_error(exc):
                        raise
                    need_captcha = True
                    if not self._is_captcha_error(exc):
                        self._backoff(attempt, exc)
                        continue

            # 3) 重新识别
            try:
                code, uuid = self.solve_captcha()
            except Exception as exc:  # noqa: BLE001
                last_err = exc
                self._backoff(attempt, exc)
                continue
            payload = {
                **base_payload,
                "captchaCode": code,
                "captchaUuid": uuid,
            }
            try:
                data = self._post_list(payload)
                self._captcha_code = code
                self._captcha_uuid = uuid
                return data
            except RuntimeError as exc:
                last_err = exc
                if not self._is_retryable_error(exc):
                    raise
                self.clear_captcha()
                self._backoff(attempt, exc)
        raise RuntimeError(f"list failed after retries: {last_err}")

    def _get_json(self, url: str, *, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        last_err: Optional[BaseException] = None
        for attempt in range(5):
            self._sleep()
            try:
                resp = self.session.get(url, params=params, timeout=45)
                try:
                    body = resp.json()
                except Exception:  # noqa: BLE001
                    body = None
                if resp.status_code >= 400:
                    msg = ""
                    if isinstance(body, dict):
                        msg = str(body.get("message") or body.get("msg") or "")
                    if not msg:
                        msg = (resp.text or "")[:300] or f"HTTP {resp.status_code}"
                    raise RuntimeError(f"HTTP {resp.status_code}: {msg}")
                if not isinstance(body, dict):
                    raise RuntimeError(f"invalid response HTTP {resp.status_code}")
                return self._unwrap(body)
            except RuntimeError as exc:
                last_err = exc
                if not self._is_retryable_error(exc):
                    raise
                self._backoff(attempt, exc)
        raise RuntimeError(f"request failed after retries: {last_err}")

    def get_detail(
        self,
        notice_id: str,
        col_code: str,
        *,
        url_type: str = "site",
        old_data: Optional[Any] = None,
    ) -> Dict[str, Any]:
        params: Dict[str, Any] = {"id": notice_id, "colCode": col_code}
        if old_data not in (None, "", 0, "0"):
            params["oldData"] = str(old_data)
        data = self._get_json(
            f"{self.base}/website/{url_type or 'site'}/getDetail",
            params=params,
        )
        if isinstance(data, dict) and "body" in data:
            data = {**data, "body": decode_notice_body(data.get("body"))}
        return data

    def get_notice_body(self, notice_id: str, col_code: str) -> Dict[str, Any]:
        data = self._get_json(
            f"{self.base}/website/site/getNoticeBody",
            params={"id": notice_id, "colCode": col_code},
        )
        if isinstance(data, dict):
            for key in ("body", "content", "value"):
                if key in data and data.get(key) is not None:
                    data[key] = decode_notice_body(data.get(key))
        return data

    @staticmethod
    def notice_key(notice_id: str) -> str:
        """列表 id 为长加密串，入库用 sha256，原文保留在 list_json.id。"""
        raw = (notice_id or "").strip()
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    @staticmethod
    def notice_detail_url(notice_id: str, col_code: str, *, old_data: Any = 0) -> str:
        query = {"id": notice_id, "colCode": col_code}
        if old_data not in (None, "", 0, "0"):
            query["oldData"] = str(old_data)
        return f"{PORTAL}/detail?{urlencode(query, quote_via=quote)}"

    @staticmethod
    def extract_attachments(detail: Dict[str, Any]) -> List[Dict[str, str]]:
        files = detail.get("files") or []
        out: List[Dict[str, str]] = []
        for item in files:
            if not isinstance(item, dict):
                continue
            url = (item.get("url") or item.get("fileUrl") or item.get("file_url") or "").strip()
            name = (item.get("fileName") or item.get("file_name") or item.get("name") or "").strip()
            if not url:
                continue
            out.append({"file_url": url, "file_name": name or url.rsplit("/", 1)[-1]})
        return out
