from django.test import TestCase

from apps.assistant.services.tool_executor import execute_tool
from apps.assistant.services.mcp_server import list_mcp_tools
from apps.assistant.tools import reset_registration_for_tests
from apps.assistant.tools.platform_account_tools import _parse_labeled_text
from apps.data_store.models import OrganizationRecord, PlatformAccountRecord, RoleRecord, UserRecord


class PlatformAccountToolsTests(TestCase):
    def setUp(self):
        reset_registration_for_tests()
        RoleRecord.objects.create(
            id="role-pa",
            name="平台账号测试",
            data={
                "id": "role-pa",
                "name": "平台账号测试",
                "permissions": [
                    "assistant.use",
                    "platformAccount.view",
                    "platformAccount.manage",
                ],
            },
        )
        self.user = UserRecord.objects.create(
            id="user-pa",
            name="平台测试员",
            phone="18600000999",
            status="启用",
            data={
                "id": "user-pa",
                "name": "平台测试员",
                "phone": "18600000999",
                "status": "启用",
                "roleIds": ["role-pa"],
                "password": "x",
            },
        )
        self.org = OrganizationRecord.objects.create(
            id="org-pa-1",
            name="济南示例科技有限公司",
            entity_type="企业",
            unified_credit_code="91370100PA0001",
            roles=["平台入驻商"],
            status="正常",
            data={"id": "org-pa-1", "name": "济南示例科技有限公司", "entityType": "企业"},
        )
        self.user_data = dict(self.user.data)

    def test_parse_labeled_text(self):
        parsed = _parse_labeled_text(
            "客户：济南示例科技有限公司\n平台：泉E采\n账号：acc-1\n密码：Secret123\n商户号：M001"
        )
        self.assertEqual(parsed["customer"], "济南示例科技有限公司")
        self.assertEqual(parsed["platform"], "泉E采")
        self.assertEqual(parsed["accountName"], "acc-1")
        self.assertEqual(parsed["accountPassword"], "Secret123")
        self.assertEqual(parsed["merchantId"], "M001")

    def test_search_create_update(self):
        created = execute_tool(
            tool_name="erp.platform_account.create",
            params={
                "text": "客户：济南示例\n平台：泉E采\n账号：acc-demo\n密码：Pass@123\n店铺名：示例店"
            },
            user_data=self.user_data,
        )
        self.assertEqual(created["status"], "completed")
        item = created["data"]["item"]
        self.assertEqual(item["platform"], "泉E采")
        self.assertEqual(item["accountName"], "acc-demo")
        self.assertEqual(item["accountPassword"], "Pass@123")
        self.assertIn("已添加平台账号", created["content"])
        self.assertTrue(PlatformAccountRecord.objects.filter(id=item["id"]).exists())

        searched = execute_tool(
            tool_name="erp.platform_account.search",
            params={"keyword": "济南", "platform": "泉E采", "include_password": True},
            user_data=self.user_data,
        )
        self.assertEqual(searched["data"]["total"], 1)
        row = searched["data"]["items"][0]
        self.assertEqual(row["accountName"], "acc-demo")
        self.assertEqual(row["accountPassword"], "Pass@123")
        self.assertEqual(row["platform"], "泉E采")
        self.assertIn("泉E采", row["name"])
        self.assertIn("账号:acc-demo", row["summary"])
        self.assertTrue(any(a.get("type") == "copy_text" for a in row.get("actions") or []))

        updated = execute_tool(
            tool_name="erp.platform_account.update",
            params={"id": item["id"], "note": "MCP更新备注", "merchantId": "M-9"},
            user_data=self.user_data,
        )
        self.assertEqual(updated["status"], "completed")
        self.assertEqual(updated["data"]["item"]["note"], "MCP更新备注")
        self.assertEqual(updated["data"]["item"]["merchantId"], "M-9")
        self.assertIn("请核对", updated["content"])

    def test_mcp_exposes_write_tools(self):
        names = {item["name"] for item in list_mcp_tools(user_data=self.user_data)}
        self.assertIn("erp.platform_account.search", names)
        self.assertIn("erp.platform_account.create", names)
        self.assertIn("erp.platform_account.update", names)
        self.assertNotIn("erp.invoice.delete", names)
