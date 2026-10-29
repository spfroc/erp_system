from django.apps import AppConfig


class AssistantConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.assistant"
    label = "assistant"
    verbose_name = "智能业务助手"

    def ready(self) -> None:
        # 注册工具（避免循环导入放在 ready）
        from .tools import register_all_tools  # noqa: WPS433

        register_all_tools()
