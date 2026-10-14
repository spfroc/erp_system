from django.test import Client, TestCase

from apps.data_store.official_sites import ensure_default_official_sites, normalize_host


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
