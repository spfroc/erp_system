"""齐鲁云采登录（对齐 vip-rebuild QlycLoginService / qlyc:login）。

流程：访问登录页 → 拉验证码 → OCR → login.do → cookie 中的 access_token。
密码：SHA1(明文) → Base64（QlycPasswordService）。
"""

from __future__ import annotations

import base64
import hashlib
import json
import time
from pathlib import Path
from typing import Any, Dict, Optional
from urllib.parse import unquote

import requests
import urllib3

from config import settings

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

BASE = "https://ggzyjyzx.shandong.gov.cn:8182"
TOKEN_CACHE = Path(__file__).resolve().parent.parent / "data" / "qlyc_access_token.json"


def encrypt_password(plain: str) -> str:
    raw = hashlib.sha1(plain.encode("utf-8")).digest()
    return base64.b64encode(raw).decode("ascii")


def _jwt_exp(token: str) -> Optional[int]:
    try:
        parts = token.split(".")
        if len(parts) < 2:
            return None
        pad = "=" * (-len(parts[1]) % 4)
        payload = json.loads(base64.urlsafe_b64decode(parts[1] + pad))
        exp = payload.get("exp")
        return int(exp) if exp is not None else None
    except Exception:  # noqa: BLE001
        return None


def token_valid(token: str, skew: int = 120) -> bool:
    if not token or not token.strip():
        return False
    exp = _jwt_exp(token.strip())
    if exp is None:
        return True
    return time.time() < exp - skew


def load_cached_token() -> Optional[str]:
    if not TOKEN_CACHE.exists():
        return None
    try:
        data = json.loads(TOKEN_CACHE.read_text(encoding="utf-8"))
        token = (data.get("access_token") or "").strip()
        if token_valid(token):
            return token
    except Exception:  # noqa: BLE001
        return None
    return None


def save_cached_token(token: str, cookies: Optional[dict] = None) -> None:
    TOKEN_CACHE.parent.mkdir(parents=True, exist_ok=True)
    TOKEN_CACHE.write_text(
        json.dumps(
            {"access_token": token, "cookies": cookies or {}, "saved_at": int(time.time())},
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )


class QlycLoginClient:
    def __init__(self) -> None:
        self.session = requests.Session()
        self.session.verify = False
        self.session.headers.update(
            {
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/122.0.0.0 Safari/537.36"
                ),
                "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            }
        )
        self.final_url: Optional[str] = None

    def visit_login_page(self) -> None:
        url = (
            f"{BASE}/gateway/gp-auth-center/login"
            "?systemRegion=120000"
            f"&redirectUrl={BASE}/gpfa-main-web/index"
            "&tenantId=ZF_JGBM_000013"
            "&code=sd"
            "&userType=2"
        )
        resp = self.session.get(url, timeout=20, allow_redirects=True)
        resp.raise_for_status()
        self.final_url = str(resp.url)

    def get_verify_code(self, save_path: Path) -> None:
        ts = int(time.time() * 1000)
        url = f"{BASE}/gp-auth-center/verify/verifyCode?d={ts}"
        resp = self.session.get(
            url,
            headers={
                "Accept": "image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8",
                "Referer": self.final_url or BASE,
                "X-Requested-With": "XMLHttpRequest",
            },
            timeout=20,
        )
        resp.raise_for_status()
        save_path.parent.mkdir(parents=True, exist_ok=True)
        save_path.write_bytes(resp.content)
        if save_path.stat().st_size < 100:
            raise RuntimeError("验证码下载失败（文件过小）")

    def recognize_verify_code(self, image_path: Path) -> str:
        """对齐 qlyc:login：POST verify.qlyc.co/upload_image。"""
        url = settings.qlyc_captcha_url
        image_b64 = base64.b64encode(image_path.read_bytes()).decode("ascii")
        resp = requests.post(
            url,
            json={"image_base64": image_b64},
            headers={"Content-Type": "application/json"},
            timeout=20,
        )
        resp.raise_for_status()
        body = resp.json()
        if body.get("status") != "success" or not body.get("text"):
            raise RuntimeError(f"验证码识别失败: {body}")
        return str(body["text"]).strip()

    def login(self, account: str, password: str, verify_code: str, *, raw_password: bool = False) -> Dict[str, Any]:
        if not self.final_url:
            self.visit_login_page()
        # 默认明文 → SHA1 → Base64；raw_password=True 表示已是接口所需 pwd
        pwd_src = unquote(password) if unquote(password) != password else password
        pwd = pwd_src if raw_password else encrypt_password(pwd_src)

        url = f"{BASE}/gp-auth-center/login.do"
        form = {
            "userType": "4",
            "userAccount": account,
            "pwd": pwd,
            "verifyCode": verify_code,
            "slideVerify": "null",
            "loginType": "LOGIN_USERNAME",
            "code": "sd",
            "SDuserType": "3",
        }
        resp = self.session.post(
            url,
            data=form,
            headers={
                "Accept": "application/json, text/javascript, */*; q=0.01",
                "Content-Type": "application/x-www-form-urlencoded",
                "Referer": self.final_url or BASE,
                "Origin": BASE,
                "X-Requested-With": "XMLHttpRequest",
            },
            timeout=20,
        )
        resp.raise_for_status()
        data = resp.json()
        if int(data.get("code") or 0) != 200:
            raise RuntimeError(data.get("msg") or f"登录失败: {data}")
        redirect = (data.get("data") or {}).get("redirectUrl")
        if redirect:
            self.session.get(redirect, timeout=20, allow_redirects=True)
        cookies = self.session.cookies.get_dict()
        token = cookies.get("access_token")
        if not token:
            raise RuntimeError("登录成功但未拿到 access_token")
        return {"access_token": token, "cookies": cookies, "raw": data}

    def login_with_captcha(self, account: str, password: str) -> Dict[str, Any]:
        self.visit_login_page()
        captcha_path = Path(settings.attachment_dir) / "tmp" / f"qlyc_captcha_{int(time.time())}.png"
        self.get_verify_code(captcha_path)
        try:
            code = self.recognize_verify_code(captcha_path)
        finally:
            try:
                captcha_path.unlink(missing_ok=True)
            except Exception:  # noqa: BLE001
                pass
        return self.login(account, password, code)


def ensure_access_token(*, force_login: bool = False) -> str:
    """优先 .env / 缓存；否则用账号密码登录。"""
    if not force_login:
        env_token = (settings.sd_access_token or "").strip()
        if token_valid(env_token):
            return env_token
        cached = load_cached_token()
        if cached:
            return cached

    account = (settings.sd_account or "").strip()
    password = settings.sd_password or ""
    if not account or not password:
        raise RuntimeError(
            "缺少有效 access_token。请在 .env 配置 SD_ACCOUNT / SD_PASSWORD（自动登录），"
            "或手动填写 SD_ACCESS_TOKEN"
        )

    last_err: Optional[Exception] = None
    for _ in range(3):
        try:
            client = QlycLoginClient()
            result = client.login_with_captcha(account, password)
            token = result["access_token"]
            save_cached_token(token, result.get("cookies"))
            return token
        except Exception as exc:  # noqa: BLE001
            last_err = exc
            time.sleep(1)
    raise RuntimeError(f"齐鲁云采登录失败: {last_err}")
