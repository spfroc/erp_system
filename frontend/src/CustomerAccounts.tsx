import { useEffect, useState } from "react";
import { X } from "lucide-react";
import { createCollectionItem, createId, patchCollectionItem, queryCollection, AuthExpiredError } from "./db";
import { CopyableLine, Pagination, SearchField } from "./listUi";
import type { PermissionKey } from "./types";

type CanAccess = (permission: PermissionKey) => boolean;

const PAGE_SIZE = 20;

export const PORTAL_PERMISSION_OPTIONS = [
  { id: "portal.notice.view", label: "公告列表", hint: "登录后可检索、筛选已采集公告" },
  { id: "portal.stats.view", label: "数据统计", hint: "查看总量、平台分布、成交标签分析与近两周趋势" },
  { id: "portal.notice.subscribe", label: "订阅消息", hint: "按关键词保存订阅（短信发送后续开通）" },
] as const;

export const PORTAL_SITE_OPTIONS = [
  { id: "sd-ggzyjyzx", label: "山东网上商城" },
  { id: "jd-quan-yicai", label: "京东泉易采" },
  { id: "jd-qing-huicai", label: "京东青慧采" },
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
  /** null/undefined = 不限制；[] = 无平台；有值 = 白名单 */
  allowedSiteIds?: string[] | null;
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
  siteScope: "all" as "all" | "limited",
  allowedSiteIds: [] as string[],
};

function siteScopeLabel(item: CustomerAccount) {
  if (item.allowedSiteIds == null) return "全部平台";
  if (item.allowedSiteIds.length === 0) return "无平台";
  const labels = PORTAL_SITE_OPTIONS.filter((site) => item.allowedSiteIds?.includes(site.id)).map((site) => site.label);
  return labels.length ? labels.join("、") : `${item.allowedSiteIds.length} 个平台`;
}

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
    const limited = Array.isArray(item.allowedSiteIds);
    setForm({
      name: item.name,
      phone: item.phone,
      password: "",
      customerName: item.customerName || "",
      status: item.status,
      permissions: item.permissions || [],
      siteScope: limited ? "limited" : "all",
      allowedSiteIds: limited ? [...(item.allowedSiteIds || [])] : PORTAL_SITE_OPTIONS.map((site) => site.id),
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

  function toggleSite(id: string) {
    setForm((current) => ({
      ...current,
      allowedSiteIds: current.allowedSiteIds.includes(id)
        ? current.allowedSiteIds.filter((item) => item !== id)
        : [...current.allowedSiteIds, id],
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
        allowedSiteIds: form.siteScope === "all" ? null : form.allowedSiteIds,
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
            <p>统计平台（portal.qlyc.co）客户账号。可配置门户模块与可查看采集平台，未勾选的接口也会拒绝。</p>
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
            <span>可查看平台</span>
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
              <span>{siteScopeLabel(item)}</span>
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
            <div className="form-grid customer-account-form">
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
              <fieldset className="portal-permission-fieldset">
                <legend>统计平台权限</legend>
                {PORTAL_PERMISSION_OPTIONS.map((option) => (
                  <label key={option.id} className="portal-permission-option">
                    <input
                      type="checkbox"
                      checked={form.permissions.includes(option.id)}
                      onChange={() => togglePermission(option.id)}
                    />
                    <span>
                      <strong>{option.label}</strong>
                      <em>{option.hint}</em>
                    </span>
                  </label>
                ))}
              </fieldset>
              <fieldset className="portal-permission-fieldset">
                <legend>可查看平台</legend>
                <label className="portal-permission-option">
                  <input
                    type="radio"
                    name="siteScope"
                    checked={form.siteScope === "all"}
                    onChange={() => setForm({ ...form, siteScope: "all" })}
                  />
                  <span>
                    <strong>不限制（全部平台）</strong>
                    <em>未配置白名单时与现网一致，可查看全部采集站点</em>
                  </span>
                </label>
                <label className="portal-permission-option">
                  <input
                    type="radio"
                    name="siteScope"
                    checked={form.siteScope === "limited"}
                    onChange={() =>
                      setForm({
                        ...form,
                        siteScope: "limited",
                        allowedSiteIds: form.allowedSiteIds.length ? form.allowedSiteIds : PORTAL_SITE_OPTIONS.map((site) => site.id),
                      })
                    }
                  />
                  <span>
                    <strong>限制可查看平台</strong>
                    <em>仅统计与列表可见勾选的采集站点；全部不勾选则无数据</em>
                  </span>
                </label>
                {form.siteScope === "limited" &&
                  PORTAL_SITE_OPTIONS.map((site) => (
                    <label key={site.id} className="portal-permission-option">
                      <input type="checkbox" checked={form.allowedSiteIds.includes(site.id)} onChange={() => toggleSite(site.id)} />
                      <span>
                        <strong>{site.label}</strong>
                        <em>{site.id}</em>
                      </span>
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
