from django.test import SimpleTestCase

from apps.assistant.services.context_manager import trim_context_for_llm
from apps.assistant.services.llm_adapter import LlmUnavailable, _parse_json_content


class LlmAdapterParseTests(SimpleTestCase):
    def test_parse_plain_json(self):
        data = _parse_json_content('{"tool_name":"notice.search","params":{}}')
        self.assertEqual(data["tool_name"], "notice.search")

    def test_parse_fenced_json(self):
        data = _parse_json_content('```json\n{"tool_name":null,"clarification":"请补充"}\n```')
        self.assertIsNone(data["tool_name"])

    def test_parse_invalid(self):
        with self.assertRaises(LlmUnavailable):
            _parse_json_content("not-json")


class ContextManagerTests(SimpleTestCase):
    def test_trim_context(self):
        trimmed = trim_context_for_llm(
            {
                "intent": "notice.search",
                "params": {"search": "济南", "password": "secret"},
                "recent_result_ids": [1, 2, 3] + list(range(20)),
                "selected_entity": {"type": "notice", "id": 1, "name": "A", "token": "x"},
            }
        )
        self.assertNotIn("password", trimmed["params"])
        self.assertEqual(len(trimmed["recent_result_ids"]), 10)
        self.assertEqual(trimmed["selected_entity"], {"type": "notice", "id": 1, "name": "A"})
