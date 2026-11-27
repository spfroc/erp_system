from django.test import SimpleTestCase

from apps.data_store.notice_subscription import (
    normalize_subscription,
    notice_matches_subscription,
    subscription_has_filters,
    validate_push_times,
)


class NoticeSubscriptionMatchTests(SimpleTestCase):
    def test_normalize_legacy_keywords_string(self):
        sub = normalize_subscription({"enabled": True, "keywords": "空调, 印刷"})
        self.assertEqual(sub["keywords"], ["空调", "印刷"])
        self.assertTrue(subscription_has_filters(sub))

    def test_or_across_dimensions(self):
        sub = {
            "enabled": True,
            "regions": [{"province": "山东省", "city": "济南", "district": ""}],
            "keywords": ["印刷"],
            "orgTypes": [],
            "noticeCategories": [],
        }
        self.assertTrue(
            notice_matches_subscription(
                subscription=sub,
                title="年鉴印刷服务项目",
                province="山东省",
                city="青岛市",
            )
        )
        self.assertTrue(
            notice_matches_subscription(
                subscription=sub,
                title="办公设备采购",
                province="山东省",
                city="济南市",
            )
        )
        self.assertFalse(
            notice_matches_subscription(
                subscription=sub,
                title="办公设备采购",
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

    def test_org_type_or_region(self):
        sub = {
            "enabled": True,
            "orgTypes": ["公安系统"],
            "regions": [{"province": "山东省", "city": "青岛", "district": ""}],
        }
        self.assertTrue(
            notice_matches_subscription(
                subscription=sub,
                title="运维服务",
                org_type="公安系统",
                city="济南",
            )
        )
        self.assertTrue(
            notice_matches_subscription(
                subscription=sub,
                title="运维服务",
                org_type="教育",
                city="青岛市",
            )
        )
        self.assertFalse(
            notice_matches_subscription(
                subscription=sub,
                title="运维服务",
                org_type="教育",
                city="济南",
            )
        )

    def test_notice_category_and_filter(self):
        sub = {
            "enabled": True,
            "noticeCategories": ["结果"],
            "keywords": ["车辆"],
        }
        self.assertTrue(
            notice_matches_subscription(
                subscription=sub,
                title="车辆采购成交公告",
                notice_kind="成交公告",
            )
        )
        self.assertFalse(
            notice_matches_subscription(
                subscription=sub,
                title="车辆采购公告",
                notice_kind="采购公告",
            )
        )

    def test_shandong_cities_only(self):
        sub = normalize_subscription(
            {
                "enabled": True,
                "regions": [
                    {"province": "江苏省", "city": "南京", "district": ""},
                    {"province": "山东省", "city": "济南市", "district": ""},
                ],
            }
        )
        self.assertEqual(sub["regions"], [{"province": "山东省", "city": "济南", "district": ""}])

    def test_push_times_limits(self):
        times, err = validate_push_times(["08:00", "08:15", "08:30", "08:45"])
        self.assertIsNotNone(err)
        times, err = validate_push_times(["08:00", "10:00", "12:00", "14:00", "16:00"])
        self.assertIsNone(err)
        self.assertEqual(len(times), 5)
        times, err = validate_push_times(["08:00", "09:00", "10:00", "11:00", "12:00", "13:00"])
        self.assertEqual(len(times), 5)
