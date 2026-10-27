"""公告类型 / 性质字典：读写 DB，缺表或空表时回退内置默认。"""

from __future__ import annotations

from django.db import DatabaseError

from .notice_tag_models import NoticeDictItem

KIND_ORG_TYPE = NoticeDictItem.KIND_ORG_TYPE
KIND_NATURE = NoticeDictItem.KIND_NATURE

DEFAULT_ORG_TYPES = (
    "幼儿园",
    "小学",
    "中学",
    "大专",
    "大学",
    "教育",
    "医疗卫生",
    "公安系统",
    "司法",
    "财税",
    "公共资源",
    "文化",
    "科研",
    "交通",
    "住建",
    "农业",
    "民政",
    "应急",
    "群团",
    "机关",
    "其他",
)
DEFAULT_NATURES = ("政府", "事业单位", "国企", "央企", "其他")


def _defaults(kind: str) -> tuple[str, ...]:
    if kind == KIND_NATURE:
        return DEFAULT_NATURES
    return DEFAULT_ORG_TYPES


def ensure_notice_dict_defaults() -> None:
    """首次空表时写入默认项，不覆盖已有人工维护。"""
    try:
        for kind, names in ((KIND_ORG_TYPE, DEFAULT_ORG_TYPES), (KIND_NATURE, DEFAULT_NATURES)):
            if NoticeDictItem.objects.filter(kind=kind).exists():
                continue
            NoticeDictItem.objects.bulk_create(
                [
                    NoticeDictItem(kind=kind, name=name, sort_order=index * 10, enabled=True)
                    for index, name in enumerate(names)
                ]
            )
    except Exception:
        return


def list_dict_names(kind: str, *, enabled_only: bool = True) -> tuple[str, ...]:
    try:
        ensure_notice_dict_defaults()
        qs = NoticeDictItem.objects.filter(kind=kind)
        if enabled_only:
            qs = qs.filter(enabled=True)
        names = list(qs.order_by("sort_order", "id").values_list("name", flat=True))
        if names:
            return tuple(names)
    except Exception:
        # 表未建、SimpleTestCase 禁库等，一律回退内置默认
        pass
    return _defaults(kind)


def serialize_dict_item(item: NoticeDictItem) -> dict:
    return {
        "id": item.id,
        "kind": item.kind,
        "name": item.name,
        "sortOrder": item.sort_order,
        "enabled": item.enabled,
        "updatedAt": item.updated_at.isoformat() if item.updated_at else "",
    }
