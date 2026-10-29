export type AssistantBlockType =
  | "text"
  | "notice_list"
  | "goods_table"
  | "buyer_profile"
  | "erp_record_list"
  | "statistics"
  | "navigation"
  | "tool_preview"
  | "tool_result"
  | "clarification"
  | "error";

export interface AssistantBlock {
  type: AssistantBlockType;
  data?: Record<string, unknown>;
}

export interface AssistantMessageItem {
  id: number | string;
  role: "user" | "assistant" | "system" | "tool";
  content: string;
  message_type?: string;
  payload?: { blocks?: AssistantBlock[] };
  created_at?: string;
}

export interface AssistantConversationItem {
  id: number;
  title: string;
  updated_at?: string;
  created_at?: string;
}

export interface AssistantChatResponse {
  conversation_id: number;
  message_id?: number;
  mode: string;
  intent?: string;
  status: string;
  content: string;
  blocks: AssistantBlock[];
  errors?: Array<{ code?: string; message?: string }>;
  context?: Record<string, unknown>;
}

export interface AssistantQuickPrompt {
  id: string;
  label: string;
  text: string;
  permission?: string;
}
