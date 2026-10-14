import { useEffect, useState } from "react";
import { Download, Search, X } from "lucide-react";
import { AuthExpiredError, deleteCollectionItem, patchCollectionItem, queryCollection } from "./db";
import { CopyableLine, Pagination, SearchField } from "./listUi";
import type { AppData, OfficialPage, OfficialSite, PermissionKey } from "./types";

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

function sitemapText(value?: string[] | string) {
  if (Array.isArray(value)) return value.join("\n");
  return String(value || "");
}

function parseSitemapUrls(text: string) {
  return text
    .split(/[\r\n,]+/)
    .map((item) => item.trim())
    .filter(Boolean);
}

const emptyForm = {
  seoTitle: "",
  seoDescription: "",
  seoKeywords: "",
  ogImageUrl: "",
  robotsTxt: "",
  sitemapUrls: "",
  jsonLd: "",
  baiduSiteVerification: "",
  googleSiteVerification: "",
};

export function OfficialSeoPanel({
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
  const debouncedSearch = useDebounced(search);
  const [page, setPage] = useState(1);
  const [items, setItems] = useState<OfficialSite[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(false);
  const [reloadTick, setReloadTick] = useState(0);
  const [editing, setEditing] = useState<OfficialSite | null>(null);
  const [form, setForm] = useState(emptyForm);
  const [importing, setImporting] = useState(false);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    setPage(1);
  }, [debouncedSearch]);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    void queryCollection<OfficialSite>("officialSites", {
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
        onNotice({ type: "error", message: error instanceof Error ? error.message : "SEO 列表加载失败" });
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [page, debouncedSearch, reloadTick, data.officialSites, onNotice]);

  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE));

  function openEdit(site: OfficialSite) {
    setEditing(site);
    setForm({
      seoTitle: site.seoTitle || "",
      seoDescription: site.seoDescription || "",
      seoKeywords: site.seoKeywords || "",
      ogImageUrl: site.ogImageUrl || "",
      robotsTxt: site.robotsTxt || "",
      sitemapUrls: sitemapText(site.sitemapUrls),
      jsonLd: site.jsonLd || "",
      baiduSiteVerification: site.baiduSiteVerification || "",
      googleSiteVerification: site.googleSiteVerification || "",
    });
  }

  function closeModal() {
    setEditing(null);
    setForm(emptyForm);
  }

  async function saveSeo() {
    if (!canManage || !editing) return;
    setSaving(true);
    try {
      const saved = await patchCollectionItem<OfficialSite>("officialSites", editing.id, {
        ...editing,
        seoTitle: form.seoTitle.trim(),
        seoDescription: form.seoDescription.trim(),
        seoKeywords: form.seoKeywords.trim(),
        ogImageUrl: form.ogImageUrl.trim(),
        robotsTxt: form.robotsTxt.trim(),
        sitemapUrls: parseSitemapUrls(form.sitemapUrls),
        jsonLd: form.jsonLd.trim(),
        baiduSiteVerification: form.baiduSiteVerification.trim(),
        googleSiteVerification: form.googleSiteVerification.trim(),
        updatedAt: new Date().toISOString(),
      });
      applyData({
        ...data,
        officialSites: data.officialSites.some((row) => row.id === saved.id)
          ? data.officialSites.map((row) => (row.id === saved.id ? saved : row))
          : [saved, ...data.officialSites],
      });
      closeModal();
      setReloadTick((value) => value + 1);
      onNotice({ type: "success", message: "SEO 配置已保存" });
    } catch (error) {
      onNotice({ type: "error", message: error instanceof Error ? error.message : "保存失败" });
    } finally {
      setSaving(false);
    }
  }

  async function clearSeo(site: OfficialSite) {
    if (!canManage) return;
    if (!window.confirm(`确认清空「${site.name}」的 SEO 配置？站点本身不会删除。`)) return;
    try {
      const saved = await patchCollectionItem<OfficialSite>("officialSites", site.id, {
        ...site,
        seoTitle: "",
        seoDescription: "",
        seoKeywords: "",
        ogImageUrl: "",
        robotsTxt: "",
        sitemapUrls: [],
        jsonLd: "",
        baiduSiteVerification: "",
        googleSiteVerification: "",
        updatedAt: new Date().toISOString(),
      });
      applyData({
        ...data,
        officialSites: data.officialSites.map((row) => (row.id === saved.id ? saved : row)),
      });
      if (editing?.id === site.id) closeModal();
      setReloadTick((value) => value + 1);
      onNotice({ type: "success", message: "SEO 配置已清空" });
    } catch (error) {
      onNotice({ type: "error", message: error instanceof Error ? error.message : "清空失败" });
    }
  }

  async function deleteSite(site: OfficialSite) {
    if (!canManage) return;
    if (!window.confirm(`确认删除站点「${site.name}」及其关联页面？`)) return;
    try {
      const pages = await queryCollection<OfficialPage>("officialPages", { page: 1, pageSize: 100, search: "" });
      for (const pageItem of pages.items.filter((item) => item.siteId === site.id)) {
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

  async function importFromStatic(overwrite: boolean) {
    if (!canManage) return;
    const tip = overwrite
      ? "将用原官网静态 SEO 覆盖当前后台配置，是否继续？"
      : "将把原官网 SEO 填入空字段（已有内容不会改动），是否继续？";
    if (!window.confirm(tip)) return;
    setImporting(true);
    try {
      const response = await fetch(apiUrl("/api/official-seo/import/"), {
        method: "POST",
        credentials: "include",
        headers: { "Content-Type": "application/json", Accept: "application/json" },
        body: JSON.stringify({ overwrite }),
      });
      const body = await response.json().catch(() => ({}));
      if (!response.ok) {
        throw new Error((body && body.detail) || `HTTP ${response.status}`);
      }
      setReloadTick((value) => value + 1);
      onNotice({
        type: "success",
        message: overwrite
          ? `已覆盖导入 ${body.total ?? 0} 个站点 SEO`
          : `已补齐 ${body.total ?? 0} 个站点空 SEO 字段`,
      });
    } catch (error) {
      onNotice({ type: "error", message: error instanceof Error ? error.message : "导入失败" });
    } finally {
      setImporting(false);
    }
  }

  return (
    <div className="stack">
      <div className="panel">
        <div className="panel-title action-title">
          <div>
            <h2>官网 SEO 配置</h2>
            <p>维护各域名的标题、描述、关键词、robots、Sitemap 与结构化数据；可从原官网静态配置导入。</p>
          </div>
          <div className="panel-title-buttons">
            {canManage && (
              <>
                <button type="button" className="ghost" disabled={importing} onClick={() => void importFromStatic(false)}>
                  <Download size={16} />导入空字段
                </button>
                <button type="button" className="primary" disabled={importing} onClick={() => void importFromStatic(true)}>
                  <Search size={16} />覆盖导入原官网 SEO
                </button>
              </>
            )}
          </div>
        </div>

        <div className="platform-account-toolbar">
          <SearchField value={search} onChange={setSearch} placeholder="搜索站点名称、域名、品牌" ariaLabel="搜索 SEO 站点" />
        </div>

        <div className="table">
          <div className="table-row seo-table head">
            <span>站点</span>
            <span>SEO 标题</span>
            <span>关键词</span>
            <span>robots / Sitemap</span>
            <span>操作</span>
          </div>
          {loading && <div className="table-empty">加载中...</div>}
          {!loading &&
            items.map((site) => (
              <div className="table-row seo-table" key={site.id}>
                <span className="site-main-cell">
                  <CopyableLine text={site.name} label="站点名称">
                    <strong>{site.name}</strong>
                  </CopyableLine>
                  <em>{site.domain}</em>
                </span>
                <span className="site-main-cell">
                  <strong>{site.seoTitle || "未配置"}</strong>
                  <em>{site.seoDescription ? `${site.seoDescription.slice(0, 48)}${site.seoDescription.length > 48 ? "…" : ""}` : "无描述"}</em>
                </span>
                <span>{site.seoKeywords ? `${site.seoKeywords.split(/[,，]/).filter(Boolean).length} 个` : "—"}</span>
                <span className="site-main-cell">
                  <strong>{site.robotsTxt ? "已配置 robots" : "无 robots"}</strong>
                  <em>{Array.isArray(site.sitemapUrls) && site.sitemapUrls.length ? `${site.sitemapUrls.length} 条 Sitemap` : "无 Sitemap"}</em>
                </span>
                <span className="option-actions">
                  {canManage && (
                    <button type="button" className="copy-link" onClick={() => openEdit(site)}>
                      编辑
                    </button>
                  )}
                  {canManage && (
                    <button type="button" className="copy-link" onClick={() => void clearSeo(site)}>
                      清空
                    </button>
                  )}
                  {canManage && (
                    <button type="button" className="copy-link danger-action" onClick={() => void deleteSite(site)}>
                      删除
                    </button>
                  )}
                </span>
              </div>
            ))}
          {!loading && items.length === 0 && <div className="table-empty">暂无站点，请先在「官网站点」中创建。</div>}
        </div>
        <Pagination page={page} totalPages={totalPages} total={total} pageSize={PAGE_SIZE} onPageChange={setPage} />
      </div>

      {editing && (
        <div className="modal-backdrop" role="presentation">
          <div className="modal official-seo-modal" role="dialog" aria-modal="true" aria-label="编辑 SEO">
            <div className="modal-head">
              <div>
                <h2>编辑 SEO</h2>
                <p>{editing.name} · {editing.domain}</p>
              </div>
              <button type="button" className="icon-button" onClick={closeModal} aria-label="关闭">
                <X size={18} />
              </button>
            </div>

            <div className="official-form">
              <section className="official-form-section">
                <h3>检索摘要</h3>
                <div className="official-form-grid">
                  <label className="span-2">
                    <span>SEO 标题</span>
                    <input value={form.seoTitle} onChange={(event) => setForm({ ...form, seoTitle: event.target.value })} placeholder="页面 title" />
                  </label>
                  <label className="span-2">
                    <span>SEO 描述</span>
                    <textarea rows={3} value={form.seoDescription} onChange={(event) => setForm({ ...form, seoDescription: event.target.value })} placeholder="meta description" />
                  </label>
                  <label className="span-2">
                    <span>SEO 关键词</span>
                    <textarea rows={2} value={form.seoKeywords} onChange={(event) => setForm({ ...form, seoKeywords: event.target.value })} placeholder="逗号分隔" />
                  </label>
                </div>
              </section>

              <section className="official-form-section">
                <h3>社交与站长验证</h3>
                <div className="official-form-grid">
                  <label className="span-2">
                    <span>OG 图片 URL</span>
                    <input value={form.ogImageUrl} onChange={(event) => setForm({ ...form, ogImageUrl: event.target.value })} placeholder="https://..." />
                  </label>
                  <label>
                    <span>百度站长验证</span>
                    <input value={form.baiduSiteVerification} onChange={(event) => setForm({ ...form, baiduSiteVerification: event.target.value })} />
                  </label>
                  <label>
                    <span>Google 验证</span>
                    <input value={form.googleSiteVerification} onChange={(event) => setForm({ ...form, googleSiteVerification: event.target.value })} />
                  </label>
                </div>
              </section>

              <section className="official-form-section">
                <h3>抓取配置</h3>
                <div className="official-form-grid">
                  <label className="span-2">
                    <span>robots.txt</span>
                    <textarea className="code-textarea" rows={7} value={form.robotsTxt} onChange={(event) => setForm({ ...form, robotsTxt: event.target.value })} spellCheck={false} />
                  </label>
                  <label className="span-2">
                    <span>Sitemap 地址（每行一条）</span>
                    <textarea className="code-textarea" rows={3} value={form.sitemapUrls} onChange={(event) => setForm({ ...form, sitemapUrls: event.target.value })} spellCheck={false} />
                  </label>
                </div>
              </section>

              <section className="official-form-section">
                <h3>结构化数据</h3>
                <div className="official-form-grid">
                  <label className="span-2">
                    <span>JSON-LD</span>
                    <textarea
                      className="code-textarea"
                      rows={8}
                      value={form.jsonLd}
                      onChange={(event) => setForm({ ...form, jsonLd: event.target.value })}
                      placeholder='{"@context":"https://schema.org","@type":"Organization",...}'
                      spellCheck={false}
                    />
                  </label>
                </div>
              </section>
            </div>

            <div className="modal-actions">
              <div className="modal-actions-left">
                {canManage && (
                  <>
                    <button type="button" className="ghost" onClick={() => void clearSeo(editing)}>
                      清空 SEO
                    </button>
                    <button type="button" className="ghost danger-action" onClick={() => void deleteSite(editing)}>
                      删除站点
                    </button>
                  </>
                )}
              </div>
              <button type="button" className="ghost" onClick={closeModal}>
                取消
              </button>
              <button type="button" className="primary" disabled={saving} onClick={() => void saveSeo()}>
                {saving ? "保存中…" : "保存"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
