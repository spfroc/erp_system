from django.test import SimpleTestCase

from apps.assistant.services.intent_router import SYSTEM_PROMPT
from apps.assistant.services.user_settings import (
    SYSTEM_PROMPT_ADDON_MAX_LEN,
    compose_system_prompt,
    resolve_avatar_fallback,
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
