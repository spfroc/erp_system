from unittest.mock import patch

from django.test import SimpleTestCase

from apps.data_store.notice_digest import build_notice_template_data, send_manual_template_for_account


class ManualTemplatePushTests(SimpleTestCase):
    def test_build_template_fields(self):
        data = build_notice_template_data(
            project="办公室电脑采购竞标",
            bid_time="2023-11-17 09:01 ~ 2023-11-17 19:00",
            initiator="张三",
            project_code="PRO-20240321-001",
        )
        self.assertEqual(data["thing1"]["value"], "办公室电脑采购竞标")
        self.assertEqual(data["time2"]["value"], "2023-11-17 09:01 ~ 2023-11-17 19:00")
        self.assertEqual(data["thing3"]["value"], "张三")
        self.assertEqual(data["character_string5"]["value"], "PRO-20240321-001")

    def test_send_manual_requires_fields(self):
        with patch("apps.data_store.notice_digest.CustomerAccountRecord.objects") as objects:
            record = type(
                "R",
                (),
                {
                    "id": "acc-1",
                    "status": "启用",
                    "data": {"wechat": {"openid": "oid-1", "followStatus": "subscribed"}},
                    "name": "测",
                    "phone": "138",
                    "customer_name": "",
                    "customer_org_id": "",
                },
            )()
            objects.filter.return_value.first.return_value = record
            with patch("apps.data_store.notice_digest.wechat_mp.mp_configured", return_value=True):
                with patch("apps.data_store.notice_digest.public_account", return_value={"name": "测", "phone": "138"}):
                    outcome = send_manual_template_for_account(
                        account_id="acc-1",
                        project="",
                        bid_time="t",
                        initiator="i",
                        project_code="c",
                    )
        self.assertEqual(outcome["status"], "failed")
        self.assertEqual(outcome["reason"], "invalid_fields")
