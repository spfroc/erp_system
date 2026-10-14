from django.test import Client, TestCase

from apps.data_store.library_sms import normalize_library_contact, send_sms_via_center
from apps.data_store.models import LibraryContactRecord, RoleRecord, SmsRecordRecord, UserRecord


class LibrarySmsTests(TestCase):
    def setUp(self):
        RoleRecord.objects.create(
            id="role-lib",
            name="资料库测试",
            data={
                "id": "role-lib",
                "name": "资料库测试",
                "permissions": [
                    "library.view",
                    "library.manage",
                    "sms.view",
                    "sms.manage",
                ],
            },
        )
        UserRecord.objects.create(
            id="user-lib",
            name="资料库员",
            phone="13800000001",
            status="启用",
            data={
                "id": "user-lib",
                "name": "资料库员",
                "phone": "13800000001",
                "password": "x",
                "roleIds": ["role-lib"],
                "status": "启用",
            },
        )
        self.client = Client()
        session = self.client.session
        session["user_id"] = "user-lib"
        session.save()

    def test_normalize_library_contact(self):
        data = normalize_library_contact(
            {
                "name": "测试公司",
                "mobile": "13900001111",
                "signed": "1",
                "origin": "3",
                "type": "代理商",
                "tags": "重点,已短信",
            }
        )
        self.assertEqual(data["signed"], "已签约")
        self.assertEqual(data["origin"], "齐鲁云采")
        self.assertIn("已短信", data["tags"])

    def test_library_contacts_collection_crud(self):
        payload = {
            "id": "lib-test-1",
            "name": "济南示例科技",
            "mobile": "13700002222",
            "signed": "有效",
            "origin": "齐鲁云采",
            "type": "经销商",
        }
        create = self.client.post(
            "/api/collections/libraryContacts/",
            data=payload,
            content_type="application/json",
        )
        self.assertEqual(create.status_code, 201)
        listed = self.client.get(
            "/api/collections/libraryContacts/",
            {"paged": "1", "page": 1, "page_size": 20, "search": "济南"},
        )
        self.assertEqual(listed.status_code, 200)
        body = listed.json()
        self.assertGreaterEqual(body["total"], 1)
        self.assertTrue(any(item["name"] == "济南示例科技" for item in body["items"]))

    def test_sms_send_local_mode(self):
        result, error = send_sms_via_center(mobile="13800138000", content="你好", prefix="壹知产")
        self.assertEqual(error, "")
        self.assertEqual(result["mode"], "local")

        response = self.client.post(
            "/api/sms/send/",
            data={"mobile": "13800138000", "content": "测试短信", "prefix": "壹知产"},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(SmsRecordRecord.objects.filter(is_deleted=False).count(), 1)
        self.assertIn("本地记录", response.json()["data"]["record"]["result"])

    def test_sms_send_tags_library_contact(self):
        contact = normalize_library_contact(
            {"id": "lib-sms-1", "name": "待短信公司", "mobile": "13600003333", "tags": []}
        )
        LibraryContactRecord.objects.create(
            id=contact["id"],
            name=contact["name"],
            mobile=contact["mobile"],
            data=contact,
        )
        response = self.client.post(
            "/api/sms/send/",
            data={
                "mobile": "13600003333",
                "content": "跟进提醒",
                "prefix": "壹知产",
                "contactIds": ["lib-sms-1"],
            },
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()["data"]["taggedContacts"], 1)
        refreshed = LibraryContactRecord.objects.get(id="lib-sms-1")
        self.assertIn("已短信", refreshed.data.get("tags") or [])
