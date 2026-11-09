import { useEffect, useMemo, useState } from "react";
import { X } from "lucide-react";
import { SearchableSelect } from "./App";
import { createCollectionItem, createId, patchCollectionItem, queryCollection, AuthExpiredError } from "./db";
import { CopyableLine, Pagination, SearchField } from "./listUi";
import type { Organization, PermissionKey } from "./types";

type CanAccess = (permission: PermissionKey) => boolean;

function apiUrl(path: string) {
  const url = new URL(path, window.location.origin);
  if (import.meta.env.DEV) url.port = "8000";
  return url.toString();
}

export const PORTAL_PERMISSION_OPTIONS = [
  { id: "portal.notice.view", label: "公告列表", hint: "登录后可检索、筛选已采集公告" },
  { id: "portal.stats.view", label: "数据统计", hint: "查看总量、平台分布、成交标签分析与近两周趋势" },
  { id: "portal.notice.subscribe", label: "订阅消息", hint: "门户按标签/地区/关键词等订阅，微信服务号每日汇总推送" },
  { id: "portal.order.view", label: "企业订单", hint: "查看本企业销售/服务订单" },
  { id: "portal.invoice.view", label: "企业发票", hint: "查看本企业作为买方的发票" },
  { id: "portal.contract.view", label: "企业合同", hint: "查看本企业相关合同附件" },
  { id: "portal.account.view", label: "查看企业账号", hint: "查看同企业可登录门户的账号" },
  { id: "portal.account.manage", label: "管理企业账号", hint: "新增/编辑/停用同企业门户账号" },
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
  wechatBound?: boolean;
  wechatFollowStatus?: string;
  createdAt?: string;
}

function wechatStatusLabel(item: CustomerAccount) {
  if (!item.wechatBound) return "未绑定";
  if (item.wechatFollowStatus === "unsubscribed") return "已绑定（已取关）";
  return "已绑定";
}

const emptyForm = {
  name: "",
  phone: "",
  password: "",
  customerOrgId: "",
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
  organizations,
  onNotice,
  can,
}: {
  organizations: Organization[];
  onNotice: (notice: { type: "success" | "error"; message: string }) => void;
  can: CanAccess;
}) {
  const canManage = can("customerAccount.manage");
  const canManualPush = can("dev.ops.manage");
  const [search, setSearch] = useState("");
  const [status, setStatus] = useState("全部");
  const debouncedSearch = useDebounced(search);
  const [page, setPage] = useState(1);
  const [pageSize, setPageSizeState] = useState(20);
  const [items, setItems] = useState<CustomerAccount[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(false);
  const [reloadTick, setReloadTick] = useState(0);
  const setPageSize = (next: number) => {
    setPageSizeState(next);
    setPage(1);
  };
  const [editing, setEditing] = useState<CustomerAccount | null>(null);
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState(emptyForm);
  const [saving, setSaving] = useState(false);
  const [pushTarget, setPushTarget] = useState<CustomerAccount | null>(null);
  const [pushForm, setPushForm] = useState({
    project: "",
    bidTime: "",
    initiator: "",
    projectCode: "",
  });
  const [pushing, setPushing] = useState(false);

  const orgOptions = useMemo(
    () =>
      [...organizations]
        .sort((a, b) => (b.createdAt || "").localeCompare(a.createdAt || "") || a.name.localeCompare(b.name, "zh"))
        .map((org) => ({
          value: org.id,
          label: org.name,
          detail: [org.unifiedCreditCode, org.legalPerson, org.phone].filter(Boolean).join(" / "),
        })),
    [organizations],
  );

  const orgNameById = useMemo(() => {
    const map = new Map<string, string>();
    for (const org of organizations) map.set(org.id, org.name);
    return map;
  }, [organizations]);

  useEffect(() => {
    setPage(1);
  }, [debouncedSearch, status]);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    void queryCollection<CustomerAccount>("customerAccounts", {
      page,
      pageSize,
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
        setItems([]);
        setTotal(0);
        onNotice({ type: "error", message: error instanceof Error ? error.message : "客户账号加载失败" });
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [page, pageSize, debouncedSearch, status, reloadTick, onNotice]);

  const totalPages = Math.max(1, Math.ceil(total / pageSize));

  function displayCustomerName(item: CustomerAccount) {
    if (item.customerOrgId && orgNameById.get(item.customerOrgId)) {
      return orgNameById.get(item.customerOrgId) || item.customerName || "—";
    }
    return item.customerName || (item.customerOrgId ? "未匹配企业" : "未绑定企业");
  }

  function openCreate() {
    setEditing(null);
    setForm(emptyForm);
    setShowForm(true);
  }

  function openEdit(item: CustomerAccount) {
    setEditing(item);
    const limited = Array.isArray(item.allowedSiteIds);
    const orgId = item.customerOrgId || "";
    setForm({
      name: item.name,
      phone: item.phone,
      password: "",
      customerOrgId: orgId,
      customerName: (orgId && orgNameById.get(orgId)) || item.customerName || "",
      status: item.status,
      permissions: item.permissions || [],
      siteScope: limited ? "limited" : "all",
      allowedSiteIds: limited ? [...(item.allowedSiteIds || [])] : PORTAL_SITE_OPTIONS.map((site) => site.id),
    });
    setShowForm(true);
  }

  function selectOrg(orgId: string) {
    const org = organizations.find((item) => item.id === orgId);
    setForm((current) => ({
      ...current,
      customerOrgId: orgId,
      customerName: org?.name || "",
    }));
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

  function openPushForm(item: CustomerAccount) {
    if (!item.wechatBound || item.wechatFollowStatus === "unsubscribed" || item.status !== "启用") return;
    const now = new Date();
    const pad = (n: number) => String(n).padStart(2, "0");
    const stamp = `${now.getFullYear()}-${pad(now.getMonth() + 1)}-${pad(now.getDate())} ${pad(now.getHours())}:${pad(now.getMinutes())}:00`;
    setPushTarget(item);
    setPushForm({
      project: "公告订阅测试推送",
      bidTime: stamp,
      initiator: item.name || "系统",
      projectCode: `TEST-${item.id.slice(-6) || "000000"}`,
    });
  }

  async function submitPushForm() {
    if (!pushTarget) return;
    if (!pushForm.project.trim() || !pushForm.bidTime.trim() || !pushForm.initiator.trim() || !pushForm.projectCode.trim()) {
      onNotice({ type: "error", message: "请完整填写竞标项目、时间、发起人、项目编码" });
      return;
    }
    setPushing(true);
    try {
      const response = await fetch(apiUrl(`/api/customer-accounts/${encodeURIComponent(pushTarget.id)}/notice-digest/send/`), {
        method: "POST",
        credentials: "include",
        headers: { "Content-Type": "application/json", Accept: "application/json" },
        body: JSON.stringify({
          project: pushForm.project.trim(),
          bidTime: pushForm.bidTime.trim(),
          initiator: pushForm.initiator.trim(),
          projectCode: pushForm.projectCode.trim(),
        }),
      });
      if (response.status === 401) throw new AuthExpiredError();
      const body = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(body.detail || body.message || "推送失败");
      setPushTarget(null);
      onNotice({ type: "success", message: body.message || "推送成功" });
    } catch (error) {
      if (error instanceof AuthExpiredError) return;
      onNotice({ type: "error", message: error instanceof Error ? error.message : "推送失败" });
    } finally {
      setPushing(false);
    }
  }

  async function save() {
    if (!form.customerOrgId.trim()) {
      onNotice({ type: "error", message: "请选择关联客户企业" });
      return;
    }
    if (!form.name.trim() || !form.phone.trim()) {
      onNotice({ type: "error", message: "请填写账号名称和手机号" });
      return;
    }
    if (!editing && !form.password.trim()) {
      onNotice({ type: "error", message: "请设置登录密码" });
      return;
    }
    const org = organizations.find((item) => item.id === form.customerOrgId);
    const customerName = org?.name || form.customerName.trim();
    if (!customerName) {
      onNotice({ type: "error", message: "所选企业无效，请重新选择" });
      return;
    }
    setSaving(true);
    try {
      const payload: CustomerAccount & { password?: string } = {
        id: editing?.id || createId("portal-user"),
        name: form.name.trim(),
        phone: form.phone.trim(),
        customerName,
        customerOrgId: form.customerOrgId,
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
            <p>统计平台（portal.qlyc.co）客户账号。须关联客户企业；可配置门户模块与可查看采集平台。</p>
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
            <span>客户企业</span>
            <span>手机号</span>
            <span>门户权限</span>
            <span>可查看平台</span>
            <span>微信</span>
            <span>状态</span>
            <span>操作</span>
          </div>
          {items.map((item) => {
            const customerLabel = displayCustomerName(item);
            const bound = Boolean(item.customerOrgId) && customerLabel !== "未匹配企业" && customerLabel !== "未绑定企业";
            return (
            <div className="table-row customer-account-table" key={item.id}>
              <div className="customer-account-main-cell">
                <CopyableLine text={item.name} label="账号名称">
                  <strong>{item.name}</strong>
                </CopyableLine>
              </div>
              <span>
                {bound ? (
                  <CopyableLine text={customerLabel} label="客户企业">
                    {customerLabel}
                  </CopyableLine>
                ) : (
                  <em>{customerLabel}</em>
                )}
              </span>
              <span>{item.phone}</span>
              <span>{PORTAL_PERMISSION_OPTIONS.filter((option) => item.permissions?.includes(option.id)).map((option) => option.label).join("、") || "—"}</span>
              <span>{siteScopeLabel(item)}</span>
              <span>{wechatStatusLabel(item)}</span>
              <span>{item.status}</span>
              <div className="option-actions">
                {canManage && (
                  <button className="copy-link" type="button" onClick={() => openEdit(item)}>
                    编辑
                  </button>
                )}
                {canManualPush && item.wechatBound && item.wechatFollowStatus !== "unsubscribed" && item.status === "启用" && (
                  <button
                    className="copy-link"
                    type="button"
                    title="仅开发可见：按模板手动推送"
                    onClick={() => openPushForm(item)}
                  >
                    手动推送
                  </button>
                )}
              </div>
            </div>
            );
          })}
          {loading && items.length === 0 && <div className="table-empty">加载中…</div>}
          {!loading && items.length === 0 && <div className="table-empty">暂无客户账号</div>}
        </div>
        <Pagination page={page} totalPages={totalPages} total={total} pageSize={pageSize} onPageChange={setPage} onPageSizeChange={setPageSize} />
      </div>
      {pushTarget && (
        <div className="modal-backdrop" onClick={() => !pushing && setPushTarget(null)}>
          <div className="modal" onClick={(event) => event.stopPropagation()}>
            <div className="modal-head">
              <h3>手动推送微信消息</h3>
              <button className="icon-button" type="button" onClick={() => !pushing && setPushTarget(null)} aria-label="关闭">
                <X size={16} />
              </button>
            </div>
            <p className="muted" style={{ margin: "0 0 12px" }}>
              接收账号：{pushTarget.name} / {pushTarget.phone}。模板：竞标结果通知。
            </p>
            <div className="form-grid customer-account-form">
              <label className="span-12">
                竞标项目（thing1）
                <input
                  value={pushForm.project}
                  maxLength={20}
                  onChange={(event) => setPushForm({ ...pushForm, project: event.target.value })}
                  placeholder="如：办公室电脑采购竞标"
                />
              </label>
              <label className="span-12">
                竞标时间（time2）
                <input
                  value={pushForm.bidTime}
                  onChange={(event) => setPushForm({ ...pushForm, bidTime: event.target.value })}
                  placeholder="如：2023-11-17 09:01:00"
                />
              </label>
              <label>
                发起人（thing3）
                <input
                  value={pushForm.initiator}
                  maxLength={20}
                  onChange={(event) => setPushForm({ ...pushForm, initiator: event.target.value })}
                  placeholder="如：张三"
                />
              </label>
              <label>
                竞标项目编码（character_string5）
                <input
                  value={pushForm.projectCode}
                  maxLength={32}
                  onChange={(event) => setPushForm({ ...pushForm, projectCode: event.target.value })}
                  placeholder="如：PRO-20240321-001"
                />
              </label>
            </div>
            <div className="modal-actions">
              <button className="ghost" type="button" disabled={pushing} onClick={() => setPushTarget(null)}>
                取消
              </button>
              <button className="primary" type="button" disabled={pushing} onClick={() => void submitPushForm()}>
                {pushing ? "发送中…" : "确认推送"}
              </button>
            </div>
          </div>
        </div>
      )}
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
              <label className="span-12">
                客户企业
                <SearchableSelect
                  value={form.customerOrgId}
                  options={orgOptions}
                  onChange={selectOrg}
                  placeholder="输入名称、信用代码或联系人搜索"
                  ariaLabel="搜索并选择客户企业"
                />
              </label>
              <label>
                账号名称
                <input value={form.name} onChange={(event) => setForm({ ...form, name: event.target.value })} />
              </label>
              <label>
                手机号
                <input value={form.phone} onChange={(event) => setForm({ ...form, phone: event.target.value })} />
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
