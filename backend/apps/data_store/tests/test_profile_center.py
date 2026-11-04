from django.contrib.auth.hashers import make_password
from django.test import Client, TestCase

from apps.data_store.models import RoleRecord, UserApiToken, UserRecord
from apps.data_store.profile_views import resolve_user_data_for_api_token


class ProfileCenterTests(TestCase):
    def setUp(self):
        self.client = Client()
        RoleRecord.objects.create(
            id="role-profile",
            name="测试角色",
            data={"id": "role-profile", "name": "测试角色", "permissions": ["dashboard.view", "notice.view"]},
        )
        UserRecord.objects.create(
            id="user-profile",
            name="张三",
            phone="13800138000",
            status="启用",
            data={
                "id": "user-profile",
                "name": "张三",
                "phone": "13800138000",
                "password": make_password("OldPass1"),
                "roleIds": ["role-profile"],
                "status": "启用",
                "createdAt": "2026-01-01T00:00:00",
            },
        )
        login = self.client.post(
            "/api/auth/login/",
            data={"identifier": "13800138000", "password": "OldPass1"},
            content_type="application/json",
        )
        self.assertEqual(login.status_code, 200)

    def test_update_profile_and_password(self):
        patched = self.client.patch(
            "/api/auth/profile/",
            data={"name": "李四", "phone": "13900139000"},
            content_type="application/json",
        )
        self.assertEqual(patched.status_code, 200)
        self.assertEqual(patched.json()["data"]["name"], "李四")

        changed = self.client.post(
            "/api/auth/change-password/",
            data={"currentPassword": "OldPass1", "newPassword": "NewPass1", "confirmPassword": "NewPass1"},
            content_type="application/json",
        )
        self.assertEqual(changed.status_code, 200)

        self.client.post("/api/auth/logout/")
        again = self.client.post(
            "/api/auth/login/",
            data={"identifier": "13900139000", "password": "NewPass1"},
            content_type="application/json",
        )
        self.assertEqual(again.status_code, 200)

    def test_api_token_lifecycle(self):
        created = self.client.post(
            "/api/auth/api-token/",
            data={"name": "企微连接器"},
            content_type="application/json",
        )
        self.assertEqual(created.status_code, 201)
        token = created.json()["data"]["token"]
        self.assertTrue(token.startswith("yzc_"))

        listed = self.client.get("/api/auth/api-token/")
        self.assertTrue(listed.json()["data"]["hasToken"])
        self.assertNotIn("token", listed.json()["data"])

        user_data = resolve_user_data_for_api_token(token)
        self.assertIsNotNone(user_data)
        self.assertEqual(user_data["id"], "user-profile")

        revoked = self.client.delete("/api/auth/api-token/")
        self.assertEqual(revoked.status_code, 200)
        self.assertIsNone(resolve_user_data_for_api_token(token))
        self.assertEqual(UserApiToken.objects.filter(user_id="user-profile", revoked_at__isnull=True).count(), 0)

    def test_my_permissions(self):
        response = self.client.get("/api/auth/permissions/")
        self.assertEqual(response.status_code, 200)
        perms = set(response.json()["data"]["permissions"])
        self.assertIn("dashboard.view", perms)
        self.assertIn("notice.view", perms)
