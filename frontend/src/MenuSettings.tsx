import { useEffect, useMemo, useState, type DragEvent } from "react";
import { GripVertical, X } from "lucide-react";
import {
  AuthExpiredError,
  createCollectionItem,
  createId,
  deleteCollectionItem,
  patchCollectionItem,
  queryCollection,
} from "./db";
import { CopyableLine, SearchField } from "./listUi";
import {
  DEFAULT_NAV_CATEGORIES,
  DEFAULT_NAV_GROUPS,
  DEFAULT_NAV_ITEMS,
  NAV_ICON_MAP,
  VIEW_CATALOG,
  type CatalogViewId,
} from "./navCatalog";
import type { AppData, NavCategory, NavGroup, NavMenuItem, PermissionKey } from "./types";

type CanAccess = (permission: PermissionKey) => boolean;

type DragKind = "category" | "group" | "item";
type DragPayload = { kind: DragKind; id: string };

const PERMISSION_OPTIONS: Array<{ id: PermissionKey; label: string }> = [
  { id: "dashboard.view", label: "查看总览" },
  { id: "project.view", label: "查看项目" },
  { id: "project.create", label: "创建项目" },
  { id: "project.edit", label: "编辑项目" },
  { id: "entity.view", label: "查看主体" },
  { id: "entity.create", label: "创建主体" },
  { id: "product.view", label: "查看商品" },
  { id: "product.manage", label: "管理商品" },
  { id: "purchase.manage", label: "管理采购" },
  { id: "serviceOrder.view", label: "查看服务订单" },
  { id: "serviceOrder.manage", label: "管理服务订单" },
  { id: "salesOrder.view", label: "查看销售订单" },
  { id: "salesOrder.manage", label: "管理销售订单" },
  { id: "purchaseOrder.view", label: "查看采购订单" },
  { id: "purchaseOrder.manage", label: "管理采购订单" },
  { id: "finance.view", label: "查看财务" },
  { id: "finance.manage", label: "管理财务" },
  { id: "invoice.manage", label: "管理发票" },
  { id: "onboarding.manage", label: "管理入驻" },
  { id: "platformAccount.view", label: "查看平台账号" },
  { id: "platformAccount.manage", label: "管理平台账号" },
  { id: "trademarkCertificate.view", label: "查看商标注册证" },
  { id: "trademarkCertificate.manage", label: "管理商标注册证" },
  { id: "notice.view", label: "查看公告" },
  { id: "notice.manage", label: "管理公告" },
  { id: "site.view", label: "查看官网站点" },
  { id: "site.manage", label: "管理官网站点" },
  { id: "library.view", label: "查看政企客户资料库" },
  { id: "library.manage", label: "管理政企客户资料库" },
  { id: "mallCustomer.view", label: "查看资料库" },
  { id: "mallCustomer.manage", label: "管理资料库" },
  { id: "sms.view", label: "查看短信日志" },
  { id: "sms.manage", label: "管理短信" },
  { id: "customerAccount.view", label: "查看登录账号" },
  { id: "customerAccount.manage", label: "管理登录账号" },
  { id: "menu.view", label: "查看菜单配置" },
  { id: "menu.manage", label: "管理菜单配置" },
  { id: "lead.manage", label: "管理商机" },
  { id: "sensitive.view", label: "查看敏感信息" },
  { id: "profit.view", label: "查看利润" },
  { id: "user.manage", label: "管理用户权限" },
];

const ICON_KEYS = Object.keys(NAV_ICON_MAP);

function permissionLabel(key: string) {
  return PERMISSION_OPTIONS.find((item) => item.id === key)?.label || key;
}

function catalogLabel(viewId: string) {
  return VIEW_CATALOG.find((item) => item.viewId === viewId)?.label || viewId;
}

function sortByOrder<T extends { sortOrder: number; id: string }>(list: T[]) {
  return list.slice().sort((a, b) => (a.sortOrder ?? 0) - (b.sortOrder ?? 0) || a.id.localeCompare(b.id));
}

function reindex<T extends { sortOrder: number }>(list: T[]): T[] {
  return list.map((item, index) => ({ ...item, sortOrder: (index + 1) * 10 }));
}

function parseDrag(event: DragEvent): DragPayload | null {
  try {
    const raw = event.dataTransfer.getData("application/x-nav-drag") || event.dataTransfer.getData("text/plain");
    if (!raw) return null;
    const parsed = JSON.parse(raw) as DragPayload;
    if (parsed?.kind && parsed?.id) return parsed;
  } catch {
    // ignore
  }
  return null;
}

export function MenuSettingsPanel({
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
  const canManage = can("menu.manage");
  const [search, setSearch] = useState("");
  const [categories, setCategories] = useState<NavCategory[]>([]);
  const [groups, setGroups] = useState<NavGroup[]>([]);
  const [items, setItems] = useState<NavMenuItem[]>([]);
  const [reloadTick, setReloadTick] = useState(0);
  const [dragging, setDragging] = useState<DragPayload | null>(null);
  const [dropHint, setDropHint] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [seeding, setSeeding] = useState(false);

  const [categoryModal, setCategoryModal] = useState(false);
  const [editingCategory, setEditingCategory] = useState<NavCategory | null>(null);
  const [categoryForm, setCategoryForm] = useState({ key: "", label: "", sortOrder: "10", enabled: true });

  const [groupModal, setGroupModal] = useState(false);
  const [editingGroup, setEditingGroup] = useState<NavGroup | null>(null);
  const [groupForm, setGroupForm] = useState({
    key: "",
    label: "",
    categoryKey: "business",
    iconKey: "ClipboardList",
    sortOrder: "10",
    enabled: true,
  });

  const [itemModal, setItemModal] = useState(false);
  const [editingItem, setEditingItem] = useState<NavMenuItem | null>(null);
  const [itemForm, setItemForm] = useState({
    viewId: VIEW_CATALOG[0]?.viewId ?? "dashboard",
    label: "",
    categoryKey: "overview",
    groupKey: "",
    permission: "dashboard.view" as PermissionKey,
    iconKey: "Home",
    sortOrder: "10",
    enabled: true,
  });

  useEffect(() => {
    let cancelled = false;
    void Promise.all([
      queryCollection<NavCategory>("navCategories", { page: 1, pageSize: 200, search: "" }),
      queryCollection<NavGroup>("navGroups", { page: 1, pageSize: 200, search: "" }),
      queryCollection<NavMenuItem>("navMenuItems", { page: 1, pageSize: 500, search: "" }),
    ])
      .then(([categoryResult, groupResult, itemResult]) => {
        if (cancelled) return;
        setCategories(sortByOrder(categoryResult.items));
        setGroups(sortByOrder(groupResult.items));
        setItems(sortByOrder(itemResult.items));
      })
      .catch((error) => {
        if (cancelled || error instanceof AuthExpiredError) return;
        onNotice({ type: "error", message: error instanceof Error ? error.message : "菜单配置加载失败" });
      });
    return () => {
      cancelled = true;
    };
  }, [reloadTick, onNotice]);

  async function refreshAppNav(next?: { categories?: NavCategory[]; groups?: NavGroup[]; items?: NavMenuItem[] }) {
    const [categoryResult, groupResult, itemResult] = await Promise.all([
      queryCollection<NavCategory>("navCategories", { page: 1, pageSize: 200 }),
      queryCollection<NavGroup>("navGroups", { page: 1, pageSize: 200 }),
      queryCollection<NavMenuItem>("navMenuItems", { page: 1, pageSize: 500 }),
    ]);
    const nextCategories = next?.categories ?? categoryResult.items;
    const nextGroups = next?.groups ?? groupResult.items;
    const nextItems = next?.items ?? itemResult.items;
    setCategories(sortByOrder(nextCategories));
    setGroups(sortByOrder(nextGroups));
    setItems(sortByOrder(nextItems));
    applyData({
      ...data,
      navCategories: nextCategories,
      navGroups: nextGroups,
      navMenuItems: nextItems,
    });
  }

  const keyword = search.trim().toLowerCase();
  const tree = useMemo(() => {
    const match = (text: string) => !keyword || text.toLowerCase().includes(keyword);
    return sortByOrder(categories)
      .filter((category) => category.enabled !== false || canManage)
      .map((category) => {
        const categoryGroups = sortByOrder(groups.filter((group) => (group.categoryKey || "") === category.key))
          .map((group) => {
            const groupItems = sortByOrder(items.filter((item) => (item.groupKey || "") === group.key)).filter(
              (item) => match(item.label) || match(item.viewId) || match(group.label) || match(category.label),
            );
            const groupMatched = match(group.label) || match(group.key) || match(category.label);
            return { group, items: groupMatched && !keyword ? sortByOrder(items.filter((item) => (item.groupKey || "") === group.key)) : groupItems };
          })
          .filter((section) => !keyword || section.items.length > 0 || match(section.group.label));
        const topItems = sortByOrder(
          items.filter((item) => !(item.groupKey || "") && (item.categoryKey || "") === category.key),
        ).filter((item) => match(item.label) || match(item.viewId) || match(category.label));
        const categoryMatched = match(category.label) || match(category.key);
        if (keyword && !categoryMatched && topItems.length === 0 && categoryGroups.length === 0) return null;
        return { category, topItems, groups: categoryGroups };
      })
      .filter(Boolean) as Array<{
      category: NavCategory;
      topItems: NavMenuItem[];
      groups: Array<{ group: NavGroup; items: NavMenuItem[] }>;
    }>;
  }, [categories, groups, items, keyword, canManage]);

  function beginDrag(event: DragEvent, payload: DragPayload) {
    if (!canManage) return;
    event.dataTransfer.effectAllowed = "move";
    event.dataTransfer.setData("application/x-nav-drag", JSON.stringify(payload));
    event.dataTransfer.setData("text/plain", JSON.stringify(payload));
    setDragging(payload);
  }

  function endDrag() {
    setDragging(null);
    setDropHint(null);
  }

  async function persistOrders(nextCategories: NavCategory[], nextGroups: NavGroup[], nextItems: NavMenuItem[]) {
    setSaving(true);
    try {
      const categoryPatches = nextCategories.filter((category) => {
        const prev = categories.find((item) => item.id === category.id);
        return !prev || prev.sortOrder !== category.sortOrder || prev.enabled !== category.enabled;
      });
      const groupPatches = nextGroups.filter((group) => {
        const prev = groups.find((item) => item.id === group.id);
        return (
          !prev ||
          prev.sortOrder !== group.sortOrder ||
          prev.categoryKey !== group.categoryKey ||
          prev.enabled !== group.enabled
        );
      });
      const itemPatches = nextItems.filter((item) => {
        const prev = items.find((row) => row.id === item.id);
        return (
          !prev ||
          prev.sortOrder !== item.sortOrder ||
          prev.categoryKey !== item.categoryKey ||
          prev.groupKey !== item.groupKey ||
          prev.enabled !== item.enabled
        );
      });
      await Promise.all([
        ...categoryPatches.map((category) => patchCollectionItem("navCategories", category.id, category)),
        ...groupPatches.map((group) => patchCollectionItem("navGroups", group.id, group)),
        ...itemPatches.map((item) => patchCollectionItem("navMenuItems", item.id, item)),
      ]);
      await refreshAppNav({ categories: nextCategories, groups: nextGroups, items: nextItems });
      onNotice({ type: "success", message: "菜单顺序已更新" });
    } catch (error) {
      if (error instanceof AuthExpiredError) return;
      onNotice({ type: "error", message: error instanceof Error ? error.message : "排序保存失败" });
      setReloadTick((value) => value + 1);
    } finally {
      setSaving(false);
    }
  }

  async function handleDrop(event: DragEvent, target: { kind: DragKind; id: string }) {
    event.preventDefault();
    if (!canManage || saving) return;
    const payload = parseDrag(event) || dragging;
    endDrag();
    if (!payload) return;

    let nextCategories = sortByOrder(categories);
    let nextGroups = sortByOrder(groups);
    let nextItems = sortByOrder(items);

    if (payload.kind === "category" && target.kind === "category" && payload.id !== target.id) {
      const from = nextCategories.findIndex((item) => item.id === payload.id);
      const to = nextCategories.findIndex((item) => item.id === target.id);
      if (from < 0 || to < 0) return;
      const [moved] = nextCategories.splice(from, 1);
      nextCategories.splice(to, 0, moved);
      nextCategories = reindex(nextCategories);
    } else if (payload.kind === "group") {
      const group = nextGroups.find((item) => item.id === payload.id);
      if (!group) return;
      if (target.kind === "category") {
        const category = nextCategories.find((item) => item.id === target.id);
        if (!category) return;
        nextGroups = nextGroups.map((row) => (row.id === group.id ? { ...row, categoryKey: category.key } : row));
        const inCat = reindex(sortByOrder(nextGroups.filter((row) => row.categoryKey === category.key)));
        const others = nextGroups.filter((row) => row.categoryKey !== category.key);
        nextGroups = [...others, ...inCat];
        nextItems = nextItems.map((item) => (item.groupKey === group.key ? { ...item, categoryKey: category.key } : item));
      } else if (target.kind === "group" && payload.id !== target.id) {
        const targetGroup = nextGroups.find((item) => item.id === target.id);
        if (!targetGroup) return;
        const categoryKey = targetGroup.categoryKey;
        const siblings = sortByOrder(nextGroups.filter((item) => item.categoryKey === categoryKey && item.id !== payload.id));
        const to = siblings.findIndex((item) => item.id === target.id);
        siblings.splice(Math.max(0, to), 0, { ...group, categoryKey });
        const reindexed = reindex(siblings);
        nextGroups = [...nextGroups.filter((item) => item.categoryKey !== categoryKey), ...reindexed];
        nextItems = nextItems.map((item) => (item.groupKey === group.key ? { ...item, categoryKey } : item));
      } else {
        return;
      }
    } else if (payload.kind === "item") {
      const item = nextItems.find((row) => row.id === payload.id);
      if (!item) return;
      if (target.kind === "category") {
        const category = nextCategories.find((row) => row.id === target.id);
        if (!category) return;
        const siblings = sortByOrder(
          nextItems.filter((row) => row.id !== item.id && !(row.groupKey || "") && (row.categoryKey || "") === category.key),
        );
        const reindexed = reindex([...siblings, { ...item, categoryKey: category.key, groupKey: "" }]);
        const byId = new Map(reindexed.map((row) => [row.id, row]));
        nextItems = nextItems.map((row) => byId.get(row.id) || row);
      } else if (target.kind === "group") {
        const targetGroup = nextGroups.find((row) => row.id === target.id);
        if (!targetGroup) return;
        const siblings = sortByOrder(nextItems.filter((row) => row.id !== item.id && (row.groupKey || "") === targetGroup.key));
        const reindexed = reindex([
          ...siblings,
          { ...item, categoryKey: targetGroup.categoryKey, groupKey: targetGroup.key },
        ]);
        const byId = new Map(reindexed.map((row) => [row.id, row]));
        nextItems = nextItems.map((row) => byId.get(row.id) || row);
      } else if (target.kind === "item" && payload.id !== target.id) {
        const targetItem = nextItems.find((row) => row.id === target.id);
        if (!targetItem) return;
        const categoryKey = targetItem.categoryKey || "";
        const groupKey = targetItem.groupKey || "";
        const siblings = sortByOrder(
          nextItems.filter(
            (row) => row.id !== item.id && (row.groupKey || "") === groupKey && (row.categoryKey || "") === categoryKey,
          ),
        );
        const to = siblings.findIndex((row) => row.id === target.id);
        siblings.splice(Math.max(0, to), 0, { ...item, categoryKey, groupKey });
        const reindexed = reindex(siblings);
        const byId = new Map(reindexed.map((row) => [row.id, row]));
        nextItems = nextItems.map((row) => byId.get(row.id) || row);
      } else {
        return;
      }
    } else {
      return;
    }

    setCategories(nextCategories);
    setGroups(nextGroups);
    setItems(nextItems);
    await persistOrders(nextCategories, nextGroups, nextItems);
  }

  async function seedDefaults() {
    if (!canManage) return;
    setSeeding(true);
    try {
      const [categoryResult, groupResult, itemResult] = await Promise.all([
        queryCollection<NavCategory>("navCategories", { page: 1, pageSize: 1 }),
        queryCollection<NavGroup>("navGroups", { page: 1, pageSize: 1 }),
        queryCollection<NavMenuItem>("navMenuItems", { page: 1, pageSize: 1 }),
      ]);
      if (categoryResult.total === 0) {
        for (const row of DEFAULT_NAV_CATEGORIES) await createCollectionItem("navCategories", { ...row });
      }
      if (groupResult.total === 0) {
        for (const row of DEFAULT_NAV_GROUPS) await createCollectionItem("navGroups", { ...row });
      }
      if (itemResult.total === 0) {
        for (const row of DEFAULT_NAV_ITEMS) await createCollectionItem("navMenuItems", { ...row });
      }
      await refreshAppNav();
      onNotice({ type: "success", message: "已写入默认菜单配置" });
    } catch (error) {
      if (error instanceof AuthExpiredError) return;
      onNotice({ type: "error", message: error instanceof Error ? error.message : "初始化失败" });
    } finally {
      setSeeding(false);
    }
  }

  function openCreateCategory() {
    setEditingCategory(null);
    setCategoryForm({ key: "", label: "", sortOrder: String((categories.length + 1) * 10), enabled: true });
    setCategoryModal(true);
  }

  function openEditCategory(category: NavCategory) {
    setEditingCategory(category);
    setCategoryForm({
      key: category.key,
      label: category.label,
      sortOrder: String(category.sortOrder ?? 0),
      enabled: category.enabled !== false,
    });
    setCategoryModal(true);
  }

  async function saveCategory() {
    const key = categoryForm.key.trim();
    const label = categoryForm.label.trim();
    if (!key || !label) {
      onNotice({ type: "error", message: "请填写分类 key 与显示名" });
      return;
    }
    setSaving(true);
    try {
      const payload: NavCategory = {
        id: editingCategory?.id || createId("nav-cat"),
        key,
        label,
        sortOrder: Number(categoryForm.sortOrder) || 0,
        enabled: categoryForm.enabled,
      };
      if (editingCategory) await patchCollectionItem("navCategories", payload.id, payload);
      else await createCollectionItem("navCategories", payload);
      setCategoryModal(false);
      await refreshAppNav();
      onNotice({ type: "success", message: editingCategory ? "分类已更新" : "分类已创建" });
    } catch (error) {
      if (error instanceof AuthExpiredError) return;
      onNotice({ type: "error", message: error instanceof Error ? error.message : "保存失败" });
    } finally {
      setSaving(false);
    }
  }

  async function removeCategory(category: NavCategory) {
    if (!window.confirm(`确认删除分类「${category.label}」？其下分组与菜单项不会自动删除。`)) return;
    try {
      await deleteCollectionItem("navCategories", category.id);
      await refreshAppNav();
      onNotice({ type: "success", message: "分类已删除" });
    } catch (error) {
      if (error instanceof AuthExpiredError) return;
      onNotice({ type: "error", message: error instanceof Error ? error.message : "删除失败" });
    }
  }

  function openCreateGroup(categoryKey?: string) {
    setEditingGroup(null);
    setGroupForm({
      key: "",
      label: "",
      categoryKey: categoryKey || categories[0]?.key || "business",
      iconKey: "ClipboardList",
      sortOrder: "10",
      enabled: true,
    });
    setGroupModal(true);
  }

  function openEditGroup(group: NavGroup) {
    setEditingGroup(group);
    setGroupForm({
      key: group.key,
      label: group.label,
      categoryKey: group.categoryKey || "",
      iconKey: group.iconKey || "ClipboardList",
      sortOrder: String(group.sortOrder ?? 0),
      enabled: group.enabled !== false,
    });
    setGroupModal(true);
  }

  async function saveGroup() {
    const key = groupForm.key.trim();
    const label = groupForm.label.trim();
    if (!key || !label) {
      onNotice({ type: "error", message: "请填写分组 key 与显示名" });
      return;
    }
    setSaving(true);
    try {
      const payload: NavGroup = {
        id: editingGroup?.id || createId("nav-group"),
        key,
        label,
        categoryKey: groupForm.categoryKey,
        iconKey: groupForm.iconKey,
        sortOrder: Number(groupForm.sortOrder) || 0,
        enabled: groupForm.enabled,
      };
      if (editingGroup) await patchCollectionItem("navGroups", payload.id, payload);
      else await createCollectionItem("navGroups", payload);
      setGroupModal(false);
      await refreshAppNav();
      onNotice({ type: "success", message: editingGroup ? "分组已更新" : "分组已创建" });
    } catch (error) {
      if (error instanceof AuthExpiredError) return;
      onNotice({ type: "error", message: error instanceof Error ? error.message : "保存失败" });
    } finally {
      setSaving(false);
    }
  }

  async function removeGroup(group: NavGroup) {
    if (!window.confirm(`确认删除分组「${group.label}」？其下菜单项不会自动删除。`)) return;
    try {
      await deleteCollectionItem("navGroups", group.id);
      await refreshAppNav();
      onNotice({ type: "success", message: "分组已删除" });
    } catch (error) {
      if (error instanceof AuthExpiredError) return;
      onNotice({ type: "error", message: error instanceof Error ? error.message : "删除失败" });
    }
  }

  function openCreateItem(categoryKey?: string, groupKey?: string) {
    const catalog = VIEW_CATALOG[0];
    setEditingItem(null);
    setItemForm({
      viewId: catalog?.viewId ?? "dashboard",
      label: catalog?.label ?? "",
      categoryKey: categoryKey || categories[0]?.key || "overview",
      groupKey: groupKey || "",
      permission: catalog?.permission ?? "dashboard.view",
      iconKey: catalog?.iconKey ?? "Home",
      sortOrder: "10",
      enabled: true,
    });
    setItemModal(true);
  }

  function openEditItem(item: NavMenuItem) {
    setEditingItem(item);
    setItemForm({
      viewId: (item.viewId as CatalogViewId) || "dashboard",
      label: item.label,
      categoryKey: item.categoryKey || "",
      groupKey: item.groupKey || "",
      permission: item.permission,
      iconKey: item.iconKey || "LayoutList",
      sortOrder: String(item.sortOrder ?? 0),
      enabled: item.enabled !== false,
    });
    setItemModal(true);
  }

  function onPickView(viewId: CatalogViewId) {
    const catalog = VIEW_CATALOG.find((item) => item.viewId === viewId);
    setItemForm((current) => ({
      ...current,
      viewId,
      label: current.label || catalog?.label || viewId,
      permission: catalog?.permission ?? current.permission,
      iconKey: catalog?.iconKey ?? current.iconKey,
    }));
  }

  async function saveItem() {
    const label = itemForm.label.trim();
    if (!label) {
      onNotice({ type: "error", message: "请填写显示名" });
      return;
    }
    if (!VIEW_CATALOG.some((item) => item.viewId === itemForm.viewId)) {
      onNotice({ type: "error", message: "请选择已注册的页面" });
      return;
    }
    const group = groups.find((row) => row.key === itemForm.groupKey);
    const categoryKey = itemForm.groupKey ? group?.categoryKey || itemForm.categoryKey : itemForm.categoryKey;
    setSaving(true);
    try {
      const payload: NavMenuItem = {
        id: editingItem?.id || createId("nav-item"),
        viewId: itemForm.viewId,
        label,
        categoryKey,
        groupKey: itemForm.groupKey,
        permission: itemForm.permission,
        iconKey: itemForm.iconKey,
        sortOrder: Number(itemForm.sortOrder) || 0,
        enabled: itemForm.enabled,
      };
      if (editingItem) await patchCollectionItem("navMenuItems", payload.id, payload);
      else await createCollectionItem("navMenuItems", payload);
      setItemModal(false);
      await refreshAppNav();
      onNotice({ type: "success", message: editingItem ? "菜单项已更新" : "菜单项已创建" });
    } catch (error) {
      if (error instanceof AuthExpiredError) return;
      onNotice({ type: "error", message: error instanceof Error ? error.message : "保存失败" });
    } finally {
      setSaving(false);
    }
  }

  async function removeItem(item: NavMenuItem) {
    if (!window.confirm(`确认删除菜单「${item.label}」？`)) return;
    try {
      await deleteCollectionItem("navMenuItems", item.id);
      await refreshAppNav();
      onNotice({ type: "success", message: "菜单项已删除" });
    } catch (error) {
      if (error instanceof AuthExpiredError) return;
      onNotice({ type: "error", message: error instanceof Error ? error.message : "删除失败" });
    }
  }

  const emptyConfig = !categories.length && !groups.length && !items.length;

  return (
    <div className="stack">
      <div className="panel">
        <div className="panel-title action-title">
          <div>
            <h2>菜单管理</h2>
            <p>按「分类 → 分组 → 菜单项」级联配置；拖动手柄可调整顺序与归属。仅可挂载代码已注册页面。</p>
          </div>
          <div className="panel-title-buttons">
            {canManage && emptyConfig && (
              <button className="ghost" type="button" disabled={seeding} onClick={() => void seedDefaults()}>
                {seeding ? "初始化中…" : "写入默认菜单"}
              </button>
            )}
            {canManage && (
              <>
                <button className="ghost" type="button" onClick={openCreateCategory}>
                  新增分类
                </button>
                <button className="ghost" type="button" onClick={() => openCreateGroup()}>
                  新增分组
                </button>
                <button className="primary" type="button" onClick={() => openCreateItem()}>
                  新增菜单项
                </button>
              </>
            )}
          </div>
        </div>

        <div className="platform-account-toolbar">
          <SearchField value={search} onChange={setSearch} placeholder="搜索分类、分组或菜单…" />
        </div>

        <div className="menu-cascade">
          {tree.map(({ category, topItems, groups: categoryGroups }, index) => (
            <div key={category.id}>
              {index > 0 && <div className="menu-cascade-sep" aria-hidden="true" />}
              <section
                className={`menu-cascade-category${dropHint === `category:${category.id}` ? " drop-target" : ""}`}
                onDragOver={(event) => {
                  if (!canManage) return;
                  event.preventDefault();
                  setDropHint(`category:${category.id}`);
                }}
                onDrop={(event) => void handleDrop(event, { kind: "category", id: category.id })}
              >
                <div
                  className="menu-cascade-category-head"
                  draggable={canManage}
                  onDragStart={(event) => beginDrag(event, { kind: "category", id: category.id })}
                  onDragEnd={endDrag}
                >
                  {canManage && (
                    <span className="grip" title="拖动分类排序">
                      <GripVertical size={16} />
                    </span>
                  )}
                  <div>
                    <strong>{category.label}</strong>
                    <em> · {category.key} · 排序 {category.sortOrder}</em>
                  </div>
                  <span className="spacer" />
                  {canManage && (
                    <div className="option-actions">
                      <button className="copy-link" type="button" onClick={() => openCreateItem(category.key, "")}>
                        加顶级项
                      </button>
                      <button className="copy-link" type="button" onClick={() => openCreateGroup(category.key)}>
                        加分组
                      </button>
                      <button className="copy-link" type="button" onClick={() => openEditCategory(category)}>
                        编辑
                      </button>
                      <button className="copy-link danger-action" type="button" onClick={() => void removeCategory(category)}>
                        删除
                      </button>
                    </div>
                  )}
                </div>
                <div className="menu-cascade-body">
                  {topItems.map((item) => (
                    <div
                      key={item.id}
                      className={`menu-cascade-row is-top-item${dragging?.id === item.id ? " dragging" : ""}${
                        dropHint === `item:${item.id}` ? " drop-target" : ""
                      }`}
                      draggable={canManage}
                      onDragStart={(event) => beginDrag(event, { kind: "item", id: item.id })}
                      onDragEnd={endDrag}
                      onDragOver={(event) => {
                        if (!canManage) return;
                        event.preventDefault();
                        event.stopPropagation();
                        setDropHint(`item:${item.id}`);
                      }}
                      onDrop={(event) => {
                        event.stopPropagation();
                        void handleDrop(event, { kind: "item", id: item.id });
                      }}
                    >
                      {canManage ? (
                        <span className="grip">
                          <GripVertical size={15} />
                        </span>
                      ) : (
                        <span />
                      )}
                      <div className="title-cell">
                        <CopyableLine text={item.label} label="菜单名称">
                          <strong>{item.label}</strong>
                        </CopyableLine>
                        <em>
                          顶级 · {catalogLabel(item.viewId)} · {item.iconKey || "—"}
                        </em>
                      </div>
                      <span>{permissionLabel(item.permission)}</span>
                      <span>{item.sortOrder}</span>
                      <span>{item.enabled === false ? "停用" : "启用"}</span>
                      <div className="option-actions">
                        {canManage && (
                          <>
                            <button className="copy-link" type="button" onClick={() => openEditItem(item)}>
                              编辑
                            </button>
                            <button className="copy-link danger-action" type="button" onClick={() => void removeItem(item)}>
                              删除
                            </button>
                          </>
                        )}
                      </div>
                    </div>
                  ))}

                  {categoryGroups.map(({ group, items: groupItems }) => (
                    <div key={group.id}>
                      <div
                        className={`menu-cascade-row is-group${dragging?.id === group.id ? " dragging" : ""}${
                          dropHint === `group:${group.id}` ? " drop-target" : ""
                        }`}
                        draggable={canManage}
                        onDragStart={(event) => beginDrag(event, { kind: "group", id: group.id })}
                        onDragEnd={endDrag}
                        onDragOver={(event) => {
                          if (!canManage) return;
                          event.preventDefault();
                          event.stopPropagation();
                          setDropHint(`group:${group.id}`);
                        }}
                        onDrop={(event) => {
                          event.stopPropagation();
                          void handleDrop(event, { kind: "group", id: group.id });
                        }}
                      >
                        {canManage ? (
                          <span className="grip">
                            <GripVertical size={15} />
                          </span>
                        ) : (
                          <span />
                        )}
                        <div className="title-cell">
                          <CopyableLine text={group.label} label="分组名称">
                            <strong>{group.label}</strong>
                          </CopyableLine>
                          <em>
                            分组 · {group.key} · {group.iconKey || "—"}
                          </em>
                        </div>
                        <span>—</span>
                        <span>{group.sortOrder}</span>
                        <span>{group.enabled === false ? "停用" : "启用"}</span>
                        <div className="option-actions">
                          {canManage && (
                            <>
                              <button className="copy-link" type="button" onClick={() => openCreateItem(category.key, group.key)}>
                                加菜单
                              </button>
                              <button className="copy-link" type="button" onClick={() => openEditGroup(group)}>
                                编辑
                              </button>
                              <button className="copy-link danger-action" type="button" onClick={() => void removeGroup(group)}>
                                删除
                              </button>
                            </>
                          )}
                        </div>
                      </div>
                      {groupItems.map((item) => (
                        <div
                          key={item.id}
                          className={`menu-cascade-row is-item${dragging?.id === item.id ? " dragging" : ""}${
                            dropHint === `item:${item.id}` ? " drop-target" : ""
                          }`}
                          draggable={canManage}
                          onDragStart={(event) => beginDrag(event, { kind: "item", id: item.id })}
                          onDragEnd={endDrag}
                          onDragOver={(event) => {
                            if (!canManage) return;
                            event.preventDefault();
                            event.stopPropagation();
                            setDropHint(`item:${item.id}`);
                          }}
                          onDrop={(event) => {
                            event.stopPropagation();
                            void handleDrop(event, { kind: "item", id: item.id });
                          }}
                        >
                          {canManage ? (
                            <span className="grip">
                              <GripVertical size={15} />
                            </span>
                          ) : (
                            <span />
                          )}
                          <div className="title-cell">
                            <CopyableLine text={item.label} label="菜单名称">
                              <strong>{item.label}</strong>
                            </CopyableLine>
                            <em>
                              {catalogLabel(item.viewId)} · {item.iconKey || "—"}
                            </em>
                          </div>
                          <span>{permissionLabel(item.permission)}</span>
                          <span>{item.sortOrder}</span>
                          <span>{item.enabled === false ? "停用" : "启用"}</span>
                          <div className="option-actions">
                            {canManage && (
                              <>
                                <button className="copy-link" type="button" onClick={() => openEditItem(item)}>
                                  编辑
                                </button>
                                <button className="copy-link danger-action" type="button" onClick={() => void removeItem(item)}>
                                  删除
                                </button>
                              </>
                            )}
                          </div>
                        </div>
                      ))}
                    </div>
                  ))}

                  {!topItems.length && !categoryGroups.length && <div className="menu-cascade-empty">该分类下暂无菜单</div>}
                </div>
              </section>
            </div>
          ))}
          {!tree.length && <div className="table-empty">暂无菜单配置</div>}
        </div>
      </div>

      {categoryModal && (
        <div className="modal-backdrop" onClick={() => setCategoryModal(false)}>
          <div className="modal" onClick={(event) => event.stopPropagation()}>
            <div className="modal-head">
              <h3>{editingCategory ? "编辑分类" : "新增分类"}</h3>
              <button className="icon-button" type="button" onClick={() => setCategoryModal(false)} aria-label="关闭">
                <X size={16} />
              </button>
            </div>
            <div className="form-grid">
              <label>
                Key
                <input
                  value={categoryForm.key}
                  disabled={Boolean(editingCategory)}
                  onChange={(event) => setCategoryForm({ ...categoryForm, key: event.target.value })}
                  placeholder="如 business"
                />
              </label>
              <label>
                显示名
                <input value={categoryForm.label} onChange={(event) => setCategoryForm({ ...categoryForm, label: event.target.value })} />
              </label>
              <label>
                排序
                <input
                  type="number"
                  value={categoryForm.sortOrder}
                  onChange={(event) => setCategoryForm({ ...categoryForm, sortOrder: event.target.value })}
                />
              </label>
              <label>
                状态
                <select
                  value={categoryForm.enabled ? "启用" : "停用"}
                  onChange={(event) => setCategoryForm({ ...categoryForm, enabled: event.target.value === "启用" })}
                >
                  <option value="启用">启用</option>
                  <option value="停用">停用</option>
                </select>
              </label>
            </div>
            <div className="modal-actions">
              <button className="ghost" type="button" onClick={() => setCategoryModal(false)}>
                取消
              </button>
              <button className="primary" type="button" disabled={saving} onClick={() => void saveCategory()}>
                保存
              </button>
            </div>
          </div>
        </div>
      )}

      {groupModal && (
        <div className="modal-backdrop" onClick={() => setGroupModal(false)}>
          <div className="modal" onClick={(event) => event.stopPropagation()}>
            <div className="modal-head">
              <h3>{editingGroup ? "编辑分组" : "新增分组"}</h3>
              <button className="icon-button" type="button" onClick={() => setGroupModal(false)} aria-label="关闭">
                <X size={16} />
              </button>
            </div>
            <div className="form-grid">
              <label>
                Key
                <input
                  value={groupForm.key}
                  disabled={Boolean(editingGroup)}
                  onChange={(event) => setGroupForm({ ...groupForm, key: event.target.value })}
                />
              </label>
              <label>
                显示名
                <input value={groupForm.label} onChange={(event) => setGroupForm({ ...groupForm, label: event.target.value })} />
              </label>
              <label>
                所属分类
                <select value={groupForm.categoryKey} onChange={(event) => setGroupForm({ ...groupForm, categoryKey: event.target.value })}>
                  {categories.map((category) => (
                    <option key={category.id} value={category.key}>
                      {category.label}
                    </option>
                  ))}
                </select>
              </label>
              <label>
                图标
                <select value={groupForm.iconKey} onChange={(event) => setGroupForm({ ...groupForm, iconKey: event.target.value })}>
                  {ICON_KEYS.map((key) => (
                    <option key={key} value={key}>
                      {key}
                    </option>
                  ))}
                </select>
              </label>
              <label>
                排序
                <input
                  type="number"
                  value={groupForm.sortOrder}
                  onChange={(event) => setGroupForm({ ...groupForm, sortOrder: event.target.value })}
                />
              </label>
              <label>
                状态
                <select
                  value={groupForm.enabled ? "启用" : "停用"}
                  onChange={(event) => setGroupForm({ ...groupForm, enabled: event.target.value === "启用" })}
                >
                  <option value="启用">启用</option>
                  <option value="停用">停用</option>
                </select>
              </label>
            </div>
            <div className="modal-actions">
              <button className="ghost" type="button" onClick={() => setGroupModal(false)}>
                取消
              </button>
              <button className="primary" type="button" disabled={saving} onClick={() => void saveGroup()}>
                保存
              </button>
            </div>
          </div>
        </div>
      )}

      {itemModal && (
        <div className="modal-backdrop" onClick={() => setItemModal(false)}>
          <div className="modal" onClick={(event) => event.stopPropagation()}>
            <div className="modal-head">
              <h3>{editingItem ? "编辑菜单项" : "新增菜单项"}</h3>
              <button className="icon-button" type="button" onClick={() => setItemModal(false)} aria-label="关闭">
                <X size={16} />
              </button>
            </div>
            <div className="form-grid">
              <label>
                页面
                <select value={itemForm.viewId} onChange={(event) => onPickView(event.target.value as CatalogViewId)}>
                  {VIEW_CATALOG.map((entry) => (
                    <option key={entry.viewId} value={entry.viewId}>
                      {entry.label} ({entry.viewId})
                    </option>
                  ))}
                </select>
              </label>
              <label>
                显示名
                <input value={itemForm.label} onChange={(event) => setItemForm({ ...itemForm, label: event.target.value })} />
              </label>
              <label>
                所属分类
                <select
                  value={itemForm.categoryKey}
                  onChange={(event) => setItemForm({ ...itemForm, categoryKey: event.target.value })}
                  disabled={Boolean(itemForm.groupKey)}
                >
                  {categories.map((category) => (
                    <option key={category.id} value={category.key}>
                      {category.label}
                    </option>
                  ))}
                </select>
              </label>
              <label>
                所属分组
                <select
                  value={itemForm.groupKey}
                  onChange={(event) => {
                    const groupKey = event.target.value;
                    const group = groups.find((row) => row.key === groupKey);
                    setItemForm({
                      ...itemForm,
                      groupKey,
                      categoryKey: group?.categoryKey || itemForm.categoryKey,
                    });
                  }}
                >
                  <option value="">顶级（挂在分类下）</option>
                  {groups.map((group) => (
                    <option key={group.id} value={group.key}>
                      {categories.find((category) => category.key === group.categoryKey)?.label || "未分类"} / {group.label}
                    </option>
                  ))}
                </select>
              </label>
              <label>
                所需权限
                <select
                  value={itemForm.permission}
                  onChange={(event) => setItemForm({ ...itemForm, permission: event.target.value as PermissionKey })}
                >
                  {PERMISSION_OPTIONS.map((option) => (
                    <option key={option.id} value={option.id}>
                      {option.label}
                    </option>
                  ))}
                </select>
              </label>
              <label>
                图标
                <select value={itemForm.iconKey} onChange={(event) => setItemForm({ ...itemForm, iconKey: event.target.value })}>
                  {ICON_KEYS.map((key) => (
                    <option key={key} value={key}>
                      {key}
                    </option>
                  ))}
                </select>
              </label>
              <label>
                排序
                <input
                  type="number"
                  value={itemForm.sortOrder}
                  onChange={(event) => setItemForm({ ...itemForm, sortOrder: event.target.value })}
                />
              </label>
              <label>
                状态
                <select
                  value={itemForm.enabled ? "启用" : "停用"}
                  onChange={(event) => setItemForm({ ...itemForm, enabled: event.target.value === "启用" })}
                >
                  <option value="启用">启用</option>
                  <option value="停用">停用</option>
                </select>
              </label>
            </div>
            <div className="modal-actions">
              <button className="ghost" type="button" onClick={() => setItemModal(false)}>
                取消
              </button>
              <button className="primary" type="button" disabled={saving} onClick={() => void saveItem()}>
                保存
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
