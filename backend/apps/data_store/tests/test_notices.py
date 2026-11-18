from django.test import Client, TestCase

from apps.data_store.models import NoticeCollectionSourceRecord, NoticeRecord, WebsiteLeadRecord
from apps.data_store.notices import (
    ensure_default_sample_source,
    mask_public_notice_sensitive,
    run_collection_source,
    upsert_notice,
)


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

    def test_public_notices_only_returns_public_items(self):
        public, _ = upsert_notice({
            "id": "notice-public-1",
            "title": "公开竞价项目A",
            "noticeKind": "竞价项目",
            "isPublic": True,
            "projectNumber": "PUB-001",
        })
        upsert_notice({
            "id": "notice-private-1",
            "title": "内部公告B",
            "noticeKind": "采购公告",
            "isPublic": False,
        })
        client = Client()
        response = client.get("/api/public/notices/", {"page": 1, "page_size": 20})
        self.assertEqual(response.status_code, 200)
        body = response.json()
        ids = {item["id"] for item in body["items"]}
        self.assertIn(public.id, ids)
        self.assertNotIn("notice-private-1", ids)

        detail = client.get(f"/api/public/notices/{public.id}/")
        self.assertEqual(detail.status_code, 200)
        self.assertEqual(detail.json()["data"]["title"], "公开竞价项目A")

        hidden = client.get("/api/public/notices/notice-private-1/")
        self.assertEqual(hidden.status_code, 404)

    def test_public_notices_sitemap_is_lightweight(self):
        public, _ = upsert_notice({
            "id": "notice-sitemap-1",
            "title": "Sitemap 公开公告",
            "noticeKind": "竞价项目",
            "isPublic": True,
            "projectNumber": "SM-001",
            "publishedAt": "2026-11-18T10:00:00+08:00",
        })
        upsert_notice({
            "id": "notice-sitemap-private",
            "title": "Sitemap 内部公告",
            "noticeKind": "采购公告",
            "isPublic": False,
        })
        client = Client()
        response = client.get("/api/public/notices/sitemap/", {"limit": 100})
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertIn("items", body)
        ids = {item["id"] for item in body["items"]}
        self.assertIn(public.id, ids)
        self.assertNotIn("notice-sitemap-private", ids)
        sample = next(item for item in body["items"] if item["id"] == public.id)
        self.assertEqual(set(sample.keys()), {"id", "publishedAt"})
        self.assertTrue(str(sample.get("publishedAt") or "").startswith("2026-11-18"))

    def test_mask_public_notice_sensitive_truncates_and_locks_attachments(self):
        lines = [f"<p>正文第{i}行内容足够长</p>" for i in range(1, 21)]
        item = {
            "title": "测试公告",
            "contactName": "张三",
            "contactPhone": "13800138000",
            "contentHtml": "".join(lines)
            + '<p><a href="https://example.com/a.pdf">附件下载</a></p>',
            "attachments": [{"name": "a.pdf", "url": "https://example.com/a.pdf"}],
        }
        masked = mask_public_notice_sensitive(item)
        self.assertTrue(masked.get("contentPreviewOnly"))
        self.assertTrue(masked.get("attachmentsLocked"))
        self.assertEqual(masked.get("attachments"), [])
        self.assertEqual(masked.get("contactName"), "登录可见")
        self.assertNotIn("https://example.com/a.pdf", masked.get("contentHtml") or "")
        self.assertIn("登录后可下载附件", masked.get("contentHtml") or "")
        self.assertLessEqual((masked.get("contentHtml") or "").count("</p>"), 12)
