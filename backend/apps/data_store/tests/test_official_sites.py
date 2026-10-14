from django.test import Client, TestCase

from apps.data_store.official_sites import apply_official_seo_defaults, ensure_default_official_sites, normalize_host


class OfficialSiteTests(TestCase):
    def test_normalize_host(self):
        self.assertEqual(normalize_host("https://www.qlyc.co/path"), "www.qlyc.co")
        self.assertEqual(normalize_host("qlyc.co:443"), "www.qlyc.co")

    def test_public_resolve_qlyc_home(self):
        ensure_default_official_sites()
        client = Client()
        response = client.get("/api/public/official-site/", {"host": "www.qlyc.co"})
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["data"]["site"]["key"], "qlyc")
        self.assertEqual(body["data"]["page"]["slug"], "home")
        self.assertEqual(body["data"]["page"]["status"], "published")
        self.assertTrue(any(block["type"] == "hero" for block in body["data"]["page"]["blocks"]))

    def test_draft_home_not_public(self):
        ensure_default_official_sites()
        client = Client()
        response = client.get("/api/public/official-site/", {"host": "www.qinghuicai.cn"})
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["data"]["site"]["key"], "qinghuicai")
        self.assertIsNone(body["data"]["page"])

    def test_public_official_seo(self):
        ensure_default_official_sites()
        client = Client()
        response = client.get("/api/public/official-seo/", {"host": "www.qlyc.co"})
        self.assertEqual(response.status_code, 200)
        body = response.json()["data"]
        self.assertEqual(body["key"], "qlyc")
        self.assertIn("壹采", body["seoTitle"])
        self.assertIn("Sitemap:", body["robotsTxt"])
        self.assertTrue(body["sitemapUrls"])

    def test_import_official_seo_requires_permission(self):
        ensure_default_official_sites()
        client = Client()
        response = client.post("/api/official-seo/import/", data="{}", content_type="application/json")
        self.assertEqual(response.status_code, 401)

    def test_apply_official_seo_defaults_fills_empty(self):
        ensure_default_official_sites()
        from apps.data_store.models import OfficialSiteRecord

        site = OfficialSiteRecord.objects.get(id="site-qlyc")
        data = dict(site.data or {})
        data["seoKeywords"] = ""
        data["robotsTxt"] = ""
        site.data = data
        site.save(update_fields=["data"])
        updated = apply_official_seo_defaults(overwrite=False)
        self.assertTrue(any(item["key"] == "qlyc" for item in updated))
        site.refresh_from_db()
        self.assertTrue(site.data.get("seoKeywords"))
        self.assertIn("Sitemap:", site.data.get("robotsTxt") or "")
