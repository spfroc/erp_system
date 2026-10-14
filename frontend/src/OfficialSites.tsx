import { useEffect, useState } from "react";
import { Globe, X } from "lucide-react";
import { createCollectionItem, createId, deleteCollectionItem, patchCollectionItem, queryCollection, AuthExpiredError } from "./db";
import { CopyableLine, Pagination, SearchField } from "./listUi";
import type { AppData, OfficialPage, OfficialSite, PermissionKey } from "./types";

type CanAccess = (permission: PermissionKey) => boolean;

const PAGE_SIZE = 20;

const emptyForm = {
  key: "",
  name: "",
  domain: "",
  brand: "",
  companyName: "",
  phone: "",
  email: "",
  address: "",
  status: "启用" as OfficialSite["status"],
};

function useDebounced(value: string, delay = 300) {
  const [debounced, setDebounced] = useState(value);
  useEffect(() => {
    const timer = window.setTimeout(() => setDebounced(value), delay);
    return () => window.clearTimeout(timer);
  }, [value, delay]);
  return debounced;
}

function domainToKey(domain: string) {
  const host = domain.trim().toLowerCase().replace(/^https?:\/\//, "").split("/")[0].split(":")[0];
  const bare = host.startsWith("www.") ? host.slice(4) : host;
  return bare.split(".")[0] || "";
}

export function OfficialSitesPanel({
  data,
  applyData,
  onNotice,
  can,
}: {
  data: AppData;
  applyData: (data: AppData) => void;
  onNotice: (notice: { type: "success" | "error"; message: string }) => void;
  can: CanAccess;
}) {
  const canManage = can("site.manage");
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState<"全部" | "启用" | "停用">("全部");
  const debouncedSearch = useDebounced(search);
  const [page, setPage] = useState(1);
  const [items, setItems] = useState<OfficialSite[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(false);
  const [reloadTick, setReloadTick] = useState(0);
  const [homePages, setHomePages] = useState<Record<string, OfficialPage>>({});
  const [editing, setEditing] = useState<OfficialSite | null>(null);
  const [creating, setCreating] = useState(false);
  const [form, setForm] = useState(emptyForm);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    setPage(1);
  }, [debouncedSearch, statusFilter]);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    void queryCollection<OfficialSite>("officialSites", {
      page,
      pageSize: PAGE_SIZE,
      search: debouncedSearch,
      filters: { status: statusFilter === "全部" ? undefined : statusFilter },
    })
      .then(async (result) => {
        if (cancelled) return;
        setItems(result.items);
        setTotal(result.total);
        const pageResult = await queryCollection<OfficialPage>("officialPages", {
          page: 1,
          pageSize: 100,
          search: "",
        });
        if (cancelled) return;
        const map: Record<string, OfficialPage> = {};
        for (const item of pageResult.items) {
          if (item.slug === "home") map[item.siteId] = item;
        }
        setHomePages(map);
      })
      .catch((error) => {
        if (cancelled || error instanceof AuthExpiredError) return;
        onNotice({ type: "error", message: error instanceof Error ? error.message : "站点列表加载失败" });
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [page, debouncedSearch, statusFilter, reloadTick, data.officialSites, data.officialPages, onNotice]);

  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE));
  const modalOpen = creating || Boolean(editing);

  function closeModal() {
    setCreating(false);
    setEditing(null);
    setForm(emptyForm);
  }

  function openCreate() {
    setEditing(null);
    setCreating(true);
    setForm(emptyForm);
  }

  function openEdit(site: OfficialSite) {
    setCreating(false);
    setEditing(site);
    setForm({
      key: site.key || "",
      name: site.name,
      domain: site.domain,
      brand: site.brand,
      companyName: site.companyName || "",
      phone: site.phone || "",
      email: site.email || "",
      address: site.address || "",
      status: site.status,
    });
  }

  async function saveSite() {
    if (!canManage) return;
    const name = form.name.trim();
    const domain = form.domain.trim();
    const key = (form.key.trim() || domainToKey(domain)).replace(/[^a-zA-Z0-9_-]/g, "");
    if (!name || !domain) {
      onNotice({ type: "error", message: "请填写站点名称和域名" });
      return;
    }
    if (!key) {
      onNotice({ type: "error", message: "请填写站点 Key，或使用可解析的域名" });
      return;
    }
    setSaving(true);
    try {
      const now = new Date().toISOString();
      if (editing) {
        const saved = await patchCollectionItem<OfficialSite>("officialSites", editing.id, {
          ...editing,
          key,
          name,
          domain,
          brand: form.brand.trim() || name,
          companyName: form.companyName.trim(),
          phone: form.phone.trim(),
          email: form.email.trim(),
          address: form.address.trim(),
          status: form.status,
          updatedAt: now,
        });
        applyData({
          ...data,
          officialSites: data.officialSites.some((row) => row.id === saved.id)
            ? data.officialSites.map((row) => (row.id === saved.id ? saved : row))
            : [saved, ...data.officialSites],
        });
        onNotice({ type: "success", message: "站点已保存" });
      } else {
        const seed: OfficialSite = {
          id: createId("site"),
          key,
          name,
          domain,
          brand: form.brand.trim() || name,
          companyName: form.companyName.trim(),
          phone: form.phone.trim(),
          email: form.email.trim(),
          address: form.address.trim(),
          status: form.status,
          createdAt: now,
          updatedAt: now,
        };
        const saved = await createCollectionItem<OfficialSite>("officialSites", seed);
        const home: OfficialPage = {
          id: createId("page"),
          siteId: saved.id,
          slug: "home",
          title: "首页",
          template: "home",
          status: "draft",
          blocks: [
            { type: "hero", data: { title: saved.brand, subtitle: "请完善站点内容", primaryCta: { label: "联系我们", href: "#contact" } } },
          ],
          createdAt: now,
          updatedAt: now,
        };
        const savedPage = await createCollectionItem<OfficialPage>("officialPages", home);
        applyData({
          ...data,
          officialSites: [saved, ...data.officialSites],
          officialPages: [savedPage, ...data.officialPages],
        });
        onNotice({ type: "success", message: "站点已创建（首页为草稿）" });
      }
      closeModal();
      setReloadTick((value) => value + 1);
    } catch (error) {
      onNotice({ type: "error", message: error instanceof Error ? error.message : "保存失败" });
    } finally {
      setSaving(false);
    }
  }

  async function toggleHomePublish(site: OfficialSite) {
    if (!canManage) return;
    const home = homePages[site.id];
    if (!home) {
      onNotice({ type: "error", message: "未找到首页，请先新建站点或补齐首页" });
      return;
    }
    const nextStatus = home.status === "published" ? "draft" : "published";
    try {
      const saved = await patchCollectionItem<OfficialPage>("officialPages", home.id, {
        ...home,
        status: nextStatus,
        updatedAt: new Date().toISOString(),
      });
      applyData({
        ...data,
        officialPages: data.officialPages.some((row) => row.id === saved.id)
          ? data.officialPages.map((row) => (row.id === saved.id ? saved : row))
          : [saved, ...data.officialPages],
      });
      setReloadTick((value) => value + 1);
      onNotice({ type: "success", message: nextStatus === "published" ? "首页已发布" : "首页已撤回为草稿" });
    } catch (error) {
      onNotice({ type: "error", message: error instanceof Error ? error.message : "更新失败" });
    }
  }

  async function deleteSite(site: OfficialSite) {
    if (!canManage) return;
    if (!window.confirm(`确认删除站点「${site.name}」及其关联页面？此操作可在后台软删除，不会自动恢复种子站点。`)) return;
    try {
      const pages = await queryCollection<OfficialPage>("officialPages", { page: 1, pageSize: 100, search: "" });
      const related = pages.items.filter((item) => item.siteId === site.id);
      for (const pageItem of related) {
        await deleteCollectionItem("officialPages", pageItem.id);
      }
      await deleteCollectionItem("officialSites", site.id);
      applyData({
        ...data,
        officialSites: data.officialSites.filter((row) => row.id !== site.id),
        officialPages: data.officialPages.filter((row) => row.siteId !== site.id),
      });
      if (editing?.id === site.id) closeModal();
      setReloadTick((value) => value + 1);
      onNotice({ type: "success", message: "站点已删除" });
    } catch (error) {
      onNotice({ type: "error", message: error instanceof Error ? error.message : "删除失败" });
    }
  }

  return (
    <div className="stack">
      <div className="panel">
        <div className="panel-title action-title">
          <div>
            <h2>官网站点</h2>
            <p>按域名维护官网品牌、联系方式与首页发布状态；SEO 请到「SEO配置」维护。</p>
          </div>
          <div className="panel-title-buttons">
            {canManage && (
              <button type="button" className="primary" onClick={openCreate}>
                <Globe size={16} />新增站点
              </button>
            )}
          </div>
        </div>

        <div className="platform-account-toolbar">
          <SearchField value={search} onChange={setSearch} placeholder="搜索站点名称、域名、品牌" ariaLabel="搜索官网站点" />
        </div>
        <div className="segmented">
          {(["全部", "启用", "停用"] as const).map((item) => (
            <button key={item} type="button" className={statusFilter === item ? "active" : ""} onClick={() => setStatusFilter(item)}>
              {item}
            </button>
          ))}
        </div>

        <div className="table">
          <div className="table-row site-table head">
            <span>站点</span>
            <span>域名</span>
            <span>公司/电话</span>
            <span>首页</span>
            <span>状态</span>
            <span>操作</span>
          </div>
          {loading && <div className="table-empty">加载中...</div>}
          {!loading && items.map((site) => {
            const home = homePages[site.id];
            return (
              <div className="table-row site-table" key={site.id}>
                <span className="site-main-cell">
                  <CopyableLine text={site.name} label="站点名称">
                    <strong>{site.name}</strong>
                  </CopyableLine>
                  <em>{site.brand || "—"} · {site.key}</em>
                </span>
                <span>
                  <CopyableLine text={site.domain} label="域名">
                    {site.domain}
                  </CopyableLine>
                </span>
                <span className="site-main-cell">
                  <strong>{site.companyName || "—"}</strong>
                  <em>{site.phone || "—"}</em>
                </span>
                <span>{home ? (home.status === "published" ? "已发布" : "草稿") : "无首页"}</span>
                <span>{site.status}</span>
                <span className="option-actions">
                  {canManage && <button type="button" className="copy-link" onClick={() => openEdit(site)}>编辑</button>}
                  {canManage && home && (
                    <button type="button" className="copy-link" onClick={() => void toggleHomePublish(site)}>
                      {home.status === "published" ? "撤回首页" : "发布首页"}
                    </button>
                  )}
                  {canManage && (
                    <button type="button" className="copy-link danger-action" onClick={() => void deleteSite(site)}>
                      删除
                    </button>
                  )}
                </span>
              </div>
            );
          })}
          {!loading && items.length === 0 && <div className="table-empty">暂无站点。可点「新增站点」。</div>}
        </div>
        <Pagination page={page} totalPages={totalPages} total={total} pageSize={PAGE_SIZE} onPageChange={setPage} />
      </div>

      {modalOpen && (
        <div className="modal-backdrop" role="presentation">
          <div className="modal official-site-modal" role="dialog" aria-modal="true" aria-label={creating ? "新增站点" : "编辑站点"}>
            <div className="modal-head">
              <div>
                <h2>{creating ? "新增站点" : "编辑站点"}</h2>
                <p>{creating ? "填写域名与品牌信息，保存后可再配置 SEO 与发布首页。" : `${editing?.key || ""} · ${editing?.domain || ""}`}</p>
              </div>
              <button type="button" className="icon-button" onClick={closeModal} aria-label="关闭">
                <X size={18} />
              </button>
            </div>

            <div className="official-form">
              <section className="official-form-section">
                <h3>基础信息</h3>
                <div className="official-form-grid">
                  <label>
                    <span>站点名称 <em>*</em></span>
                    <input value={form.name} onChange={(event) => setForm({ ...form, name: event.target.value })} placeholder="如：壹采官网" />
                  </label>
                  <label>
                    <span>域名 <em>*</em></span>
                    <input
                      value={form.domain}
                      onChange={(event) => {
                        const domain = event.target.value;
                        setForm((prev) => ({
                          ...prev,
                          domain,
                          key: creating && !prev.key ? domainToKey(domain) : prev.key,
                        }));
                      }}
                      placeholder="www.qlyc.co"
                    />
                  </label>
                  <label>
                    <span>站点 Key</span>
                    <input value={form.key} onChange={(event) => setForm({ ...form, key: event.target.value })} placeholder="qlyc" />
                  </label>
                  <label>
                    <span>品牌</span>
                    <input value={form.brand} onChange={(event) => setForm({ ...form, brand: event.target.value })} placeholder="壹采" />
                  </label>
                  <label>
                    <span>状态</span>
                    <select value={form.status} onChange={(event) => setForm({ ...form, status: event.target.value as OfficialSite["status"] })}>
                      <option value="启用">启用</option>
                      <option value="停用">停用</option>
                    </select>
                  </label>
                </div>
              </section>

              <section className="official-form-section">
                <h3>联系信息</h3>
                <div className="official-form-grid">
                  <label>
                    <span>公司名称</span>
                    <input value={form.companyName} onChange={(event) => setForm({ ...form, companyName: event.target.value })} />
                  </label>
                  <label>
                    <span>电话</span>
                    <input value={form.phone} onChange={(event) => setForm({ ...form, phone: event.target.value })} />
                  </label>
                  <label>
                    <span>邮箱</span>
                    <input value={form.email} onChange={(event) => setForm({ ...form, email: event.target.value })} />
                  </label>
                  <label className="span-2">
                    <span>地址</span>
                    <input value={form.address} onChange={(event) => setForm({ ...form, address: event.target.value })} />
                  </label>
                </div>
                <p className="official-form-hint">标题、关键词、robots 等请到「官网 → SEO配置」维护。</p>
              </section>
            </div>

            <div className="modal-actions">
              <div className="modal-actions-left">
                {editing && canManage && (
                  <button type="button" className="ghost danger-action" onClick={() => void deleteSite(editing)}>
                    删除站点
                  </button>
                )}
              </div>
              <button type="button" className="ghost" onClick={closeModal}>取消</button>
              <button type="button" className="primary" disabled={saving} onClick={() => void saveSite()}>
                {saving ? "保存中…" : "保存"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
