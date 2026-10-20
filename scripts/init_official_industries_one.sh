#!/usr/bin/env bash
set -euo pipefail
cd /home/spf/projects/erp_system/deploy
docker compose -f docker-compose.one.yml -p yzc-erp up -d --force-recreate --no-deps backend frontend

echo "==== wait backend ===="
for i in $(seq 1 40); do
  if curl -fsS http://127.0.0.1:8000/api/health/ >/dev/null 2>&1; then
    echo "backend healthy"
    break
  fi
  sleep 1
done

docker exec yzc-erp-backend-1 python - <<'PY'
import os, django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()
from apps.data_store.official_sites import ensure_default_official_sites
from apps.data_store.models import OfficialSiteRecord
ensure_default_official_sites()
for site in OfficialSiteRecord.objects.filter(is_deleted=False).order_by("key"):
    industries = (site.data or {}).get("industries") or []
    contact = (site.data or {}).get("contact") or {}
    print(site.key, "industries=", len(industries), "wechatQrUrl=", contact.get("wechatQrUrl"))
PY
