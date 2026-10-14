#!/usr/bin/env bash
set -euo pipefail
SRC=/home/spf/projects/erp_system/imports/library_sms
DST=/home/spf/projects/erp_system/backend/imports/library_sms
rm -f /home/spf/projects/erp_system/backend/imports 2>/dev/null || true
rm -rf /home/spf/projects/erp_system/backend/imports
mkdir -p "$DST"
for f in customers.ndjson short_messages.ndjson admin_note_templates.ndjson failed_short_message_mobiles.ndjson manifest.json; do
  if ! ln -f "$SRC/$f" "$DST/$f" 2>/dev/null; then
    cp -a "$SRC/$f" "$DST/$f"
  fi
done
ls -lh "$DST"
docker exec yzc-erp-backend-1 ls -lh /app/imports/library_sms/
