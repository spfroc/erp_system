"""注册全部助手工具。"""

from __future__ import annotations

_REGISTERED = False


def register_all_tools() -> None:
    global _REGISTERED
    if _REGISTERED:
        return
    from . import (  # noqa: F401,WPS433
        buyer_tools,
        devops_tools,
        erp_tools,
        navigation_tools,
        notice_tools,
        platform_account_tools,
    )

    notice_tools.register()
    buyer_tools.register()
    erp_tools.register()
    platform_account_tools.register()
    navigation_tools.register()
    devops_tools.register()
    _REGISTERED = True


def reset_registration_for_tests() -> None:
    global _REGISTERED
    from apps.assistant.services.tool_registry import clear_registry_for_tests

    clear_registry_for_tests()
    _REGISTERED = False
    register_all_tools()
