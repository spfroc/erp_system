from __future__ import annotations

from typing import List, Optional

from tqdm import tqdm

from clients.qlyc_login import ensure_access_token
from clients.sd_supplier import (
    AGREEMENT_TYPES,
    SdSupplierClient,
    agreement_type_list,
    enrich_from_store,
    map_list_item,
)
from db import exists_mall_customer, get_session, upsert_mall_customer


class _DupStop:
    def __init__(self, limit: Optional[int]) -> None:
        self.limit = limit if limit and limit > 0 else None
        self.streak = 0

    def hit(self, duplicated: bool) -> bool:
        if not self.limit:
            return False
        if duplicated:
            self.streak += 1
            return self.streak >= self.limit
        self.streak = 0
        return False


def crawl_suppliers(
    *,
    agreement_types: Optional[List[int]] = None,
    max_pages: Optional[int] = None,
    page_size: int = 50,
    with_store: bool = False,
    stop_dup: Optional[int] = None,
) -> int:
    """抓取供应商到 mall_customer，返回 upsert 条数。"""
    token = ensure_access_token()
    tqdm.write("齐鲁云采 access_token 已就绪")
    client = SdSupplierClient()
    session = get_session()
    saved = 0
    try:
        for agreement_type in agreement_type_list(agreement_types):
            label = AGREEMENT_TYPES[agreement_type]
            page = 1
            total_pages = None
            dup = _DupStop(stop_dup)
            stop_category = False
            pbar = tqdm(desc=f"mall_customer/{label}", unit="page")
            while True:
                if max_pages and page > max_pages:
                    break
                data = client.list_by_agreement(
                    agreement_type=agreement_type,
                    page_num=page,
                    page_size=page_size,
                    access_token=token,
                )
                items = data.get("data") or []
                total = int(data.get("total") or 0)
                if total_pages is None:
                    total_pages = int(data.get("totalPage") or 0) or max(
                        1, (total + page_size - 1) // page_size if total else 1
                    )
                    pbar.total = min(total_pages, max_pages or total_pages)

                for item in items:
                    if not isinstance(item, dict):
                        continue
                    mapped = map_list_item(item, agreement_type)
                    pid = mapped.get("platform_customer_id") or ""
                    if not mapped.get("name"):
                        continue
                    if dup.hit(exists_mall_customer(session, pid)):
                        stop_category = True
                        tqdm.write(f"{label} 连续重复 {dup.limit} 条，停止该类型")
                        break
                    if dup.streak:
                        continue
                    if with_store and pid:
                        try:
                            store = client.get_store(pid, access_token=token)
                            mapped = enrich_from_store(mapped, store)
                        except Exception as exc:  # noqa: BLE001
                            tqdm.write(f"店铺详情失败 {mapped['name']}: {exc}")
                    upsert_mall_customer(session, mapped)
                    saved += 1

                session.commit()
                pbar.update(1)
                if stop_category or page >= (total_pages or 1) or not items:
                    break
                page += 1
            pbar.close()
    finally:
        session.close()
    return saved
