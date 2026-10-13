from django.test import SimpleTestCase

from apps.data_store.views import _is_masked_value, _preserve_sensitive_fields


class MaskedSecretTests(SimpleTestCase):
    def test_real_password_with_asterisk_is_not_masked(self):
        self.assertFalse(_is_masked_value("*F!lL3Z@"))
        self.assertFalse(_is_masked_value("P@ss*w0rd"))
        self.assertFalse(_is_masked_value("secret-a"))

    def test_display_masks_are_detected(self):
        self.assertTrue(_is_masked_value(None))
        self.assertTrue(_is_masked_value(""))
        self.assertTrue(_is_masked_value("已保存"))
        self.assertTrue(_is_masked_value("****"))
        self.assertTrue(_is_masked_value("se***-a"))
        self.assertTrue(_is_masked_value("ol***ss"))

    def test_preserve_keeps_password_containing_asterisk(self):
        existing = {"accountPasswordMasked": "old-pass"}
        payload = {"accountPasswordMasked": "*F!lL3Z@"}
        merged = _preserve_sensitive_fields("platformAccounts", payload, existing)
        self.assertEqual(merged["accountPasswordMasked"], "*F!lL3Z@")

    def test_preserve_ignores_masked_placeholder(self):
        existing = {"accountPasswordMasked": "old-pass"}
        payload = {"accountPasswordMasked": "ol***ss"}
        merged = _preserve_sensitive_fields("platformAccounts", payload, existing)
        self.assertEqual(merged["accountPasswordMasked"], "old-pass")

    def test_preserve_ignores_short_mask(self):
        existing = {"accountPasswordMasked": "abc"}
        payload = {"accountPasswordMasked": "****"}
        merged = _preserve_sensitive_fields("platformAccounts", payload, existing)
        self.assertEqual(merged["accountPasswordMasked"], "abc")
