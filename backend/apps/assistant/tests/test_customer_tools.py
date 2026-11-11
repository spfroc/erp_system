from django.test import TestCase

from apps.assistant.services.mcp_server import list_mcp_tools
from apps.assistant.services.tool_executor import execute_tool
from apps.assistant.tools import reset_registration_for_tests
from apps.assistant.tools.customer_tools import _parse_labeled_text
from apps.data_store.models import OrganizationRecord, RoleRecord, UserRecord


class CustomerToolsTests(TestCase):
    def setUp(self):
        reset_registration_for_tests()
        RoleRecord.objects.create(
            id="role-customer",
            name="客户资料测试",
            data={
                "id": "role-customer",
                "name": "客户资料测试",
                "permissions": [
                    "assistant.use",
                    "entity.view",
                    "entity.create",
                ],
            },
        )
        self.user = UserRecord.objects.create(
            id="user-customer",
            name="客户测试员",
            phone="18600000888",
            status="启用",
            data={
                "id": "user-customer",
                "name": "客户测试员",
                "phone": "18600000888",
                "status": "启用",
                "roleIds": ["role-customer"],
                "password": "x",
            },
        )
        self.user_data = dict(self.user.data)

    def test_parse_labeled_text(self):
        parsed = _parse_labeled_text(
            "名称：济南示例科技有限公司\n统一社会信用代码：91370100AB0001\n法人：张三\n电话：13800001111"
        )
        self.assertEqual(parsed["name"], "济南示例科技有限公司")
        self.assertEqual(parsed["unifiedCreditCode"], "91370100AB0001")
        self.assertEqual(parsed["legalPerson"], "张三")
        self.assertEqual(parsed["phone"], "13800001111")

    def test_create_duplicate_then_confirm_update(self):
        created = execute_tool(
            tool_name="erp.customer.create",
            params={
                "text": (
                    "名称：济南云谷测试有限公司\n"
                    "统一社会信用代码：91370100YG0001\n"
                    "法人：李四\n"
                    "电话：13900002222"
                )
            },
            user_data=self.user_data,
        )
        self.assertEqual(created["status"], "completed")
        self.assertTrue(created["data"]["created"])
        item = created["data"]["item"]
        self.assertEqual(item["name"], "济南云谷测试有限公司")
        self.assertEqual(item["unifiedCreditCode"], "91370100YG0001")
        self.assertTrue(OrganizationRecord.objects.filter(id=item["id"]).exists())

        dup = execute_tool(
            tool_name="erp.customer.create",
            params={
                "name": "济南云谷测试有限公司（更名）",
                "unifiedCreditCode": "91370100YG0001",
                "legalPerson": "王五",
                "phone": "13700003333",
            },
            user_data=self.user_data,
        )
        self.assertEqual(dup["status"], "completed")
        self.assertTrue(dup["data"]["duplicate"])
        self.assertTrue(dup["data"]["requires_confirm_update"])
        self.assertEqual(dup["data"]["existing"]["id"], item["id"])
        self.assertEqual(OrganizationRecord.objects.filter(unified_credit_code="91370100YG0001").count(), 1)

        updated = execute_tool(
            tool_name="erp.customer.create",
            params={
                "id": item["id"],
                "confirm_update": True,
                "name": "济南云谷测试有限公司（更名）",
                "unifiedCreditCode": "91370100YG0001",
                "legalPerson": "王五",
                "phone": "13700003333",
            },
            user_data=self.user_data,
        )
        self.assertEqual(updated["status"], "completed")
        self.assertTrue(updated["data"]["updated"])
        self.assertEqual(updated["data"]["item"]["name"], "济南云谷测试有限公司（更名）")
        self.assertEqual(updated["data"]["item"]["legalPerson"], "王五")
        self.assertEqual(updated["data"]["item"]["phone"], "13700003333")
        self.assertEqual(OrganizationRecord.objects.filter(unified_credit_code="91370100YG0001").count(), 1)

    def test_search_and_mcp_expose(self):
        OrganizationRecord.objects.create(
            id="org-search-1",
            name="青岛检索客户有限公司",
            entity_type="企业",
            unified_credit_code="91370200SEARCH1",
            roles=["平台入驻商"],
            status="正常",
            data={
                "id": "org-search-1",
                "name": "青岛检索客户有限公司",
                "entityType": "企业",
                "unifiedCreditCode": "91370200SEARCH1",
            },
        )
        searched = execute_tool(
            tool_name="erp.customer.search",
            params={"keyword": "青岛检索"},
            user_data=self.user_data,
        )
        self.assertEqual(searched["data"]["total"], 1)
        self.assertEqual(searched["data"]["items"][0]["unifiedCreditCode"], "91370200SEARCH1")

        names = {item["name"] for item in list_mcp_tools(user_data=self.user_data)}
        self.assertIn("erp.customer.search", names)
        self.assertIn("erp.customer.create", names)
