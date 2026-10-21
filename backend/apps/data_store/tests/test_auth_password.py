from django.contrib.auth.hashers import make_password
from django.test import Client, TestCase

from apps.data_store.models import AppState, UserRecord
from apps.data_store.views import DEFAULT_KEY, save_app_data


class AuthPasswordTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.user_id = "user-pwd-demo"
        self.phone = "13800009999"
        UserRecord.objects.create(
            id=self.user_id,
            name="改密测试",
            phone=self.phone,
            status="启用",
            data={
                "id": self.user_id,
                "name": "改密测试",
                "phone": self.phone,
                "password": make_password("OldPass123"),
                "roleIds": ["role-admin"],
                "status": "启用",
            },
        )
        # 模拟部分保存未同步快照：AppState 仍是旧密码。
        AppState.objects.update_or_create(
            key=DEFAULT_KEY,
            defaults={
                "data": {
                    "users": [
                        {
                            "id": self.user_id,
                            "name": "改密测试",
                            "phone": self.phone,
                            "password": make_password("OldPass123"),
                            "roleIds": ["role-admin"],
                            "status": "启用",
                        }
                    ]
                }
            },
        )

    def test_old_password_rejected_after_user_table_password_change(self):
        user = UserRecord.objects.get(id=self.user_id)
        data = dict(user.data)
        data["password"] = make_password("NewPass456")
        user.data = data
        user.save(update_fields=["data"])

        ok = self.client.post(
            "/api/auth/login/",
            data={"identifier": self.phone, "password": "NewPass456"},
            content_type="application/json",
        )
        self.assertEqual(ok.status_code, 200)

        stale = self.client.post(
            "/api/auth/login/",
            data={"identifier": self.phone, "password": "OldPass123"},
            content_type="application/json",
        )
        self.assertEqual(stale.status_code, 401)

    def test_partial_save_syncs_app_state_password(self):
        save_app_data(
            {
                "users": [
                    {
                        "id": self.user_id,
                        "name": "改密测试",
                        "phone": self.phone,
                        "password": "BrandNew789",
                        "roleIds": ["role-admin"],
                        "status": "启用",
                    }
                ]
            },
            partial=True,
        )
        state = AppState.objects.get(key=DEFAULT_KEY)
        snapshot_user = next(item for item in state.data["users"] if item["id"] == self.user_id)
        self.assertNotEqual(snapshot_user["password"], "BrandNew789")
        self.assertTrue(str(snapshot_user["password"]).startswith("pbkdf2_"))

        ok = self.client.post(
            "/api/auth/login/",
            data={"identifier": self.phone, "password": "BrandNew789"},
            content_type="application/json",
        )
        self.assertEqual(ok.status_code, 200)
        stale = self.client.post(
            "/api/auth/login/",
            data={"identifier": self.phone, "password": "OldPass123"},
            content_type="application/json",
        )
        self.assertEqual(stale.status_code, 401)
