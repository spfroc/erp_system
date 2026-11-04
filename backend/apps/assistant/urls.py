from django.urls import path

from . import mcp_views, views

urlpatterns = [
    path("mcp/", mcp_views.mcp_endpoint, name="assistant-mcp"),
    path("assistant/status/", views.assistant_status, name="assistant-status"),
    path("assistant/tools/", views.assistant_tools, name="assistant-tools"),
    path("assistant/settings/", views.assistant_settings, name="assistant-settings"),
    path("assistant/chat/", views.assistant_chat, name="assistant-chat"),
    path("assistant/conversations/", views.assistant_conversations, name="assistant-conversations"),
    path(
        "assistant/conversations/<int:conversation_id>/",
        views.assistant_conversation_detail,
        name="assistant-conversation-detail",
    ),
    path("assistant/actions/<int:execution_id>/", views.assistant_action_detail, name="assistant-action-detail"),
    path(
        "assistant/actions/<int:execution_id>/confirm/",
        views.assistant_action_confirm,
        name="assistant-action-confirm",
    ),
]
