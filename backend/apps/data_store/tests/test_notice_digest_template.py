from datetime import date, datetime
from zoneinfo import ZoneInfo

from django.test import SimpleTestCase

from apps.data_store.notice_digest import _template_data
from apps.data_store.wechat_mp import portal_messages_url


class NoticeDigestTemplateTests(SimpleTestCase):
    def test_template_is_summary_style(self):
        data = _template_data(
            digest_date=date(2026, 11, 10),
            hits=[{"id": 1}, {"id": 2}, {"id": 3}],
            now=datetime(2026, 11, 11, 9, 30, 0, tzinfo=ZoneInfo("Asia/Shanghai")),
        )
        self.assertEqual(data["thing1"]["value"], "有3条公告更新了")
        self.assertEqual(data["time2"]["value"], "2026-11-11 09:30:00")
        self.assertEqual(data["thing3"]["value"], "点击查看消息列表")
        self.assertEqual(data["character_string5"]["value"], "3")

    def test_portal_messages_url_appends_hash(self):
        with self.settings(WECHAT_MP_PORTAL_NOTICE_URL="https://example.com/portal/"):
            self.assertEqual(portal_messages_url(), "https://example.com/portal/#messages")
        with self.settings(WECHAT_MP_PORTAL_NOTICE_URL="https://example.com/portal/#notices"):
            self.assertEqual(portal_messages_url(), "https://example.com/portal/#messages")
