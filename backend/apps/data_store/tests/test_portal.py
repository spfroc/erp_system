from unittest.mock import patch

from django.contrib.auth.hashers import make_password
from django.test import Client, SimpleTestCase, TestCase

from apps.data_store.models import CustomerAccountRecord, NoticeRecord
from apps.data_store.portal import (
    PORTAL_COOKIE,
    _force_index_clause,
    _parsed_force_index_clause,
    _raw_force_index_clause,
)
from apps.data_store.portal_enterprise import portal_format_datetime


class PortalDatetimeFormatTests(SimpleTestCase):
    def test_utc_iso_converts_to_shanghai_wall_clock(self):
        self.assertEqual(portal_format_datetime("2026-09-09T05:35:00.000Z"), "2026-09-09 13:35")
        self.assertEqual(
            portal_format_datetime("2026-09-09T05:35:00.000Z", seconds=True),
            "2026-09-09 13:35:00",
        )

    def test_naive_wall_clock_kept_as_shanghai(self):
        self.assertEqual(portal_format_datetime("2026-09-09 13:35:00"), "2026-09-09 13:35")
        self.assertEqual(portal_format_datetime("2026-09-09"), "2026-09-09")


class PortalStatsForceIndexTests(SimpleTestCase):
    def test_force_index_clause_skips_missing_indexes(self):
        with patch("apps.data_store.portal._mysql_index_exists", return_value=False):
            self.assertEqual(_force_index_clause("notice_raw", "idx_raw_site_publish"), "")
            self.assertEqual(_raw_force_index_clause(None), "")
            self.assertEqual(_parsed_force_index_clause(["sd-ggzyjyzx"]), "")

    def test_force_index_clause_uses_first_existing(self):
        def exists(table, name):
            return name == "idx_raw_publish_id"

        with patch("apps.data_store.portal._mysql_index_exists", side_effect=exists):
            self.assertEqual(
                _raw_force_index_clause(["sd-ggzyjyzx"]),
                " FORCE INDEX (idx_raw_publish_id)",
            )


class PortalAccountTests(TestCase):
    def setUp(self):
        CustomerAccountRecord.objects.create(
            id="portal-user-demo",
            name="演示客户",
            phone="13900001111",
            customer_name="演示客户",
            status="启用",
            data={
                "id": "portal-user-demo",
                "name": "演示客户",
                "phone": "13900001111",
                "password": make_password("Portal123456"),
                "customerName": "演示客户",
                "status": "启用",
                "permissions": ["portal.notice.view", "portal.stats.view"],
                "subscription": {"enabled": False, "keywords": ""},
            },
        )
        NoticeRecord.objects.create(
            id="notice-portal-1",
            title="门户可见公告",
            notice_kind="采购公告",
            is_public=True,
            data={"id": "notice-portal-1", "title": "门户可见公告", "isPublic": True},
        )

    def test_public_crawled_notices_is_anonymous_and_capped(self):
        client = Client()
        response = client.get("/api/public/crawled-notices/", {"page": 1, "page_size": 50})
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertIn("items", body)
        self.assertLessEqual(body.get("page_size") or 0, 10)
        self.assertLessEqual(len(body.get("items") or []), 10)

    def test_login_cookie_can_read_notices_and_blocks_subscription(self):
        client = Client()
        denied = client.get("/api/portal/notices/")
        self.assertEqual(denied.status_code, 401)
        login = client.post("/api/portal/login/", data={"phone": "13900001111", "password": "Portal123456"}, content_type="application/json")
        self.assertEqual(login.status_code, 200)
        self.assertNotIn("password", login.json()["data"])
        self.assertIn(PORTAL_COOKIE, login.cookies)
        notices = client.get("/api/portal/notices/")
        self.assertEqual(notices.status_code, 200)
        self.assertIn("items", notices.json())
        self.assertIn("sites", notices.json())
        stats = client.get("/api/portal/stats/")
        self.assertEqual(stats.status_code, 200)
        payload = stats.json()["data"]
        self.assertIn("publicNoticeTotal", payload)
        self.assertIn("lastMonthPurchaseAmount", payload)
        self.assertIn("lastMonthDealAmount", payload)
        self.assertNotIn("latestPublishTime", payload)
        self.assertIn("bySite", payload)
        self.assertIn("byKind", payload)
        self.assertEqual(len(payload["daily"]), 14)
        self.assertEqual(len(payload["monthlyDeal"]), 6)
        self.assertEqual(payload["customerName"], "演示客户")
        subscription = client.put("/api/portal/subscription/", data={"enabled": True, "keywords": "济南"}, content_type="application/json")
        self.assertEqual(subscription.status_code, 403)

    def test_staff_session_is_not_a_portal_login(self):
        client = Client()
        session = client.session
        session["user_id"] = "user-initial-admin"
        session.save()
        response = client.get("/api/portal/me/")
        self.assertEqual(response.status_code, 401)
