from django.test import SimpleTestCase

from apps.data_store.notice_views import _auction_no, _normalize_project_code


class NoticeFlowKeyTests(SimpleTestCase):
    def test_normalize_project_code_drops_package_suffix(self):
        self.assertEqual(_normalize_project_code("SCDZ-2026-1406634，1"), "SCDZ-2026-1406634")
        self.assertEqual(_normalize_project_code("SCJJ-3704062026042103227,1"), "SCJJ-3704062026042103227")
        self.assertEqual(_normalize_project_code("SDGP371600000202601002849_A"), "SDGP371600000202601002849_A")

    def test_auction_no_uses_jd_notice_key_prefix(self):
        self.assertEqual(_auction_no("jd-qing-huicai", "JJ20261020110000001:4"), "JJ20261020110000001")
        self.assertEqual(_auction_no("sd-ggzyjyzx", "7512225214894374912"), "")
        self.assertEqual(_auction_no("jd-qing-huicai", "F20261020124510000018"), "")
