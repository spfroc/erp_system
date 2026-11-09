"""开发侧：登录账号手动发送模板消息。"""

from __future__ import annotations

from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from .notice_digest import send_manual_template_for_account
from .views import _read_body, _require_permission


REASON_MESSAGES = {
    "not_found": "账号不存在",
    "disabled": "账号已停用",
    "wechat_unbound": "尚未绑定微信",
    "wechat_unsubscribed": "已取关服务号，无法推送",
    "wechat_not_configured": "微信服务号尚未配置",
    "invalid_fields": "请完整填写竞标项目、时间、发起人、项目编码",
}


@csrf_exempt
@require_http_methods(["POST"])
def customer_account_manual_notice_push(request, account_id: str):
    _user, error = _require_permission(request, "dev.ops.manage")
    if error:
        return error

    payload, body_error = _read_body(request)
    if body_error:
        return body_error
    payload = payload if isinstance(payload, dict) else {}

    outcome = send_manual_template_for_account(
        account_id=str(account_id or "").strip(),
        project=str(payload.get("project") or payload.get("thing1") or "").strip(),
        bid_time=str(payload.get("bidTime") or payload.get("time2") or "").strip(),
        initiator=str(payload.get("initiator") or payload.get("thing3") or "").strip(),
        project_code=str(payload.get("projectCode") or payload.get("character_string5") or "").strip(),
        jump_url=str(payload.get("url") or "").strip(),
    )
    status = str(outcome.get("status") or "")
    reason = str(outcome.get("reason") or "")
    if status != "sent":
        detail = REASON_MESSAGES.get(reason) or str(outcome.get("errmsg") or "推送失败")
        return JsonResponse({"detail": detail, "data": outcome}, status=400)

    return JsonResponse({"data": outcome, "message": "推送成功", "ok": True})
