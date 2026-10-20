#!/usr/bin/env bash
set -euo pipefail
docker exec -w /app yzc-erp-backend-1 python manage.py shell <<'PY'
from apps.data_store.official_sites import ensure_default_official_sites
from apps.data_store.models import OfficialSiteRecord
ensure_default_official_sites()
for site in OfficialSiteRecord.objects.filter(is_deleted=False).order_by("key"):
    industries = (site.data or {}).get("industries") or []
    contact = (site.data or {}).get("contact") or {}
    print(site.key, "industries=", len(industries), "qr=", contact.get("wechatQrUrl"))
PY
