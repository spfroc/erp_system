"""静态工具注册表。模型不可动态创建可执行代码/SQL/HTTP。"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable


RiskLevel = str  # "read" | "write" | "dangerous"


@dataclass(frozen=True)
class ToolDefinition:
    name: str
    description: str
    input_schema: dict[str, Any]
    permission: str
    risk_level: RiskLevel = "read"
    requires_confirmation: bool = False
    handler: Callable[..., dict[str, Any]] | None = field(default=None, compare=False, repr=False)

    def public_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "input_schema": self.input_schema,
            "permission": self.permission,
            "risk_level": self.risk_level,
            "requires_confirmation": self.requires_confirmation,
        }


_REGISTRY: dict[str, ToolDefinition] = {}


def register_tool(definition: ToolDefinition) -> ToolDefinition:
    if not definition.name:
        raise ValueError("tool name required")
    if definition.name in _REGISTRY:
        raise ValueError(f"tool already registered: {definition.name}")
    if definition.handler is None:
        raise ValueError(f"tool handler required: {definition.name}")
    _REGISTRY[definition.name] = definition
    return definition


def get_tool(name: str) -> ToolDefinition | None:
    return _REGISTRY.get(name)


def list_tools(*, permission_filter: Callable[[str], bool] | None = None) -> list[ToolDefinition]:
    tools = list(_REGISTRY.values())
    if permission_filter is None:
        return sorted(tools, key=lambda item: item.name)
    return sorted(
        [tool for tool in tools if permission_filter(tool.permission)],
        key=lambda item: item.name,
    )


def clear_registry_for_tests() -> None:
    _REGISTRY.clear()
