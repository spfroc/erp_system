import { useEffect, useState } from "react";
import { Loader2, Plus, Trash2, X } from "lucide-react";
import { fetchAssistantSettings, saveAssistantSettings } from "./assistantApi";
import type { AssistantQuickPrompt, AssistantUserSettings } from "./assistantTypes";

const EMPTY: AssistantUserSettings = {
  system_prompt_addon: "",
  show_token_usage: true,
  display_name: "",
  display_avatar_url: "",
  quick_prompts: [],
};

function newPromptId(): string {
  if (typeof crypto !== "undefined" && "randomUUID" in crypto) {
    return `qp-${crypto.randomUUID()}`;
  }
  return `qp-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
}

export function AssistantSettingsPanel({
  open,
  onClose,
  onSaved,
  onNotice,
}: {
  open: boolean;
  onClose: () => void;
  onSaved: (settings: AssistantUserSettings) => void;
  onNotice?: (message: string) => void;
}) {
  const [form, setForm] = useState<AssistantUserSettings>(EMPTY);
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const addonMax = form.limits?.system_prompt_addon_max ?? 500;
  const promptsMax = form.limits?.quick_prompts_max ?? 10;
  const nameMax = form.limits?.quick_prompt_name_max ?? 32;
  const contentMax = form.limits?.quick_prompt_content_max ?? 500;
  const prompts = form.quick_prompts || [];

  useEffect(() => {
    if (!open) return;
    let cancelled = false;
    setLoading(true);
    (async () => {
      try {
        const data = await fetchAssistantSettings();
        if (!cancelled) {
          setForm({
            ...EMPTY,
            ...data,
            quick_prompts: Array.isArray(data.quick_prompts) ? data.quick_prompts : [],
          });
        }
      } catch (error) {
        onNotice?.(error instanceof Error ? error.message : "加载设置失败");
        if (!cancelled) onClose();
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [open]);

  if (!open) return null;

  function updatePrompt(index: number, patch: Partial<AssistantQuickPrompt>) {
    setForm((prev) => {
      const next = [...(prev.quick_prompts || [])];
      const current = next[index];
      if (!current) return prev;
      next[index] = { ...current, ...patch };
      return { ...prev, quick_prompts: next };
    });
  }

  function addPrompt() {
    setForm((prev) => {
      const current = prev.quick_prompts || [];
      if (current.length >= promptsMax) return prev;
      return {
        ...prev,
        quick_prompts: [...current, { id: newPromptId(), name: "", content: "", direct_send: false }],
      };
    });
  }

  function removePrompt(index: number) {
    setForm((prev) => ({
      ...prev,
      quick_prompts: (prev.quick_prompts || []).filter((_, i) => i !== index),
    }));
  }

  async function handleSave() {
    const cleaned = (form.quick_prompts || [])
      .map((item) => ({
        id: String(item.id || newPromptId()),
        name: String(item.name || "").trim().slice(0, nameMax),
        content: String(item.content || "").trim().slice(0, contentMax),
        direct_send: Boolean(item.direct_send),
      }))
      .filter((item) => item.name && item.content)
      .slice(0, promptsMax);

    if ((form.quick_prompts || []).some((item) => item.name.trim() || item.content.trim()) && cleaned.length === 0) {
      onNotice?.("快捷提示词需同时填写名称和内容");
      return;
    }

    setSaving(true);
    try {
      const saved = await saveAssistantSettings({
        system_prompt_addon: form.system_prompt_addon,
        show_token_usage: form.show_token_usage,
        display_name: form.display_name,
        display_avatar_url: form.display_avatar_url,
        quick_prompts: cleaned,
      });
      onSaved(saved);
      onClose();
    } catch (error) {
      onNotice?.(error instanceof Error ? error.message : "保存失败");
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="modal-backdrop" role="presentation" onClick={onClose}>
      <div
        className="modal assistant-settings-modal"
        role="dialog"
        aria-labelledby="assistant-settings-title"
        onClick={(event) => event.stopPropagation()}
      >
        <div className="modal-head">
          <div>
            <h3 id="assistant-settings-title">助手设置</h3>
            <p className="muted">仅影响当前登录账号，不会改全局模型配置。</p>
          </div>
          <button className="icon-button" type="button" onClick={onClose} aria-label="关闭设置">
            <X size={18} />
          </button>
        </div>

        {loading ? (
          <div className="table-empty">
            <Loader2 className="spin" size={18} /> 加载中…
          </div>
        ) : (
          <div className="form-grid assistant-settings-form">
            <label>
              <span>聊天显示昵称</span>
              <input
                value={form.display_name}
                maxLength={form.limits?.display_name_max ?? 64}
                placeholder={form.user_name ? `默认：${form.user_name}` : "默认：我"}
                onChange={(event) => setForm((prev) => ({ ...prev, display_name: event.target.value }))}
              />
            </label>
            <label>
              <span>头像 URL</span>
              <input
                value={form.display_avatar_url}
                maxLength={form.limits?.display_avatar_url_max ?? 512}
                placeholder={
                  form.user_avatar_url ? "留空则沿用账号已有头像" : "可选，粘贴图片链接"
                }
                onChange={(event) =>
                  setForm((prev) => ({ ...prev, display_avatar_url: event.target.value }))
                }
              />
            </label>
            <label className="assistant-settings-check">
              <input
                type="checkbox"
                checked={form.show_token_usage}
                onChange={(event) =>
                  setForm((prev) => ({ ...prev, show_token_usage: event.target.checked }))
                }
              />
              <span>显示 token 消耗数量</span>
            </label>
            <label className="assistant-settings-prompt">
              <span>
                个人系统提示词（追加）
                <em>
                  不会替换服务端安全约束；拼入意图解析时最多 {addonMax} 字
                </em>
              </span>
              <textarea
                rows={5}
                value={form.system_prompt_addon}
                maxLength={addonMax * 2}
                placeholder="例如：回答尽量简洁；优先按客户简称理解项目名称…"
                onChange={(event) =>
                  setForm((prev) => ({ ...prev, system_prompt_addon: event.target.value }))
                }
              />
            </label>

            <div className="assistant-settings-prompts">
              <div className="assistant-settings-prompts-head">
                <div>
                  <strong>快捷提示词</strong>
                  <em>
                    最多 {promptsMax} 条；默认点击填入输入框，勾选「直接发送」则一点即发
                  </em>
                </div>
                <button
                  type="button"
                  className="ghost"
                  disabled={prompts.length >= promptsMax}
                  onClick={addPrompt}
                >
                  <Plus size={14} /> 添加
                </button>
              </div>
              {prompts.length === 0 ? (
                <div className="table-empty">暂无快捷提示词</div>
              ) : (
                <div className="assistant-settings-prompt-list">
                  {prompts.map((item, index) => (
                    <div className="assistant-settings-prompt-row" key={item.id || index}>
                      <label>
                        <span>名称</span>
                        <input
                          value={item.name}
                          maxLength={nameMax}
                          placeholder="按钮显示名，如：查云谷账号"
                          onChange={(event) => updatePrompt(index, { name: event.target.value })}
                        />
                      </label>
                      <label>
                        <span>内容</span>
                        <textarea
                          rows={2}
                          value={item.content}
                          maxLength={contentMax}
                          placeholder="点击后填入对话框的完整问句"
                          onChange={(event) => updatePrompt(index, { content: event.target.value })}
                        />
                      </label>
                      <div className="assistant-settings-prompt-side">
                        <label className="assistant-settings-check">
                          <input
                            type="checkbox"
                            checked={Boolean(item.direct_send)}
                            onChange={(event) =>
                              updatePrompt(index, { direct_send: event.target.checked })
                            }
                          />
                          <span>直接发送</span>
                        </label>
                        <button
                          type="button"
                          className="icon-button danger-action"
                          aria-label="删除快捷提示词"
                          onClick={() => removePrompt(index)}
                        >
                          <Trash2 size={16} />
                        </button>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        )}

        <div className="modal-actions">
          <button className="ghost" type="button" onClick={onClose} disabled={saving}>
            取消
          </button>
          <button className="primary" type="button" onClick={() => void handleSave()} disabled={loading || saving}>
            {saving ? (
              <>
                <Loader2 className="spin" size={16} /> 保存中…
              </>
            ) : (
              "保存"
            )}
          </button>
        </div>
      </div>
    </div>
  );
}
