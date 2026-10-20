import os
import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()

from apps.data_store.models import OfficialSiteRecord
from apps.data_store.official_sites import ensure_default_official_sites

ensure_default_official_sites()
for site in OfficialSiteRecord.objects.filter(is_deleted=False).order_by("key"):
    industries = (site.data or {}).get("industries") or []
    contact = (site.data or {}).get("contact") or {}
    print(
        site.key,
        "industries=",
        len(industries),
        "qr=",
        contact.get("wechatQrUrl"),
    )
