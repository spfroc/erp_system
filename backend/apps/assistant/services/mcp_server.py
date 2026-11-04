"""企业微信等客户端用的 MCP（Streamable HTTP）协议处理。

仅暴露 risk_level=read 且不在排除名单中的工具；鉴权由视图层完成。
"""

from __future__ import annotations

import json
import os
import secrets
from typing import Any

from apps.assistant.permissions import ASSISTANT_USE
from apps.assistant.services.tool_executor import ToolExecutionError, execute_tool
from apps.assistant.services.tool_registry import get_tool, list_tools
from apps.assistant.tools import register_all_tools

PROTOCOL_VERSIONS = (
    "2025-06-18",
    "2025-03-26",
    "2024-11-05",
)
DEFAULT_PROTOCOL_VERSION = "2025-06-18"
SERVER_INFO = {"name": "yzc-erp-assistant", "version": "1.0.0"}

# 管理端导航 / 运维状态对企微查询场景价值低，默认不暴露
DEFAULT_EXCLUDED_TOOLS = frozenset({"navigation.find", "devops.get_status"})

MCP_READ_PERMISSIONS = (
    ASSISTANT_USE,
    "notice.view",
    "product.view",
    "salesOrder.view",
    "purchaseOrder.view",
    "serviceOrder.view",
    "finance.view",
    "project.view",
)


def mcp_enabled() -> bool:
    return (os.getenv("ASSISTANT_MCP_ENABLED") or "false").strip().lower() in {"1", "true", "yes", "on"}


def mcp_token() -> str:
    return (os.getenv("ASSISTANT_MCP_TOKEN") or "").strip()


def mcp_service_user() -> dict[str, Any]:
    """连接器以服务账号身份执行只读工具（直传 permissions，不依赖角色表）。"""
    raw = (os.getenv("ASSISTANT_MCP_PERMISSIONS") or "").strip()
    if raw:
        permissions = [item.strip() for item in raw.split(",") if item.strip()]
    else:
        permissions = list(MCP_READ_PERMISSIONS)
    return {
        "id": (os.getenv("ASSISTANT_MCP_USER_ID") or "wecom-mcp").strip() or "wecom-mcp",
        "username": (os.getenv("ASSISTANT_MCP_USERNAME") or "wecom-mcp").strip() or "wecom-mcp",
        "status": "启用",
        "permissions": permissions,
        "roleIds": [],
    }


def _excluded_tools() -> set[str]:
    raw = (os.getenv("ASSISTANT_MCP_EXCLUDE_TOOLS") or "").strip()
    if not raw:
        return set(DEFAULT_EXCLUDED_TOOLS)
    return {item.strip() for item in raw.split(",") if item.strip()}


def _allowlist() -> set[str] | None:
    raw = (os.getenv("ASSISTANT_MCP_ALLOW_TOOLS") or "").strip()
    if not raw:
        return None
    return {item.strip() for item in raw.split(",") if item.strip()}


def list_mcp_tools() -> list[dict[str, Any]]:
    register_all_tools()
    excluded = _excluded_tools()
    allow = _allowlist()
    tools: list[dict[str, Any]] = []
    for tool in list_tools():
        if tool.risk_level != "read":
            continue
        if tool.requires_confirmation:
            continue
        if tool.name in excluded:
            continue
        if allow is not None and tool.name not in allow:
            continue
        tools.append(
            {
                "name": tool.name,
                "description": tool.description or tool.name,
                "inputSchema": tool.input_schema or {"type": "object", "properties": {}},
            }
        )
    return tools


def _jsonrpc_error(req_id: Any, code: int, message: str) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": req_id, "error": {"code": code, "message": message}}


def _jsonrpc_result(req_id: Any, result: Any) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": req_id, "result": result}


def _tool_result_text(payload: dict[str, Any]) -> str:
    summary = str(payload.get("content") or payload.get("summary") or "").strip()
    data = payload.get("data")
    body: dict[str, Any] = {
        "tool_name": payload.get("tool_name"),
        "status": payload.get("status"),
        "summary": summary,
    }
    if isinstance(data, dict):
        body["data"] = data
    return json.dumps(body, ensure_ascii=False, default=str)


def handle_jsonrpc(message: dict[str, Any], *, user_data: dict[str, Any]) -> tuple[dict[str, Any] | None, int, dict[str, str]]:
    """处理单条 JSON-RPC。

    返回 (response_body_or_None, http_status, extra_headers)。
    notification 成功时 body 为 None、status 202。
    """
    if not isinstance(message, dict) or message.get("jsonrpc") != "2.0":
        return _jsonrpc_error(None, -32600, "Invalid Request"), 400, {}

    method = message.get("method")
    req_id = message.get("id", None)
    params = message.get("params") if isinstance(message.get("params"), dict) else {}
    is_notification = "id" not in message

    if not isinstance(method, str) or not method:
        if is_notification:
            return None, 400, {}
        return _jsonrpc_error(req_id, -32600, "Missing method"), 400, {}

    # notifications
    if method.startswith("notifications/"):
        return None, 202, {}

    if is_notification:
        return None, 202, {}

    if method == "initialize":
        requested = str(params.get("protocolVersion") or DEFAULT_PROTOCOL_VERSION)
        version = requested if requested in PROTOCOL_VERSIONS else DEFAULT_PROTOCOL_VERSION
        session_id = secrets.token_urlsafe(18)
        result = {
            "protocolVersion": version,
            "capabilities": {"tools": {"listChanged": False}},
            "serverInfo": SERVER_INFO,
        }
        return _jsonrpc_result(req_id, result), 200, {"Mcp-Session-Id": session_id}

    if method == "ping":
        return _jsonrpc_result(req_id, {}), 200, {}

    if method == "tools/list":
        return _jsonrpc_result(req_id, {"tools": list_mcp_tools()}), 200, {}

    if method == "tools/call":
        name = str(params.get("name") or "").strip()
        arguments = params.get("arguments") if isinstance(params.get("arguments"), dict) else {}
        if not name:
            return _jsonrpc_error(req_id, -32602, "tools/call missing name"), 400, {}

        tool = get_tool(name)
        allowed_names = {item["name"] for item in list_mcp_tools()}
        if not tool or name not in allowed_names:
            return _jsonrpc_result(
                req_id,
                {
                    "content": [{"type": "text", "text": f"工具不可用或不存在：{name}"}],
                    "isError": True,
                },
            ), 200, {}

        try:
            payload = execute_tool(tool_name=name, params=arguments, user_data=user_data)
            text = _tool_result_text(payload)
            return _jsonrpc_result(
                req_id,
                {"content": [{"type": "text", "text": text}], "isError": False},
            ), 200, {}
        except ToolExecutionError as exc:
            return _jsonrpc_result(
                req_id,
                {
                    "content": [{"type": "text", "text": f"{exc.code}: {exc.message}"}],
                    "isError": True,
                },
            ), 200, {}

    return _jsonrpc_error(req_id, -32601, f"Method not found: {method}"), 404, {}
