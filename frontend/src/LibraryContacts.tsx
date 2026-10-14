import { useEffect, useState } from "react";
import { BookUser, X } from "lucide-react";
import { createCollectionItem, createId, deleteCollectionItem, patchCollectionItem, queryCollection, AuthExpiredError } from "./db";
import { CopyableLine, Pagination, SearchField } from "./listUi";
import type {
  AppData,
  LibraryContact,
  LibraryContactType,
  LibraryOrigin,
  LibrarySigned,
  PermissionKey,
  User,
} from "./types";

type CanAccess = (permission: PermissionKey) => boolean;

const PAGE_SIZE = 20;
const SIGNED_OPTIONS: Array<LibrarySigned | "全部"> = ["全部", "有效", "已签约", "无效"];
const TYPE_OPTIONS: LibraryContactType[] = ["超市电商", "定点供应商", "代理商", "经销商", "超市厂商", "其他"];
const ORIGIN_OPTIONS: LibraryOrigin[] = [
  "百度",
  "公共资源",
  "招投标",
  "齐鲁云采",
  "青岛政采",
  "烟台政采",
  "滨州政采",
  "菏泽政采",
  "其他",
];

const emptyForm = {
  name: "",
  legalPerson: "",
  mobile: "",
  email: "",
  licenseCode: "",
  address: "",
  province: "山东省",
  city: "济南市",
  origin: "其他" as LibraryOrigin,
  signed: "有效" as LibrarySigned,
  type: "其他" as LibraryContactType,
  tags: "",
  sellUserId: "",
};

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

export function LibraryContactsPanel({
  data,
  applyData,
  onNotice,
  can,
  currentUser,
  onSendSms,
}: {
  data: AppData;
  applyData: (data: AppData) => void;
  onNotice: (notice: { type: "success" | "error"; message: string }) => void;
  can: CanAccess;
  currentUser: User;
  onSendSms?: (contacts: LibraryContact[]) => void;
}) {
  const canManage = can("library.manage");
  const canSms = can("sms.manage");
  const [search, setSearch] = useState("");
  const [signedFilter, setSignedFilter] = useState<LibrarySigned | "全部">("全部");
  const debouncedSearch = useDebounced(search);
  const [page, setPage] = useState(1);
  const [items, setItems] = useState<LibraryContact[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(false);
  const [reloadTick, setReloadTick] = useState(0);
  const [selected, setSelected] = useState<Record<string, boolean>>({});
  const [editing, setEditing] = useState<LibraryContact | null>(null);
  const [creating, setCreating] = useState(false);
  const [form, setForm] = useState(emptyForm);
  const [saving, setSaving] = useState(false);

  const salesUsers = data.users.filter((user) => user.status === "启用");

  useEffect(() => {
    setPage(1);
  }, [debouncedSearch, signedFilter]);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    void queryCollection<LibraryContact>("libraryContacts", {
      page,
      pageSize: PAGE_SIZE,
      search: debouncedSearch,
      filters: { signed: signedFilter === "全部" ? undefined : signedFilter },
    })
      .then((result) => {
        if (cancelled) return;
        setItems(result.items);
        setTotal(result.total);
      })
      .catch((error) => {
        if (cancelled || error instanceof AuthExpiredError) return;
        onNotice({ type: "error", message: error instanceof Error ? error.message : "资料库加载失败" });
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [page, debouncedSearch, signedFilter, reloadTick, data.libraryContacts, onNotice]);

  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE));

  function openCreate() {
    setCreating(true);
    setEditing(null);
    setForm({ ...emptyForm, sellUserId: currentUser.id });
  }

  function openEdit(item: LibraryContact) {
    setEditing(item);
    setCreating(false);
    setForm({
      name: item.name || "",
      legalPerson: item.legalPerson || "",
      mobile: item.mobile || "",
      email: item.email || "",
      licenseCode: item.licenseCode || "",
      address: item.address || "",
      province: item.province || "山东省",
      city: item.city || "济南市",
      origin: item.origin || "其他",
      signed: item.signed || "有效",
      type: item.type || "其他",
      tags: (item.tags || []).join(","),
      sellUserId: item.sellUserId || "",
    });
  }

  function closeModal() {
    setCreating(false);
    setEditing(null);
    setForm(emptyForm);
  }

  function buildPayload(id: string, createdAt?: string): LibraryContact {
    const sell = salesUsers.find((user) => user.id === form.sellUserId);
    return {
      id,
      name: form.name.trim(),
      legalPerson: form.legalPerson.trim() || undefined,
      mobile: form.mobile.trim(),
      email: form.email.trim() || undefined,
      licenseCode: form.licenseCode.trim() || undefined,
      address: form.address.trim() || undefined,
      province: form.province.trim() || undefined,
      city: form.city.trim() || undefined,
      origin: form.origin,
      signed: form.signed,
      type: form.type,
      tags: form.tags
        .split(/[,，]/)
        .map((item) => item.trim())
        .filter(Boolean),
      sellUserId: form.sellUserId || undefined,
      sellUserName: sell?.name,
      communicationRecords: editing?.communicationRecords || [],
      createdAt: createdAt || new Date().toISOString(),
      updatedAt: new Date().toISOString(),
    };
  }

  async function save() {
    if (!form.name.trim() || !form.mobile.trim()) {
      onNotice({ type: "error", message: "请填写公司名称和手机号" });
      return;
    }
    setSaving(true);
    try {
      if (editing) {
        const payload = buildPayload(editing.id, editing.createdAt);
        const saved = await patchCollectionItem<LibraryContact>("libraryContacts", editing.id, payload);
        applyData({
          ...data,
          libraryContacts: data.libraryContacts.some((row) => row.id === saved.id)
            ? data.libraryContacts.map((row) => (row.id === saved.id ? saved : row))
            : [saved, ...data.libraryContacts],
        });
        onNotice({ type: "success", message: "已更新资料" });
      } else {
        const payload = buildPayload(createId("lib"));
        const saved = await createCollectionItem<LibraryContact>("libraryContacts", payload);
        applyData({ ...data, libraryContacts: [saved, ...data.libraryContacts] });
        onNotice({ type: "success", message: "已新增资料" });
      }
      closeModal();
      setReloadTick((value) => value + 1);
    } catch (error) {
      if (error instanceof AuthExpiredError) return;
      onNotice({ type: "error", message: error instanceof Error ? error.message : "保存失败" });
    } finally {
      setSaving(false);
    }
  }

  async function remove(item: LibraryContact) {
    if (!window.confirm(`确认删除「${item.name}」？`)) return;
    try {
      await deleteCollectionItem("libraryContacts", item.id);
      applyData({ ...data, libraryContacts: data.libraryContacts.filter((row) => row.id !== item.id) });
      setSelected((prev) => {
        const next = { ...prev };
        delete next[item.id];
        return next;
      });
      onNotice({ type: "success", message: "已删除" });
      setReloadTick((value) => value + 1);
    } catch (error) {
      if (error instanceof AuthExpiredError) return;
      onNotice({ type: "error", message: error instanceof Error ? error.message : "删除失败" });
    }
  }

  const selectedContacts = items.filter((item) => selected[item.id]);

  return (
    <div className="stack">
      <div className="panel">
        <div className="panel-title action-title">
          <div>
            <h2>资料库</h2>
            <p>维护客户公司、联系人与跟进标签；可勾选后发送短信。</p>
          </div>
          <div className="panel-title-buttons">
            {canSms && selectedContacts.length > 0 && (
              <button className="primary" onClick={() => onSendSms?.(selectedContacts)}>
                发送短信（{selectedContacts.length}）
              </button>
            )}
            {canManage && (
              <button className="primary" onClick={openCreate}>
                <BookUser size={16} />
                新增资料
              </button>
            )}
          </div>
        </div>

        <div className="platform-account-toolbar">
          <SearchField value={search} onChange={setSearch} placeholder="搜索公司、手机号、执照、标签…" />
        </div>

        <div className="segmented">
          {SIGNED_OPTIONS.map((item) => (
            <button key={item} className={signedFilter === item ? "active" : ""} onClick={() => setSignedFilter(item)}>
              {item}
            </button>
          ))}
        </div>

        <div className="table">
          <div className="table-row library-table head">
            <span>{canSms ? "选" : "#"}</span>
            <span>公司/法人</span>
            <span>手机号</span>
            <span>类型/来源</span>
            <span>状态</span>
            <span>负责人</span>
            <span>标签</span>
            <span>更新</span>
            <span>操作</span>
          </div>
          {items.map((item) => (
            <div className="table-row library-table" key={item.id}>
              <span>
                {canSms ? (
                  <input
                    type="checkbox"
                    checked={Boolean(selected[item.id])}
                    onChange={(event) => setSelected((prev) => ({ ...prev, [item.id]: event.target.checked }))}
                    aria-label={`选择 ${item.name}`}
                  />
                ) : (
                  "·"
                )}
              </span>
              <span className="library-main-cell">
                <CopyableLine text={item.name} label="公司名称">
                  <strong>{item.name}</strong>
                </CopyableLine>
                <em>{item.legalPerson || "未填法人"}{item.licenseCode ? ` / ${item.licenseCode}` : ""}</em>
              </span>
              <span>
                <CopyableLine text={item.mobile} label="手机号">
                  {item.mobile || "—"}
                </CopyableLine>
              </span>
              <span>
                {item.type}
                <em>{item.origin}</em>
              </span>
              <span>{item.signed}</span>
              <span>{item.sellUserName || "—"}</span>
              <span>{(item.tags || []).join("、") || "—"}</span>
              <span>{formatTime(item.updatedAt || item.createdAt)}</span>
              <span className="option-actions">
                {canSms && (
                  <button className="copy-link" onClick={() => onSendSms?.([item])}>
                    短信
                  </button>
                )}
                {canManage && (
                  <>
                    <button className="copy-link" onClick={() => openEdit(item)}>
                      编辑
                    </button>
                    <button className="copy-link danger-action" onClick={() => void remove(item)}>
                      删除
                    </button>
                  </>
                )}
              </span>
            </div>
          ))}
          {items.length === 0 && <div className="table-empty">{loading ? "加载中…" : "暂无数据"}</div>}
        </div>

        <Pagination page={page} totalPages={totalPages} total={total} pageSize={PAGE_SIZE} onPageChange={setPage} />
      </div>

      {(creating || editing) && (
        <div className="modal-backdrop" role="presentation" onClick={closeModal}>
          <div className="modal" role="dialog" aria-modal="true" aria-label={editing ? "编辑资料" : "新增资料"} onClick={(event) => event.stopPropagation()}>
            <div className="modal-head">
              <div>
                <h3>{editing ? "编辑资料" : "新增资料"}</h3>
                <p>对齐原资料库字段：公司、法人、手机号、执照、省市、来源与状态。</p>
              </div>
              <button className="icon-button" onClick={closeModal} aria-label="关闭">
                <X size={18} />
              </button>
            </div>
            <div className="form-grid official-form-grid">
              <label>
                <span>公司名称</span>
                <input value={form.name} onChange={(event) => setForm({ ...form, name: event.target.value })} />
              </label>
              <label>
                <span>法人</span>
                <input value={form.legalPerson} onChange={(event) => setForm({ ...form, legalPerson: event.target.value })} />
              </label>
              <label>
                <span>手机号</span>
                <input value={form.mobile} onChange={(event) => setForm({ ...form, mobile: event.target.value })} />
              </label>
              <label>
                <span>邮箱</span>
                <input value={form.email} onChange={(event) => setForm({ ...form, email: event.target.value })} />
              </label>
              <label>
                <span>执照编号</span>
                <input value={form.licenseCode} onChange={(event) => setForm({ ...form, licenseCode: event.target.value })} />
              </label>
              <label>
                <span>负责人</span>
                <select value={form.sellUserId} onChange={(event) => setForm({ ...form, sellUserId: event.target.value })}>
                  <option value="">未指定</option>
                  {salesUsers.map((user) => (
                    <option key={user.id} value={user.id}>
                      {user.name}
                    </option>
                  ))}
                </select>
              </label>
              <label>
                <span>类型</span>
                <select value={form.type} onChange={(event) => setForm({ ...form, type: event.target.value as LibraryContactType })}>
                  {TYPE_OPTIONS.map((item) => (
                    <option key={item}>{item}</option>
                  ))}
                </select>
              </label>
              <label>
                <span>来源</span>
                <select value={form.origin} onChange={(event) => setForm({ ...form, origin: event.target.value as LibraryOrigin })}>
                  {ORIGIN_OPTIONS.map((item) => (
                    <option key={item}>{item}</option>
                  ))}
                </select>
              </label>
              <label>
                <span>状态</span>
                <select value={form.signed} onChange={(event) => setForm({ ...form, signed: event.target.value as LibrarySigned })}>
                  {SIGNED_OPTIONS.filter((item) => item !== "全部").map((item) => (
                    <option key={item}>{item}</option>
                  ))}
                </select>
              </label>
              <label>
                <span>省份</span>
                <input value={form.province} onChange={(event) => setForm({ ...form, province: event.target.value })} />
              </label>
              <label>
                <span>城市</span>
                <input value={form.city} onChange={(event) => setForm({ ...form, city: event.target.value })} />
              </label>
              <label className="full">
                <span>地址</span>
                <input value={form.address} onChange={(event) => setForm({ ...form, address: event.target.value })} />
              </label>
              <label className="full">
                <span>标签</span>
                <input value={form.tags} onChange={(event) => setForm({ ...form, tags: event.target.value })} placeholder="逗号分隔，如 已短信,重点" />
              </label>
            </div>
            <div className="modal-actions">
              <button onClick={closeModal}>取消</button>
              <button className="primary" disabled={saving} onClick={() => void save()}>
                {saving ? "保存中…" : "保存"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
