import { useEffect, useMemo, useState } from "react";
import { Loader2, Plus, Trash2 } from "lucide-react";
import type { PermissionKey } from "../types";
import {
  createConversation,
  deleteConversation,
  fetchAssistantStatus,
  fetchConversation,
  fetchConversations,
  renameConversation,
  sendChatMessage,
} from "./assistantApi";
import { AssistantResultRenderer } from "./AssistantResultRenderer";
import type {
  AssistantChatResponse,
  AssistantConversationItem,
  AssistantMessageItem,
  AssistantQuickPrompt,
} from "./assistantTypes";

const QUICK_PROMPTS: AssistantQuickPrompt[] = [
  { id: "notice", label: "查询采购公告", text: "查找最近一个月济南市办公设备采购公告", permission: "notice.view" },
  { id: "goods", label: "搜索采购商品", text: "查找惠普打印机相关采购记录", permission: "notice.view" },
  { id: "buyer", label: "分析采购单位", text: "查询这家医院过去一年采购过什么商品", permission: "notice.view" },
  { id: "deal", label: "查询历史成交", text: "查询最近成交的办公设备公告", permission: "notice.view" },
  { id: "product", label: "查询 ERP 商品", text: "查找商品名称中包含交换机的商品", permission: "product.view" },
  { id: "sales", label: "查询销售订单", text: "查询最近三十天未完成的销售订单", permission: "salesOrder.view" },
  { id: "purchase", label: "查询采购订单", text: "查询最近三十天未完成的采购订单", permission: "purchaseOrder.view" },
  { id: "devops", label: "查看采集任务", text: "查看最近执行失败的采集任务", permission: "dev.ops.view" },
  { id: "nav", label: "查找后台功能", text: "打开销售订单管理" },
];

function localMessage(role: "user" | "assistant", content: string, blocks?: AssistantChatResponse["blocks"]): AssistantMessageItem {
  return {
    id: `local-${Date.now()}-${Math.random()}`,
    role,
    content,
    payload: blocks ? { blocks } : undefined,
    created_at: new Date().toISOString(),
  };
}

export function AssistantPage({
  can,
  onNavigate,
  onNotice,
}: {
  can: (permission: PermissionKey) => boolean;
  onNavigate?: (viewId: string) => void;
  onNotice?: (message: string) => void;
}) {
  const canUse = can("assistant.use");
  const [status, setStatus] = useState<{ mode?: string; llm?: { online?: boolean; enabled?: boolean } } | null>(null);
  const [conversations, setConversations] = useState<AssistantConversationItem[]>([]);
  const [activeId, setActiveId] = useState<number | null>(null);
  const [messages, setMessages] = useState<AssistantMessageItem[]>([]);
  const [context, setContext] = useState<Record<string, unknown>>({});
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [booting, setBooting] = useState(true);

  const prompts = useMemo(
    () => QUICK_PROMPTS.filter((item) => !item.permission || can(item.permission as PermissionKey)),
    [can]
  );

  async function refreshConversations() {
    const items = await fetchConversations();
    setConversations(items);
    return items;
  }

  async function openConversation(id: number) {
    const detail = await fetchConversation(id);
    setActiveId(detail.id);
    setMessages(detail.messages || []);
    setContext(detail.context || {});
  }

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const [statusData, items] = await Promise.all([fetchAssistantStatus(), fetchConversations()]);
        if (cancelled) return;
        setStatus(statusData);
        setConversations(items);
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
        localMessage("assistant", result.content || "", result.blocks || []),
      ]);
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
            <p>用自然语言查询公告、商品与订单；当前为规则路由模式，模型离线时仍可搜索与导航。</p>
          </div>
          <div className="panel-title-buttons">
            <span className="muted">
              模式：{status?.mode || "rule_only"}
              {status?.llm?.enabled
                ? status.llm.online
                  ? " · 模型在线"
                  : " · 模型离线（已降级）"
                : " · 未启用模型（规则优先）"}
            </span>
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
            <div className="assistant-messages">
              {messages.length === 0 && (
                <div className="table-empty">选择快捷提示或直接输入问题开始查询。</div>
              )}
              {messages.map((msg) => (
                <div key={String(msg.id)} className={`assistant-message assistant-message-${msg.role}`}>
                  <div className="assistant-bubble">
                    <p>{msg.content}</p>
                    {msg.payload?.blocks ? (
                      <AssistantResultRenderer
                        blocks={msg.payload.blocks}
                        onNavigate={onNavigate}
                        onFollowUp={(text) => void submit(text)}
                      />
                    ) : null}
                  </div>
                </div>
              ))}
              {loading && (
                <div className="assistant-message assistant-message-assistant">
                  <div className="assistant-bubble muted">
                    <Loader2 className="spin" size={16} /> 正在查询…
                  </div>
                </div>
              )}
            </div>

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
              <input
                value={input}
                onChange={(event) => setInput(event.target.value)}
                placeholder={canUse ? "输入自然语言指令，例如：查济南打印机公告" : "当前账号无助手使用权限"}
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
          </section>
        </div>
      </div>
    </div>
  );
}

export default AssistantPage;
