from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase

from apps.assistant.models import AssistantToolExecution
from apps.assistant.services.confirmation import confirm_action, hash_token
from apps.assistant.services.tool_executor import ToolExecutionError, execute_tool
from apps.assistant.tools import reset_registration_for_tests


class ConfirmationFlowTests(SimpleTestCase):
    def setUp(self):
        reset_registration_for_tests()

    def _user(self):
        return {
            "id": "u-confirm",
            "permissions": ["assistant.use", "dev.ops.manage", "dev.ops.view"],
        }

    @patch("apps.assistant.services.tool_executor.AssistantToolExecution.objects.create")
    def test_write_tool_requires_preview(self, create_mock):
        record = MagicMock()
        record.id = 7
        create_mock.return_value = record
        result = execute_tool(
            tool_name="devops.run_safe_job",
            params={"job_id": 3},
            user_data=self._user(),
            confirmed=False,
        )
        self.assertEqual(result["status"], "awaiting_confirmation")
        self.assertEqual(result["block_type"], "tool_preview")
        self.assertIn("confirmation_token", result["data"])
        kwargs = create_mock.call_args.kwargs
        self.assertEqual(kwargs["status"], AssistantToolExecution.STATUS_AWAITING_CONFIRMATION)
        self.assertTrue(kwargs["confirmation_token_hash"])

    @patch("apps.assistant.services.confirmation.execute_tool")
    @patch("apps.assistant.services.confirmation.get_action")
    def test_confirm_success_and_idempotent(self, get_action, execute_mock):
        record = MagicMock()
        record.id = 8
        record.user_id = "u-confirm"
        record.tool_name = "devops.run_safe_job"
        record.parameters_json = {"job_id": 3}
        record.conversation_id = 1
        record.status = AssistantToolExecution.STATUS_AWAITING_CONFIRMATION
        token = "plain-token"
        record.confirmation_token_hash = hash_token(token)
        get_action.return_value = record
        execute_mock.return_value = {
            "execution_id": 8,
            "status": "completed",
            "block_type": "tool_result",
            "content": "已触发",
            "summary": "已触发",
            "data": {"run": {"id": 99}},
        }

        first = confirm_action(user_data=self._user(), execution_id=8, confirmation_token=token)
        self.assertEqual(first["status"], "completed")
        self.assertFalse(first["idempotent"])
        execute_mock.assert_called_once()
        self.assertEqual(execute_mock.call_args.kwargs["confirmed"], True)

        record.status = AssistantToolExecution.STATUS_COMPLETED
        record.result_summary = "已触发"
        record.result_json = {"block_type": "tool_result", "data": {"run": {"id": 99}}}
        second = confirm_action(user_data=self._user(), execution_id=8, confirmation_token=token)
        self.assertTrue(second["idempotent"])

    @patch("apps.assistant.services.confirmation.get_action")
    def test_invalid_token_rejected(self, get_action):
        record = MagicMock()
        record.id = 9
        record.status = AssistantToolExecution.STATUS_AWAITING_CONFIRMATION
        record.confirmation_token_hash = hash_token("good")
        get_action.return_value = record
        with self.assertRaises(ToolExecutionError) as ctx:
            confirm_action(user_data=self._user(), execution_id=9, confirmation_token="bad")
        self.assertEqual(ctx.exception.code, "invalid_token")
