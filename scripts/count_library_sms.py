import django
import os

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()

from apps.data_store.models import LibraryContactRecord, SmsRecordRecord, SmsTemplateRecord

print("contacts", LibraryContactRecord.objects.filter(is_deleted=False).count())
print("sms", SmsRecordRecord.objects.filter(is_deleted=False).count())
print("templates", SmsTemplateRecord.objects.filter(is_deleted=False).count())
print("legacy_contacts", LibraryContactRecord.objects.filter(id__startswith="lib-legacy-").count())
print("legacy_sms", SmsRecordRecord.objects.filter(id__startswith="sms-legacy-").count())
