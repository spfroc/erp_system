from django.test import SimpleTestCase, TestCase

from apps.assistant.services.intent_router import SYSTEM_PROMPT
from apps.assistant.services.user_settings import (
    QUICK_PROMPTS_MAX,
    SYSTEM_PROMPT_ADDON_MAX_LEN,
    compose_system_prompt,
    normalize_quick_prompts,
    resolve_avatar_fallback,
    update_user_settings,
)


class UserSettingsHelpersTests(SimpleTestCase):
    def test_compose_keeps_base_and_truncates_addon(self):
        long_addon = "偏" * (SYSTEM_PROMPT_ADDON_MAX_LEN + 80)
        prompt = compose_system_prompt(SYSTEM_PROMPT, long_addon)
        self.assertTrue(prompt.startswith(SYSTEM_PROMPT.rstrip()))
        self.assertIn("用户个人偏好", prompt)
        self.assertLessEqual(len(prompt) - len(SYSTEM_PROMPT), SYSTEM_PROMPT_ADDON_MAX_LEN + 80)

    def test_compose_empty_addon_unchanged(self):
        self.assertEqual(compose_system_prompt(SYSTEM_PROMPT, "  "), SYSTEM_PROMPT)

    def test_avatar_fallback_keys(self):
        self.assertEqual(resolve_avatar_fallback({"avatarUrl": "https://x/a.png"}), "https://x/a.png")
        self.assertEqual(resolve_avatar_fallback({"name": "张三"}), "")

    def test_normalize_quick_prompts(self):
        items = normalize_quick_prompts(
            [
                {"id": "a", "name": " 查账号 ", "content": "山东云谷平台账号", "direct_send": True},
                {"name": "", "content": "缺名称"},
                {"name": "仅名称", "content": ""},
                {"label": "旧字段", "text": "兼容 label/text"},
                *[{"name": f"n{i}", "content": f"c{i}"} for i in range(20)],
            ]
        )
        self.assertEqual(items[0]["name"], "查账号")
        self.assertTrue(items[0]["direct_send"])
        self.assertEqual(items[1]["name"], "旧字段")
        self.assertEqual(items[1]["content"], "兼容 label/text")
        self.assertFalse(items[1]["direct_send"])
        self.assertLessEqual(len(items), QUICK_PROMPTS_MAX)
        self.assertTrue(all(item["name"] and item["content"] for item in items))


class UserSettingsPersistTests(TestCase):
    def test_update_quick_prompts(self):
        saved = update_user_settings(
            "user-settings-1",
            {
                "quick_prompts": [
                    {"id": "qp-1", "name": "到期", "content": "查本月到期客户", "direct_send": True},
                    {"name": "忽略空", "content": ""},
                ]
            },
        )
        self.assertEqual(len(saved["quick_prompts"]), 1)
        self.assertEqual(saved["quick_prompts"][0]["name"], "到期")
        self.assertEqual(saved["quick_prompts"][0]["content"], "查本月到期客户")
        self.assertTrue(saved["quick_prompts"][0]["direct_send"])
