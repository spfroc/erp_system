import { useEffect, useMemo, useRef, useState } from "react";
import { Loader2, Plus, Settings, Trash2 } from "lucide-react";
import { fetchNoticeDetail, NoticeDetailModal, type NoticeDetail } from "../NoticeDetailModal";
import type { PermissionKey, User } from "../types";
import {
  confirmAssistantAction,
  createConversation,
  deleteConversation,
  fetchAssistantSettings,
  fetchAssistantStatus,
  fetchConversation,
  fetchConversations,
  renameConversation,
  sendChatMessage,
} from "./assistantApi";
import { AssistantResultRenderer } from "./AssistantResultRenderer";
import { AssistantSettingsPanel } from "./AssistantSettingsPanel";
import type {
  AssistantBlock,
  AssistantChatResponse,
  AssistantConversationItem,
  AssistantLlmUsage,
  AssistantMessageItem,
  AssistantMessagePayload,
  AssistantQuickPrompt,
  AssistantUserSettings,
} from "./assistantTypes";

const QUICK_PROMPTS: AssistantQuickPrompt[] = [
  { id: "notice", label: "查询采购公告", text: "查找最近一个月济南市办公设备采购公告", permission: "notice.view" },
  { id: "goods", label: "搜索采购商品", text: "查找惠普打印机相关采购记录", permission: "notice.view" },
  { id: "buyer", label: "分析采购单位", text: "查询这家医院过去一年采购过什么商品", permission: "notice.view" },
  { id: "deal", label: "查询历史成交", text: "查询最近成交的办公设备公告", permission: "notice.view" },
  { id: "product", label: "查询 ERP 商品", text: "查找商品名称中包含交换机的商品", permission: "product.view" },
  { id: "sales", label: "查询销售订单", text: "查询最近三十天未完成的销售订单", permission: "salesOrder.view" },
  { id: "purchase", label: "查询采购订单", text: "查询最近三十天未完成的采购订单", permission: "purchaseOrder.view" },
  { id: "expiry", label: "客户到期时间", text: "查询客户的到期时间", permission: "project.view" },
  { id: "serviceOrder", label: "客户服务订单", text: "查询客户的服务订单", permission: "serviceOrder.view" },
  { id: "customerSales", label: "客户商品订单", text: "查询某个客户购买的商品订单", permission: "salesOrder.view" },
  { id: "projectStatus", label: "项目开票状态", text: "查询项目开票状态", permission: "project.view" },
  { id: "devops", label: "查看采集任务", text: "查看最近执行失败的采集任务", permission: "dev.ops.view" },
  { id: "nav", label: "查找后台功能", text: "打开销售订单管理" },
];

function messageMode(payload?: AssistantMessagePayload): string | undefined {
  return payload?.mode || payload?.route?.mode;
}

function messageUsage(payload?: AssistantMessagePayload): AssistantLlmUsage | null | undefined {
  return payload?.llm_usage ?? payload?.route?.llm_usage;
}

function routeModeLabel(mode?: string): string {
  if (mode === "llm_assisted") return "已使用模型";
  if (mode === "degraded") return "模型降级";
  if (mode === "rule_only") return "未使用模型";
  return "";
}

function tokenLabel(usage?: AssistantLlmUsage | null): string {
  if (!usage) return "";
  const total = Number(usage.total_tokens || 0);
  if (!total) return "";
  const prefix = usage.source === "exact" ? "" : "约 ";
  return `${prefix}${total} tokens`;
}

function localMessage(
  role: "user" | "assistant",
  content: string,
  blocks?: AssistantChatResponse["blocks"],
  mode?: string,
  llmUsage?: AssistantLlmUsage | null,
  llmModel?: string | null
): AssistantMessageItem {
  return {
    id: `local-${Date.now()}-${Math.random()}`,
    role,
    content,
    payload:
      blocks || mode || llmUsage || llmModel
        ? { blocks, mode, llm_usage: llmUsage ?? null, llm_model: llmModel ?? null }
        : undefined,
    created_at: new Date().toISOString(),
  };
}

function userAvatarFromProfile(user?: User | null): string {
  if (!user) return "";
  const data = user as User & { avatarUrl?: string; avatar?: string; photoUrl?: string };
  return String(data.avatarUrl || data.avatar || data.photoUrl || "").trim();
}

export function AssistantPage({
  can,
  currentUser,
  onNavigate,
  onNotice,
}: {
  can: (permission: PermissionKey) => boolean;
  currentUser?: User;
  onNavigate?: (viewId: string) => void;
  onNotice?: (message: string, type?: "success" | "error") => void;
}) {
  const canUse = can("assistant.use");
  const [status, setStatus] = useState<{ mode?: string; llm?: { online?: boolean; enabled?: boolean } } | null>(null);
  const [conversations, setConversations] = useState<AssistantConversationItem[]>([]);
  const [activeId, setActiveId] = useState<number | null>(null);
  const [messages, setMessages] = useState<AssistantMessageItem[]>([]);
  const [context, setContext] = useState<Record<string, unknown>>({});
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [confirming, setConfirming] = useState(false);
  const [booting, setBooting] = useState(true);
  const [noticeDetail, setNoticeDetail] = useState<NoticeDetail | null>(null);
  const [noticeDetailLoading, setNoticeDetailLoading] = useState(false);
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [settings, setSettings] = useState<AssistantUserSettings | null>(null);
  const messagesRef = useRef<HTMLDivElement | null>(null);
  const shouldJumpScrollRef = useRef(true);

  const showTokenUsage = settings?.show_token_usage !== false;
  const chatDisplayName =
    (settings?.display_name || "").trim() || (currentUser?.name || "").trim() || "我";
  const chatAvatarUrl =
    (settings?.display_avatar_url || "").trim() ||
    (settings?.user_avatar_url || "").trim() ||
    userAvatarFromProfile(currentUser);

  const prompts = useMemo(
    () => QUICK_PROMPTS.filter((item) => !item.permission || can(item.permission as PermissionKey)),
    [can]
  );

  useEffect(() => {
    if (booting) return;
    const el = messagesRef.current;
    if (!el) return;
    const behavior: ScrollBehavior = shouldJumpScrollRef.current ? "auto" : "smooth";
    shouldJumpScrollRef.current = false;
    let cancelled = false;
    const scrollToBottom = () => {
      if (cancelled) return;
      el.scrollTop = el.scrollHeight;
      if (behavior === "smooth") {
        el.scrollTo({ top: el.scrollHeight, behavior: "smooth" });
      }
    };
    const frame = window.requestAnimationFrame(() => {
      scrollToBottom();
      window.requestAnimationFrame(scrollToBottom);
    });
    const timer = window.setTimeout(scrollToBottom, 80);
    return () => {
      cancelled = true;
      window.cancelAnimationFrame(frame);
      window.clearTimeout(timer);
    };
  }, [booting, messages, loading, activeId]);

  async function refreshConversations() {
    const items = await fetchConversations();
    setConversations(items);
    return items;
  }

  async function openConversation(id: number) {
    const detail = await fetchConversation(id);
    shouldJumpScrollRef.current = true;
    setActiveId(detail.id);
    setMessages(detail.messages || []);
    setContext(detail.context || {});
  }

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const tasks: Promise<unknown>[] = [fetchAssistantStatus(), fetchConversations()];
        if (canUse) tasks.push(fetchAssistantSettings().catch(() => null));
        const [statusData, items, prefs] = (await Promise.all(tasks)) as [
          Awaited<ReturnType<typeof fetchAssistantStatus>>,
          AssistantConversationItem[],
          AssistantUserSettings | null | undefined,
        ];
        if (cancelled) return;
        setStatus(statusData);
        setConversations(items);
        if (prefs) setSettings(prefs);
        if (items[0]) {
          await openConversation(items[0].id);
        }
      } catch (error) {
        onNotice?.(error instanceof Error ? error.message : "助手初始化失败");
      } finally {
        if (!cancelled) setBooting(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  async function handleNewChat() {
    if (!canUse) return;
    const created = await createConversation("新会话");
    await refreshConversations();
    setActiveId(created.id);
    setMessages([]);
    setContext({});
  }

  async function handleDelete(id: number) {
    if (!canUse) return;
    if (!window.confirm("确定删除该会话？")) return;
    await deleteConversation(id);
    const items = await refreshConversations();
    if (activeId === id) {
      if (items[0]) await openConversation(items[0].id);
      else {
        setActiveId(null);
        setMessages([]);
        setContext({});
      }
    }
  }

  async function handleRename(id: number, title: string) {
    if (!canUse) return;
    const next = window.prompt("重命名会话", title);
    if (!next?.trim()) return;
    await renameConversation(id, next.trim());
    await refreshConversations();
  }

  async function openNoticeDetail(noticeId: number) {
    if (!noticeId) return;
    setNoticeDetailLoading(true);
    try {
      const detail = await fetchNoticeDetail(noticeId);
      setNoticeDetail(detail);
    } catch (error) {
      onNotice?.(error instanceof Error ? error.message : "加载公告详情失败");
    } finally {
      setNoticeDetailLoading(false);
    }
  }

  function maybeOpenNoticeFromBlocks(blocks?: AssistantBlock[]) {
    const detailBlock = (blocks || []).find((block) => block.type === "notice_detail");
    if (!detailBlock?.data) return;
    const item = (detailBlock.data.item || {}) as Record<string, unknown>;
    const id = Number(item.id || detailBlock.data.notice_id || 0);
    if (id > 0) void openNoticeDetail(id);
  }

  function maybeNavigateFromBlocks(blocks?: AssistantBlock[]) {
    const navBlock = (blocks || []).find((block) => block.type === "navigation");
    if (!navBlock?.data?.auto_open) return;
    const items = Array.isArray(navBlock.data.items) ? navBlock.data.items : [];
    const first = items[0] as Record<string, unknown> | undefined;
    const viewId = String(first?.id || first?.viewId || "");
    if (viewId) onNavigate?.(viewId);
  }

  async function handleConfirm(executionId: number, token: string) {
    if (!canUse || confirming) return;
    setConfirming(true);
    try {
      const result = await confirmAssistantAction(executionId, token);
      setMessages((prev) => [
        ...prev,
        localMessage("assistant", result.content || "已执行。", result.blocks || []),
      ]);
    } catch (error) {
      const errText = error instanceof Error ? error.message : "确认失败";
      setMessages((prev) => [...prev, localMessage("assistant", errText, [{ type: "error", data: { text: errText } }])]);
      onNotice?.(errText);
    } finally {
      setConfirming(false);
    }
  }

  async function submit(text: string) {
    const message = text.trim();
    if (!message || !canUse || loading) return;
    setLoading(true);
    setInput("");
    setMessages((prev) => [...prev, localMessage("user", message)]);
    try {
      const result = await sendChatMessage(message, activeId);
      setActiveId(result.conversation_id);
      setContext(result.context || {});
      setMessages((prev) => [
        ...prev,
        localMessage(
          "assistant",
          result.content || "",
          result.blocks || [],
          result.mode,
          result.llm_usage,
          result.llm_model
        ),
      ]);
      maybeOpenNoticeFromBlocks(result.blocks);
      maybeNavigateFromBlocks(result.blocks);
      await refreshConversations();
    } catch (error) {
      const errText = error instanceof Error ? error.message : "发送失败";
      setMessages((prev) => [...prev, localMessage("assistant", errText, [{ type: "error", data: { text: errText } }])]);
      onNotice?.(errText);
    } finally {
      setLoading(false);
    }
  }

  if (booting) {
    return (
      <div className="stack">
        <div className="panel">
          <div className="table-empty">
            <Loader2 className="spin" size={18} /> 正在加载智能助手…
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="stack assistant-page">
      <div className="panel">
        <div className="panel-title action-title">
          <div>
            <h2>智能助手</h2>
            <p>规则能直接命中时秒回；复杂问句再交云端模型选工具。每条回复会标注是否使用模型及 token 用量。</p>
          </div>
          <div className="panel-title-buttons">
            <span className="muted">
              策略：规则优先
              {status?.llm?.enabled
                ? status.llm.online
                  ? " · 模型在线"
                  : " · 模型离线（仅规则）"
                : " · 未启用模型"}
            </span>
            {canUse && (
              <button
                type="button"
                className="ghost"
                onClick={() => setSettingsOpen(true)}
                title="助手设置"
                aria-label="助手设置"
              >
                <Settings size={16} /> 设置
              </button>
            )}
            {canUse && (
              <button type="button" className="primary" onClick={() => void handleNewChat()}>
                <Plus size={16} /> 新建会话
              </button>
            )}
          </div>
        </div>

        <div className="assistant-layout">
          <aside className="assistant-sidebar">
            <div className="assistant-sidebar-title">会话历史</div>
            {conversations.length === 0 && <div className="table-empty">暂无会话</div>}
            {conversations.map((item) => (
              <div
                key={item.id}
                className={`assistant-session ${activeId === item.id ? "active" : ""}`}
              >
                <button type="button" className="ghost assistant-session-main" onClick={() => void openConversation(item.id)}>
                  <strong>{item.title || "未命名会话"}</strong>
                  <em>{item.updated_at ? new Date(item.updated_at).toLocaleString() : ""}</em>
                </button>
                {canUse && (
                  <div className="option-actions">
                    <button type="button" className="copy-link" onClick={() => void handleRename(item.id, item.title)}>
                      重命名
                    </button>
                    <button type="button" className="copy-link danger-action" onClick={() => void handleDelete(item.id)}>
                      <Trash2 size={14} />
                    </button>
                  </div>
                )}
              </div>
            ))}
          </aside>

          <section className="assistant-main">
            <div className="assistant-messages" ref={messagesRef}>
              <div className="assistant-messages-inner">
                {messages.length === 0 && !loading && (
                  <div className="table-empty">选择快捷提示或直接输入问题开始查询。</div>
                )}
                {messages.map((msg) => {
                  const mode = messageMode(msg.payload);
                  const usage = messageUsage(msg.payload);
                  const modeText = msg.role === "assistant" ? routeModeLabel(mode) : "";
                  const tokensText =
                    showTokenUsage && mode === "llm_assisted" ? tokenLabel(usage) : "";
                  const who = msg.role === "user" ? chatDisplayName : "助手";
                  return (
                    <div key={String(msg.id)} className={`assistant-message assistant-message-${msg.role}`}>
                      <div className="assistant-bubble">
                        <div className="assistant-bubble-meta">
                          <div className="assistant-bubble-meta-left">
                            {msg.role === "user" && chatAvatarUrl ? (
                              <img className="assistant-avatar" src={chatAvatarUrl} alt="" />
                            ) : null}
                            <strong className="assistant-bubble-who">{who}</strong>
                            {modeText ? (
                              <span className={`assistant-mode-chip assistant-mode-chip-${mode || "unknown"}`}>
                                {modeText}
                                {tokensText ? <span className="assistant-token-chip">{tokensText}</span> : null}
                              </span>
                            ) : null}
                          </div>
                          <time dateTime={msg.created_at || undefined}>
                            {msg.created_at ? new Date(msg.created_at).toLocaleString() : ""}
                          </time>
                        </div>
                        {msg.content ? <p>{msg.content}</p> : null}
                        {msg.payload?.blocks ? (
                          <AssistantResultRenderer
                            blocks={msg.payload.blocks}
                            onNavigate={onNavigate}
                            onFollowUp={(text) => void submit(text)}
                            onOpenNotice={(noticeId) => void openNoticeDetail(noticeId)}
                            onConfirmAction={(executionId, token) => void handleConfirm(executionId, token)}
                            confirming={confirming}
                          />
                        ) : null}
                      </div>
                    </div>
                  );
                })}
                {loading && (
                  <div className="assistant-message assistant-message-assistant">
                    <div className="assistant-bubble muted">
                      <div className="assistant-bubble-meta">
                        <div className="assistant-bubble-meta-left">
                          <strong className="assistant-bubble-who">助手</strong>
                        </div>
                        <time>{new Date().toLocaleString()}</time>
                      </div>
                      <p>
                        <Loader2 className="spin" size={16} /> 正在查询…
                      </p>
                    </div>
                  </div>
                )}
              </div>
            </div>

            <div className="assistant-composer">
              <div className="assistant-prompts segmented">
                {prompts.map((item) => (
                  <button
                    key={item.id}
                    type="button"
                    disabled={!canUse || loading}
                    onClick={() => void submit(item.text)}
                  >
                    {item.label}
                  </button>
                ))}
              </div>

              <form
                className="assistant-input-row"
                onSubmit={(event) => {
                  event.preventDefault();
                  void submit(input);
                }}
              >
                <textarea
                  className="assistant-input"
                  value={input}
                  rows={3}
                  onChange={(event) => setInput(event.target.value)}
                  onKeyDown={(event) => {
                    if (event.key === "Enter" && event.ctrlKey && !event.nativeEvent.isComposing) {
                      event.preventDefault();
                      void submit(input);
                    }
                  }}
                  placeholder={
                    canUse
                      ? "输入自然语言指令，例如：查济南打印机公告（Ctrl+Enter 发送）"
                      : "当前账号无助手使用权限"
                  }
                  disabled={!canUse || loading}
                />
                <button className="primary" type="submit" disabled={!canUse || loading || !input.trim()}>
                  发送
                </button>
              </form>

              <div className="assistant-meta muted">
                当前意图：{String(context.intent || "-")}
                {Array.isArray(context.recent_result_ids)
                  ? ` · 最近结果 ${context.recent_result_ids.length} 条`
                  : ""}
              </div>
            </div>
          </section>
        </div>
      </div>

      {noticeDetail && (
        <NoticeDetailModal
          detail={noticeDetail}
          loading={noticeDetailLoading}
          onClose={() => {
            setNoticeDetail(null);
            setNoticeDetailLoading(false);
          }}
          onSelectRelated={(id) => void openNoticeDetail(id)}
        />
      )}

      <AssistantSettingsPanel
        open={settingsOpen}
        onClose={() => setSettingsOpen(false)}
        onSaved={(next) => {
          setSettings(next);
          onNotice?.("助手设置已保存", "success");
        }}
        onNotice={(message) => onNotice?.(message, "error")}
      />
    </div>
  );
}

export default AssistantPage;
