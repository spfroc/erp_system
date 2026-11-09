from django.test import SimpleTestCase

from apps.data_store.notice_views import extract_gov_project_codes, _normalize_project_code


class NoticeProjectCodeSearchTests(SimpleTestCase):
    def test_extract_from_natural_language(self):
        codes = extract_gov_project_codes("查询SDGP371400000202601002301_A项目相关的公告")
        self.assertEqual(codes, ["SDGP371400000202601002301_A"])

    def test_extract_multiple_unique(self):
        text = "对比 SDGP111111111111111111_A 与 SDGP111111111111111111_A 以及 SCJJ20260102003"
        codes = extract_gov_project_codes(text)
        self.assertEqual(codes[0], "SDGP111111111111111111_A")
        self.assertIn("SCJJ20260102003", codes)
        self.assertEqual(len(codes), 2)

    def test_normalize_strips_package_suffix(self):
        self.assertEqual(_normalize_project_code("SDGP123，1"), "SDGP123")
        self.assertEqual(_normalize_project_code("SDGP123,2"), "SDGP123")
