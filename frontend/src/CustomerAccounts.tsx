import { useEffect, useState } from "react";
import { X } from "lucide-react";
import { createCollectionItem, createId, patchCollectionItem, queryCollection, AuthExpiredError } from "./db";
import { CopyableLine, Pagination, SearchField } from "./listUi";
import type { PermissionKey } from "./types";

type CanAccess = (permission: PermissionKey) => boolean;

const PAGE_SIZE = 20;

export const PORTAL_PERMISSION_OPTIONS = [
  { id: "portal.notice.view", label: "查看公告" },
  { id: "portal.notice.subscribe", label: "接收订阅消息" },
  { id: "portal.stats.view", label: "查看数据统计" },
] as const;

export type PortalPermission = (typeof PORTAL_PERMISSION_OPTIONS)[number]["id"];

export interface CustomerAccount {
  id: string;
  name: string;
  phone: string;
  customerName?: string;
  customerOrgId?: string;
  status: "启用" | "停用";
  permissions: PortalPermission[];
  subscription?: { enabled?: boolean; keywords?: string };
  createdAt?: string;
}

const emptyForm = {
  name: "",
  phone: "",
  password: "",
  customerName: "",
  status: "启用" as "启用" | "停用",
  permissions: ["portal.notice.view"] as PortalPermission[],
};

function useDebounced(value: string, delay = 300) {
  const [debounced, setDebounced] = useState(value);
  useEffect(() => {
    const timer = window.setTimeout(() => setDebounced(value), delay);
    return () => window.clearTimeout(timer);
  }, [value, delay]);
  return debounced;
}

export function CustomerAccountsPanel({
  onNotice,
  can,
}: {
  onNotice: (notice: { type: "success" | "error"; message: string }) => void;
  can: CanAccess;
}) {
  const canManage = can("customerAccount.manage");
  const [search, setSearch] = useState("");
  const [status, setStatus] = useState("全部");
  const debouncedSearch = useDebounced(search);
  const [page, setPage] = useState(1);
  const [items, setItems] = useState<CustomerAccount[]>([]);
  const [total, setTotal] = useState(0);
  const [reloadTick, setReloadTick] = useState(0);
  const [editing, setEditing] = useState<CustomerAccount | null>(null);
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState(emptyForm);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    setPage(1);
  }, [debouncedSearch, status]);

  useEffect(() => {
    let cancelled = false;
    void queryCollection<CustomerAccount>("customerAccounts", {
      page,
      pageSize: PAGE_SIZE,
      search: debouncedSearch,
      filters: { status },
    })
      .then((result) => {
        if (cancelled) return;
        setItems(result.items);
        setTotal(result.total);
      })
      .catch((error) => {
        if (cancelled || error instanceof AuthExpiredError) return;
        onNotice({ type: "error", message: error instanceof Error ? error.message : "客户账号加载失败" });
      });
    return () => {
      cancelled = true;
    };
  }, [page, debouncedSearch, status, reloadTick, onNotice]);

  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE));

  function openCreate() {
    setEditing(null);
    setForm(emptyForm);
    setShowForm(true);
  }

  function openEdit(item: CustomerAccount) {
    setEditing(item);
    setForm({
      name: item.name,
      phone: item.phone,
      password: "",
      customerName: item.customerName || "",
      status: item.status,
      permissions: item.permissions || [],
    });
    setShowForm(true);
  }

  function togglePermission(id: PortalPermission) {
    setForm((current) => ({
      ...current,
      permissions: current.permissions.includes(id)
        ? current.permissions.filter((item) => item !== id)
        : [...current.permissions, id],
    }));
  }

  async function save() {
    setSaving(true);
    try {
      const payload: CustomerAccount & { password?: string } = {
        id: editing?.id || createId("portal-user"),
        name: form.name.trim(),
        phone: form.phone.trim(),
        customerName: form.customerName.trim(),
        customerOrgId: editing?.customerOrgId || "",
        status: form.status,
        permissions: form.permissions,
        subscription: editing?.subscription || { enabled: form.permissions.includes("portal.notice.subscribe"), keywords: "" },
        createdAt: editing?.createdAt || new Date().toISOString(),
      };
      if (form.password.trim()) payload.password = form.password.trim();
      if (editing) await patchCollectionItem("customerAccounts", payload.id, payload);
      else await createCollectionItem("customerAccounts", payload);
      setShowForm(false);
      setReloadTick((value) => value + 1);
      onNotice({ type: "success", message: editing ? "客户账号已更新" : "客户账号已创建" });
    } catch (error) {
      if (error instanceof AuthExpiredError) return;
      onNotice({ type: "error", message: error instanceof Error ? error.message : "保存失败" });
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="stack">
      <div className="panel">
        <div className="panel-title action-title">
          <div>
            <h2>登录账号管理</h2>
            <p>官网客户控制台登录账号。与员工账号分开，权限只控制公告、订阅和统计。</p>
          </div>
          <div className="panel-title-buttons">
            {canManage && (
              <button className="primary" type="button" onClick={openCreate}>
                新增账号
              </button>
            )}
          </div>
        </div>
        <div className="platform-account-toolbar">
          <SearchField value={search} onChange={setSearch} placeholder="搜索名称、手机号、客户" />
        </div>
        <div className="segmented">
          {["全部", "启用", "停用"].map((item) => (
            <button key={item} type="button" className={status === item ? "active" : ""} onClick={() => setStatus(item)}>
              {item}
            </button>
          ))}
        </div>
        <div className="table">
          <div className="table-row customer-account-table head">
            <span>账号</span>
            <span>客户</span>
            <span>手机号</span>
            <span>门户权限</span>
            <span>状态</span>
            <span>操作</span>
          </div>
          {items.map((item) => (
            <div className="table-row customer-account-table" key={item.id}>
              <div className="customer-account-main-cell">
                <CopyableLine text={item.name} label="账号名称">
                  <strong>{item.name}</strong>
                </CopyableLine>
              </div>
              <span>{item.customerName || "—"}</span>
              <span>{item.phone}</span>
              <span>{PORTAL_PERMISSION_OPTIONS.filter((option) => item.permissions?.includes(option.id)).map((option) => option.label).join("、") || "—"}</span>
              <span>{item.status}</span>
              <div className="option-actions">
                {canManage && (
                  <button className="copy-link" type="button" onClick={() => openEdit(item)}>
                    编辑
                  </button>
                )}
              </div>
            </div>
          ))}
          {items.length === 0 && <div className="table-empty">暂无客户账号</div>}
        </div>
        <Pagination page={page} totalPages={totalPages} total={total} pageSize={PAGE_SIZE} onPageChange={setPage} />
      </div>
      {showForm && (
        <div className="modal-backdrop" onClick={() => setShowForm(false)}>
          <div className="modal" onClick={(event) => event.stopPropagation()}>
            <div className="modal-head">
              <h3>{editing ? "编辑登录账号" : "新增登录账号"}</h3>
              <button className="icon-button" type="button" onClick={() => setShowForm(false)} aria-label="关闭">
                <X size={16} />
              </button>
            </div>
            <div className="form-grid">
              <label>
                账号名称
                <input value={form.name} onChange={(event) => setForm({ ...form, name: event.target.value })} />
              </label>
              <label>
                手机号
                <input value={form.phone} onChange={(event) => setForm({ ...form, phone: event.target.value })} />
              </label>
              <label>
                客户名称
                <input value={form.customerName} onChange={(event) => setForm({ ...form, customerName: event.target.value })} />
              </label>
              <label>
                {editing ? "重置密码（留空则不改）" : "登录密码"}
                <input type="password" value={form.password} onChange={(event) => setForm({ ...form, password: event.target.value })} />
              </label>
              <label>
                状态
                <select value={form.status} onChange={(event) => setForm({ ...form, status: event.target.value as "启用" | "停用" })}>
                  <option value="启用">启用</option>
                  <option value="停用">停用</option>
                </select>
              </label>
              <fieldset>
                <legend>门户权限</legend>
                {PORTAL_PERMISSION_OPTIONS.map((option) => (
                  <label key={option.id}>
                    <input
                      type="checkbox"
                      checked={form.permissions.includes(option.id)}
                      onChange={() => togglePermission(option.id)}
                    />
                    {option.label}
                  </label>
                ))}
              </fieldset>
            </div>
            <div className="modal-actions">
              <button className="ghost" type="button" onClick={() => setShowForm(false)}>
                取消
              </button>
              <button className="primary" type="button" disabled={saving} onClick={() => void save()}>
                保存
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
