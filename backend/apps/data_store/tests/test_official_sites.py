from django.test import Client, TestCase

from apps.data_store.models import OfficialSiteRecord
from apps.data_store.official_sites import (
    apply_official_seo_defaults,
    bare_host,
    ensure_default_official_sites,
    find_official_site_by_host,
    normalize_host,
    public_home_config,
)


class OfficialSiteTests(TestCase):
    def test_normalize_host(self):
        self.assertEqual(normalize_host("https://www.qlyc.co/path"), "www.qlyc.co")
        self.assertEqual(normalize_host("qlyc.co:443"), "www.qlyc.co")
        self.assertEqual(bare_host("www.yizhichan.co"), "yizhichan.co")

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
        home = body["data"]["homeConfig"]
        self.assertEqual(home["contact"]["hotline"], "0531-86099058")
        self.assertTrue(home["industries"])
        self.assertTrue(home["inquiryPlatforms"])
        self.assertTrue(home["footer"]["platforms"])
        self.assertIn("yizhichan.co", " ".join(home["domains"]))

    def test_yizhichan_host_resolves_to_qlyc_shared_config(self):
        ensure_default_official_sites()
        site = find_official_site_by_host("www.yizhichan.co")
        self.assertIsNotNone(site)
        self.assertEqual(site.key, "qlyc")
        self.assertFalse(OfficialSiteRecord.objects.filter(id="site-yizhichan", is_deleted=False).exists())
        client = Client()
        response = client.get("/api/public/official-site/", {"host": "yizhichan.co"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["data"]["site"]["key"], "qlyc")
        self.assertEqual(response.json()["data"]["homeConfig"]["key"], "qlyc")

    def test_qinghuicai_home_config(self):
        ensure_default_official_sites()
        client = Client()
        response = client.get("/api/public/official-site/", {"host": "www.qinghuicai.cn"})
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["data"]["site"]["key"], "qinghuicai")
        self.assertIsNotNone(body["data"]["page"])
        home = body["data"]["homeConfig"]
        self.assertEqual(home["inquiryPlatforms"][0]["value"], "青慧采")
        self.assertTrue(home["footer"]["keywords"])
        self.assertIn("37010302001037", home["beian"]["policeText"])
        self.assertEqual(public_home_config(body["data"]["site"])["footer"]["platforms"][0]["name"], "青岛政企阳光采购平台")

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
