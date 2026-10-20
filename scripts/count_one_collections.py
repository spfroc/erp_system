import os
import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()

from apps.data_store import models as m

pairs = [
    ("libraryContacts", m.LibraryContactRecord),
    ("smsRecords", m.SmsRecordRecord),
    ("smsTemplates", m.SmsTemplateRecord),
    ("notices", m.NoticeRecord),
    ("officialSites", m.OfficialSiteRecord),
    ("platformAccounts", m.PlatformAccountRecord),
    ("projects", m.ProjectRecord),
    ("salesOrders", m.SalesOrderRecord),
    ("organizations", m.OrganizationRecord),
    ("websiteLeads", m.WebsiteLeadRecord),
]
for name, model in pairs:
    print(f"{name}: {model.objects.filter(is_deleted=False).count()}")
