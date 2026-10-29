import { AuthExpiredError } from "../db";
import { backendApiUrl } from "../apiConfig";
import type {
  AssistantChatResponse,
  AssistantConversationItem,
  AssistantMessageItem,
} from "./assistantTypes";

async function assistantFetch(path: string, init?: RequestInit) {
  const response = await fetch(backendApiUrl(path), {
    credentials: "include",
    ...init,
  });
  if (response.status === 401) throw new AuthExpiredError();
  return response;
}

export async function fetchAssistantStatus() {
  const response = await assistantFetch("/api/assistant/status/");
  if (!response.ok) throw new Error("无法获取助手状态");
  return response.json();
}

export async function fetchConversations(): Promise<AssistantConversationItem[]> {
  const response = await assistantFetch("/api/assistant/conversations/");
  if (!response.ok) throw new Error("无法加载会话列表");
  const data = await response.json();
  return Array.isArray(data.items) ? data.items : [];
}

export async function createConversation(title = ""): Promise<AssistantConversationItem> {
  const response = await assistantFetch("/api/assistant/conversations/", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ title }),
  });
  if (!response.ok) throw new Error("无法创建会话");
  return response.json();
}

export async function fetchConversation(id: number): Promise<{
  id: number;
  title: string;
  messages: AssistantMessageItem[];
  context?: Record<string, unknown>;
}> {
  const response = await assistantFetch(`/api/assistant/conversations/${id}/`);
  if (!response.ok) throw new Error("无法加载会话");
  return response.json();
}

export async function renameConversation(id: number, title: string) {
  const response = await assistantFetch(`/api/assistant/conversations/${id}/`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ title }),
  });
  if (!response.ok) throw new Error("无法重命名会话");
  return response.json();
}

export async function deleteConversation(id: number) {
  const response = await assistantFetch(`/api/assistant/conversations/${id}/`, { method: "DELETE" });
  if (!response.ok) throw new Error("无法删除会话");
  return response.json();
}

export async function sendChatMessage(
  message: string,
  conversationId?: number | null
): Promise<AssistantChatResponse> {
  const response = await assistantFetch("/api/assistant/chat/", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      message,
      conversation_id: conversationId || undefined,
    }),
  });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(data.detail || data.content || "助手请求失败");
  }
  return data as AssistantChatResponse;
}

export async function confirmAssistantAction(executionId: number, confirmationToken: string) {
  const response = await assistantFetch(`/api/assistant/actions/${executionId}/confirm/`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ confirmation_token: confirmationToken }),
  });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(data.detail || "确认执行失败");
  }
  return data as {
    execution_id: number;
    status: string;
    content: string;
    blocks: AssistantChatResponse["blocks"];
    idempotent?: boolean;
  };
}
