from django.urls import path

from . import views

urlpatterns = [
    path("assistant/status/", views.assistant_status, name="assistant-status"),
    path("assistant/tools/", views.assistant_tools, name="assistant-tools"),
    path("assistant/chat/", views.assistant_chat, name="assistant-chat"),
    path("assistant/conversations/", views.assistant_conversations, name="assistant-conversations"),
    path(
        "assistant/conversations/<int:conversation_id>/",
        views.assistant_conversation_detail,
        name="assistant-conversation-detail",
    ),
]
