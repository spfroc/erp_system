import { useEffect, useState } from "react";
import { Pencil, Plus, Trash2, X } from "lucide-react";
import { backendApiUrl } from "./apiConfig";
import { AuthExpiredError } from "./db";
import { CopyableLine, Pagination, SearchField } from "./listUi";

type SiteItem = {
  id: number;
  siteId: string;
  label: string;
  enabled: boolean;
  sortOrder: number;
  fixedRegion: string;
  updatedAt: string;
};

const BUILTIN_SITE_IDS = new Set([
  "sd-ggzyjyzx",
  "sd-gpfa-frame",
  "sd-ccgp",
  "jd-quan-yicai",
  "jd-qing-huicai",
]);

async function readJson<T>(response: Response): Promise<T> {
  const text = await response.text();
  let data: T & { detail?: string };
  try {
    data = JSON.parse(text) as T & { detail?: string };
  } catch {
    throw new Error(response.ok ? "响应不是 JSON" : `请求失败（${response.status}）`);
  }
  if (response.status === 401) throw new AuthExpiredError();
  if (!response.ok && response.status !== 503) throw new Error(data.detail || "请求失败");
  return data;
}

export function NoticeSites({
  onNotice,
  canManage,
}: {
  onNotice: (notice: { type: "success" | "error"; message: string }) => void;
  canManage: boolean;
}) {
  const [search, setSearch] = useState("");
  const [query, setQuery] = useState("");
  const [page, setPage] = useState(1);
  const [total, setTotal] = useState(0);
  const [items, setItems] = useState<SiteItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [refreshKey, setRefreshKey] = useState(0);
  const [editing, setEditing] = useState<Partial<SiteItem> | null>(null);
  const [saving, setSaving] = useState(false);
  const [pageSize, setPageSizeState] = useState(50);
  const setPageSize = (next: number) => {
    setPageSizeState(next);
    setPage(1);
  };

  useEffect(() => {
    const timer = window.setTimeout(() => setQuery(search.trim()), 300);
    return () => window.clearTimeout(timer);
  }, [search]);

  useEffect(() => {
    setPage(1);
  }, [query]);

  useEffect(() => {
    const params = new URLSearchParams({
      page: String(page),
      page_size: String(pageSize),
    });
    if (query) params.set("search", query);
    let cancelled = false;
    setLoading(true);
    fetch(backendApiUrl(`/api/notices/sites/?${params.toString()}`), { credentials: "include" })
      .then((response) => readJson<{ items: SiteItem[]; total: number }>(response))
      .then((data) => {
        if (cancelled) return;
        setItems(data.items || []);
        setTotal(data.total || 0);
      })
      .catch((error) => {
        if (cancelled) return;
        if (error instanceof AuthExpiredError) throw error;
        onNotice({ type: "error", message: error instanceof Error ? error.message : "加载失败" });
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
    // onNotice 故意不入依赖：父组件每次渲染会换新函数，避免 4xx 后死循环请求
  }, [page, pageSize, query, refreshKey]);

  const totalPages = Math.max(1, Math.ceil(total / pageSize));

  async function saveItem() {
    if (!editing) return;
    const siteId = (editing.siteId || "").trim();
    const label = (editing.label || "").trim();
    if (!editing.id && !siteId) {
      onNotice({ type: "error", message: "站点 ID 不能为空" });
      return;
    }
    if (!label) {
      onNotice({ type: "error", message: "显示名称不能为空" });
      return;
    }
    setSaving(true);
    try {
      const body = {
        siteId,
        label,
        sortOrder: Number(editing.sortOrder) || 0,
        enabled: editing.enabled !== false,
        fixedRegion: (editing.fixedRegion || "").trim(),
      };
      const response = await fetch(
        backendApiUrl(editing.id ? `/api/notices/sites/${editing.id}/` : "/api/notices/sites/"),
        {
          method: editing.id ? "PATCH" : "POST",
          credentials: "include",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(body),
        },
      );
      await readJson(response);
      setEditing(null);
      setRefreshKey((value) => value + 1);
      onNotice({ type: "success", message: editing.id ? "已保存" : "已新增" });
    } catch (error) {
      if (error instanceof AuthExpiredError) throw error;
      onNotice({ type: "error", message: error instanceof Error ? error.message : "保存失败" });
    } finally {
      setSaving(false);
    }
  }

  async function removeItem(item: SiteItem) {
    if (BUILTIN_SITE_IDS.has(item.siteId)) {
      onNotice({ type: "error", message: "内置抓取站点不可删除，可改为禁用" });
      return;
    }
    if (!window.confirm(`确定删除站点「${item.label}」？`)) return;
    try {
      const response = await fetch(backendApiUrl(`/api/notices/sites/${item.id}/`), {
        method: "DELETE",
        credentials: "include",
      });
      await readJson(response);
      setRefreshKey((value) => value + 1);
      onNotice({ type: "success", message: "已删除" });
    } catch (error) {
      if (error instanceof AuthExpiredError) throw error;
      onNotice({ type: "error", message: error instanceof Error ? error.message : "删除失败" });
    }
  }

  return (
    <div className="stack">
      <div className="panel">
        <div className="page-toolbar">
          <p className="muted" style={{ margin: 0 }}>
            抓取站点默认已填充；可改显示名、排序与启用状态。禁用后公告列表站点筛选项不再出现。
          </p>
          <div className="page-toolbar-actions">
            <SearchField value={search} onChange={setSearch} placeholder="搜索站点 ID / 名称" />
            {canManage && (
              <button
                className="primary"
                type="button"
                onClick={() =>
                  setEditing({
                    siteId: "",
                    label: "",
                    sortOrder: (total + 1) * 10,
                    enabled: true,
                    fixedRegion: "",
                  })
                }
              >
                <Plus size={16} /> 新增站点
              </button>
            )}
          </div>
        </div>

        <div className="table">
          <div className="table-row notice-site-table head">
            <span>站点 ID</span>
            <span>显示名称</span>
            <span>固定地区</span>
            <span>排序</span>
            <span>状态</span>
            <span>操作</span>
          </div>
          {items.map((item) => (
            <div className="table-row notice-site-table" key={item.id}>
              <div className="notice-dict-main-cell">
                <CopyableLine text={item.siteId} label="站点 ID">
                  <code>{item.siteId}</code>
                </CopyableLine>
              </div>
              <strong>{item.label}</strong>
              <span>{item.fixedRegion || "—"}</span>
              <span>{item.sortOrder}</span>
              <span>{item.enabled ? "启用" : "停用"}</span>
              <div className="option-actions">
                {canManage && (
                  <>
                    <button type="button" className="copy-link" onClick={() => setEditing(item)}>
                      <Pencil size={14} /> 修改
                    </button>
                    {!BUILTIN_SITE_IDS.has(item.siteId) && (
                      <button
                        type="button"
                        className="copy-link danger-action"
                        onClick={() => void removeItem(item)}
                      >
                        <Trash2 size={14} /> 删除
                      </button>
                    )}
                  </>
                )}
              </div>
            </div>
          ))}
          {loading && <div className="table-empty">加载中…</div>}
          {!loading && items.length === 0 && <div className="table-empty">暂无数据</div>}
        </div>

        <Pagination
          page={page}
          totalPages={totalPages}
          total={total}
          pageSize={pageSize}
          onPageChange={setPage}
          onPageSizeChange={setPageSize}
        />
      </div>

      {editing && (
        <div className="modal-backdrop" role="presentation" onClick={() => !saving && setEditing(null)}>
          <div
            className="modal notice-dict-modal"
            role="dialog"
            aria-modal="true"
            aria-label={editing.id ? "修改站点" : "新增站点"}
            onClick={(event) => event.stopPropagation()}
          >
            <div className="modal-head">
              <div>
                <h2>{editing.id ? "修改站点" : "新增站点"}</h2>
                <p>站点 ID 需与爬虫 site_id 一致；显示名称用于公告列表筛选。</p>
              </div>
              <button type="button" className="icon-button" onClick={() => setEditing(null)} aria-label="关闭">
                <X size={18} />
              </button>
            </div>
            <div className="notice-dict-form">
              <label className="span-2">
                <span>站点 ID</span>
                <input
                  value={editing.siteId || ""}
                  onChange={(event) => setEditing({ ...editing, siteId: event.target.value })}
                  placeholder="如：sd-ccgp"
                  disabled={!!editing.id}
                  autoFocus={!editing.id}
                />
              </label>
              <label className="span-2">
                <span>显示名称</span>
                <input
                  value={editing.label || ""}
                  onChange={(event) => setEditing({ ...editing, label: event.target.value })}
                  placeholder="如：山东政府采购网"
                  autoFocus={!!editing.id}
                />
              </label>
              <label>
                <span>固定地区</span>
                <input
                  value={editing.fixedRegion || ""}
                  onChange={(event) => setEditing({ ...editing, fixedRegion: event.target.value })}
                  placeholder="可选，如：济南"
                />
              </label>
              <label>
                <span>排序</span>
                <input
                  type="number"
                  value={editing.sortOrder ?? 0}
                  onChange={(event) => setEditing({ ...editing, sortOrder: Number(event.target.value) || 0 })}
                />
              </label>
              <label className="notice-dict-enabled span-2">
                <span>状态</span>
                <span className="notice-dict-enabled-control">
                  <input
                    type="checkbox"
                    checked={editing.enabled !== false}
                    onChange={(event) => setEditing({ ...editing, enabled: event.target.checked })}
                  />
                  <em>启用（停用后不出现在公告列表站点筛选）</em>
                </span>
              </label>
            </div>
            <div className="modal-actions">
              <button type="button" onClick={() => setEditing(null)} disabled={saving}>
                取消
              </button>
              <button type="button" className="primary" onClick={() => void saveItem()} disabled={saving}>
                {saving ? "保存中…" : "保存"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
