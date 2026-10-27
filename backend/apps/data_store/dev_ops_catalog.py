"""可执行脚本白名单。页面不可任意填 shell。"""

from __future__ import annotations

from typing import Any

SCRIPT_CATALOG: dict[str, dict[str, Any]] = {
    "tag_notice_results": {
        "label": "结果公告规则打标",
        "kind": "django",
        "queue": "default",
        "command": "tag_notice_results",
        "argSchema": [
            {"key": "limit", "label": "条数上限", "type": "int", "default": 200},
            {"key": "rebuild", "label": "重算未锁定", "type": "bool", "default": False},
        ],
        "timeout": 1800,
    },
    "repair_transaction_projects": {
        "label": "修复交易项目关联",
        "kind": "django",
        "queue": "default",
        "command": "repair_transaction_projects",
        "argSchema": [],
        "timeout": 600,
    },
    "import_library_sms": {
        "label": "导入资料库短信",
        "kind": "django",
        "queue": "default",
        "command": "import_library_sms",
        "argSchema": [],
        "timeout": 1800,
    },
    "notice_crawl_once": {
        "label": "公告采集一轮",
        "kind": "crawler",
        "queue": "crawler",
        "cli": ["crawl"],
        "argSchema": [
            {"key": "lookback_days", "label": "回溯天数", "type": "int", "default": 2},
            {"key": "page_size", "label": "每页条数", "type": "int", "default": 20},
            {"key": "max_pages", "label": "每类最多页数(空=不限)", "type": "int", "default": None, "optional": True},
            {"key": "stop_dup", "label": "连续已入库条数后停止", "type": "int", "default": 5},
            {"key": "list_only", "label": "只抓列表", "type": "bool", "default": False},
            {"key": "site", "label": "站点 all/sd-mall/jd", "type": "str", "default": "all"},
        ],
        "timeout": 7200,
    },
    # 独立全量采集：不设日期窗口、默认不因连续重复提前停止；与 notice_crawl_once 互不影响。
    "notice_crawl_all": {
        "label": "公告全量采集",
        "kind": "crawler",
        "queue": "crawler",
        "cli": ["crawl"],
        "argSchema": [
            {"key": "page_size", "label": "每页条数", "type": "int", "default": 20},
            {"key": "max_pages", "label": "每类最多页数(空=不限)", "type": "int", "default": None, "optional": True},
            {"key": "stop_dup", "label": "连续已入库条数后停止(空=不提前停)", "type": "int", "default": None, "optional": True},
            {"key": "list_only", "label": "只抓列表", "type": "bool", "default": False},
            {"key": "site", "label": "站点 all/sd-mall/jd", "type": "str", "default": "all"},
        ],
        "timeout": 86400,
    },
    "notice_migrate_list_indexes": {
        "label": "采集表列表索引迁移",
        "kind": "crawler",
        "queue": "crawler",
        "cli": ["migrate-list-indexes"],
        "argSchema": [],
        "timeout": 600,
    },
}


def list_scripts() -> list[dict[str, Any]]:
    return [
        {
            "key": key,
            "label": item["label"],
            "kind": item["kind"],
            "queue": item["queue"],
            "argSchema": item.get("argSchema") or [],
        }
        for key, item in SCRIPT_CATALOG.items()
    ]


def get_script(script_key: str) -> dict[str, Any] | None:
    item = SCRIPT_CATALOG.get(script_key)
    if not item:
        return None
    return {"key": script_key, **item}
