import { useEffect, useState } from "react";
import { Globe, Plus, Trash2, X } from "lucide-react";
import { createCollectionItem, createId, deleteCollectionItem, patchCollectionItem, queryCollection, AuthExpiredError } from "./db";
import { CopyableLine, Pagination, SearchField } from "./listUi";
import type {
  AppData,
  OfficialIndustryItem,
  OfficialInquiryPlatform,
  OfficialPage,
  OfficialSite,
  OfficialSiteBeian,
  OfficialSiteContact,
  OfficialSiteFooter,
  PermissionKey,
} from "./types";

type CanAccess = (permission: PermissionKey) => boolean;
type EditTab = "basic" | "contact" | "industries" | "platforms" | "footer" | "beian";

const PAGE_SIZE = 20;
const TABS: Array<{ id: EditTab; label: string }> = [
  { id: "basic", label: "基本信息" },
  { id: "contact", label: "联系方式" },
  { id: "industries", label: "常见行业" },
  { id: "platforms", label: "感兴趣的平台" },
  { id: "footer", label: "页脚" },
  { id: "beian", label: "备案" },
];

type SiteForm = {
  key: string;
  name: string;
  domain: string;
  domainsText: string;
  brand: string;
  companyName: string;
  status: OfficialSite["status"];
  contact: OfficialSiteContact;
  industries: OfficialIndustryItem[];
  inquiryPlatforms: OfficialInquiryPlatform[];
  footer: OfficialSiteFooter;
  beian: OfficialSiteBeian;
};

const emptyContact = (): OfficialSiteContact => ({
  hotline: "",
  mobile: "",
  wechatQrUrl: "/image/wx.png",
  email: "",
  contactName: "",
  address: "",
});

const emptyFooter = (): OfficialSiteFooter => ({
  platforms: [],
  services: [],
  keywords: "",
});

const emptyBeian = (): OfficialSiteBeian => ({
  copyright: "",
  icpText: "",
  icpUrl: "https://beian.miit.gov.cn/#/Integrated/index",
  telecomLicense: "",
  policeText: "",
  policeUrl: "https://beian.mps.gov.cn/#/query/webSearch",
});

const emptyForm = (): SiteForm => ({
  key: "",
  name: "",
  domain: "",
  domainsText: "",
  brand: "",
  companyName: "",
  status: "启用",
  contact: emptyContact(),
  industries: [],
  inquiryPlatforms: [],
  footer: emptyFooter(),
  beian: emptyBeian(),
});

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

function parseDomainsText(text: string, primary: string): string[] {
  const items = text
    .split(/[\r\n,]+/)
    .map((item) => item.trim())
    .filter(Boolean);
  const primaryHost = primary.trim();
  const result: string[] = [];
  const seen = new Set<string>();
  for (const item of [primaryHost, ...items]) {
    if (!item) continue;
    const key = item.toLowerCase().replace(/^https?:\/\//, "").replace(/^www\./, "").split("/")[0];
    if (!key || seen.has(key)) continue;
    seen.add(key);
    result.push(item);
  }
  return result;
}

function domainsLabel(site: OfficialSite) {
  const domains = Array.isArray(site.domains) && site.domains.length ? site.domains : [site.domain].filter(Boolean);
  if (domains.length <= 1) return site.domain || "—";
  return `${site.domain || domains[0]} +${domains.length - 1}`;
}

function siteToForm(site: OfficialSite): SiteForm {
  const domains = Array.isArray(site.domains) && site.domains.length ? site.domains : [site.domain].filter(Boolean);
  const contact = { ...emptyContact(), ...(site.contact || {}) };
  if (!contact.hotline) contact.hotline = site.phone || "";
  if (!contact.email) contact.email = site.email || "";
  if (!contact.address) contact.address = site.address || "";
  return {
    key: site.key || "",
    name: site.name || "",
    domain: site.domain || "",
    domainsText: domains.join("\n"),
    brand: site.brand || "",
    companyName: site.companyName || "",
    status: site.status || "启用",
    contact,
    industries: Array.isArray(site.industries) ? site.industries.map((item) => ({ ...item })) : [],
    inquiryPlatforms: Array.isArray(site.inquiryPlatforms) ? site.inquiryPlatforms.map((item) => ({ ...item })) : [],
    footer: {
      ...emptyFooter(),
      ...(site.footer || {}),
      platforms: Array.isArray(site.footer?.platforms) ? site.footer!.platforms!.map((item) => ({ ...item })) : [],
      services: Array.isArray(site.footer?.services) ? site.footer!.services!.map((item) => ({ ...item })) : [],
    },
    beian: { ...emptyBeian(), ...(site.beian || {}) },
  };
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
  const [form, setForm] = useState<SiteForm>(emptyForm);
  const [tab, setTab] = useState<EditTab>("basic");
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
    setForm(emptyForm());
    setTab("basic");
  }

  function openCreate() {
    setEditing(null);
    setCreating(true);
    setForm(emptyForm());
    setTab("basic");
  }

  function openEdit(site: OfficialSite) {
    setCreating(false);
    setEditing(site);
    setForm(siteToForm(site));
    setTab("basic");
  }

  function buildPayload(base?: OfficialSite): OfficialSite {
    const now = new Date().toISOString();
    const domains = parseDomainsText(form.domainsText, form.domain);
    const domain = form.domain.trim() || domains[0] || "";
    const key = (form.key.trim() || domainToKey(domain)).replace(/[^a-zA-Z0-9_-]/g, "");
    const contact = {
      ...form.contact,
      hotline: form.contact.hotline?.trim() || "",
      mobile: form.contact.mobile?.trim() || "",
      wechatQrUrl: form.contact.wechatQrUrl?.trim() || "/image/wx.png",
      email: form.contact.email?.trim() || "",
      contactName: form.contact.contactName?.trim() || "",
      address: form.contact.address?.trim() || "",
    };
    return {
      ...(base || {}),
      id: base?.id || createId("site"),
      key,
      name: form.name.trim(),
      domain,
      domains,
      mirrorKey: base?.mirrorKey || key,
      brand: form.brand.trim() || form.name.trim(),
      companyName: form.companyName.trim(),
      phone: contact.hotline,
      email: contact.email,
      address: contact.address,
      contact,
      industries: form.industries
        .map((item) => ({
          title: item.title.trim(),
          description: (item.description || "").trim(),
          icon: (item.icon || "").trim(),
        }))
        .filter((item) => item.title),
      inquiryPlatforms: form.inquiryPlatforms
        .map((item) => ({
          label: item.label.trim(),
          value: (item.value || item.label).trim(),
        }))
        .filter((item) => item.label && item.value),
      footer: {
        platforms: (form.footer.platforms || [])
          .map((item) => ({ name: (item.name || item.title || "").trim(), url: (item.url || "").trim() }))
          .filter((item) => item.name),
        services: (form.footer.services || [])
          .map((item) => ({
            title: (item.title || item.name || "").trim(),
            contentHtml: (item.contentHtml || "").trim(),
            url: (item.url || "").trim(),
          }))
          .filter((item) => item.title),
        keywords: (form.footer.keywords || "").trim(),
      },
      beian: {
        copyright: (form.beian.copyright || "").trim(),
        icpText: (form.beian.icpText || "").trim(),
        icpUrl: (form.beian.icpUrl || "").trim(),
        telecomLicense: (form.beian.telecomLicense || "").trim(),
        policeText: (form.beian.policeText || "").trim(),
        policeUrl: (form.beian.policeUrl || "").trim(),
      },
      status: form.status,
      createdAt: base?.createdAt || now,
      updatedAt: now,
      seoTitle: base?.seoTitle,
      seoDescription: base?.seoDescription,
      seoKeywords: base?.seoKeywords,
      ogImageUrl: base?.ogImageUrl,
      robotsTxt: base?.robotsTxt,
      sitemapUrls: base?.sitemapUrls,
      jsonLd: base?.jsonLd,
      baiduSiteVerification: base?.baiduSiteVerification,
      googleSiteVerification: base?.googleSiteVerification,
      logoUrl: base?.logoUrl,
      primaryColor: base?.primaryColor,
    };
  }

  async function saveSite() {
    if (!canManage) return;
    const name = form.name.trim();
    const domain = form.domain.trim();
    if (!name || !domain) {
      onNotice({ type: "error", message: "请填写站点名称和主域名" });
      setTab("basic");
      return;
    }
    const key = (form.key.trim() || domainToKey(domain)).replace(/[^a-zA-Z0-9_-]/g, "");
    if (!key) {
      onNotice({ type: "error", message: "请填写站点 Key，或使用可解析的域名" });
      setTab("basic");
      return;
    }
    setSaving(true);
    try {
      if (editing) {
        const saved = await patchCollectionItem<OfficialSite>("officialSites", editing.id, buildPayload(editing));
        applyData({
          ...data,
          officialSites: data.officialSites.some((row) => row.id === saved.id)
            ? data.officialSites.map((row) => (row.id === saved.id ? saved : row))
            : [saved, ...data.officialSites],
        });
        onNotice({ type: "success", message: "站点已保存" });
      } else {
        const seed = buildPayload();
        const saved = await createCollectionItem<OfficialSite>("officialSites", seed);
        const now = new Date().toISOString();
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
            <p>多域名站点首页运营配置：联系方式、行业、表单选项、页脚与备案；SEO 请到「SEO配置」维护。</p>
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
                <span className="site-main-cell">
                  <CopyableLine text={site.domain} label="主域名">
                    <strong>{site.domain}</strong>
                  </CopyableLine>
                  <em>{domainsLabel(site)}</em>
                </span>
                <span className="site-main-cell">
                  <strong>{site.companyName || "—"}</strong>
                  <em>{site.contact?.hotline || site.phone || "—"}</em>
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
                <p>{creating ? "配置多域名与首页运营字段；SEO 另页维护。" : `${editing?.key || ""} · ${editing?.domain || ""}`}</p>
              </div>
              <button type="button" className="icon-button" onClick={closeModal} aria-label="关闭">
                <X size={18} />
              </button>
            </div>

            <div className="segmented" style={{ marginBottom: 12 }}>
              {TABS.map((item) => (
                <button key={item.id} type="button" className={tab === item.id ? "active" : ""} onClick={() => setTab(item.id)}>
                  {item.label}
                </button>
              ))}
            </div>

            <div className="official-form">
              {tab === "basic" && (
                <section className="official-form-section">
                  <h3>基本信息</h3>
                  <div className="official-form-grid">
                    <label>
                      <span>站点名称 <em>*</em></span>
                      <input value={form.name} onChange={(event) => setForm({ ...form, name: event.target.value })} placeholder="如：壹采官网" />
                    </label>
                    <label>
                      <span>主域名 <em>*</em></span>
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
                      <span>公司名称</span>
                      <input value={form.companyName} onChange={(event) => setForm({ ...form, companyName: event.target.value })} />
                    </label>
                    <label>
                      <span>状态</span>
                      <select value={form.status} onChange={(event) => setForm({ ...form, status: event.target.value as OfficialSite["status"] })}>
                        <option value="启用">启用</option>
                        <option value="停用">停用</option>
                      </select>
                    </label>
                    <label className="span-2">
                      <span>域名别名（一行一个，含主域）</span>
                      <textarea
                        rows={4}
                        value={form.domainsText}
                        onChange={(event) => setForm({ ...form, domainsText: event.target.value })}
                        placeholder={"www.qlyc.co\nwww.yizhichan.co"}
                      />
                    </label>
                  </div>
                  <p className="official-form-hint">壹采站可将 qlyc.co 与 yizhichan.co 配在同一站点，改一处两边生效。</p>
                </section>
              )}

              {tab === "contact" && (
                <section className="official-form-section">
                  <h3>联系方式</h3>
                  <p className="official-form-hint">右侧栏、联系我们区、页脚联系我们共用本组字段。</p>
                  <div className="official-form-grid">
                    <label>
                      <span>咨询热线</span>
                      <input value={form.contact.hotline || ""} onChange={(event) => setForm({ ...form, contact: { ...form.contact, hotline: event.target.value } })} />
                    </label>
                    <label>
                      <span>手机</span>
                      <input value={form.contact.mobile || ""} onChange={(event) => setForm({ ...form, contact: { ...form.contact, mobile: event.target.value } })} />
                    </label>
                    <label>
                      <span>邮箱</span>
                      <input value={form.contact.email || ""} onChange={(event) => setForm({ ...form, contact: { ...form.contact, email: event.target.value } })} />
                    </label>
                    <label>
                      <span>联系人</span>
                      <input value={form.contact.contactName || ""} onChange={(event) => setForm({ ...form, contact: { ...form.contact, contactName: event.target.value } })} />
                    </label>
                    <label className="span-2">
                      <span>微信二维码 URL</span>
                      <input value={form.contact.wechatQrUrl || ""} onChange={(event) => setForm({ ...form, contact: { ...form.contact, wechatQrUrl: event.target.value } })} placeholder="/image/wx.png" />
                    </label>
                    <label className="span-2">
                      <span>地址</span>
                      <input value={form.contact.address || ""} onChange={(event) => setForm({ ...form, contact: { ...form.contact, address: event.target.value } })} />
                    </label>
                  </div>
                </section>
              )}

              {tab === "industries" && (
                <section className="official-form-section">
                  <div className="action-title" style={{ marginBottom: 12 }}>
                    <h3>常见行业</h3>
                    {canManage && (
                      <button
                        type="button"
                        className="ghost"
                        onClick={() => setForm({ ...form, industries: [...form.industries, { title: "", description: "", icon: "" }] })}
                      >
                        <Plus size={14} /> 添加
                      </button>
                    )}
                  </div>
                  <p className="official-form-hint">青慧采无该区块时可留空。</p>
                  {form.industries.map((item, index) => (
                    <div className="official-form-grid" key={`industry-${index}`} style={{ marginBottom: 10 }}>
                      <label>
                        <span>标题</span>
                        <input
                          value={item.title}
                          onChange={(event) => {
                            const industries = [...form.industries];
                            industries[index] = { ...item, title: event.target.value };
                            setForm({ ...form, industries });
                          }}
                        />
                      </label>
                      <label>
                        <span>图标 class（可选）</span>
                        <input
                          value={item.icon || ""}
                          onChange={(event) => {
                            const industries = [...form.industries];
                            industries[index] = { ...item, icon: event.target.value };
                            setForm({ ...form, industries });
                          }}
                          placeholder="fa-laptop"
                        />
                      </label>
                      <label className="span-2">
                        <span>说明</span>
                        <input
                          value={item.description || ""}
                          onChange={(event) => {
                            const industries = [...form.industries];
                            industries[index] = { ...item, description: event.target.value };
                            setForm({ ...form, industries });
                          }}
                        />
                      </label>
                      <div className="span-2">
                        <button
                          type="button"
                          className="copy-link danger-action"
                          onClick={() => setForm({ ...form, industries: form.industries.filter((_, i) => i !== index) })}
                        >
                          <Trash2 size={14} /> 删除
                        </button>
                      </div>
                    </div>
                  ))}
                  {form.industries.length === 0 && <div className="table-empty">暂无行业条目</div>}
                </section>
              )}

              {tab === "platforms" && (
                <section className="official-form-section">
                  <div className="action-title" style={{ marginBottom: 12 }}>
                    <h3>感兴趣的平台</h3>
                    {canManage && (
                      <button
                        type="button"
                        className="ghost"
                        onClick={() => setForm({ ...form, inquiryPlatforms: [...form.inquiryPlatforms, { label: "", value: "" }] })}
                      >
                        <Plus size={14} /> 添加
                      </button>
                    )}
                  </div>
                  {form.inquiryPlatforms.map((item, index) => (
                    <div className="official-form-grid" key={`platform-${index}`} style={{ marginBottom: 10 }}>
                      <label>
                        <span>显示名</span>
                        <input
                          value={item.label}
                          onChange={(event) => {
                            const inquiryPlatforms = [...form.inquiryPlatforms];
                            inquiryPlatforms[index] = { ...item, label: event.target.value, value: item.value || event.target.value };
                            setForm({ ...form, inquiryPlatforms });
                          }}
                        />
                      </label>
                      <label>
                        <span>提交值</span>
                        <input
                          value={item.value}
                          onChange={(event) => {
                            const inquiryPlatforms = [...form.inquiryPlatforms];
                            inquiryPlatforms[index] = { ...item, value: event.target.value };
                            setForm({ ...form, inquiryPlatforms });
                          }}
                        />
                      </label>
                      <div className="span-2">
                        <button
                          type="button"
                          className="copy-link danger-action"
                          onClick={() => setForm({ ...form, inquiryPlatforms: form.inquiryPlatforms.filter((_, i) => i !== index) })}
                        >
                          <Trash2 size={14} /> 删除
                        </button>
                      </div>
                    </div>
                  ))}
                  {form.inquiryPlatforms.length === 0 && <div className="table-empty">暂无平台选项</div>}
                </section>
              )}

              {tab === "footer" && (
                <section className="official-form-section">
                  <div className="action-title" style={{ marginBottom: 12 }}>
                    <h3>官方平台</h3>
                    {canManage && (
                      <button
                        type="button"
                        className="ghost"
                        onClick={() => setForm({
                          ...form,
                          footer: { ...form.footer, platforms: [...(form.footer.platforms || []), { name: "", url: "" }] },
                        })}
                      >
                        <Plus size={14} /> 添加
                      </button>
                    )}
                  </div>
                  {(form.footer.platforms || []).map((item, index) => (
                    <div className="official-form-grid" key={`fp-${index}`} style={{ marginBottom: 10 }}>
                      <label>
                        <span>名称</span>
                        <input
                          value={item.name || ""}
                          onChange={(event) => {
                            const platforms = [...(form.footer.platforms || [])];
                            platforms[index] = { ...item, name: event.target.value };
                            setForm({ ...form, footer: { ...form.footer, platforms } });
                          }}
                        />
                      </label>
                      <label>
                        <span>链接</span>
                        <input
                          value={item.url || ""}
                          onChange={(event) => {
                            const platforms = [...(form.footer.platforms || [])];
                            platforms[index] = { ...item, url: event.target.value };
                            setForm({ ...form, footer: { ...form.footer, platforms } });
                          }}
                        />
                      </label>
                      <div className="span-2">
                        <button
                          type="button"
                          className="copy-link danger-action"
                          onClick={() => setForm({
                            ...form,
                            footer: { ...form.footer, platforms: (form.footer.platforms || []).filter((_, i) => i !== index) },
                          })}
                        >
                          <Trash2 size={14} /> 删除
                        </button>
                      </div>
                    </div>
                  ))}

                  <div className="action-title" style={{ margin: "16px 0 12px" }}>
                    <h3>我们的服务 / 快速链接</h3>
                    {canManage && (
                      <button
                        type="button"
                        className="ghost"
                        onClick={() => setForm({
                          ...form,
                          footer: { ...form.footer, services: [...(form.footer.services || []), { title: "", contentHtml: "", url: "" }] },
                        })}
                      >
                        <Plus size={14} /> 添加
                      </button>
                    )}
                  </div>
                  <p className="official-form-hint">壹采：标题+可选富文本 HTML+链接；青慧采：用作快速链接（内容可空）。</p>
                  {(form.footer.services || []).map((item, index) => (
                    <div className="official-form-grid" key={`fs-${index}`} style={{ marginBottom: 10 }}>
                      <label>
                        <span>标题</span>
                        <input
                          value={item.title || item.name || ""}
                          onChange={(event) => {
                            const services = [...(form.footer.services || [])];
                            services[index] = { ...item, title: event.target.value };
                            setForm({ ...form, footer: { ...form.footer, services } });
                          }}
                        />
                      </label>
                      <label>
                        <span>链接</span>
                        <input
                          value={item.url || ""}
                          onChange={(event) => {
                            const services = [...(form.footer.services || [])];
                            services[index] = { ...item, url: event.target.value };
                            setForm({ ...form, footer: { ...form.footer, services } });
                          }}
                        />
                      </label>
                      <label className="span-2">
                        <span>内容 HTML（可选）</span>
                        <textarea
                          rows={3}
                          value={item.contentHtml || ""}
                          onChange={(event) => {
                            const services = [...(form.footer.services || [])];
                            services[index] = { ...item, contentHtml: event.target.value };
                            setForm({ ...form, footer: { ...form.footer, services } });
                          }}
                        />
                      </label>
                      <div className="span-2">
                        <button
                          type="button"
                          className="copy-link danger-action"
                          onClick={() => setForm({
                            ...form,
                            footer: { ...form.footer, services: (form.footer.services || []).filter((_, i) => i !== index) },
                          })}
                        >
                          <Trash2 size={14} /> 删除
                        </button>
                      </div>
                    </div>
                  ))}

                  <label className="span-2" style={{ display: "block", marginTop: 12 }}>
                    <span>平台关键词（青慧采页脚）</span>
                    <textarea
                      rows={3}
                      value={form.footer.keywords || ""}
                      onChange={(event) => setForm({ ...form, footer: { ...form.footer, keywords: event.target.value } })}
                      placeholder="青慧采 | 青慧采入驻代办 | …"
                    />
                  </label>
                </section>
              )}

              {tab === "beian" && (
                <section className="official-form-section">
                  <h3>备案相关</h3>
                  <div className="official-form-grid">
                    <label className="span-2">
                      <span>版权文案</span>
                      <input value={form.beian.copyright || ""} onChange={(event) => setForm({ ...form, beian: { ...form.beian, copyright: event.target.value } })} />
                    </label>
                    <label>
                      <span>ICP 文案</span>
                      <input value={form.beian.icpText || ""} onChange={(event) => setForm({ ...form, beian: { ...form.beian, icpText: event.target.value } })} />
                    </label>
                    <label>
                      <span>ICP 链接</span>
                      <input value={form.beian.icpUrl || ""} onChange={(event) => setForm({ ...form, beian: { ...form.beian, icpUrl: event.target.value } })} />
                    </label>
                    <label className="span-2">
                      <span>电信增值业务许可证</span>
                      <input value={form.beian.telecomLicense || ""} onChange={(event) => setForm({ ...form, beian: { ...form.beian, telecomLicense: event.target.value } })} />
                    </label>
                    <label>
                      <span>公安备案文案</span>
                      <input value={form.beian.policeText || ""} onChange={(event) => setForm({ ...form, beian: { ...form.beian, policeText: event.target.value } })} />
                    </label>
                    <label>
                      <span>公安备案链接</span>
                      <input value={form.beian.policeUrl || ""} onChange={(event) => setForm({ ...form, beian: { ...form.beian, policeUrl: event.target.value } })} />
                    </label>
                  </div>
                </section>
              )}
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
