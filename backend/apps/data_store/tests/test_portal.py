from unittest.mock import patch

from django.contrib.auth.hashers import make_password
from django.core import signing
from django.test import Client, SimpleTestCase, TestCase, override_settings

from apps.data_store.models import CustomerAccountRecord, NoticeRecord
from apps.data_store.portal import (
    PORTAL_COOKIE,
    PORTAL_WECHAT_LOGIN_SALT,
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
        self.assertLessEqual(body.get("page_size") or 0, 50)
        self.assertLessEqual(len(body.get("items") or []), 50)

    def test_login_cookie_shares_parent_domain_for_official_sites(self):
        client = Client()
        login = client.post(
            "/api/portal/login/",
            data={"phone": "13900001111", "password": "Portal123456"},
            content_type="application/json",
            HTTP_X_FORWARDED_HOST="portal.qlyc.co",
            HTTP_X_FORWARDED_PROTO="https",
        )
        self.assertEqual(login.status_code, 200)
        cookie = login.cookies.get(PORTAL_COOKIE)
        self.assertIsNotNone(cookie)
        self.assertEqual(cookie.get("domain"), ".qlyc.co")

    def test_handoff_can_issue_qinghuicai_cookie(self):
        origin = Client()
        login = origin.post(
            "/api/portal/login/",
            data={"phone": "13900001111", "password": "Portal123456"},
            content_type="application/json",
            HTTP_X_FORWARDED_HOST="portal.qlyc.co",
            HTTP_X_FORWARDED_PROTO="https",
        )
        self.assertEqual(login.status_code, 200)
        create = origin.post(
            "/api/portal/handoff/create/",
            data="{}",
            content_type="application/json",
            HTTP_X_FORWARDED_HOST="portal.qlyc.co",
            HTTP_X_FORWARDED_PROTO="https",
        )
        self.assertEqual(create.status_code, 200)
        code = create.json().get("code")
        self.assertTrue(code)

        target = Client()
        claim = target.post(
            "/api/portal/handoff/claim/",
            data={"code": code},
            content_type="application/json",
            HTTP_X_FORWARDED_HOST="preview.qinghuicai.cn",
            HTTP_X_FORWARDED_PROTO="https",
        )
        self.assertEqual(claim.status_code, 200)
        cookie = claim.cookies.get(PORTAL_COOKIE)
        self.assertIsNotNone(cookie)
        self.assertEqual(cookie.get("domain"), ".qinghuicai.cn")
        me = target.get(
            "/api/portal/me/",
            HTTP_X_FORWARDED_HOST="preview.qinghuicai.cn",
            HTTP_X_FORWARDED_PROTO="https",
        )
        self.assertEqual(me.status_code, 200)

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


@override_settings(
    WECHAT_MP_APP_ID="wx-test-app",
    WECHAT_MP_APP_SECRET="wx-test-secret",
    WECHAT_MP_OAUTH_REDIRECT_URI="https://example.com/api/wechat/mp/oauth/callback/",
    WECHAT_MP_PORTAL_NOTICE_URL="https://example.com/portal/",
)
class PortalWechatSilentLoginTests(TestCase):
    def setUp(self):
        CustomerAccountRecord.objects.create(
            id="portal-user-wx",
            name="微信客户",
            phone="13900002222",
            customer_name="微信客户",
            status="启用",
            data={
                "id": "portal-user-wx",
                "name": "微信客户",
                "phone": "13900002222",
                "password": make_password("Portal123456"),
                "customerName": "微信客户",
                "status": "启用",
                "permissions": ["portal.notice.view"],
                "wechat": {"openid": "oid-bound-demo", "followStatus": "subscribed"},
            },
        )

    def test_silent_login_redirects_to_wechat_oauth(self):
        client = Client()
        response = client.get("/api/portal/wechat/silent-login/?next=messages")
        self.assertEqual(response.status_code, 200)
        html = response.content.decode("utf-8")
        self.assertIn("open.weixin.qq.com/connect/oauth2/authorize", html)
        self.assertIn("snsapi_base", html)
        self.assertIn("state=", html)
        self.assertIn("location.replace(", html)

    def test_oauth_callback_issues_cookie_for_bound_openid(self):
        client = Client()
        state = signing.dumps(
            {"purpose": "login", "next": "messages", "ts": 1},
            salt=PORTAL_WECHAT_LOGIN_SALT,
        )
        with patch(
            "apps.data_store.portal.wechat_mp.exchange_oauth_code",
            return_value={"openid": "oid-bound-demo"},
        ):
            response = client.get(
                "/api/wechat/mp/oauth/callback/",
                {"code": "mock-code", "state": state},
            )
        self.assertEqual(response.status_code, 200)
        self.assertIn(PORTAL_COOKIE, response.cookies)
        self.assertIn("#messages", response.content.decode("utf-8"))
        me = client.get("/api/portal/me/")
        self.assertEqual(me.status_code, 200)
        self.assertEqual(me.json()["data"]["id"], "portal-user-wx")

    def test_oauth_callback_unbound_openid_goes_login(self):
        client = Client()
        state = signing.dumps(
            {"purpose": "login", "next": "messages", "ts": 1},
            salt=PORTAL_WECHAT_LOGIN_SALT,
        )
        with patch(
            "apps.data_store.portal.wechat_mp.exchange_oauth_code",
            return_value={"openid": "oid-unknown"},
        ):
            response = client.get(
                "/api/wechat/mp/oauth/callback/",
                {"code": "mock-code", "state": state},
            )
        self.assertEqual(response.status_code, 200)
        self.assertNotIn(PORTAL_COOKIE, response.cookies)
        html = response.content.decode("utf-8")
        self.assertIn("wechat=unbound", html)
        self.assertIn("#login", html)
