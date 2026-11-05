"""Backfill qiluAccountType for migrated 齐鲁云采 accounts + ensure option group."""
import json
from apps.data_store.models import OptionGroupRecord, PlatformAccountRecord
from apps.data_store.views import _record_defaults

OPTION_KEY = "qilu_account_type"
OPTION_ITEMS = [
    {"id": f"opt-{OPTION_KEY}-{index}", "value": value, "label": value, "enabled": True, "sortOrder": index}
    for index, value in enumerate(["电商/代理商", "定点"], start=1)
]
OPTION_PAYLOAD = {
    "id": "opt-qilu-account-type",
    "key": OPTION_KEY,
    "name": "齐鲁云采账号类型",
    "description": "齐鲁云采平台账号细分：电商/代理商与定点可并存。",
    "usages": ["平台账号：齐鲁云采类型筛选/新增"],
    "items": OPTION_ITEMS,
}

existing_opt = OptionGroupRecord.objects.filter(key=OPTION_KEY, is_deleted=False).first()
if existing_opt:
    data = dict(existing_opt.data or {})
    data.update(OPTION_PAYLOAD)
    data["id"] = existing_opt.id
    existing_opt.data = data
    existing_opt.name = OPTION_PAYLOAD["name"]
    existing_opt.save(update_fields=["data", "name", "updated_at"])
    print("option updated", existing_opt.id)
else:
    defaults = _record_defaults(OptionGroupRecord, OPTION_PAYLOAD)
    OptionGroupRecord.objects.create(id=OPTION_PAYLOAD["id"], **defaults)
    print("option created", OPTION_PAYLOAD["id"])

stats = {"designated": 0, "emall": 0, "already": 0, "other_qilu": 0, "skipped_non_qilu": 0}
for rec in PlatformAccountRecord.objects.filter(is_deleted=False):
    data = dict(rec.data or {})
    platform = (rec.platform or data.get("platform") or "").strip()
    if platform != "齐鲁云采":
        stats["skipped_non_qilu"] += 1
        continue
    current = (data.get("qiluAccountType") or "").strip()
    if current in {"电商/代理商", "定点"}:
        stats["already"] += 1
        continue
    note = str(data.get("note") or "")
    if "旧designated#" in note:
        data["qiluAccountType"] = "定点"
        stats["designated"] += 1
    elif "旧companies#" in note or "mall#" in note:
        data["qiluAccountType"] = "电商/代理商"
        stats["emall"] += 1
    else:
        data["qiluAccountType"] = "电商/代理商"
        stats["other_qilu"] += 1
    rec.data = data
    rec.save(update_fields=["data", "updated_at"])

print(json.dumps(stats, ensure_ascii=False, indent=2))
print(
    "qilu counts",
    PlatformAccountRecord.objects.filter(is_deleted=False, platform="齐鲁云采", data__qiluAccountType="电商/代理商").count(),
    PlatformAccountRecord.objects.filter(is_deleted=False, platform="齐鲁云采", data__qiluAccountType="定点").count(),
)
