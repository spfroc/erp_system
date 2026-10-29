"""助手权限常量与校验辅助。具体工具仍二次校验业务权限。"""

from __future__ import annotations

ASSISTANT_VIEW = "assistant.view"
ASSISTANT_USE = "assistant.use"
ASSISTANT_MANAGE = "assistant.manage"

ASSISTANT_PERMISSIONS = (
    ASSISTANT_VIEW,
    ASSISTANT_USE,
    ASSISTANT_MANAGE,
)

# manage 蕴含 use/view；use 蕴含 view
ASSISTANT_PERMISSION_IMPLIES = {
    ASSISTANT_MANAGE: (ASSISTANT_USE, ASSISTANT_VIEW),
    ASSISTANT_USE: (ASSISTANT_VIEW,),
}


def expand_assistant_permissions(permissions: list[str] | set[str]) -> set[str]:
    result = set(permissions or [])
    if ASSISTANT_MANAGE in result:
        result.update(ASSISTANT_PERMISSION_IMPLIES[ASSISTANT_MANAGE])
    if ASSISTANT_USE in result:
        result.update(ASSISTANT_PERMISSION_IMPLIES[ASSISTANT_USE])
    return result


def user_has_permission(user_data: dict | None, permission: str) -> bool:
    """优先走 ERP 角色权限；测试/直传 permissions 列表时作兼容回退。"""
    if not user_data:
        return False
    try:
        from apps.data_store.views import PERMISSION_ALIASES, _has_permission

        if user_data.get("status") == "启用" and user_data.get("roleIds"):
            if _has_permission(user_data, permission):
                return True
        # 直传 permissions（单测或临时上下文）
        direct = expand_assistant_permissions(set(user_data.get("permissions") or []))
        accepted = PERMISSION_ALIASES.get(permission, (permission,))
        if set(accepted) & direct:
            return True
        # 助手别名
        if permission == ASSISTANT_VIEW and (ASSISTANT_USE in direct or ASSISTANT_MANAGE in direct):
            return True
        if permission == ASSISTANT_USE and ASSISTANT_MANAGE in direct:
            return True
        return False
    except Exception:  # noqa: BLE001
        perms = expand_assistant_permissions(set(user_data.get("permissions") or []))
        if permission in perms:
            return True
        if permission == ASSISTANT_VIEW and (ASSISTANT_USE in perms or ASSISTANT_MANAGE in perms):
            return True
        if permission == ASSISTANT_USE and ASSISTANT_MANAGE in perms:
            return True
        return False
