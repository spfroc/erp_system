import { useEffect, useMemo, useState } from "react";
import { Pencil, Plus, Trash2, X } from "lucide-react";
import { backendApiUrl } from "./apiConfig";
import { AuthExpiredError } from "./db";
import { SearchField } from "./listUi";

type SiteItem = {
  id: number;
  siteId: string;
  label: string;
  enabled: boolean;
};

type CategoryItem = {
  id: number;
  name: string;
  enabled: boolean;
  sortOrder: number;
  optionCount?: number;
  updatedAt?: string;
};

type SiteOption = {
  id: number;
  siteId: string;
  channelKey: string;
  channelLabel: string;
  noticeType: string;
  noticeTypeLabel: string;
  enabled: boolean;
  sortOrder: number;
};

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

function optionLabel(option: SiteOption) {
  const channel = option.channelLabel || option.channelKey || "不区分种类";
  const notice = option.noticeTypeLabel || option.noticeType;
  return `${channel} / ${notice}`;
}

export function NoticeCategoryMap({
  onNotice,
  canManage,
}: {
  onNotice: (notice: { type: "success" | "error"; message: string }) => void;
  canManage: boolean;
}) {
  const [sites, setSites] = useState<SiteItem[]>([]);
  const [categories, setCategories] = useState<CategoryItem[]>([]);
  const [options, setOptions] = useState<SiteOption[]>([]);
  const [selectedCategoryId, setSelectedCategoryId] = useState<number | null>(null);
  const [selectedOptionIds, setSelectedOptionIds] = useState<number[]>([]);
  const [draftOptionIds, setDraftOptionIds] = useState<number[]>([]);
  const [siteFilter, setSiteFilter] = useState("");
  const [optionSearch, setOptionSearch] = useState("");
  const [categorySearch, setCategorySearch] = useState("");
  const [loading, setLoading] = useState(false);
  const [savingLinks, setSavingLinks] = useState(false);
  const [refreshKey, setRefreshKey] = useState(0);
  const [editingCategory, setEditingCategory] = useState<Partial<CategoryItem> | null>(null);
  const [savingCategory, setSavingCategory] = useState(false);

  const siteLabelById = useMemo(() => {
    const map = new Map<string, string>();
    for (const site of sites) map.set(site.siteId, site.label);
    return map;
  }, [sites]);

  const filteredCategories = useMemo(() => {
    const q = categorySearch.trim().toLowerCase();
    if (!q) return categories;
    return categories.filter((item) => item.name.toLowerCase().includes(q));
  }, [categories, categorySearch]);

  const filteredOptions = useMemo(() => {
    const q = optionSearch.trim().toLowerCase();
    return options.filter((item) => {
      if (siteFilter && item.siteId !== siteFilter) return false;
      if (!q) return true;
      const hay = `${item.channelLabel} ${item.channelKey} ${item.noticeTypeLabel} ${item.noticeType}`.toLowerCase();
      return hay.includes(q);
    });
  }, [options, optionSearch, siteFilter]);

  const optionsBySite = useMemo(() => {
    const groups = new Map<string, SiteOption[]>();
    for (const option of filteredOptions) {
      const list = groups.get(option.siteId) || [];
      list.push(option);
      groups.set(option.siteId, list);
    }
    return [...groups.entries()].map(([siteId, items]) => ({
      siteId,
      label: siteLabelById.get(siteId) || siteId,
      items,
    }));
  }, [filteredOptions, siteLabelById]);

  const selectedCategory = categories.find((item) => item.id === selectedCategoryId) || null;
  const dirty =
    selectedCategoryId != null &&
    [...draftOptionIds].sort((a, b) => a - b).join(",") !==
      [...selectedOptionIds].sort((a, b) => a - b).join(",");

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    Promise.all([
      fetch(backendApiUrl("/api/notices/sites/meta/"), { credentials: "include" }).then((response) =>
        readJson<{ sites: SiteItem[] }>(response),
      ),
      fetch(backendApiUrl("/api/notices/mapped-categories/?page_size=200"), {
        credentials: "include",
      }).then((response) => readJson<{ items: CategoryItem[] }>(response)),
      fetch(backendApiUrl("/api/notices/site-options/?page_size=200"), {
        credentials: "include",
      }).then((response) => readJson<{ items: SiteOption[] }>(response)),
    ])
      .then(([meta, categoryData, optionData]) => {
        if (cancelled) return;
        const nextCategories = categoryData.items || [];
        setSites(meta.sites || []);
        setCategories(nextCategories);
        setOptions(optionData.items || []);
        setSelectedCategoryId((current) => {
          if (current && nextCategories.some((item) => item.id === current)) return current;
          return nextCategories[0]?.id ?? null;
        });
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
  }, [refreshKey]);

  useEffect(() => {
    if (!selectedCategoryId) {
      setSelectedOptionIds([]);
      setDraftOptionIds([]);
      return;
    }
    let cancelled = false;
    fetch(
      backendApiUrl(`/api/notices/mapped-categories/${selectedCategoryId}/options/`),
      { credentials: "include" },
    )
      .then((response) => readJson<{ optionIds: number[] }>(response))
      .then((data) => {
        if (cancelled) return;
        const ids = (data.optionIds || []).map(Number);
        setSelectedOptionIds(ids);
        setDraftOptionIds(ids);
      })
      .catch((error) => {
        if (cancelled) return;
        if (error instanceof AuthExpiredError) throw error;
        onNotice({ type: "error", message: error instanceof Error ? error.message : "加载对照失败" });
      });
    return () => {
      cancelled = true;
    };
  }, [selectedCategoryId, refreshKey]);

  function toggleOption(optionId: number) {
    setDraftOptionIds((current) =>
      current.includes(optionId) ? current.filter((id) => id !== optionId) : [...current, optionId],
    );
  }

  function toggleSiteAll(siteId: string, checked: boolean) {
    const ids = options.filter((item) => item.siteId === siteId).map((item) => item.id);
    setDraftOptionIds((current) => {
      if (checked) return Array.from(new Set([...current, ...ids]));
      const drop = new Set(ids);
      return current.filter((id) => !drop.has(id));
    });
  }

  async function saveLinks() {
    if (!selectedCategoryId || !canManage) return;
    setSavingLinks(true);
    try {
      const response = await fetch(
        backendApiUrl(`/api/notices/mapped-categories/${selectedCategoryId}/options/`),
        {
          method: "PUT",
          credentials: "include",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ optionIds: draftOptionIds }),
        },
      );
      const data = await readJson<{ optionIds: number[] }>(response);
      const ids = (data.optionIds || []).map(Number);
      setSelectedOptionIds(ids);
      setDraftOptionIds(ids);
      setRefreshKey((value) => value + 1);
      onNotice({ type: "success", message: "对照已保存" });
    } catch (error) {
      if (error instanceof AuthExpiredError) throw error;
      onNotice({ type: "error", message: error instanceof Error ? error.message : "保存失败" });
    } finally {
      setSavingLinks(false);
    }
  }

  async function saveCategory() {
    if (!editingCategory) return;
    const name = (editingCategory.name || "").trim();
    if (!name) {
      onNotice({ type: "error", message: "分类名称不能为空" });
      return;
    }
    setSavingCategory(true);
    try {
      const body = {
        name,
        sortOrder: Number(editingCategory.sortOrder) || 0,
        enabled: editingCategory.enabled !== false,
      };
      const response = await fetch(
        backendApiUrl(
          editingCategory.id
            ? `/api/notices/mapped-categories/${editingCategory.id}/`
            : "/api/notices/mapped-categories/",
        ),
        {
          method: editingCategory.id ? "PATCH" : "POST",
          credentials: "include",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(body),
        },
      );
      const data = await readJson<{ item: CategoryItem }>(response);
      setEditingCategory(null);
      setRefreshKey((value) => value + 1);
      if (data.item?.id) setSelectedCategoryId(data.item.id);
      onNotice({ type: "success", message: editingCategory.id ? "分类已保存" : "分类已新建" });
    } catch (error) {
      if (error instanceof AuthExpiredError) throw error;
      onNotice({ type: "error", message: error instanceof Error ? error.message : "保存失败" });
    } finally {
      setSavingCategory(false);
    }
  }

  async function removeCategory(item: CategoryItem) {
    if (!window.confirm(`确定删除映射分类「${item.name}」？对照关系也会一并删除。`)) return;
    try {
      const response = await fetch(backendApiUrl(`/api/notices/mapped-categories/${item.id}/`), {
        method: "DELETE",
        credentials: "include",
      });
      await readJson(response);
      if (selectedCategoryId === item.id) setSelectedCategoryId(null);
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
            先新建映射分类，再勾选各站点的种类/方式选项进行多对多对照。公告列表类型筛选项只显示这些映射分类。
          </p>
        </div>

        <div className="notice-map-layout">
          <section className="notice-map-categories">
            <div className="page-toolbar">
              <strong>映射分类</strong>
              <div className="page-toolbar-actions">
                <SearchField value={categorySearch} onChange={setCategorySearch} placeholder="搜索分类" />
                {canManage && (
                  <button
                    className="primary"
                    type="button"
                    onClick={() =>
                      setEditingCategory({
                        name: "",
                        sortOrder: (categories.length + 1) * 10,
                        enabled: true,
                      })
                    }
                  >
                    <Plus size={16} /> 新建分类
                  </button>
                )}
              </div>
            </div>
            <div className="notice-map-category-list">
              {filteredCategories.map((item) => (
                <button
                  key={item.id}
                  type="button"
                  className={`notice-map-category-item ${selectedCategoryId === item.id ? "active" : ""}`}
                  onClick={() => setSelectedCategoryId(item.id)}
                >
                  <span>
                    <strong>{item.name}</strong>
                    <em>
                      {item.optionCount ?? 0} 个选项
                      {!item.enabled ? " · 停用" : ""}
                    </em>
                  </span>
                  {canManage && (
                    <span className="option-actions" onClick={(event) => event.stopPropagation()}>
                      <button type="button" className="copy-link" onClick={() => setEditingCategory(item)}>
                        <Pencil size={14} />
                      </button>
                      <button
                        type="button"
                        className="copy-link danger-action"
                        onClick={() => void removeCategory(item)}
                      >
                        <Trash2 size={14} />
                      </button>
                    </span>
                  )}
                </button>
              ))}
              {loading && <div className="table-empty">加载中…</div>}
              {!loading && filteredCategories.length === 0 && <div className="table-empty">暂无映射分类</div>}
            </div>
          </section>

          <section className="notice-map-options">
            <div className="page-toolbar">
              <strong>
                {selectedCategory ? `对照：${selectedCategory.name}` : "请选择左侧映射分类"}
              </strong>
              <div className="page-toolbar-actions">
                <select
                  value={siteFilter}
                  onChange={(event) => setSiteFilter(event.target.value)}
                  aria-label="按站点筛选选项"
                  disabled={!selectedCategory}
                >
                  <option value="">全部站点</option>
                  {sites.map((site) => (
                    <option key={site.siteId} value={site.siteId}>
                      {site.label}
                    </option>
                  ))}
                </select>
                <SearchField
                  value={optionSearch}
                  onChange={setOptionSearch}
                  placeholder="搜索种类 / 方式"
                />
                {canManage && selectedCategory && (
                  <button
                    className="primary"
                    type="button"
                    disabled={!dirty || savingLinks}
                    onClick={() => void saveLinks()}
                  >
                    {savingLinks ? "保存中…" : "保存对照"}
                  </button>
                )}
              </div>
            </div>

            {!selectedCategory && <div className="table-empty">选择一个映射分类后，勾选右侧站点选项</div>}
            {selectedCategory &&
              optionsBySite.map((group) => {
                const groupIds = group.items.map((item) => item.id);
                const checkedCount = groupIds.filter((id) => draftOptionIds.includes(id)).length;
                const allChecked = groupIds.length > 0 && checkedCount === groupIds.length;
                return (
                  <div className="notice-map-option-group" key={group.siteId}>
                    <label className="notice-map-option-group-head">
                      <input
                        type="checkbox"
                        checked={allChecked}
                        disabled={!canManage}
                        onChange={(event) => toggleSiteAll(group.siteId, event.target.checked)}
                      />
                      <strong>{group.label}</strong>
                      <em>
                        {checkedCount}/{group.items.length}
                      </em>
                    </label>
                    <div className="notice-map-option-grid">
                      {group.items.map((option) => (
                        <label key={option.id} className="notice-map-option-item">
                          <input
                            type="checkbox"
                            checked={draftOptionIds.includes(option.id)}
                            disabled={!canManage}
                            onChange={() => toggleOption(option.id)}
                          />
                          <span>
                            <strong>{optionLabel(option)}</strong>
                            <em>
                              {option.channelKey ? `种类 ${option.channelKey}` : "不区分种类"} · 方式{" "}
                              {option.noticeType}
                            </em>
                          </span>
                        </label>
                      ))}
                    </div>
                  </div>
                );
              })}
            {selectedCategory && !loading && optionsBySite.length === 0 && (
              <div className="table-empty">当前筛选下没有站点选项</div>
            )}
          </section>
        </div>
      </div>

      {editingCategory && (
        <div
          className="modal-backdrop"
          role="presentation"
          onClick={() => !savingCategory && setEditingCategory(null)}
        >
          <div
            className="modal notice-dict-modal"
            role="dialog"
            aria-modal="true"
            aria-label={editingCategory.id ? "修改映射分类" : "新建映射分类"}
            onClick={(event) => event.stopPropagation()}
          >
            <div className="modal-head">
              <div>
                <h2>{editingCategory.id ? "修改映射分类" : "新建映射分类"}</h2>
                <p>分类名称会出现在公告列表的类型筛选中。</p>
              </div>
              <button
                type="button"
                className="icon-button"
                onClick={() => setEditingCategory(null)}
                aria-label="关闭"
              >
                <X size={18} />
              </button>
            </div>
            <div className="notice-dict-form">
              <label className="span-2">
                <span>分类名称</span>
                <input
                  value={editingCategory.name || ""}
                  onChange={(event) => setEditingCategory({ ...editingCategory, name: event.target.value })}
                  placeholder="如：采购公告"
                  autoFocus
                />
              </label>
              <label>
                <span>排序</span>
                <input
                  type="number"
                  value={editingCategory.sortOrder ?? 0}
                  onChange={(event) =>
                    setEditingCategory({
                      ...editingCategory,
                      sortOrder: Number(event.target.value) || 0,
                    })
                  }
                />
              </label>
              <label className="notice-dict-enabled">
                <span>状态</span>
                <span className="notice-dict-enabled-control">
                  <input
                    type="checkbox"
                    checked={editingCategory.enabled !== false}
                    onChange={(event) =>
                      setEditingCategory({ ...editingCategory, enabled: event.target.checked })
                    }
                  />
                  <em>启用</em>
                </span>
              </label>
            </div>
            <div className="modal-actions">
              <button type="button" onClick={() => setEditingCategory(null)} disabled={savingCategory}>
                取消
              </button>
              <button
                type="button"
                className="primary"
                onClick={() => void saveCategory()}
                disabled={savingCategory}
              >
                {savingCategory ? "保存中…" : "保存"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
