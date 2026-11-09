from django.test import SimpleTestCase

from apps.data_store.notice_subscription import (
    normalize_subscription,
    notice_matches_subscription,
    subscription_has_filters,
)


class NoticeSubscriptionMatchTests(SimpleTestCase):
    def test_normalize_legacy_keywords_string(self):
        sub = normalize_subscription({"enabled": True, "keywords": "空调, 印刷"})
        self.assertEqual(sub["keywords"], ["空调", "印刷"])
        self.assertTrue(subscription_has_filters(sub))

    def test_and_across_dimensions(self):
        sub = {
            "enabled": True,
            "contentTags": ["印刷"],
            "regions": [{"province": "山东省", "city": "济南市", "district": ""}],
            "keywords": [],
            "buyers": [],
            "orgTypes": [],
        }
        self.assertTrue(
            notice_matches_subscription(
                subscription=sub,
                title="年鉴印刷服务项目",
                content_tag="印刷",
                province="山东省",
                city="济南市",
            )
        )
        self.assertFalse(
            notice_matches_subscription(
                subscription=sub,
                title="年鉴印刷服务项目",
                content_tag="印刷",
                province="山东省",
                city="青岛市",
            )
        )

    def test_keyword_on_title_not_buyer(self):
        sub = {"enabled": True, "keywords": ["LED"]}
        self.assertTrue(
            notice_matches_subscription(
                subscription=sub,
                title="LED屏幕询比采购",
                buyer_name="某单位",
            )
        )
        self.assertFalse(
            notice_matches_subscription(
                subscription=sub,
                title="办公家具采购",
                buyer_name="LED科技公司",
            )
        )

    def test_buyer_and_org_type(self):
        sub = {
            "enabled": True,
            "buyers": ["交通管理"],
            "orgTypes": ["公安系统"],
        }
        self.assertTrue(
            notice_matches_subscription(
                subscription=sub,
                title="运维服务",
                buyer_name="济南市公安局交通管理支队",
                org_type="公安系统",
            )
        )
        self.assertFalse(
            notice_matches_subscription(
                subscription=sub,
                title="运维服务",
                buyer_name="济南市公安局交通管理支队",
                org_type="教育",
            )
        )
