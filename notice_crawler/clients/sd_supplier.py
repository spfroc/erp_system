"""山东网上商城供应商列表（对齐 vip-rebuild TouchCustomer / NewQlyc\\GrabSupplier）。

列表接口响应加密。默认仅本地 node js/decode.js（需 SD_ACCESS_TOKEN）。
"""

from __future__ import annotations

import json
import os
import subprocess
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from clients.http_session import build_session
from config import settings

AGREEMENT_TYPES = {
    1: "超市厂商",
    2: "定点供应商",
    3: "代理商",
    4: "经销商",
    5: "超市电商",
}

_JS_DIR = Path(__file__).resolve().parent.parent / "js"
_DECODE_JS = _JS_DIR / "decode.js"


class SdSupplierClient:
    def __init__(self) -> None:
        self.session = build_session(
            headers={
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/131.0.0.0 Safari/537.36"
                ),
                "Accept": "application/json, text/plain, */*",
                "Content-Type": "application/json",
                "siteCode": settings.sd_site_code,
                "Regionguid": settings.sd_region_guid,
                "Regioncode": settings.sd_region_code,
            }
        )

    def _sleep(self) -> None:
        time.sleep(settings.request_interval)

    def _list_params(self, agreement_type: int, page_num: int, page_size: int) -> dict:
        return {
            "unitScopeCodeList": [],
            "regionGuid": settings.sd_region_guid,
            "agreementType": agreement_type,
            "pageSize": page_size,
            "pageNum": page_num,
        }

    def _via_local_node(self, params: dict, access_token: str) -> Dict[str, Any]:
        token = (access_token or "").strip()
        if not token:
            raise RuntimeError("本地解密需要 access_token（请先登录或配置 SD_ACCESS_TOKEN）")
        if not _DECODE_JS.exists():
            raise RuntimeError(f"缺少本地解密脚本: {_DECODE_JS}")
        if not (_JS_DIR / "node_modules").exists():
            raise RuntimeError(f"请先安装解密依赖: cd {_JS_DIR} && npm install")
        cmd = [
            "node",
            str(_DECODE_JS),
            settings.sd_supplier_list_url,
            json.dumps(params, ensure_ascii=False),
            "POST",
            token,
        ]
        env = os.environ.copy()
        env["SD_ACCESS_TOKEN"] = token
        proc = subprocess.run(
            cmd,
            cwd=str(_JS_DIR),
            capture_output=True,
            text=True,
            encoding="utf-8",
            env=env,
            timeout=90,
        )
        out = (proc.stdout or "").strip()
        if proc.returncode != 0 or not out:
            err = (proc.stderr or proc.stdout or "").strip()[:400]
            raise RuntimeError(f"本地解密失败: {err}")
        data = json.loads(out)
        if not isinstance(data, dict):
            raise RuntimeError(f"本地解密结果异常: {str(data)[:200]}")
        return data

    def list_by_agreement(
        self,
        *,
        agreement_type: int,
        page_num: int = 1,
        page_size: int = 50,
        access_token: Optional[str] = None,
    ) -> Dict[str, Any]:
        from clients.qlyc_login import ensure_access_token

        self._sleep()
        params = self._list_params(agreement_type, page_num, page_size)
        token = (access_token or "").strip() or ensure_access_token()
        return self._via_local_node(params, token)

    def get_store(self, supplier_guid: str, access_token: Optional[str] = None) -> Dict[str, Any]:
        from clients.qlyc_login import ensure_access_token

        token = (access_token or "").strip() or ensure_access_token()
        if not token:
            return {}
        self._sleep()
        body = {
            "regionGuid": settings.sd_region_guid,
            "categoryGuid": "",
            "categoryName": "",
            "goodsBrandGuid": "",
            "goodsBrandName": "",
            "paramInfos": "",
            "minPrice": "",
            "maxPrice": "",
            "pageNo": 1,
            "pageSize": 20,
            "keyword": "",
            "supplierGuid": supplier_guid,
            "platform": "",
            "orderinfos": '{"sortType":"sellCount","orderRole":"down"}',
        }
        headers = {
            "access_token": token,
            "Regionguid": settings.sd_region_guid,
            "Regioncode": settings.sd_region_code,
            "siteCode": settings.sd_site_code,
        }
        resp = self.session.post(settings.sd_store_url, json=body, headers=headers, timeout=60)
        resp.raise_for_status()
        data = resp.json()
        return data if isinstance(data, dict) else {}


def map_list_item(item: dict, agreement_type: int) -> dict:
    reg = str(item.get("regAddr") or item.get("address") or "")
    parts = [p.strip() for p in reg.split("-")]
    while len(parts) < 3:
        parts.append("")
    mobiles = []
    for key in ("personMobile", "telPhone", "supplyTel"):
        val = (item.get(key) or "").strip()
        if val and val not in mobiles:
            mobiles.append(val)
    return {
        "platform_customer_id": str(item.get("supplierGuid") or item.get("id") or ""),
        "name": (item.get("suppliername") or item.get("supplierName") or "").strip(),
        "type": AGREEMENT_TYPES.get(agreement_type, str(agreement_type)),
        "address": reg or (parts[2] if parts[2] else ""),
        "province": parts[0] or "山东",
        "city": parts[1] or "未知",
        "legal_person": item.get("personName") or "",
        "new_mobile": ",".join(mobiles),
        "email": item.get("supplyEmail"),
        "origin": "10",
        "list_json": item,
    }


def enrich_from_store(mapped: dict, store: dict) -> dict:
    data = store.get("data") if isinstance(store, dict) else None
    if not isinstance(data, dict):
        return mapped
    entity = data.get("supplierEntity") if isinstance(data.get("supplierEntity"), dict) else {}
    info = data.get("supplierInfoVO") if isinstance(data.get("supplierInfoVO"), dict) else {}
    if entity.get("license"):
        mapped["license_code"] = entity.get("license")
    if entity.get("email"):
        mapped["email"] = entity.get("email")
    if info.get("mainTradeScope"):
        mapped["business_scope"] = info.get("mainTradeScope")
    if data.get("totalGoods") is not None:
        mapped["agent_shop_product_number"] = data.get("totalGoods")
    mapped["store_json"] = store
    return mapped


def agreement_type_list(selected: Optional[List[int]] = None) -> List[int]:
    if selected:
        return [t for t in selected if t in AGREEMENT_TYPES]
    return sorted(AGREEMENT_TYPES.keys())
