from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase

from apps.data_store.models import ManagedFile
from apps.data_store.views import save_app_data


class SiteWechatQrDocumentTests(TestCase):
    def setUp(self):
        save_app_data(
            {
                "roles": [{"id": "role-admin", "name": "管理员", "permissions": ["site.manage", "site.view"]}],
                "users": [
                    {
                        "id": "user-admin",
                        "name": "管理员",
                        "phone": "13800000000",
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
            data={"identifier": "13800000000", "password": "123456"},
            content_type="application/json",
        )
        self.assertEqual(login.status_code, 200)

    def test_upload_and_anonymous_download(self):
        png = SimpleUploadedFile("wx.png", b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR", content_type="image/png")
        response = self.client.post(
            "/api/documents/upload/",
            {"documentType": "site_wechat_qr", "ownerId": "site-qlyc", "file": png},
        )
        self.assertEqual(response.status_code, 201, response.content)
        file_id = response.json()["data"]["id"]
        self.assertTrue(ManagedFile.objects.filter(id=file_id, document_type="site_wechat_qr").exists())

        anon = Client()
        download = anon.get(f"/api/documents/{file_id}/")
        self.assertEqual(download.status_code, 200)
        self.assertIn("image", download["Content-Type"])
