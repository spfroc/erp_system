import { useEffect, useState } from "react";
import { MessageCircle, X } from "lucide-react";
import { createCollectionItem, createId, deleteCollectionItem, patchCollectionItem, queryCollection, AuthExpiredError } from "./db";
import { CopyableLine, Pagination, SearchField } from "./listUi";
import type { AppData, LibraryContact, PermissionKey, SmsRecord, SmsTemplate, User } from "./types";

type CanAccess = (permission: PermissionKey) => boolean;

const PAGE_SIZE = 20;

function apiUrl(path: string) {
  const url = new URL(path, window.location.origin);
  if (import.meta.env.DEV) url.port = "8000";
  return url.toString();
}

function useDebounced(value: string, delay = 300) {
  const [debounced, setDebounced] = useState(value);
  useEffect(() => {
    const timer = window.setTimeout(() => setDebounced(value), delay);
    return () => window.clearTimeout(timer);
  }, [value, delay]);
  return debounced;
}

function formatTime(value?: string) {
  if (!value) return "—";
  return value.replace("T", " ").slice(0, 16);
}

async function fetchSmsStatus() {
  const response = await fetch(apiUrl("/api/sms/status/"), { credentials: "include" });
  if (response.status === 401) throw new AuthExpiredError();
  const body = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(body.detail || "读取短信通道失败");
  return body.data as { configured: boolean; dryRun: boolean; baseUrl: string };
}

async function sendSmsRequest(payload: {
  mobile: string;
  content: string;
  prefix: string;
  contactIds?: string[];
}) {
  const response = await fetch(apiUrl("/api/sms/send/"), {
    method: "POST",
    credentials: "include",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (response.status === 401) throw new AuthExpiredError();
  const body = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(body.detail || "发送失败");
  return body.data as { record: SmsRecord; mode: string; taggedContacts: number };
}

export function SmsPanel({
  data,
  applyData,
  onNotice,
  can,
  currentUser,
  draftContacts,
  onDraftConsumed,
}: {
  data: AppData;
  applyData: (data: AppData) => void;
  onNotice: (notice: { type: "success" | "error"; message: string }) => void;
  can: CanAccess;
  currentUser: User;
  draftContacts?: LibraryContact[];
  onDraftConsumed?: () => void;
}) {
  const canManage = can("sms.manage");
  const [tab, setTab] = useState<"records" | "templates">("records");
  const [search, setSearch] = useState("");
  const debouncedSearch = useDebounced(search);
  const [page, setPage] = useState(1);
  const [items, setItems] = useState<SmsRecord[]>([]);
  const [templates, setTemplates] = useState<SmsTemplate[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(false);
  const [reloadTick, setReloadTick] = useState(0);
  const [channel, setChannel] = useState<{ configured: boolean; dryRun: boolean; baseUrl: string } | null>(null);

  const [sendOpen, setSendOpen] = useState(false);
  const [mobile, setMobile] = useState("");
  const [prefix, setPrefix] = useState("壹知产");
  const [content, setContent] = useState("");
  const [contactIds, setContactIds] = useState<string[]>([]);
  const [templateId, setTemplateId] = useState("");
  const [templateName, setTemplateName] = useState("");
  const [sending, setSending] = useState(false);

  const [templateModal, setTemplateModal] = useState<"create" | "edit" | null>(null);
  const [editingTemplate, setEditingTemplate] = useState<SmsTemplate | null>(null);
  const [templateForm, setTemplateForm] = useState({ name: "", content: "", prefix: "壹知产" });
  const [savingTemplate, setSavingTemplate] = useState(false);

  useEffect(() => {
    setPage(1);
  }, [debouncedSearch, tab]);

  useEffect(() => {
    void fetchSmsStatus()
      .then(setChannel)
      .catch((error) => {
        if (error instanceof AuthExpiredError) return;
      });
  }, [reloadTick]);

  useEffect(() => {
    if (!draftContacts?.length) return;
    setSendOpen(true);
    setMobile(draftContacts.map((item) => item.mobile).filter(Boolean).join(","));
    setContactIds(draftContacts.map((item) => item.id));
    onDraftConsumed?.();
  }, [draftContacts, onDraftConsumed]);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    if (tab === "records") {
      void queryCollection<SmsRecord>("smsRecords", {
        page,
        pageSize: PAGE_SIZE,
        search: debouncedSearch,
      })
        .then((result) => {
          if (cancelled) return;
          setItems(result.items);
          setTotal(result.total);
        })
        .catch((error) => {
          if (cancelled || error instanceof AuthExpiredError) return;
          onNotice({ type: "error", message: error instanceof Error ? error.message : "短信记录加载失败" });
        })
        .finally(() => {
          if (!cancelled) setLoading(false);
        });
    } else {
      void queryCollection<SmsTemplate>("smsTemplates", {
        page: 1,
        pageSize: 100,
        search: debouncedSearch,
      })
        .then((result) => {
          if (cancelled) return;
          setTemplates(result.items);
          setTotal(result.total);
        })
        .catch((error) => {
          if (cancelled || error instanceof AuthExpiredError) return;
          onNotice({ type: "error", message: error instanceof Error ? error.message : "模板加载失败" });
        })
        .finally(() => {
          if (!cancelled) setLoading(false);
        });
    }
    return () => {
      cancelled = true;
    };
  }, [tab, page, debouncedSearch, reloadTick, data.smsRecords, data.smsTemplates, onNotice]);

  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE));
  const remnant = Math.max(0, 100 - content.length);

  function openSend() {
    setSendOpen(true);
    setMobile("");
    setContactIds([]);
    setContent("");
    setPrefix("壹知产");
    setTemplateId("");
    setTemplateName("");
  }

  function applyTemplate(id: string) {
    setTemplateId(id);
    const item = templates.find((row) => row.id === id) || data.smsTemplates.find((row) => row.id === id);
    if (!item) {
      setContent("");
      setTemplateName("");
      return;
    }
    setContent(item.content || "");
    setPrefix(item.prefix || "壹知产");
    setTemplateName(item.name || "");
  }

  async function ensureTemplatesLoaded() {
    if (templates.length > 0) return templates;
    const result = await queryCollection<SmsTemplate>("smsTemplates", { page: 1, pageSize: 100, search: "" });
    setTemplates(result.items);
    return result.items;
  }

  async function saveTemplateFromSend() {
    if (!content.trim() || !templateName.trim()) {
      onNotice({ type: "error", message: "请填写模板名称和内容" });
      return;
    }
    try {
      const payload: SmsTemplate = {
        id: templateId || createId("smt"),
        name: templateName.trim(),
        content: content.trim(),
        prefix: prefix.trim() || "壹知产",
        createdAt: new Date().toISOString(),
        updatedAt: new Date().toISOString(),
      };
      const saved = templateId
        ? await patchCollectionItem<SmsTemplate>("smsTemplates", templateId, payload)
        : await createCollectionItem<SmsTemplate>("smsTemplates", payload);
      applyData({
        ...data,
        smsTemplates: data.smsTemplates.some((row) => row.id === saved.id)
          ? data.smsTemplates.map((row) => (row.id === saved.id ? saved : row))
          : [saved, ...data.smsTemplates],
      });
      setTemplateId(saved.id);
      setReloadTick((value) => value + 1);
      onNotice({ type: "success", message: "模板已保存" });
    } catch (error) {
      if (error instanceof AuthExpiredError) return;
      onNotice({ type: "error", message: error instanceof Error ? error.message : "保存模板失败" });
    }
  }

  async function submitSend() {
    if (!mobile.trim() || !content.trim()) {
      onNotice({ type: "error", message: "请补全短信信息" });
      return;
    }
    setSending(true);
    try {
      const result = await sendSmsRequest({
        mobile: mobile.trim(),
        content: content.trim(),
        prefix: prefix.trim(),
        contactIds,
      });
      applyData({
        ...data,
        smsRecords: [result.record, ...data.smsRecords],
      });
      setSendOpen(false);
      setReloadTick((value) => value + 1);
      const modeText = result.mode === "center" ? "已发送" : "已记录（本地/未对接）";
      onNotice({
        type: "success",
        message: `${modeText}${result.taggedContacts ? `，已标记 ${result.taggedContacts} 条资料` : ""}`,
      });
    } catch (error) {
      if (error instanceof AuthExpiredError) return;
      onNotice({ type: "error", message: error instanceof Error ? error.message : "发送失败" });
    } finally {
      setSending(false);
    }
  }

  async function saveTemplate() {
    if (!templateForm.name.trim() || !templateForm.content.trim()) {
      onNotice({ type: "error", message: "请填写模板名称和内容" });
      return;
    }
    setSavingTemplate(true);
    try {
      const payload: SmsTemplate = {
        id: editingTemplate?.id || createId("smt"),
        name: templateForm.name.trim(),
        content: templateForm.content.trim(),
        prefix: templateForm.prefix.trim() || "壹知产",
        createdAt: editingTemplate?.createdAt || new Date().toISOString(),
        updatedAt: new Date().toISOString(),
      };
      const saved = editingTemplate
        ? await patchCollectionItem<SmsTemplate>("smsTemplates", editingTemplate.id, payload)
        : await createCollectionItem<SmsTemplate>("smsTemplates", payload);
      applyData({
        ...data,
        smsTemplates: data.smsTemplates.some((row) => row.id === saved.id)
          ? data.smsTemplates.map((row) => (row.id === saved.id ? saved : row))
          : [saved, ...data.smsTemplates],
      });
      setEditingTemplate(null);
      setTemplateModal(null);
      setTemplateForm({ name: "", content: "", prefix: "壹知产" });
      setReloadTick((value) => value + 1);
      onNotice({ type: "success", message: "模板已保存" });
    } catch (error) {
      if (error instanceof AuthExpiredError) return;
      onNotice({ type: "error", message: error instanceof Error ? error.message : "保存失败" });
    } finally {
      setSavingTemplate(false);
    }
  }

  async function removeTemplate(item: SmsTemplate) {
    if (!window.confirm(`确认删除模板「${item.name}」？`)) return;
    try {
      await deleteCollectionItem("smsTemplates", item.id);
      applyData({ ...data, smsTemplates: data.smsTemplates.filter((row) => row.id !== item.id) });
      setReloadTick((value) => value + 1);
      onNotice({ type: "success", message: "已删除模板" });
    } catch (error) {
      if (error instanceof AuthExpiredError) return;
      onNotice({ type: "error", message: error instanceof Error ? error.message : "删除失败" });
    }
  }

  return (
    <div className="stack">
      <div className="panel">
        <div className="panel-title action-title">
          <div>
            <h2>短信管理</h2>
            <p>
              独立查看发送记录与模板；通道
              {channel == null
                ? "读取中…"
                : channel.configured
                  ? channel.dryRun
                    ? "已配置（dry-run）"
                    : `已对接 ${channel.baseUrl}`
                  : "未配置（本地记录，设置 CENTER_SMS_BASE_URL 后对接）"}
              。
            </p>
          </div>
          <div className="panel-title-buttons">
            <div className="segmented">
              <button className={tab === "records" ? "active" : ""} onClick={() => setTab("records")}>
                发送记录
              </button>
              <button className={tab === "templates" ? "active" : ""} onClick={() => setTab("templates")}>
                模板
              </button>
            </div>
            {canManage && (
              <button
                className="primary"
                onClick={() => {
                  if (tab === "templates") {
                    setEditingTemplate(null);
                    setTemplateForm({ name: "", content: "", prefix: "壹知产" });
                    setTemplateModal("create");
                  } else {
                    void ensureTemplatesLoaded().then(() => openSend());
                  }
                }}
              >
                <MessageCircle size={16} />
                {tab === "templates" ? "新增模板" : "发送短信"}
              </button>
            )}
          </div>
        </div>

        <div className="platform-account-toolbar">
          <SearchField
            value={search}
            onChange={setSearch}
            placeholder={tab === "records" ? "搜索手机号、内容、任务号…" : "搜索模板名称、内容…"}
          />
        </div>

        {tab === "records" ? (
          <>
            <div className="table">
              <div className="table-row sms-table head">
                <span>任务号</span>
                <span>手机号</span>
                <span>内容</span>
                <span>类型</span>
                <span>结果</span>
                <span>剩余</span>
                <span>发送时间</span>
              </div>
              {items.map((item) => (
                <div className="table-row sms-table" key={item.id}>
                  <span>{item.taskId || "—"}</span>
                  <span>
                    <CopyableLine text={item.mobile} label="手机号">
                      {item.mobile}
                    </CopyableLine>
                  </span>
                  <span className="sms-content-cell">{item.content}</span>
                  <span>{item.type || "—"}</span>
                  <span>{item.result || "—"}</span>
                  <span>{item.balance === "" || item.balance == null ? "—" : String(item.balance)}</span>
                  <span>
                    {formatTime(item.createdAt)}
                    <em>{item.createdBy || ""}</em>
                  </span>
                </div>
              ))}
              {items.length === 0 && <div className="table-empty">{loading ? "加载中…" : "暂无发送记录"}</div>}
            </div>
            <Pagination page={page} totalPages={totalPages} total={total} pageSize={PAGE_SIZE} onPageChange={setPage} />
          </>
        ) : (
          <div className="table">
            <div className="table-row sms-template-table head">
              <span>名称</span>
              <span>前缀</span>
              <span>内容</span>
              <span>更新</span>
              <span>操作</span>
            </div>
            {templates.map((item) => (
              <div className="table-row sms-template-table" key={item.id}>
                <span>
                  <CopyableLine text={item.name} label="模板名称">
                    <strong>{item.name}</strong>
                  </CopyableLine>
                </span>
                <span>{item.prefix || "—"}</span>
                <span className="sms-content-cell">{item.content}</span>
                <span>{formatTime(item.updatedAt || item.createdAt)}</span>
                <span className="option-actions">
                  {canManage && (
                    <>
                      <button
                        className="copy-link"
                        onClick={() => {
                          setEditingTemplate(item);
                          setTemplateForm({
                            name: item.name,
                            content: item.content,
                            prefix: item.prefix || "壹知产",
                          });
                          setTemplateModal("edit");
                        }}
                      >
                        编辑
                      </button>
                      <button className="copy-link danger-action" onClick={() => void removeTemplate(item)}>
                        删除
                      </button>
                    </>
                  )}
                </span>
              </div>
            ))}
            {templates.length === 0 && <div className="table-empty">{loading ? "加载中…" : "暂无模板"}</div>}
          </div>
        )}
      </div>

      {sendOpen && (
        <div className="modal-backdrop" role="presentation" onClick={() => setSendOpen(false)}>
          <div className="modal" role="dialog" aria-modal="true" aria-label="发送短信" onClick={(event) => event.stopPropagation()}>
            <div className="modal-head">
              <div>
                <h3>发送短信</h3>
                <p>群发手机号用逗号分隔；未配置 center 时写入本地发送记录。</p>
              </div>
              <button className="icon-button" onClick={() => setSendOpen(false)} aria-label="关闭">
                <X size={18} />
              </button>
            </div>
            <div className="form-grid official-form-grid">
              <label className="full">
                <span>接收人</span>
                <input value={mobile} onChange={(event) => setMobile(event.target.value)} placeholder="群发请使用逗号隔开" />
              </label>
              <label>
                <span>模板</span>
                <select
                  value={templateId}
                  onChange={(event) => applyTemplate(event.target.value)}
                  onFocus={() => void ensureTemplatesLoaded()}
                >
                  <option value="">不使用模板</option>
                  {(templates.length ? templates : data.smsTemplates).map((item) => (
                    <option key={item.id} value={item.id}>
                      {item.name}
                    </option>
                  ))}
                </select>
              </label>
              <label>
                <span>模板名称</span>
                <input value={templateName} onChange={(event) => setTemplateName(event.target.value)} placeholder="保存模板时使用" />
              </label>
              <label>
                <span>前缀</span>
                <input value={prefix} onChange={(event) => setPrefix(event.target.value)} />
              </label>
              <label className="full">
                <span>内容（剩余 {remnant}）</span>
                <textarea
                  rows={5}
                  maxLength={100}
                  value={content}
                  onChange={(event) => setContent(event.target.value)}
                  placeholder="请输入短信内容"
                />
              </label>
              <div className="full form-hint">
                预览：{prefix ? `【${prefix}】` : ""}
                {content || "（空）"}
              </div>
            </div>
            <div className="modal-actions">
              <button onClick={() => setSendOpen(false)}>取消</button>
              {canManage && <button onClick={() => void saveTemplateFromSend()}>保存模板</button>}
              <button className="primary" disabled={sending} onClick={() => void submitSend()}>
                {sending ? "发送中…" : "发送"}
              </button>
            </div>
          </div>
        </div>
      )}

      {templateModal && (
        <div
          className="modal-backdrop"
          role="presentation"
          onClick={() => {
            setTemplateModal(null);
            setEditingTemplate(null);
          }}
        >
          <div className="modal" role="dialog" aria-modal="true" aria-label="短信模板" onClick={(event) => event.stopPropagation()}>
            <div className="modal-head">
              <div>
                <h3>{templateModal === "edit" ? "编辑模板" : "新增模板"}</h3>
                <p>模板可供资料库与短信页快速套用。</p>
              </div>
              <button
                className="icon-button"
                onClick={() => {
                  setTemplateModal(null);
                  setEditingTemplate(null);
                }}
                aria-label="关闭"
              >
                <X size={18} />
              </button>
            </div>
            <div className="form-grid official-form-grid">
              <label>
                <span>名称</span>
                <input value={templateForm.name} onChange={(event) => setTemplateForm({ ...templateForm, name: event.target.value })} />
              </label>
              <label>
                <span>前缀</span>
                <input value={templateForm.prefix} onChange={(event) => setTemplateForm({ ...templateForm, prefix: event.target.value })} />
              </label>
              <label className="full">
                <span>内容</span>
                <textarea
                  rows={5}
                  maxLength={100}
                  value={templateForm.content}
                  onChange={(event) => setTemplateForm({ ...templateForm, content: event.target.value })}
                />
              </label>
            </div>
            <div className="modal-actions">
              <button
                onClick={() => {
                  setTemplateModal(null);
                  setEditingTemplate(null);
                }}
              >
                取消
              </button>
              <button className="primary" disabled={savingTemplate} onClick={() => void saveTemplate()}>
                {savingTemplate ? "保存中…" : "保存"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
