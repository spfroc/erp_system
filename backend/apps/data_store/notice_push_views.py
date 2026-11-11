"""微信推送：手动发送 + 后台推送记录。"""

from __future__ import annotations

from django.db.models import Q
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from .models import CustomerAccountRecord
from .notice_digest import send_manual_template_for_account
from .notice_push_models import NoticePushLog
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


def _account_label_map(account_ids: list[str]) -> dict[str, dict[str, str]]:
    ids = [str(item) for item in account_ids if item]
    if not ids:
        return {}
    out: dict[str, dict[str, str]] = {}
    for row in CustomerAccountRecord.objects.filter(id__in=ids, is_deleted=False).only("id", "name", "phone", "data"):
        data = row.data if isinstance(row.data, dict) else {}
        out[row.id] = {
            "accountName": str(data.get("name") or row.name or ""),
            "phone": str(data.get("phone") or row.phone or ""),
            "customerName": str(data.get("customerName") or data.get("companyName") or ""),
        }
    return out


@require_http_methods(["GET"])
def wechat_push_logs(request):
    _user, error = _require_permission(request, "wechatMp.view")
    if error:
        return error

    page = max(int(request.GET.get("page") or 1), 1)
    page_size = min(max(int(request.GET.get("page_size") or 20), 1), 100)
    search = str(request.GET.get("search") or "").strip()
    status = str(request.GET.get("status") or "").strip()
    digest_date = str(request.GET.get("digest_date") or request.GET.get("digestDate") or "").strip()

    qs = NoticePushLog.objects.all().order_by("-digest_date", "-id")
    if status:
        qs = qs.filter(status=status)
    if digest_date:
        qs = qs.filter(digest_date=digest_date)
    if search:
        account_ids = list(
            CustomerAccountRecord.objects.filter(is_deleted=False)
            .filter(
                Q(name__icontains=search)
                | Q(phone__icontains=search)
                | Q(id__icontains=search)
                | Q(data__name__icontains=search)
                | Q(data__phone__icontains=search)
                | Q(data__customerName__icontains=search)
            )
            .values_list("id", flat=True)[:300]
        )
        qs = qs.filter(
            Q(customer_account_id__icontains=search)
            | Q(openid__icontains=search)
            | Q(errmsg__icontains=search)
            | Q(customer_account_id__in=account_ids)
        )

    total = qs.count()
    rows = list(qs[(page - 1) * page_size : page * page_size])
    labels = _account_label_map([row.customer_account_id for row in rows])
    items = []
    for row in rows:
        meta = labels.get(row.customer_account_id) or {}
        notice_ids = row.notice_ids if isinstance(row.notice_ids, list) else []
        items.append(
            {
                "id": row.id,
                "customerAccountId": row.customer_account_id,
                "accountName": meta.get("accountName") or "",
                "customerName": meta.get("customerName") or "",
                "phone": meta.get("phone") or "",
                "channel": row.channel,
                "digestDate": row.digest_date.isoformat() if row.digest_date else "",
                "openid": row.openid or "",
                "noticeIds": notice_ids,
                "matchedCount": len(notice_ids),
                "status": row.status,
                "errcode": row.errcode,
                "errmsg": row.errmsg or "",
                "createdAt": row.created_at.isoformat() if row.created_at else "",
                "updatedAt": row.updated_at.isoformat() if row.updated_at else "",
            }
        )
    return JsonResponse(
        {
            "items": items,
            "total": total,
            "page": page,
            "page_size": page_size,
        }
    )
