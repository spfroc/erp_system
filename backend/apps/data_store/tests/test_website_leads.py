from django.test import Client, SimpleTestCase, TestCase, override_settings

from apps.data_store.models import WebsiteLeadRecord
from apps.data_store.views import (
    _restore_system_deleted_website_leads,
    _soft_delete_queryset,
    parse_website_lead_payload,
    save_app_data,
)


class ParseWebsiteLeadPayloadTests(SimpleTestCase):
    def test_official_site_fields(self):
        parsed, error = parse_website_lead_payload({
            "name": "孙鹏飞",
            "phone": "18698853145",
            "enterprise_name": "青岛移联电",
            "platform_name": "运营商业务",
            "requirement": "商机接口调用测试",
        })
        self.assertEqual(error, "")
        self.assertEqual(parsed["companyName"], "青岛移联电")
        self.assertEqual(parsed["contactName"], "孙鹏飞")
        self.assertEqual(parsed["phone"], "18698853145")
        self.assertEqual(parsed["platform"], "其他")
        self.assertEqual(parsed["remark"], "商机接口调用测试；平台：运营商业务")

    def test_does_not_treat_person_name_as_company(self):
        parsed, error = parse_website_lead_payload({
            "name": "孙鹏飞",
            "enterprise_name": "青岛移联电",
            "phone": "18698853145",
        })
        self.assertEqual(error, "")
        self.assertEqual(parsed["companyName"], "青岛移联电")
        self.assertEqual(parsed["contactName"], "孙鹏飞")

    def test_legacy_name_as_company(self):
        parsed, error = parse_website_lead_payload({
            "name": "某公司",
            "phone": "13800000000",
        })
        self.assertEqual(error, "")
        self.assertEqual(parsed["companyName"], "某公司")
        self.assertEqual(parsed["contactName"], "")

    def test_maps_qilu_alias(self):
        parsed, error = parse_website_lead_payload({
            "companyName": "测试公司",
            "phone": "13800000000",
            "platform": "齐鲁云采入驻",
        })
        self.assertEqual(error, "")
        self.assertEqual(parsed["platform"], "齐鲁云采")


@override_settings(ROOT_URLCONF="config.urls")
class WebsiteLeadApiTests(TestCase):
    def setUp(self):
        self.client = Client()

    def test_official_payload_creates_lead(self):
        response = self.client.post(
            "/api/website-leads/",
            data={
                "name": "孙鹏飞",
                "phone": "18698853145",
                "enterprise_name": "青岛移联电",
                "platform_name": "运营商业务",
                "requirement": "商机接口调用测试",
            },
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 201)
        body = response.json()
        self.assertEqual(body["code"], 20000)
        lead = body["data"]
        self.assertEqual(lead["companyName"], "青岛移联电")
        self.assertEqual(lead["contactName"], "孙鹏飞")
        self.assertEqual(lead["platform"], "其他")
        self.assertIn("商机接口调用测试", lead["remark"])
        record = WebsiteLeadRecord.objects.get(id=lead["id"])
        self.assertEqual(record.company_name, "青岛移联电")
        self.assertEqual(record.contact_name, "孙鹏飞")

    def test_official_site_inquiry_returns_legacy_shape(self):
        response = self.client.post(
            "/api/official-site-inquiry",
            data={
                "name": "孙鹏飞",
                "phone": "18698853145",
                "enterprise_name": "青岛移联电",
                "platform_name": "运营商业务",
                "requirement": "商机接口调用测试",
            },
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["code"], 20000)
        self.assertEqual(body["message"], "success")
        self.assertEqual(body["data"]["enterprise_name"], "青岛移联电")
        self.assertEqual(body["data"]["companyName"], "青岛移联电")
        self.assertEqual(WebsiteLeadRecord.objects.filter(company_name="青岛移联电").count(), 1)


class WebsiteLeadPersistenceTests(TestCase):
    def setUp(self):
        self.client = Client()
        save_app_data({
            "users": [{
                "id": "user-admin",
                "name": "管理员",
                "phone": "13800000000",
                "password": "123456",
                "status": "启用",
                "roleIds": ["role-admin"],
            }],
            "roles": [{
                "id": "role-admin",
                "name": "管理员",
                "permissions": ["lead.manage"],
            }],
            "websiteLeads": [{
                "id": "lead-keep",
                "companyName": "甲公司",
                "phone": "13800000001",
                "contactName": "张三",
                "platform": "泉E采",
                "remark": "官网进线",
                "status": "未跟进",
                "createdAt": "2026-08-20T01:00:00",
                "memos": [{
                    "id": "lmemo-1",
                    "content": "已电话联系",
                    "createdBy": "张三",
                    "createdAt": "2026-08-20T01:10:00",
                }],
            }, {
                "id": "lead-other",
                "companyName": "乙公司",
                "phone": "13800000002",
                "contactName": "李四",
                "platform": "齐鲁云采",
                "status": "未跟进",
                "createdAt": "2026-08-21T01:00:00",
                "memos": [],
            }],
        })
        login = self.client.post(
            "/api/auth/login/",
            data={"identifier": "13800000000", "password": "123456"},
            content_type="application/json",
        )
        self.assertEqual(login.status_code, 200)

    def test_patch_status_keeps_company_phone_and_memos(self):
        response = self.client.patch(
            "/api/collections/websiteLeads/lead-keep/",
            data={"data": {"status": "已跟进"}},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        body = response.json()["data"]
        self.assertEqual(body["status"], "已跟进")
        self.assertEqual(body["companyName"], "甲公司")
        self.assertEqual(body["phone"], "13800000001")
        self.assertEqual(body["contactName"], "张三")
        self.assertEqual(body["remark"], "官网进线")
        self.assertEqual(len(body["memos"]), 1)
        self.assertEqual(body["memos"][0]["content"], "已电话联系")

        record = WebsiteLeadRecord.objects.get(id="lead-keep")
        self.assertEqual(record.company_name, "甲公司")
        self.assertEqual(record.phone, "13800000001")
        self.assertEqual(record.status, "已跟进")
        self.assertEqual(record.data["memos"][0]["content"], "已电话联系")

    def test_list_restores_system_deleted_leads(self):
        _soft_delete_queryset(WebsiteLeadRecord.objects.filter(id="lead-other"), "system")
        other = WebsiteLeadRecord.objects.get(id="lead-other")
        self.assertTrue(other.is_deleted)
        self.assertEqual(other.deleted_by, "system")

        response = self.client.get(
            "/api/collections/websiteLeads/",
            {"page": 1, "page_size": 20},
        )
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        ids = {item["id"] for item in payload["items"]}
        self.assertIn("lead-keep", ids)
        self.assertIn("lead-other", ids)
        restored = WebsiteLeadRecord.objects.get(id="lead-other")
        self.assertFalse(restored.is_deleted)
        self.assertEqual(restored.deleted_by, "")
        self.assertEqual(restored.company_name, "乙公司")
        self.assertEqual(restored.phone, "13800000002")

    def test_restore_skips_operator_deleted_leads(self):
        record = WebsiteLeadRecord.objects.get(id="lead-other")
        record.is_deleted = True
        record.deleted_by = "张三"
        record.save(update_fields=["is_deleted", "deleted_by"])

        _restore_system_deleted_website_leads()

        record.refresh_from_db()
        self.assertTrue(record.is_deleted)
        self.assertEqual(record.deleted_by, "张三")
