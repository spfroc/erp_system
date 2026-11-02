import { useEffect, useState } from "react";
import { Loader2, X } from "lucide-react";
import { fetchAssistantSettings, saveAssistantSettings } from "./assistantApi";
import type { AssistantUserSettings } from "./assistantTypes";

const EMPTY: AssistantUserSettings = {
  system_prompt_addon: "",
  show_token_usage: true,
  display_name: "",
  display_avatar_url: "",
};

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

  useEffect(() => {
    if (!open) return;
    let cancelled = false;
    setLoading(true);
    (async () => {
      try {
        const data = await fetchAssistantSettings();
        if (!cancelled) setForm({ ...EMPTY, ...data });
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

  async function handleSave() {
    setSaving(true);
    try {
      const saved = await saveAssistantSettings({
        system_prompt_addon: form.system_prompt_addon,
        show_token_usage: form.show_token_usage,
        display_name: form.display_name,
        display_avatar_url: form.display_avatar_url,
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
        className="modal"
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
