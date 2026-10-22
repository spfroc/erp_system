from django.contrib.auth.hashers import make_password
from django.test import Client, TestCase

from apps.data_store.models import CustomerAccountRecord, NoticeRecord
from apps.data_store.portal import PORTAL_COOKIE


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
