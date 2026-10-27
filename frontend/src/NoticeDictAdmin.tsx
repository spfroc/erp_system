import { useEffect, useState } from "react";
import { Pencil, Plus, Trash2, X } from "lucide-react";
import { backendApiUrl } from "./apiConfig";
import { AuthExpiredError } from "./db";
import { CopyableLine, Pagination, SearchField } from "./listUi";

type DictKind = "org_type" | "nature";

type DictItem = {
  id: number;
  kind: DictKind;
  name: string;
  sortOrder: number;
  enabled: boolean;
  updatedAt: string;
};

const TABS: Array<{ kind: DictKind; label: string }> = [
  { kind: "org_type", label: "公告类型" },
  { kind: "nature", label: "性质" },
];

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

export function NoticeDictAdmin({
  onNotice,
  canManageOrgType,
  canManageNature,
}: {
  onNotice: (notice: { type: "success" | "error"; message: string }) => void;
  canManageOrgType: boolean;
  canManageNature: boolean;
}) {
  const [kind, setKind] = useState<DictKind>("org_type");
  const [search, setSearch] = useState("");
  const [query, setQuery] = useState("");
  const [page, setPage] = useState(1);
  const [total, setTotal] = useState(0);
  const [items, setItems] = useState<DictItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [refreshKey, setRefreshKey] = useState(0);
  const [editing, setEditing] = useState<Partial<DictItem> | null>(null);
  const [saving, setSaving] = useState(false);
  const pageSize = 20;
  const canManage = kind === "org_type" ? canManageOrgType : canManageNature;
  const kindLabel = TABS.find((item) => item.kind === kind)?.label || "选项";

  useEffect(() => {
    const timer = window.setTimeout(() => setQuery(search.trim()), 300);
    return () => window.clearTimeout(timer);
  }, [search]);

  useEffect(() => {
    setPage(1);
  }, [query, kind]);

  useEffect(() => {
    const params = new URLSearchParams({
      kind,
      page: String(page),
      page_size: String(pageSize),
    });
    if (query) params.set("search", query);
    let cancelled = false;
    setLoading(true);
    fetch(backendApiUrl(`/api/notices/dict/?${params.toString()}`), { credentials: "include" })
      .then((response) => readJson<{ items: DictItem[]; total: number }>(response))
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
  }, [kind, page, query, refreshKey, onNotice]);

  const totalPages = Math.max(1, Math.ceil(total / pageSize));

  async function saveItem() {
    if (!editing) return;
    const name = (editing.name || "").trim();
    if (!name) {
      onNotice({ type: "error", message: "名称不能为空" });
      return;
    }
    setSaving(true);
    try {
      const body = {
        kind,
        name,
        sortOrder: Number(editing.sortOrder) || 0,
        enabled: editing.enabled !== false,
      };
      const response = await fetch(
        backendApiUrl(editing.id ? `/api/notices/dict/${editing.id}/` : "/api/notices/dict/"),
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

  async function removeItem(item: DictItem) {
    if (!window.confirm(`确定删除「${item.name}」？已打标数据不会自动改写。`)) return;
    try {
      const response = await fetch(backendApiUrl(`/api/notices/dict/${item.id}/`), {
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
          <div className="segmented" role="tablist" aria-label="字典分类">
            {TABS.map((tab) => (
              <button
                key={tab.kind}
                type="button"
                className={kind === tab.kind ? "active" : ""}
                onClick={() => {
                  setKind(tab.kind);
                  setSearch("");
                  setEditing(null);
                }}
              >
                {tab.label}
              </button>
            ))}
          </div>
          <div className="page-toolbar-actions">
            <SearchField value={search} onChange={setSearch} placeholder="搜索名称" />
            {canManage && (
              <button
                className="primary"
                type="button"
                onClick={() => setEditing({ name: "", sortOrder: (total + 1) * 10, enabled: true })}
              >
                <Plus size={16} /> 新增{kindLabel}
              </button>
            )}
          </div>
        </div>

        <div className="table">
          <div className="table-row notice-dict-table head">
            <span>名称</span>
            <span>排序</span>
            <span>状态</span>
            <span>操作</span>
          </div>
          {items.map((item) => (
            <div className="table-row notice-dict-table" key={item.id}>
              <div className="notice-dict-main-cell">
                <CopyableLine text={item.name} label="名称">
                  <strong>{item.name}</strong>
                </CopyableLine>
              </div>
              <span>{item.sortOrder}</span>
              <span>{item.enabled ? "启用" : "停用"}</span>
              <div className="option-actions">
                {canManage && (
                  <>
                    <button type="button" className="copy-link" onClick={() => setEditing(item)}>
                      <Pencil size={14} /> 修改
                    </button>
                    <button type="button" className="copy-link danger-action" onClick={() => void removeItem(item)}>
                      <Trash2 size={14} /> 删除
                    </button>
                  </>
                )}
              </div>
            </div>
          ))}
          {loading && <div className="table-empty">加载中…</div>}
          {!loading && items.length === 0 && <div className="table-empty">暂无数据</div>}
        </div>

        <Pagination page={page} totalPages={totalPages} total={total} pageSize={pageSize} onPageChange={setPage} />
      </div>

      {editing && (
        <div className="modal-backdrop" role="presentation" onClick={() => !saving && setEditing(null)}>
          <div
            className="modal notice-dict-modal"
            role="dialog"
            aria-modal="true"
            aria-label={editing.id ? `修改${kindLabel}` : `新增${kindLabel}`}
            onClick={(event) => event.stopPropagation()}
          >
            <div className="modal-head">
              <div>
                <h2>{editing.id ? `修改${kindLabel}` : `新增${kindLabel}`}</h2>
                <p>名称会用于标签修正筛选与下拉；停用后不再出现在选项中。</p>
              </div>
              <button type="button" className="icon-button" onClick={() => setEditing(null)} aria-label="关闭">
                <X size={18} />
              </button>
            </div>
            <div className="notice-dict-form">
              <label className="span-2">
                <span>名称</span>
                <input
                  value={editing.name || ""}
                  onChange={(event) => setEditing({ ...editing, name: event.target.value })}
                  placeholder={kind === "org_type" ? "如：医疗卫生" : "如：事业单位"}
                  autoFocus
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
              <label className="notice-dict-enabled">
                <span>状态</span>
                <span className="notice-dict-enabled-control">
                  <input
                    type="checkbox"
                    checked={editing.enabled !== false}
                    onChange={(event) => setEditing({ ...editing, enabled: event.target.checked })}
                  />
                  <em>启用（停用后不出现在标签下拉）</em>
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
