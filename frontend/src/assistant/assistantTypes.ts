export type AssistantBlockType =
  | "text"
  | "notice_list"
  | "notice_detail"
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

export interface AssistantLlmUsage {
  prompt_tokens?: number;
  completion_tokens?: number;
  total_tokens?: number;
  source?: "exact" | "estimated" | string;
}

export interface AssistantMessagePayload {
  blocks?: AssistantBlock[];
  mode?: string;
  llm_usage?: AssistantLlmUsage | null;
  llm_model?: string | null;
  route?: {
    mode?: string;
    llm_usage?: AssistantLlmUsage | null;
    llm_model?: string | null;
  };
  execution_id?: number;
}

export interface AssistantMessageItem {
  id: number | string;
  role: "user" | "assistant" | "system" | "tool";
  content: string;
  message_type?: string;
  payload?: AssistantMessagePayload;
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
  llm_usage?: AssistantLlmUsage | null;
  llm_model?: string | null;
  errors?: Array<{ code?: string; message?: string }>;
  context?: Record<string, unknown>;
}

export interface AssistantQuickPrompt {
  id: string;
  name: string;
  content: string;
  /** 点击后直接发送；false 时仅填入输入框 */
  direct_send?: boolean;
}

export interface AssistantUserSettings {
  system_prompt_addon: string;
  show_token_usage: boolean;
  display_name: string;
  display_avatar_url: string;
  quick_prompts: AssistantQuickPrompt[];
  user_name?: string;
  user_avatar_url?: string;
  updated_at?: string;
  limits?: {
    system_prompt_addon_max?: number;
    display_name_max?: number;
    display_avatar_url_max?: number;
    quick_prompts_max?: number;
    quick_prompt_name_max?: number;
    quick_prompt_content_max?: number;
  };
}
