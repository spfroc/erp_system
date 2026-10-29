from django.urls import path

from . import views

urlpatterns = [
    path("assistant/status/", views.assistant_status, name="assistant-status"),
    path("assistant/tools/", views.assistant_tools, name="assistant-tools"),
    path("assistant/chat/", views.assistant_chat, name="assistant-chat"),
]
