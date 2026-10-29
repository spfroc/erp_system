import { useEffect, useState } from "react";
import { X } from "lucide-react";
import { backendApiUrl } from "./apiConfig";
import { AuthExpiredError } from "./db";
import { CopyableLine, Pagination, SearchField } from "./listUi";
import type { PermissionKey, User } from "./types";

type CanAccess = (permission: PermissionKey) => boolean;

const PAGE_SIZE = 20;

const ORIGIN_OPTIONS: Array<{ value: string; label: string }> = [
  { value: "1", label: "百度" },
  { value: "2", label: "公共资源" },
  { value: "3", label: "招投标" },
  { value: "4", label: "齐鲁云采" },
  { value: "5", label: "青岛政采" },
  { value: "6", label: "烟台政采" },
  { value: "7", label: "滨州政采" },
  { value: "8", label: "菏泽政采" },
  { value: "9", label: "其他" },
  { value: "10", label: "新齐鲁云采" },
];

const SIGNED_OPTIONS: Array<{ value: string; label: string } | { value: ""; label: "全部" }> = [
  { value: "", label: "全部" },
  { value: "0", label: "有效" },
  { value: "1", label: "已签约" },
  { value: "2", label: "无效" },
];

export interface MallCustomerItem {
  id: number;
  name: string;
  platformCustomerId?: string;
  type?: string;
  address?: string;
  province?: string;
  city?: string;
  licenseCode?: string;
  enterTime?: string;
  legalPerson?: string;
  mobile?: string;
  newMobile?: string;
  email?: string;
  origin?: string;
  originLabel?: string;
  signed?: string;
  signedLabel?: string;
  tag?: string;
  sellId?: number;
  sellUserId?: string;
  sellUserName?: string;
  remark?: string;
  agentShopProductNumber?: number | null;
  onlineShopProductNumber?: number | null;
  manufacturerShopProductNumber?: number | null;
  crawledAt?: string | null;
  updatedAt?: string | null;
}

interface ListResponse {
  items: MallCustomerItem[];
  total: number;
  page: number;
  pageSize: number;
  detail?: string;
}

function useDebounced(value: string, delay = 300) {
  const [debounced, setDebounced] = useState(value);
  useEffect(() => {
    const timer = window.setTimeout(() => setDebounced(value), delay);
    return () => window.clearTimeout(timer);
  }, [value, delay]);
  return debounced;
}

function splitPhones(value?: string): string[] {
  if (!value) return [];
  return value
    .split(/[,，\s;/|]+/)
    .map((item) => item.trim())
    .filter(Boolean);
}

function formatTime(value?: string | null) {
  if (!value) return "—";
  return value.replace("T", " ").slice(0, 19);
}

function badgeCount(value?: number | null) {
  if (value == null || Number.isNaN(Number(value))) return 0;
  return Number(value);
}

async function fetchList(params: URLSearchParams): Promise<ListResponse> {
  const response = await fetch(backendApiUrl(`/api/mall-customers/?${params.toString()}`), {
    credentials: "include",
  });
  if (response.status === 401) throw new AuthExpiredError();
  const data = (await response.json()) as ListResponse;
  if (!response.ok && response.status !== 503) {
    throw new Error(data.detail || "加载资料库失败");
  }
  return data;
}

async function patchItem(id: number, payload: Record<string, unknown>): Promise<MallCustomerItem> {
  const response = await fetch(backendApiUrl(`/api/mall-customers/${id}/`), {
    method: "PATCH",
    credentials: "include",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (response.status === 401) throw new AuthExpiredError();
  const data = await response.json();
  if (!response.ok) {
    throw new Error(data.detail || "保存失败");
  }
  return data as MallCustomerItem;
}

const emptyForm = {
  name: "",
  legalPerson: "",
  mobile: "",
  newMobile: "",
  email: "",
  type: "",
  address: "",
  province: "",
  city: "",
  licenseCode: "",
  origin: "4",
  signed: "0",
  remark: "",
  enterTime: "",
};

export function MallCustomersPanel({
  onNotice,
  can,
  currentUser,
}: {
  onNotice: (notice: { type: "success" | "error"; message: string }) => void;
  can: CanAccess;
  currentUser: User;
}) {
  const canManage = can("mallCustomer.manage");
  const [search, setSearch] = useState("");
  const [signedFilter, setSignedFilter] = useState("");
  const debouncedSearch = useDebounced(search);
  const [page, setPage] = useState(1);
  const [items, setItems] = useState<MallCustomerItem[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(false);
  const [reloadTick, setReloadTick] = useState(0);
  const [editing, setEditing] = useState<MallCustomerItem | null>(null);
  const [form, setForm] = useState(emptyForm);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    setPage(1);
  }, [debouncedSearch, signedFilter]);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    const params = new URLSearchParams({
      page: String(page),
      page_size: String(PAGE_SIZE),
    });
    if (debouncedSearch) params.set("search", debouncedSearch);
    if (signedFilter) params.set("signed", signedFilter);
    void fetchList(params)
      .then((result) => {
        if (cancelled) return;
        setItems(result.items || []);
        setTotal(result.total || 0);
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
  }, [page, debouncedSearch, signedFilter, reloadTick, onNotice]);

  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE));

  function openEdit(item: MallCustomerItem) {
    setEditing(item);
    setForm({
      name: item.name || "",
      legalPerson: item.legalPerson || "",
      mobile: item.mobile || "",
      newMobile: item.newMobile || "",
      email: item.email || "",
      type: item.type || "",
      address: item.address || "",
      province: item.province || "",
      city: item.city || "",
      licenseCode: item.licenseCode || "",
      origin: (item.origin || "4").split(",")[0] || "4",
      signed: item.signed || "0",
      remark: item.remark || "",
      enterTime: item.enterTime || "",
    });
  }

  function closeModal() {
    setEditing(null);
    setForm(emptyForm);
  }

  async function save() {
    if (!editing) return;
    if (!form.name.trim()) {
      onNotice({ type: "error", message: "请填写公司名称" });
      return;
    }
    setSaving(true);
    try {
      await patchItem(editing.id, {
        name: form.name.trim(),
        legalPerson: form.legalPerson.trim(),
        mobile: form.mobile.trim(),
        newMobile: form.newMobile.trim(),
        email: form.email.trim(),
        type: form.type.trim(),
        address: form.address.trim(),
        province: form.province.trim(),
        city: form.city.trim(),
        licenseCode: form.licenseCode.trim(),
        origin: form.origin,
        signed: form.signed,
        remark: form.remark.trim(),
        enterTime: form.enterTime.trim(),
      });
      onNotice({ type: "success", message: "已更新" });
      closeModal();
      setReloadTick((value) => value + 1);
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
            <h2>资料库</h2>
            <p>展示 mall_customer（由旧 customers 导入 / 商城抓取），支持搜索与编辑。</p>
          </div>
        </div>

        <div className="platform-account-toolbar">
          <SearchField value={search} onChange={setSearch} placeholder="搜索公司、电话、法人、城市…" />
        </div>

        <div className="segmented">
          {SIGNED_OPTIONS.map((item) => (
            <button
              key={item.label}
              className={signedFilter === item.value ? "active" : ""}
              onClick={() => setSignedFilter(item.value)}
            >
              {item.label}
            </button>
          ))}
        </div>

        <div className="table">
          <div className="table-row mall-customer-table head">
            <span>公司名称</span>
            <span>联系电话</span>
            <span>新联系电话</span>
            <span>类型</span>
            <span>状态</span>
            <span>操作</span>
            <span>来源</span>
          </div>
          {items.map((item) => {
            const mobiles = splitPhones(item.mobile);
            const newMobiles = splitPhones(item.newMobile);
            const licenseCode = (item.licenseCode || "").trim();
            const email = (item.email || "").trim();
            const agent = badgeCount(item.agentShopProductNumber);
            return (
              <div className="table-row mall-customer-table" key={item.id}>
                <span className="mall-customer-main-cell">
                  <span className="mall-customer-badges">
                    {licenseCode ? (
                      <CopyableLine text={licenseCode} label="营业执照编号">
                        <span className="mall-badge" title={`营业执照编号：${licenseCode}`}>
                          NO
                        </span>
                      </CopyableLine>
                    ) : (
                      <span className="mall-badge is-empty" title="无营业执照编号">
                        NO
                      </span>
                    )}
                    {email ? (
                      <CopyableLine text={email} label="邮箱">
                        <span className="mall-badge" title={`邮箱：${email}`}>
                          AD
                        </span>
                      </CopyableLine>
                    ) : (
                      <span className="mall-badge is-empty" title="无邮箱">
                        AD
                      </span>
                    )}
                    <em>
                      {item.legalPerson || "—"} · {item.city || "—"}
                    </em>
                  </span>
                  <CopyableLine text={item.name} label="公司名称">
                    <strong className="mall-customer-name">{item.name}</strong>
                  </CopyableLine>
                  <em>入驻时间：{formatTime(item.enterTime)}</em>
                  <em>更新时间：{formatTime(item.updatedAt)}</em>
                </span>
                <span className="mall-phone-cell">
                  {mobiles.length === 0 && "—"}
                  {mobiles.map((phone) => (
                    <CopyableLine key={phone} text={phone} label="联系电话">
                      {phone}
                    </CopyableLine>
                  ))}
                </span>
                <span className="mall-phone-cell">
                  {newMobiles.length === 0 && "—"}
                  {newMobiles.map((phone) => (
                    <CopyableLine key={phone} text={phone} label="新联系电话">
                      {phone}
                    </CopyableLine>
                  ))}
                </span>
                <span>
                  {item.type || "—"}
                  {agent}
                </span>
                <span>{item.signedLabel || "有效"}</span>
                <span className="option-actions">
                  {canManage ? (
                    <button className="copy-link" onClick={() => openEdit(item)}>
                      编辑
                    </button>
                  ) : (
                    "—"
                  )}
                </span>
                <span>{item.originLabel || item.origin || "—"}</span>
              </div>
            );
          })}
          {items.length === 0 && <div className="table-empty">{loading ? "加载中…" : "暂无数据"}</div>}
        </div>

        <Pagination page={page} totalPages={totalPages} total={total} pageSize={PAGE_SIZE} onPageChange={setPage} />
      </div>

      {editing && (
        <div className="modal-backdrop" role="presentation" onClick={closeModal}>
          <div
            className="modal"
            role="dialog"
            aria-modal="true"
            aria-label="编辑资料"
            onClick={(event) => event.stopPropagation()}
          >
            <div className="modal-head">
              <div>
                <h3>编辑资料</h3>
                <p>修改后写入 mall_customer。当前操作人：{currentUser.name}</p>
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
                <span>法人/联系人</span>
                <input value={form.legalPerson} onChange={(event) => setForm({ ...form, legalPerson: event.target.value })} />
              </label>
              <label>
                <span>联系电话</span>
                <input value={form.mobile} onChange={(event) => setForm({ ...form, mobile: event.target.value })} />
              </label>
              <label>
                <span>新联系电话</span>
                <input value={form.newMobile} onChange={(event) => setForm({ ...form, newMobile: event.target.value })} />
              </label>
              <label>
                <span>类型</span>
                <input value={form.type} onChange={(event) => setForm({ ...form, type: event.target.value })} />
              </label>
              <label>
                <span>状态</span>
                <select value={form.signed} onChange={(event) => setForm({ ...form, signed: event.target.value })}>
                  {SIGNED_OPTIONS.filter((item) => item.value !== "").map((item) => (
                    <option key={item.value} value={item.value}>
                      {item.label}
                    </option>
                  ))}
                </select>
              </label>
              <label>
                <span>来源</span>
                <select value={form.origin} onChange={(event) => setForm({ ...form, origin: event.target.value })}>
                  {ORIGIN_OPTIONS.map((item) => (
                    <option key={item.value} value={item.value}>
                      {item.label}
                    </option>
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
              <label>
                <span>执照编号</span>
                <input value={form.licenseCode} onChange={(event) => setForm({ ...form, licenseCode: event.target.value })} />
              </label>
              <label>
                <span>入驻时间</span>
                <input value={form.enterTime} onChange={(event) => setForm({ ...form, enterTime: event.target.value })} />
              </label>
              <label>
                <span>邮箱</span>
                <input value={form.email} onChange={(event) => setForm({ ...form, email: event.target.value })} />
              </label>
              <label className="full">
                <span>地址</span>
                <input value={form.address} onChange={(event) => setForm({ ...form, address: event.target.value })} />
              </label>
              <label className="full">
                <span>备注</span>
                <input value={form.remark} onChange={(event) => setForm({ ...form, remark: event.target.value })} />
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
