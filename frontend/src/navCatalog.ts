import type { LucideIcon } from "lucide-react";
import {
  BadgeCheck,
  Banknote,
  BarChart3,
  Bell,
  BookUser,
  Boxes,
  Building2,
  ClipboardList,
  FileScan,
  FileText,
  Globe,
  History,
  Home,
  LayoutList,
  MessageCircle,
  MessageSquare,
  Search,
  ShieldCheck,
  ShoppingCart,
  Stamp,
  Truck,
  Users,
  WalletCards,
} from "lucide-react";
import type { NavCategory, NavGroup, NavMenuItem, PermissionKey } from "./types";

/** 侧栏可挂载的页面目录；新页面先在此注册，再在「菜单管理」中挂载。 */
export type CatalogViewId =
  | "dashboard"
  | "productProjects"
  | "serviceProjects"
  | "serviceOrders"
  | "salesOrders"
  | "purchaseOrders"
  | "contracts"
  | "entities"
  | "products"
  | "platformAccounts"
  | "websiteLeads"
  | "notices"
  | "libraryContacts"
  | "customerAccounts"
  | "sms"
  | "officialSites"
  | "officialSeo"
  | "reminders"
  | "invoices"
  | "transactions"
  | "financeStatements"
  | "receiptStats"
  | "paymentStats"
  | "trademarkCertificates"
  | "logs"
  | "collectionAccounts"
  | "optionSettings"
  | "menuSettings"
  | "access";

export type View = CatalogViewId;

export type NavIconKey = keyof typeof NAV_ICON_MAP;

export const NAV_ICON_MAP = {
  Home,
  ClipboardList,
  ShieldCheck,
  ShoppingCart,
  Truck,
  FileText,
  Building2,
  Boxes,
  FileScan,
  MessageSquare,
  Bell,
  BookUser,
  Users,
  Globe,
  Search,
  MessageCircle,
  WalletCards,
  BarChart3,
  Stamp,
  History,
  Banknote,
  BadgeCheck,
  LayoutList,
} as const;

export interface ViewCatalogEntry {
  viewId: CatalogViewId;
  label: string;
  iconKey: NavIconKey;
  permission: PermissionKey;
}

export const VIEW_CATALOG: ViewCatalogEntry[] = [
  { viewId: "dashboard", label: "总览", iconKey: "Home", permission: "dashboard.view" },
  { viewId: "productProjects", label: "商品项目", iconKey: "ClipboardList", permission: "project.view" },
  { viewId: "serviceProjects", label: "服务项目", iconKey: "ShieldCheck", permission: "project.view" },
  { viewId: "contracts", label: "合同管理", iconKey: "FileText", permission: "project.view" },
  { viewId: "websiteLeads", label: "商机管理", iconKey: "MessageSquare", permission: "lead.manage" },
  { viewId: "platformAccounts", label: "平台账号", iconKey: "FileScan", permission: "platformAccount.view" },
  { viewId: "reminders", label: "每日任务清单", iconKey: "ClipboardList", permission: "dashboard.view" },
  { viewId: "trademarkCertificates", label: "商标管理", iconKey: "Stamp", permission: "trademarkCertificate.view" },
  { viewId: "notices", label: "公告管理", iconKey: "FileText", permission: "notice.view" },
  { viewId: "serviceOrders", label: "服务订单", iconKey: "ShieldCheck", permission: "serviceOrder.view" },
  { viewId: "salesOrders", label: "销售订单", iconKey: "ShoppingCart", permission: "salesOrder.view" },
  { viewId: "purchaseOrders", label: "采购订单", iconKey: "Truck", permission: "purchaseOrder.view" },
  { viewId: "products", label: "商品及价格体系", iconKey: "Boxes", permission: "product.view" },
  { viewId: "entities", label: "客户基础信息管理", iconKey: "Building2", permission: "entity.view" },
  { viewId: "customerAccounts", label: "登录账号管理", iconKey: "Users", permission: "customerAccount.view" },
  { viewId: "libraryContacts", label: "政企客户资料库", iconKey: "BookUser", permission: "library.view" },
  { viewId: "officialSites", label: "官网站点", iconKey: "Globe", permission: "site.view" },
  { viewId: "officialSeo", label: "SEO配置", iconKey: "Search", permission: "site.view" },
  { viewId: "invoices", label: "发票管理", iconKey: "FileText", permission: "invoice.manage" },
  { viewId: "transactions", label: "交易流水", iconKey: "WalletCards", permission: "finance.view" },
  { viewId: "financeStatements", label: "财务清单", iconKey: "ClipboardList", permission: "finance.view" },
  { viewId: "receiptStats", label: "收款统计", iconKey: "BarChart3", permission: "finance.view" },
  { viewId: "paymentStats", label: "付款统计", iconKey: "BarChart3", permission: "finance.view" },
  { viewId: "sms", label: "短信日志", iconKey: "MessageCircle", permission: "sms.view" },
  { viewId: "logs", label: "系统操作日志", iconKey: "History", permission: "user.manage" },
  { viewId: "collectionAccounts", label: "收款账号管理", iconKey: "Banknote", permission: "user.manage" },
  { viewId: "optionSettings", label: "选项管理", iconKey: "BadgeCheck", permission: "user.manage" },
  { viewId: "menuSettings", label: "菜单管理", iconKey: "LayoutList", permission: "menu.view" },
  { viewId: "access", label: "用户权限", iconKey: "Users", permission: "user.manage" },
];

export const VIEW_CATALOG_BY_ID = Object.fromEntries(VIEW_CATALOG.map((item) => [item.viewId, item])) as Record<
  CatalogViewId,
  ViewCatalogEntry
>;

export const DEFAULT_NAV_CATEGORIES: NavCategory[] = [
  { id: "nav-cat-overview", key: "overview", label: "总览", sortOrder: 10, enabled: true },
  { id: "nav-cat-business", key: "business", label: "业务经营", sortOrder: 20, enabled: true },
  { id: "nav-cat-web", key: "web", label: "网站与公告", sortOrder: 30, enabled: true },
  { id: "nav-cat-system", key: "system", label: "系统运维", sortOrder: 40, enabled: true },
];

export const DEFAULT_NAV_GROUPS: NavGroup[] = [
  { id: "nav-group-serviceProjects", key: "serviceProjects", label: "服务项目管理", categoryKey: "business", iconKey: "ShieldCheck", sortOrder: 10, enabled: true },
  { id: "nav-group-productProjects", key: "productProjects", label: "商品项目管理", categoryKey: "business", iconKey: "ClipboardList", sortOrder: 20, enabled: true },
  { id: "nav-group-customers", key: "customers", label: "客户管理", categoryKey: "business", iconKey: "Building2", sortOrder: 30, enabled: true },
  { id: "nav-group-finance", key: "finance", label: "财务管理", categoryKey: "business", iconKey: "WalletCards", sortOrder: 40, enabled: true },
  { id: "nav-group-official", key: "official", label: "前端网站配置", categoryKey: "web", iconKey: "Globe", sortOrder: 10, enabled: true },
  { id: "nav-group-notices", key: "notices", label: "公告管理", categoryKey: "web", iconKey: "Bell", sortOrder: 20, enabled: true },
  { id: "nav-group-logs", key: "logs", label: "日志管理", categoryKey: "system", iconKey: "History", sortOrder: 10, enabled: true },
  { id: "nav-group-system", key: "system", label: "系统设置", categoryKey: "system", iconKey: "Users", sortOrder: 20, enabled: true },
];

/** 旧分组：重组后软删，避免侧栏残留「项目管理 / 订单」。 */
export const OBSOLETE_NAV_GROUP_IDS = ["nav-group-projects", "nav-group-orders"] as const;

function item(
  id: string,
  viewId: CatalogViewId,
  categoryKey: string,
  groupKey: string,
  sortOrder: number,
  overrides: Partial<Pick<NavMenuItem, "label" | "permission" | "iconKey">> = {},
): NavMenuItem {
  const catalog = VIEW_CATALOG_BY_ID[viewId];
  return {
    id,
    viewId,
    label: overrides.label ?? catalog.label,
    categoryKey,
    groupKey,
    permission: overrides.permission ?? catalog.permission,
    iconKey: overrides.iconKey ?? catalog.iconKey,
    sortOrder,
    enabled: true,
  };
}

export const DEFAULT_NAV_ITEMS: NavMenuItem[] = [
  item("nav-item-dashboard", "dashboard", "overview", "", 10),
  // 服务项目管理
  item("nav-item-websiteLeads", "websiteLeads", "business", "serviceProjects", 10),
  item("nav-item-serviceProjects", "serviceProjects", "business", "serviceProjects", 20),
  item("nav-item-serviceOrders", "serviceOrders", "business", "serviceProjects", 30),
  item("nav-item-platformAccounts", "platformAccounts", "business", "serviceProjects", 40),
  item("nav-item-reminders", "reminders", "business", "serviceProjects", 50),
  item("nav-item-trademarkCertificates", "trademarkCertificates", "business", "serviceProjects", 60),
  // 商品项目管理
  item("nav-item-productProjects", "productProjects", "business", "productProjects", 10),
  item("nav-item-salesOrders", "salesOrders", "business", "productProjects", 20),
  item("nav-item-purchaseOrders", "purchaseOrders", "business", "productProjects", 30),
  item("nav-item-products", "products", "business", "productProjects", 40),
  // 客户 / 财务（合同并入财务）/ 网站 / 系统
  item("nav-item-entities", "entities", "business", "customers", 10),
  item("nav-item-customerAccounts", "customerAccounts", "business", "customers", 20),
  item("nav-item-libraryContacts", "libraryContacts", "business", "customers", 30),
  item("nav-item-contracts", "contracts", "business", "finance", 10),
  item("nav-item-invoices", "invoices", "business", "finance", 20),
  item("nav-item-transactions", "transactions", "business", "finance", 30),
  item("nav-item-financeStatements", "financeStatements", "business", "finance", 40),
  item("nav-item-receiptStats", "receiptStats", "business", "finance", 50),
  item("nav-item-paymentStats", "paymentStats", "business", "finance", 60),
  item("nav-item-notices", "notices", "web", "notices", 10),
  item("nav-item-officialSites", "officialSites", "web", "official", 10),
  item("nav-item-officialSeo", "officialSeo", "web", "official", 20),
  item("nav-item-sms", "sms", "system", "logs", 10),
  item("nav-item-logs", "logs", "system", "logs", 20),
  item("nav-item-collectionAccounts", "collectionAccounts", "system", "system", 10),
  item("nav-item-optionSettings", "optionSettings", "system", "system", 20),
  item("nav-item-menuSettings", "menuSettings", "system", "system", 30),
  item("nav-item-access", "access", "system", "system", 40),
];

export function resolveNavIcon(iconKey?: string): LucideIcon {
  if (iconKey && iconKey in NAV_ICON_MAP) {
    return NAV_ICON_MAP[iconKey as NavIconKey];
  }
  return LayoutList;
}

export function catalogEntryForView(viewId: string): ViewCatalogEntry | undefined {
  return VIEW_CATALOG_BY_ID[viewId as CatalogViewId];
}

/** 防锁死：菜单管理 / 用户权限在配置被关掉时仍对有权限用户显示。 */
export const CRITICAL_NAV_VIEW_IDS = new Set<CatalogViewId>(["menuSettings", "access"]);
