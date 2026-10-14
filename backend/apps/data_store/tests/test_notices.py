from django.test import TestCase

from apps.data_store.models import NoticeCollectionSourceRecord, NoticeRecord, WebsiteLeadRecord
from apps.data_store.notices import ensure_default_sample_source, run_collection_source


class NoticeCollectionTests(TestCase):
    def test_sample_collection_creates_public_notices_and_leads(self):
        source = ensure_default_sample_source()
        run = run_collection_source(source)
        self.assertEqual(run.status, "成功")
        self.assertGreaterEqual(run.created_count, 2)
        self.assertGreaterEqual(NoticeRecord.objects.filter(is_deleted=False).count(), 2)
        self.assertTrue(NoticeRecord.objects.filter(is_deleted=False, is_public=True).exists())
        self.assertGreaterEqual(WebsiteLeadRecord.objects.filter(is_deleted=False, data__source="公告采集").count(), 1)
        self.assertEqual(NoticeCollectionSourceRecord.objects.get(id=source.id).last_status, "成功")

    def test_sample_collection_is_idempotent_by_external_id(self):
        source = ensure_default_sample_source()
        first = run_collection_source(source)
        second = run_collection_source(source)
        self.assertEqual(first.created_count, second.created_count + second.updated_count)
        self.assertEqual(second.created_count, 0)
        self.assertEqual(second.updated_count, first.created_count)
