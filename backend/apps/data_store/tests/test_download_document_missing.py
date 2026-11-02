from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase, override_settings

from apps.data_store.models import ManagedFile
from apps.data_store.views import save_app_data


@override_settings(DEBUG=True)
class DownloadDocumentMissingTests(TestCase):
    def setUp(self):
        save_app_data(
            {
                "roles": [
                    {
                        "id": "role-admin",
                        "name": "管理员",
                        "permissions": ["project.view", "project.edit", "site.manage", "site.view"],
                    }
                ],
                "users": [
                    {
                        "id": "user-admin",
                        "name": "管理员",
                        "phone": "13800000001",
                        "password": "123456",
                        "roleIds": ["role-admin"],
                        "status": "启用",
                    }
                ],
            }
        )
        self.client = Client()
        login = self.client.post(
            "/api/auth/login/",
            data={"identifier": "13800000001", "password": "123456"},
            content_type="application/json",
        )
        self.assertEqual(login.status_code, 200)

    def _upload_contract(self) -> str:
        pdf = SimpleUploadedFile("合同.pdf", b"%PDF-1.4 missing-later", content_type="application/pdf")
        response = self.client.post(
            "/api/documents/upload/",
            {"documentType": "contract", "ownerId": "order-missing-file", "file": pdf},
        )
        self.assertEqual(response.status_code, 201, response.content)
        return response.json()["data"]["id"]

    def test_missing_disk_file_returns_friendly_html(self):
        file_id = self._upload_contract()
        record = ManagedFile.objects.get(id=file_id)
        storage = record.file.storage
        storage.delete(record.file.name)

        response = self.client.get(
            f"/api/documents/{file_id}/",
            HTTP_ACCEPT="text/html,application/xhtml+xml",
        )
        self.assertEqual(response.status_code, 404)
        self.assertIn("text/html", response["Content-Type"])
        body = response.content.decode("utf-8")
        self.assertIn("合同文件不存在或已被移除，请联系管理员", body)
        self.assertNotIn("/app/media", body)
        self.assertNotIn("business_documents", body)
        self.assertNotIn("FileNotFoundError", body)
        self.assertNotIn("Traceback", body)

    def test_missing_disk_file_returns_json_when_accept_json(self):
        file_id = self._upload_contract()
        record = ManagedFile.objects.get(id=file_id)
        record.file.storage.delete(record.file.name)

        response = self.client.get(
            f"/api/documents/{file_id}/",
            HTTP_ACCEPT="application/json",
        )
        self.assertEqual(response.status_code, 404)
        self.assertEqual(
            response.json()["detail"],
            "合同文件不存在或已被移除，请联系管理员。",
        )

    def test_unknown_file_id_html(self):
        response = self.client.get(
            "/api/documents/file-does-not-exist/",
            HTTP_ACCEPT="text/html",
        )
        self.assertEqual(response.status_code, 404)
        self.assertIn("文件不存在或已被移除", response.content.decode("utf-8"))
