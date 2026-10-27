from datetime import datetime
from zoneinfo import ZoneInfo

from django.test import SimpleTestCase

from apps.data_store.dev_ops_catalog import get_script, list_scripts
from apps.data_store.dev_ops_schedule import cron_matches, next_run_at

SHANGHAI = ZoneInfo("Asia/Shanghai")


class DevOpsScheduleTests(SimpleTestCase):
    def test_catalog_whitelist(self):
        keys = {item["key"] for item in list_scripts()}
        self.assertIn("tag_notice_results", keys)
        self.assertIn("notice_crawl_once", keys)
        self.assertIn("notice_crawl_all", keys)
        self.assertIsNone(get_script("seed_database"))
        all_script = get_script("notice_crawl_all")
        self.assertIsNotNone(all_script)
        self.assertNotIn("lookback_days", {field["key"] for field in all_script["argSchema"]})

    def test_interval_next_run(self):
        now = datetime(2026, 10, 26, 10, 0, tzinfo=SHANGHAI)
        nxt = next_run_at(schedule_type="interval", interval_seconds=3600, cron_expr="", now=now, last_run_at=None)
        self.assertEqual(nxt, datetime(2026, 10, 26, 11, 0, tzinfo=SHANGHAI))

    def test_cron_matches_and_next(self):
        when = datetime(2026, 10, 26, 3, 0, tzinfo=SHANGHAI)
        self.assertTrue(cron_matches("0 3 * * *", when))
        self.assertFalse(cron_matches("0 4 * * *", when))
        nxt = next_run_at(schedule_type="cron", interval_seconds=None, cron_expr="0 3 * * *", now=when)
        self.assertEqual(nxt.hour, 3)
        self.assertEqual(nxt.minute, 0)
        self.assertGreater(nxt, when)
