import { Fragment, useEffect, useMemo, useRef, useState } from "react";
import type { FormEvent, ReactNode } from "react";
import * as XLSX from "xlsx";
import { backendApiUrl, ocrServiceUrl } from "./apiConfig";
import {
  AlertTriangle,
  BadgeCheck,
  Banknote,
  BarChart3,
  Bell,
  BookUser,
  Boxes,
  Building2,
  ChevronDown,
  CircleHelp,
  ClipboardList,
  Copy,
  Download,
  History,
  FileScan,
  FileText,
  Globe,
  Home,
  Link2,
  LogOut,
  MessageCircle,
  MessageSquare,
  Package,
  PackagePlus,
  RefreshCw,
  RotateCcw,
  RotateCw,
  Search,
  ShieldCheck,
  ShoppingCart,
  Stamp,
  Table2,
  Trash2,
  Truck,
  WalletCards,
  Upload,
  UserPlus,
  Users,
  X,
  ZoomIn,
  ZoomOut,
} from "lucide-react";
import { createCollectionItem, createId, deleteCollectionItem, diffPartialAppData, downloadServiceContract, downloadStandaloneServiceContract, loadData, patchCollectionItem, queryCollection, resetData, saveData, AUTH_EXPIRED_EVENT, AuthExpiredError } from "./db";
import {
  CRITICAL_NAV_VIEW_IDS,
  DEFAULT_NAV_CATEGORIES,
  DEFAULT_NAV_GROUPS,
  DEFAULT_NAV_ITEMS,
  VIEW_CATALOG_BY_ID,
  catalogEntryForView,
  resolveNavIcon,
  type View,
} from "./navCatalog";
import { MenuSettingsPanel } from "./MenuSettings";
import { organizationReferenceCounts, formatOrganizationReferences } from "./dataIntegrity";
import { LibraryContactsPanel } from "./LibraryContacts";
import { Notices } from "./Notices";
import { NoticeStats } from "./NoticeStats";
import { NoticeDictAdmin } from "./NoticeDictAdmin";
import { NoticeTags } from "./NoticeTags";
import { DevOps } from "./DevOps";
import { CustomerAccountsPanel } from "./CustomerAccounts";
import { OfficialSeoPanel } from "./OfficialSeo";
import { OfficialSitesPanel } from "./OfficialSites";
import { SmsPanel } from "./SmsPanel";
import { DateTimeField } from "./DateTimeField";
import { CopyableLine, Pagination, PanelTitle, SearchField, writeClipboardText } from "./listUi";
import {
  PERIOD_PRESETS,
  buildPaymentStats,
  buildReceiptStats,
  chartRows,
  formatPeriodRange,
  periodRange,
  type PaymentDimension,
  type PeriodPreset,
  type ReceiptDimension,
  type ReceiptScope,
} from "./cashflowStats";
import { CashflowStatsChart } from "./cashflowStatsChart";
import { calculateDashboardMetrics, projectPaidAmount, projectPendingInvoiceAmount, projectPurchaseAmount, projectReceivedAmount, projectSalesAmount } from "./dashboardMetrics";
import {
  buildSalesCollectionTransaction,
  buildServiceCollectionTransaction,
  applyServiceRefundToData,
  applyPurchasePaymentToData,
  defaultServiceRefundAmount,
  collectionTxTotalForOrder,
  latestCollectionOccurredAt,
  missingCollectionAmount,
  purchaseOrderPaidAmount,
  resolveOrderCollectionVoucher,
  roundMoney,
} from "./financeBackfill";
import {
  aggregateFulfillmentFromPurchaseOrders,
  applyProductProjectSync,
  DEFAULT_ACCEPTANCE_STATUS,
  DEFAULT_CONTRACT_STATUS,
  DEFAULT_DELIVERY_STATUS,
  DEFAULT_LOGISTICS_STATUS,
  DEFAULT_ORDER_PAYMENT_STATUS,
  DEFAULT_RECONCILE_STATUS,
  hasProductPurchaseOrder,
  hasProductSalesOrder,
  invoiceBelongsToProject,
  invoicesForOrder,
  invoiceAmountForOrder,
  invoiceLineGrossAmount,
  allocatedInvoiceLineGross,
  applyInvoiceLineAllocations,
  defaultInvoiceLinePickIndexes,
  invoiceLineAssignedOrderId,
  invoiceLinkedToOrder,
  invoiceLinkBlockReason,
  invoicesEligibleToLink,
  invoiceTypeForLinkTarget,
  invoiceRemainingAmount,
  invoiceCompletelyMatchingProjectId,
  reconcileInvoiceProjectIds,
  orderInvoiceOverview,
  applyServiceInvoiceAllocation,
  removeServiceInvoiceAllocation,
  normalizeServiceAllocations,
  invoiceDirectProjectIds,
  deriveServiceProjectInvoiceStatus,
  invoiceAmountForServiceOrder,
  serviceOrderInvoicedAmount,
  PRODUCT_PROJECT_STATUSES,
  productProjectCompletionIssues,
  productProjectOrderStatusLines,
  projectVisibleInvoices,
  buildProjectScopedProduct,
  applySalesOrderPurchaseLinks,
  canEditSalesOrderItems,
  isSalesOrderLogisticsLocked,
  purchaseOrderIdsTakenBySalesOrders,
  salesOrderLinkedPurchaseOrders,
  salesOrderProfit,
  salesOrderItemsEditBlockReason,
  canAppendPurchaseOrderItems,
  buildProductProjectName,
  isCatalogProduct,
  isProjectScopedProduct,
  nextPrefixedOrderNo,
  salesOrderItemsAmount,
  salesOrderLineItems,
} from "./productProjectFlow";
import {
  canTransition,
  getAllowedInvoiceStatuses,
  getAllowedOrderPaymentStatuses,
  getAllowedProjectStatuses,
  getAllowedPurchaseOrderStatuses,
  getAllowedSalesOrderStatuses,
  getAllowedServiceOrderStatuses,
} from "./statusRules";
import {
  appendProductsToPurchaseOrder as appendLinesToPurchaseOrder,
  blankSalesChannelLine as createBlankSalesChannelLine,
  buildGroupedPurchaseOrders as createGroupedPurchaseOrders,
  parsePurchaserQuickText,
  purchaserDraftFromProject,
  submitSalesOrderComposer,
  type PurchaserQuickFill,
  type SalesChannelLineDraft,
  type SalesComposerDraft,
} from "./salesOrderComposer";
import {
  amountToChinese,
  buildServiceContractDraft,
  buildStandaloneContractDraft,
  canGenerateServiceContract,
  contractNeedsCollectionAccount,
  formatShopCategories,
  mergeStandaloneDraft,
  normalizeContractPlatform,
  ownCompanyShortName,
  SERVICE_CONTRACT_PLATFORMS,
  serviceContractDraftErrors,
  shopNameFromCompany,
  SHOP_CATEGORY_OPTIONS,
  type ServiceContractDraft,
  type ServiceContractFileFormat,
  type ServiceContractPlatform,
} from "./serviceContract";
import type { AcceptanceStatus, AppData, ContractStatus, DeliveryStatus, EntityType, FinanceStatementRow, Invoice, InvoiceLineItem, LibraryContact, LogisticsStatus, NavCategory, NavGroup, NavMenuItem, OperationLog, OptionGroup, OrderPaymentStatus, Organization, OrganizationRole, ReconcileStatus, TaxpayerType, PermissionKey, PlatformAccount, Product, Project, ProjectItem, ProjectMemo, ProjectReminder, ProjectStatus, PurchaseOrder, ReminderWorkContent, Role, SalesOrder, ServiceCustomerKind, ServiceOrder, ServicePeriodUnit, ServiceType, SupplierPrice, TrademarkAttachment, TrademarkCertificate, Transaction, User, WebsiteLead, WebsiteLeadMemo } from "./types";

type OrderListTab = "销售订单" | "采购订单" | "服务订单";
type OrderFocus = { projectId?: string };
const ORDER_PAGE_COPY: Record<OrderListTab, { title: string; subtitle: string; search: string }> = {
  服务订单: { title: "服务订单列表", subtitle: "查看服务订单收款、状态与开票；点击订单查看详情。", search: "搜索订单、客户、服务" },
  销售订单: { title: "销售订单列表", subtitle: "查看销售订单收款、状态与开票；点击订单查看详情。", search: "搜索订单、客户、采购人、商品、收款账户" },
  采购订单: { title: "采购订单列表", subtitle: "查看采购订单付款、状态与收票；点击订单查看详情。", search: "搜索订单、供应商、商品" },
};
type CanAccess = (permission: PermissionKey) => boolean;
type ProductDetailTab = "basic" | "sales" | "purchase" | "invoices" | "logs" | "memos";
type ServiceDetailTab = "basic" | "overview" | "reminders" | "logs";
const PRODUCT_DETAIL_TABS: Array<{ id: ProductDetailTab; label: string }> = [
  { id: "basic", label: "基本信息" },
  { id: "sales", label: "销售订单" },
  { id: "purchase", label: "采购订单" },
  { id: "invoices", label: "项目发票" },
  { id: "logs", label: "日志" },
  { id: "memos", label: "备忘" },
];
const SERVICE_DETAIL_TABS: Array<{ id: ServiceDetailTab; label: string }> = [
  { id: "basic", label: "基本信息" },
  { id: "overview", label: "综合" },
  { id: "reminders", label: "跟进提醒" },
  { id: "logs", label: "日志" },
];
const PROJECT_MEMO_MAX_LENGTH = 200;
const SESSION_USER_KEY = "yicai-erp-current-user-id";
const VIEW_STORAGE_KEY = "yicai-erp-active-view";

function isCatalogView(value: string): value is View {
  return Boolean(VIEW_CATALOG_BY_ID[value as View]);
}

function readStoredView(): View {
  const fromHash = window.location.hash.replace(/^#\/?/, "").trim();
  if (fromHash && isCatalogView(fromHash)) return fromHash;
  try {
    const stored = window.sessionStorage.getItem(VIEW_STORAGE_KEY) || window.localStorage.getItem(VIEW_STORAGE_KEY) || "";
    if (stored && isCatalogView(stored)) return stored;
  } catch {
    // private mode / storage blocked
  }
  return "dashboard";
}

function persistActiveView(next: View) {
  try {
    window.sessionStorage.setItem(VIEW_STORAGE_KEY, next);
    window.localStorage.setItem(VIEW_STORAGE_KEY, next);
  } catch {
    // ignore
  }
  const hash = `#${next}`;
  if (window.location.hash !== hash) {
    window.history.replaceState(null, "", `${window.location.pathname}${window.location.search}${hash}`);
  }
}

interface SearchableSelectOption {
  value: string;
  label: string;
  detail?: string;
}

type ResolvedNavItem = {
  id: View;
  label: string;
  icon: typeof Home;
  permission: PermissionKey;
  categoryKey: string;
  groupKey: string;
  sortOrder: number;
};

function resolveNavConfig(data: AppData): { categories: NavCategory[]; groups: NavGroup[]; items: ResolvedNavItem[] } {
  const categories = (data.navCategories?.length ? data.navCategories : DEFAULT_NAV_CATEGORIES)
    .filter((category) => category.enabled !== false)
    .slice()
    .sort((a, b) => (a.sortOrder ?? 0) - (b.sortOrder ?? 0) || a.key.localeCompare(b.key));
  const groups = (data.navGroups?.length ? data.navGroups : DEFAULT_NAV_GROUPS)
    .filter((group) => group.enabled !== false)
    .slice()
    .sort((a, b) => (a.sortOrder ?? 0) - (b.sortOrder ?? 0) || a.key.localeCompare(b.key));
  const groupCategory = new Map(groups.map((group) => [group.key, group.categoryKey || ""]));
  const rawItems = data.navMenuItems?.length ? data.navMenuItems : DEFAULT_NAV_ITEMS;
  const items = rawItems
    .filter((item) => item.enabled !== false && catalogEntryForView(item.viewId))
    .map((item) => {
      const catalog = VIEW_CATALOG_BY_ID[item.viewId as View];
      const groupKey = item.groupKey || "";
      const categoryKey = item.categoryKey || groupCategory.get(groupKey) || "";
      return {
        id: item.viewId as View,
        label: item.label || catalog.label,
        icon: resolveNavIcon(item.iconKey || catalog.iconKey),
        permission: (item.permission || catalog.permission) as PermissionKey,
        categoryKey,
        groupKey,
        sortOrder: item.sortOrder ?? 0,
      };
    })
    .sort((a, b) => a.sortOrder - b.sortOrder || a.label.localeCompare(b.label));
  return { categories, groups, items };
}

function withCriticalNavItems(items: ResolvedNavItem[], can: (permission: PermissionKey) => boolean): ResolvedNavItem[] {
  const byId = new Map(items.map((item) => [item.id, item]));
  for (const viewId of CRITICAL_NAV_VIEW_IDS) {
    const catalog = VIEW_CATALOG_BY_ID[viewId];
    if (!catalog || !can(catalog.permission)) continue;
    if (byId.has(viewId)) continue;
    const fallback = DEFAULT_NAV_ITEMS.find((item) => item.viewId === viewId);
    byId.set(viewId, {
      id: viewId,
      label: catalog.label,
      icon: resolveNavIcon(catalog.iconKey),
      permission: catalog.permission,
      categoryKey: fallback?.categoryKey || "system",
      groupKey: fallback?.groupKey || "system",
      sortOrder: fallback?.sortOrder ?? 999,
    });
  }
  return Array.from(byId.values()).sort((a, b) => a.sortOrder - b.sortOrder || a.label.localeCompare(b.label));
}

const statusColumns: ProjectStatus[] = ["初始化", "进行中", "已完成", "终止"];
const projectStatusOptions: ProjectStatus[] = [...PRODUCT_PROJECT_STATUSES];
const entityTypes: EntityType[] = ["企业", "个体户", "政府", "事业单位", "学校", "医院", "其他"];
const orgRoles: OrganizationRole[] = ["平台入驻商", "中间销售商", "上游供应商", "使用单位", "终端采购人", "自有主体"];
const taxpayerTypes: TaxpayerType[] = ["一般纳税人", "小规模纳税人", "非企业单位"];

function orgHasRole(org: Organization, ...roles: OrganizationRole[]) {
  return roles.some((role) => org.roles.includes(role));
}

function isSupplierOrganization(org: Organization) {
  return orgHasRole(org, "上游供应商", "供应商");
}

function isOwnCompanyOrganization(org: Organization) {
  return orgHasRole(org, "自有主体", "本方主体");
}

function normalizeOrgName(name: string) {
  return name.replace(/\s+/g, "").toLowerCase();
}

function normalizeCreditCode(value?: string) {
  return (value ?? "").replace(/\s+/g, "").toUpperCase();
}

function orgNameMatches(a: string, b: string) {
  const left = normalizeOrgName(a);
  const right = normalizeOrgName(b);
  if (!left || !right) return false;
  return left === right || left.includes(right) || right.includes(left);
}

function findOrganizationByInvoiceParty(
  organizations: Organization[],
  taxNo?: string,
  name?: string,
) {
  const code = normalizeCreditCode(taxNo);
  if (code) {
    const byCode = organizations.find((org) => normalizeCreditCode(org.unifiedCreditCode) === code);
    if (byCode) return byCode;
  }
  const partyName = name?.trim() ?? "";
  if (!partyName) return undefined;
  return organizations.find((org) => orgNameMatches(org.name, partyName));
}

function normalizeInvoiceNo(value?: string) {
  return (value ?? "").replace(/\s+/g, "");
}

function findInvoiceByNo(invoices: Invoice[], invoiceNo: string) {
  const normalized = normalizeInvoiceNo(invoiceNo);
  if (!normalized) return undefined;
  return invoices.find((invoice) => invoice.status !== "作废" && normalizeInvoiceNo(invoice.invoiceNo) === normalized);
}

/** OCR 购/销方与己方主体比对：己方≈销方→销项，己方≈购方→进项；无法判断返回 null。 */
function detectInvoiceTypeFromParties(
  buyerName: string | undefined,
  sellerName: string | undefined,
  ownCompanyNames: string[],
): Invoice["type"] | null {
  const buyer = buyerName?.trim() ?? "";
  const seller = sellerName?.trim() ?? "";
  if ((!buyer && !seller) || ownCompanyNames.length === 0) return null;
  const matchesOwn = (name: string) => ownCompanyNames.some((own) => orgNameMatches(own, name));
  const sellerIsOwn = Boolean(seller && matchesOwn(seller));
  const buyerIsOwn = Boolean(buyer && matchesOwn(buyer));
  if (sellerIsOwn && !buyerIsOwn) return "销项";
  if (buyerIsOwn && !sellerIsOwn) return "进项";
  return null;
}

function isCustomerOrganization(org: Organization) {
  return orgHasRole(org, "终端采购人", "平台入驻商", "客户", "平台入驻客户");
}

function isResellerOrganization(org: Organization) {
  return orgHasRole(org, "中间销售商");
}
const permissionLabels: Record<PermissionKey, string> = {
  "dashboard.view": "查看总览",
  "project.view": "查看项目",
  "project.create": "新建项目",
  "project.edit": "编辑项目",
  "entity.view": "查看客户基础信息",
  "entity.create": "维护客户基础信息",
  "product.view": "查看商品及价格体系",
  "product.manage": "管理商品及价格体系",
  "purchase.manage": "管理采购履约",
  "serviceOrder.view": "查看服务订单",
  "serviceOrder.manage": "管理服务订单",
  "salesOrder.view": "查看销售订单",
  "salesOrder.manage": "管理销售订单",
  "purchaseOrder.view": "查看采购订单",
  "purchaseOrder.manage": "管理采购订单",
  "finance.view": "查看财务",
  "finance.manage": "管理流水",
  "invoice.manage": "管理发票",
  "onboarding.manage": "管理入驻服务",
  "platformAccount.view": "查看平台账号",
  "platformAccount.manage": "管理平台账号",
  "trademarkCertificate.view": "查看商标管理",
  "trademarkCertificate.manage": "管理商标",
  "notice.view": "查看公告",
  "notice.manage": "管理公告",
  "notice.stats.view": "查看公告统计",
  "notice.tag.view": "查看公告标签",
  "notice.tag.manage": "修正公告标签",
  "notice.orgType.view": "查看公告类型",
  "notice.orgType.manage": "管理公告类型",
  "notice.nature.view": "查看性质",
  "notice.nature.manage": "管理性质",
  "site.view": "查看前端网站配置",
  "site.manage": "管理前端网站配置",
  "library.view": "查看政企客户资料库",
  "library.manage": "管理政企客户资料库",
  "sms.view": "查看短信日志",
  "sms.manage": "短信管理",
  "customerAccount.view": "查看登录账号",
  "customerAccount.manage": "管理登录账号",
  "menu.view": "查看菜单配置",
  "menu.manage": "管理菜单配置",
  "lead.manage": "管理商机",
  "sensitive.view": "查看敏感信息",
  "profit.view": "查看利润",
  "dev.ops.view": "查看定时任务",
  "dev.ops.manage": "管理定时任务",
  "user.manage": "管理用户权限",
};
const permissionGroups: Array<{ title: string; keys: PermissionKey[] }> = [
  { title: "基础", keys: ["dashboard.view", "project.view", "entity.view", "product.view", "platformAccount.view", "trademarkCertificate.view", "notice.view", "notice.stats.view", "notice.tag.view", "notice.orgType.view", "notice.nature.view", "site.view", "library.view", "sms.view", "customerAccount.view", "menu.view", "serviceOrder.view", "salesOrder.view", "purchaseOrder.view", "dev.ops.view"] },
  { title: "业务", keys: ["project.create", "project.edit", "entity.create", "product.manage", "purchase.manage", "onboarding.manage", "platformAccount.manage", "trademarkCertificate.manage", "notice.manage", "notice.tag.manage", "notice.orgType.manage", "notice.nature.manage", "site.manage", "library.manage", "sms.manage", "customerAccount.manage", "menu.manage", "lead.manage", "serviceOrder.manage", "salesOrder.manage", "purchaseOrder.manage"] },
  { title: "财务", keys: ["finance.view", "finance.manage", "invoice.manage", "profit.view"] },
  { title: "安全", keys: ["sensitive.view", "dev.ops.manage", "user.manage"] },
];

function hasPermission(permissionSet: Set<PermissionKey>, permission: PermissionKey) {
  if (permissionSet.has(permission)) return true;
  if (permission === "platformAccount.view") {
    return permissionSet.has("platformAccount.manage") || permissionSet.has("onboarding.manage");
  }
  if (permission === "platformAccount.manage") {
    return permissionSet.has("onboarding.manage");
  }
  if (permission === "trademarkCertificate.view") {
    return permissionSet.has("trademarkCertificate.manage");
  }
  if (permission === "notice.view") {
    return permissionSet.has("notice.manage");
  }
  if (permission === "notice.tag.view") {
    return permissionSet.has("notice.tag.manage") || permissionSet.has("notice.manage");
  }
  if (permission === "notice.stats.view") {
    return permissionSet.has("notice.manage");
  }
  if (permission === "notice.tag.manage") {
    return permissionSet.has("notice.manage");
  }
  if (permission === "notice.orgType.view") {
    return (
      permissionSet.has("notice.orgType.manage") ||
      permissionSet.has("notice.manage") ||
      permissionSet.has("notice.nature.view") ||
      permissionSet.has("notice.nature.manage")
    );
  }
  if (permission === "notice.orgType.manage") {
    return permissionSet.has("notice.manage");
  }
  if (permission === "notice.nature.view") {
    return permissionSet.has("notice.nature.manage") || permissionSet.has("notice.manage");
  }
  if (permission === "notice.nature.manage") {
    return permissionSet.has("notice.manage");
  }
  if (permission === "dev.ops.view") {
    return permissionSet.has("dev.ops.manage");
  }
  if (permission === "site.view") {
    return permissionSet.has("site.manage");
  }
  if (permission === "library.view") {
    return permissionSet.has("library.manage");
  }
  if (permission === "customerAccount.view") {
    return permissionSet.has("customerAccount.manage");
  }
  if (permission === "menu.view") {
    return permissionSet.has("menu.manage");
  }
  if (permission === "sms.view") {
    return permissionSet.has("sms.manage");
  }
  if (permission === "serviceOrder.view") {
    return permissionSet.has("serviceOrder.manage");
  }
  if (permission === "salesOrder.view") {
    return permissionSet.has("salesOrder.manage");
  }
  if (permission === "purchaseOrder.view") {
    return permissionSet.has("purchaseOrder.manage");
  }
  return false;
}
const reminderWorkContents: ReminderWorkContent[] = ["绑定账期", "产品上架", "产品审核", "服务类入池", "产品类入池", "加分类", "加品牌", "服务类上架", "开发票", "做合同"];

function money(value: number) {
  return new Intl.NumberFormat("zh-CN", { style: "currency", currency: "CNY", minimumFractionDigits: 2, maximumFractionDigits: 2 }).format(value);
}

function grossMarginText(margin: number | null) {
  return margin == null ? "—" : `${(margin * 100).toFixed(1)}%`;
}

function PurchaserQuickPaste({ onFill }: { onFill: (parsed: PurchaserQuickFill) => void }) {
  const [text, setText] = useState("");
  const fill = (raw: string) => {
    const parsed = parsePurchaserQuickText(raw);
    if (!parsed) {
      window.alert("请按三行粘贴：第一行姓名[编号]，第二行电话，第三行收货地址[编号]。编号会接到电话后面，例如 18400840905-3015。");
      return;
    }
    onFill(parsed);
    setText("");
  };
  return (
    <div className="sales-composer-field sales-composer-field-full purchaser-quick-paste">
      <span>快捷拆分</span>
      <textarea
        value={text}
        rows={3}
        aria-label="采购人快捷拆分"
        placeholder={"郑筱[3015]\n18400840905\n山东济南市历下区姚家街道-九宸赋营销中心[3015]"}
        onChange={(event) => setText(event.target.value)}
        onPaste={(event) => {
          const pasted = event.clipboardData.getData("text");
          if (!parsePurchaserQuickText(pasted)) return;
          event.preventDefault();
          fill(pasted);
        }}
      />
      <div className="purchaser-quick-paste-actions">
        <button className="ghost" type="button" onClick={() => fill(text)}>拆分填入</button>
      </div>
    </div>
  );
}

function today() {
  return new Date().toISOString();
}

function todayDate() {
  return formatLocalDate(new Date());
}

function localDateTimeInputValue(date = new Date()) {
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, "0");
  const day = String(date.getDate()).padStart(2, "0");
  const hours = String(date.getHours()).padStart(2, "0");
  const minutes = String(date.getMinutes()).padStart(2, "0");
  return `${year}-${month}-${day}T${hours}:${minutes}`;
}

function toDateTimeLocalInput(value?: string) {
  if (!value) return localDateTimeInputValue();
  if (/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}/.test(value)) return value.slice(0, 16);
  if (/^\d{4}-\d{2}-\d{2}$/.test(value)) return `${value}T00:00`;
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return localDateTimeInputValue();
  return localDateTimeInputValue(parsed);
}

function fromDateTimeLocalValue(value: string) {
  if (!value) return today();
  const parsed = new Date(value);
  return Number.isNaN(parsed.getTime()) ? today() : parsed.toISOString();
}

function defaultOrderTimeFromProject(project?: { createdAt?: string }) {
  return project?.createdAt ? toDateTimeLocalInput(project.createdAt) : localDateTimeInputValue();
}

function formatYearMonth(value?: string) {
  const source = value ? new Date(`${value.slice(0, 10)}T00:00:00`) : new Date();
  const date = Number.isNaN(source.getTime()) ? new Date() : source;
  return `${date.getFullYear()}年${String(date.getMonth() + 1).padStart(2, "0")}月`;
}

function formatYearMonthDay(value?: string) {
  const source = value ? new Date(`${value.slice(0, 10)}T00:00:00`) : new Date();
  const date = Number.isNaN(source.getTime()) ? new Date() : source;
  return `${date.getFullYear()}年${String(date.getMonth() + 1).padStart(2, "0")}月${String(date.getDate()).padStart(2, "0")}日`;
}

function addMonths(date: Date, months: number) {
  const next = new Date(date);
  const targetMonth = next.getMonth() + months;
  next.setMonth(targetMonth);
  return next;
}

function formatLocalDate(date: Date) {
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, "0");
  const day = String(date.getDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
}

function formatDateTimeValue(value?: string) {
  if (!value) return "未记录";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleString("zh-CN", { hour12: false });
}

function formatOrderStamp(value?: string) {
  if (!value) return "未记录";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, "0");
  const day = String(date.getDate()).padStart(2, "0");
  const hour = String(date.getHours()).padStart(2, "0");
  const minute = String(date.getMinutes()).padStart(2, "0");
  const second = String(date.getSeconds()).padStart(2, "0");
  return `${year}-${month}-${day} ${hour}:${minute}:${second}`;
}

function productSpecText(product?: Pick<Product, "capacity" | "energyLevel" | "shape" | "category">) {
  const spec = [product?.capacity, product?.energyLevel, product?.shape].filter(Boolean).join(" / ");
  if (spec) return spec;
  if (product?.category && product.category !== "项目商品") return product.category;
  return "";
}

function formatDateTimeMinute(value?: string) {
  if (!value) return "未记录";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleString("zh-CN", {
    year: "numeric",
    month: "numeric",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  });
}

function addDays(date: Date, days: number) {
  const next = new Date(date);
  next.setDate(next.getDate() + days);
  return next;
}

function calculateServiceEndDate(startDate: string, unit: ServicePeriodUnit, value: number, giftUnit: "天" | "月", giftValue: number) {
  const start = new Date(`${startDate}T00:00:00`);
  const months = unit === "年" ? value * 12 : value;
  let end = addMonths(start, months);
  end = giftUnit === "月" ? addMonths(end, giftValue) : addDays(end, giftValue);
  end.setDate(end.getDate() - 1);
  return formatLocalDate(end);
}

function parseOptionNumber(value: string) {
  return Number(value.match(/\d+/)?.[0] ?? "0");
}

async function prepareOcrUpload(file: File) {
  if (!file.type.startsWith("image/") || file.type === "image/svg+xml" || file.type === "image/gif") return file;
  try {
    const bitmap = await createImageBitmap(file, { imageOrientation: "from-image" });
    const scale = Math.min(1, 2000 / Math.max(bitmap.width, bitmap.height));
    if (scale === 1 && file.size < 1_500_000) {
      bitmap.close();
      return file;
    }
    const canvas = document.createElement("canvas");
    canvas.width = Math.max(1, Math.round(bitmap.width * scale));
    canvas.height = Math.max(1, Math.round(bitmap.height * scale));
    const context = canvas.getContext("2d");
    if (!context) {
      bitmap.close();
      return file;
    }
    context.fillStyle = "#ffffff";
    context.fillRect(0, 0, canvas.width, canvas.height);
    context.drawImage(bitmap, 0, 0, canvas.width, canvas.height);
    bitmap.close();
    const blob = await new Promise<Blob | null>((resolve) => canvas.toBlob(resolve, "image/jpeg", 0.9));
    return blob ? new File([blob], file.name.replace(/\.[^.]+$/, "") + ".jpg", { type: "image/jpeg" }) : file;
  } catch {
    return file;
  }
}

function throwIfAuthExpired(response: Response) {
  if (response.status !== 401) return;
  window.dispatchEvent(new Event(AUTH_EXPIRED_EVENT));
  throw new AuthExpiredError();
}

async function uploadBusinessDocument(
  file: File,
  documentType: "business_license" | "invoice" | "payment_voucher" | "contract" | "trademark_certificate" | "trademark_attachment",
  ownerId: string,
) {
  const formData = new FormData();
  formData.append("documentType", documentType);
  formData.append("ownerId", ownerId);
  formData.append("file", file);
  let response: Response;
  try {
    response = await fetch(backendApiUrl("/api/documents/upload/"), {
      method: "POST",
      credentials: "include",
      body: formData,
    });
  } catch {
    throw new Error("文件上传失败，请检查网络后重试。");
  }
  let payload: { data?: { id: string; fileName: string }; detail?: string } = {};
  try {
    payload = await response.json() as { data?: { id: string; fileName: string }; detail?: string };
  } catch {
    // 非 JSON 响应走统一错误文案。
  }
  if (response.status === 401) {
    window.dispatchEvent(new Event(AUTH_EXPIRED_EVENT));
    throw new AuthExpiredError();
  }
  if (!response.ok || !payload.data) throw new Error(payload.detail || "文件保存失败。");
  return payload.data;
}

async function deleteBusinessDocument(fileId: string) {
  let response: Response;
  try {
    response = await fetch(backendApiUrl(`/api/documents/${encodeURIComponent(fileId)}/delete/`), {
      method: "DELETE",
      credentials: "include",
    });
  } catch {
    throw new Error("删除附件失败，请检查网络后重试。");
  }
  throwIfAuthExpired(response);
  if (!response.ok) {
    let detail = "删除附件失败。";
    try {
      const payload = await response.json() as { detail?: string };
      if (payload.detail) detail = payload.detail;
    } catch {
      // ignore
    }
    throw new Error(detail);
  }
}

function openBusinessDocument(fileId?: string) {
  if (!fileId) return;
  window.open(backendApiUrl(`/api/documents/${encodeURIComponent(fileId)}/`), "_blank", "noopener,noreferrer");
}

function businessDocumentUrl(fileId: string) {
  return backendApiUrl(`/api/documents/${encodeURIComponent(fileId)}/`);
}

async function loginOnServer(identifier: string, password: string) {
  let response: Response;
  try {
    response = await fetch(backendApiUrl("/api/auth/login/"), {
      method: "POST",
      credentials: "include",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ identifier, password }),
    });
  } catch {
    throw new Error("无法连接登录服务，请检查网络后重试。");
  }
  if (!response.ok) {
    if (response.status === 401) throw new Error("账号或密码错误，请重新输入。");
    if (response.status === 403) throw new Error("账号已停用，请联系管理员启用。");
    if (response.status === 429) throw new Error("登录尝试过于频繁，请稍后再试。");
    let detail = "";
    try {
      const payload = await response.json() as { detail?: string };
      detail = payload.detail ?? "";
    } catch {
      // 非 JSON 响应使用状态码对应的提示。
    }
    if (response.status >= 500) throw new Error("登录服务暂时不可用，请稍后重试。");
    throw new Error(detail ? `登录失败：${detail}` : "登录失败，请检查输入后重试。");
  }
  const payload = await response.json() as { data: User };
  return payload.data;
}

async function logoutOnServer() {
  await fetch(backendApiUrl("/api/auth/logout/"), {
    method: "POST",
    credentials: "include",
  });
}

type SessionProbe =
  | { status: "authenticated"; user: User }
  | { status: "unauthenticated" }
  | { status: "unavailable" };

async function probeServerSession(): Promise<SessionProbe> {
  try {
    const response = await fetch(backendApiUrl("/api/auth/me/"), { credentials: "include" });
    if (response.status === 401) return { status: "unauthenticated" };
    if (!response.ok) return { status: "unavailable" };
    const payload = await response.json() as { data?: User };
    if (!payload.data?.id) return { status: "unavailable" };
    return { status: "authenticated", user: payload.data };
  } catch {
    return { status: "unavailable" };
  }
}

async function auditSensitiveAccess(payload: { targetName?: string; fieldLabel: string; platform?: string; source?: string }) {
  const response = await fetch(backendApiUrl("/api/audit/sensitive-access/"), {
    method: "POST",
    credentials: "include",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  throwIfAuthExpired(response);
}

type PlatformSensitiveField = "accountName" | "accountPasswordMasked" | "supplierAccount" | "supplierPasswordMasked" | "cloudAccount" | "cloudPasswordMasked" | "caAccount" | "caPasswordMasked";

async function fetchPlatformSensitiveValue(accountId: string, field: PlatformSensitiveField) {
  const response = await fetch(backendApiUrl(`/api/platform-accounts/${encodeURIComponent(accountId)}/sensitive/${field}/`), {
    credentials: "include",
    headers: { Accept: "application/json" },
  });
  throwIfAuthExpired(response);
  if (!response.ok) throw new Error("Sensitive value request failed");
  const payload = await response.json() as { data: { value?: string } };
  return payload.data.value;
}

function ProjectProductMark({ product }: { product?: { source?: string } }) {
  if (product?.source !== "project") return null;
  return <em className="project-product-tag">项目商品</em>;
}

function isPdfContractFile(file: File) {
  return file.type === "application/pdf" || file.name.toLowerCase().endsWith(".pdf");
}

function ContractFileActions({
  fileId,
  canReplace,
  onView,
  onReplace,
}: {
  fileId?: string;
  canReplace: boolean;
  onView: () => void;
  onReplace: () => void;
}) {
  if (!fileId && !canReplace) return <>未上传</>;
  return (
    <div className="contract-file-actions">
      {fileId ? <button type="button" className="copy-link" onClick={onView}>查看合同</button> : null}
      {canReplace ? (
        <button type="button" className="copy-link" onClick={onReplace}>
          {fileId ? "替换合同" : "上传合同"}
        </button>
      ) : null}
    </div>
  );
}

function FilePicker({
  accept,
  fileName,
  placeholder = "未选择文件",
  buttonLabel = "选择文件",
  ariaLabel,
  onFile,
}: {
  accept?: string;
  fileName?: string;
  placeholder?: string;
  buttonLabel?: string;
  ariaLabel?: string;
  onFile: (file: File | undefined) => void;
}) {
  const inputRef = useRef<HTMLInputElement>(null);
  return (
    <div className="file-picker">
      <input
        ref={inputRef}
        type="file"
        accept={accept}
        className="file-picker-input"
        tabIndex={-1}
        aria-hidden="true"
        onChange={(event) => {
          onFile(event.target.files?.[0]);
          event.target.value = "";
        }}
      />
      <button
        type="button"
        className="ghost file-picker-trigger"
        onClick={() => inputRef.current?.click()}
        aria-label={ariaLabel ?? buttonLabel}
      >
        <Upload size={16} />
        {buttonLabel}
      </button>
      <span className={`file-picker-name${fileName ? "" : " is-empty"}`} title={fileName || undefined}>
        {fileName || placeholder}
      </span>
      {fileName ? (
        <button type="button" className="file-picker-clear" aria-label="清除已选文件" onClick={() => onFile(undefined)}>
          <X size={14} />
        </button>
      ) : null}
    </div>
  );
}

function ContractFormatPicker({
  value,
  onChange,
  disabled,
  name = "contract-file-format",
}: {
  value: ServiceContractFileFormat;
  onChange: (value: ServiceContractFileFormat) => void;
  disabled?: boolean;
  name?: string;
}) {
  return (
    <div className="contract-format-picker" role="radiogroup" aria-label="下载格式">
      <span>下载格式</span>
      <label>
        <input type="radio" name={name} checked={value === "word"} disabled={disabled} onChange={() => onChange("word")} />
        Word
      </label>
      <label>
        <input type="radio" name={name} checked={value === "pdf"} disabled={disabled} onChange={() => onChange("pdf")} />
        PDF
      </label>
    </div>
  );
}

interface FinanceValidationDetails {
  projectName?: string;
  projectNo?: string;
  projectId?: string;
  buyerName?: string;
  sellerName?: string;
  orderNo?: string;
  orderStatus?: string;
  orderAmount?: number;
  invoiceAmount?: number;
  receivedAmount?: number;
  txTotal?: number;
  invoicedAmount?: number;
  projectAmount?: number;
  orderTotal?: number;
  projectCost?: number;
  purchaseTotal?: number;
  unallocatedAmount?: number;
  orderAllocations?: Array<{
    orderId?: string;
    orderNo: string;
    orderAmount: number;
    allocatedAmount: number;
    projectName?: string;
    projectNo?: string;
    projectId?: string;
  }>;
}

interface FinanceValidationIssue {
  level: "error" | "warning";
  code: string;
  message: string;
  targetType: string;
  targetId?: string;
  targetName?: string;
  diff?: number;
  details?: FinanceValidationDetails;
}

interface FinanceValidationResult {
  summary: {
    errors: number;
    warnings: number;
    checkedAt: string;
  };
  issues: FinanceValidationIssue[];
}

async function fetchFinanceValidation() {
  const response = await fetch(backendApiUrl(`/api/validation/finance/?t=${Date.now()}`), {
    credentials: "include",
    cache: "no-store",
    headers: { Accept: "application/json" },
  });
  throwIfAuthExpired(response);
  if (!response.ok) throw new Error("财务一致性校验失败");
  const payload = await response.json() as { data: FinanceValidationResult };
  return payload.data;
}

function isRedundantReceivedIssue(issue: FinanceValidationIssue, issues: FinanceValidationIssue[]) {
  if (issue.code !== "received_transaction_mismatch") return false;
  const sibling = issues.find((item) => (
    item.code === "order_amount_transaction_mismatch"
    && item.targetId === issue.targetId
    && item.targetType === issue.targetType
  ));
  if (!sibling) return false;
  const orderAmount = issue.details?.orderAmount;
  const receivedAmount = issue.details?.receivedAmount;
  if (typeof orderAmount === "number" && typeof receivedAmount === "number") {
    return Math.abs(orderAmount - receivedAmount) <= 0.01;
  }
  return Math.abs((issue.diff ?? 0) - (sibling.diff ?? 0)) <= 0.01;
}

function visibleFinanceIssues(issues: FinanceValidationIssue[]) {
  return issues.filter((issue) => !isRedundantReceivedIssue(issue, issues));
}

function orgNameById(data: AppData, orgId?: string) {
  if (!orgId) return "";
  return data.organizations.find((org) => org.id === orgId)?.name || "";
}

function displayLogValue(value: unknown) {
  if (value == null || value === "") return "空";
  return String(value);
}

function pushFieldChange(changes: string[], label: string, before: unknown, after: unknown) {
  const left = displayLogValue(before);
  const right = displayLogValue(after);
  if (left === right) return;
  changes.push(`${label}：${left} → ${right}`);
}

/** 服务项目编辑日志：逐字段记录变更前后。 */
export function describeServiceProjectEditChanges(
  data: AppData,
  before: Project,
  after: Project,
) {
  const changes: string[] = [];
  pushFieldChange(changes, "项目名称", before.name, after.name);
  pushFieldChange(
    changes,
    "客户",
    orgNameById(data, before.customerOrgId) || before.customerOrgId,
    orgNameById(data, after.customerOrgId) || after.customerOrgId,
  );
  pushFieldChange(
    changes,
    "签约主体",
    orgNameById(data, before.ownCompanyOrgId) || before.ownCompanyOrgId,
    orgNameById(data, after.ownCompanyOrgId) || after.ownCompanyOrgId,
  );
  pushFieldChange(changes, "服务平台", before.sourcePlatform, after.sourcePlatform);
  pushFieldChange(changes, "服务", before.serviceProductName, after.serviceProductName);
  pushFieldChange(changes, "客户类型", before.serviceCustomerKind, after.serviceCustomerKind);
  pushFieldChange(changes, "类型", before.serviceType || "周期", after.serviceType || "周期");
  pushFieldChange(changes, "开始日期", before.serviceStartDate, after.serviceStartDate);
  pushFieldChange(changes, "到期日期", before.serviceEndDate, after.serviceEndDate);
  pushFieldChange(changes, "周期单位", before.servicePeriodUnit, after.servicePeriodUnit);
  pushFieldChange(changes, "周期数值", before.servicePeriodValue, after.servicePeriodValue);
  const beforeGift = before.serviceGiftValue ?? before.serviceGiftMonths;
  const afterGift = after.serviceGiftValue ?? after.serviceGiftMonths;
  pushFieldChange(changes, "赠送单位", before.serviceGiftUnit, after.serviceGiftUnit);
  pushFieldChange(changes, "赠送数量", beforeGift, afterGift);
  pushFieldChange(changes, "业务员", before.serviceSalesName || before.owner, after.serviceSalesName || after.owner);
  pushFieldChange(changes, "备注", before.serviceRemark, after.serviceRemark);
  const beforeAmount = Number(before.totalAmount) || 0;
  const afterAmount = Number(after.totalAmount) || 0;
  if (Math.abs(beforeAmount - afterAmount) > 0.009) {
    changes.push(`项目金额：${money(beforeAmount)} → ${money(afterAmount)}`);
  }
  return changes;
}

function invoiceProjectIds(invoice: Invoice) {
  return invoice.projectIds ?? (invoice.projectId ? [invoice.projectId] : []);
}

function invoiceRelatedProjects(data: AppData, invoice: Invoice) {
  return invoiceProjectIds(invoice)
    .map((id) => data.projects.find((project) => project.id === id))
    .filter((project): project is Project => Boolean(project));
}

function invoiceRelatedOrders(data: AppData, invoice: Invoice) {
  const salesIds = Array.from(new Set([
    ...(invoice.salesOrderIds ?? []),
    ...(invoice.lineItems ?? []).map((item) => item.salesOrderId).filter((id): id is string => Boolean(id)),
  ]));
  const purchaseIds = Array.from(new Set([
    ...(invoice.purchaseOrderIds ?? []),
    ...(invoice.lineItems ?? []).map((item) => item.purchaseOrderId).filter((id): id is string => Boolean(id)),
  ]));
  return {
    sales: salesIds.map((id) => data.salesOrders.find((order) => order.id === id)).filter((order): order is SalesOrder => Boolean(order)),
    purchases: purchaseIds.map((id) => data.purchaseOrders.find((order) => order.id === id)).filter((order): order is PurchaseOrder => Boolean(order)),
  };
}

type InvoiceOrderEntry = {
  id: string;
  kind: "销售" | "采购" | "服务";
  orderNo: string;
  amount: number;
  party: string;
  direct: boolean;
};

function invoiceOrderEntries(data: AppData, invoice: Invoice): InvoiceOrderEntry[] {
  const related = invoiceRelatedOrders(data, invoice);
  const serviceIds = new Set(
    (invoice.serviceAllocations ?? []).map((item) => item.serviceOrderId).filter((id): id is string => Boolean(id)),
  );
  const direct: InvoiceOrderEntry[] = [
    ...related.sales.map((order) => ({
      id: `sales-${order.id}`,
      kind: "销售" as const,
      orderNo: order.orderNo,
      amount: order.amount,
      party: orgNameById(data, order.customerOrgId),
      direct: true,
    })),
    ...related.purchases.map((order) => ({
      id: `purchase-${order.id}`,
      kind: "采购" as const,
      orderNo: order.orderNo,
      amount: order.amount,
      party: orgNameById(data, order.supplierOrgId),
      direct: true,
    })),
    ...data.serviceOrders.filter((order) => serviceIds.has(order.id)).map((order) => ({
      id: `service-${order.id}`,
      kind: "服务" as const,
      orderNo: order.orderNo,
      amount: order.amount,
      party: orgNameById(data, order.customerOrgId),
      direct: true,
    })),
  ];
  if (direct.length > 0) return direct;
  const projectIds = new Set(invoiceProjectIds(invoice));
  if (projectIds.size === 0) return [];
  if (invoice.type === "进项") {
    return data.purchaseOrders
      .filter((order) => projectIds.has(order.projectId) && order.status !== "已取消")
      .map((order) => ({
        id: `purchase-${order.id}`,
        kind: "采购" as const,
        orderNo: order.orderNo,
        amount: order.amount,
        party: orgNameById(data, order.supplierOrgId),
        direct: false,
      }));
  }
  return [
    ...data.salesOrders
      .filter((order) => projectIds.has(order.projectId) && order.status !== "取消" && order.status !== "退款")
      .map((order) => ({
        id: `sales-${order.id}`,
        kind: "销售" as const,
        orderNo: order.orderNo,
        amount: order.amount,
        party: orgNameById(data, order.customerOrgId),
        direct: false,
      })),
    ...data.serviceOrders
      .filter((order) => projectIds.has(order.projectId) && order.status !== "取消" && order.status !== "退款")
      .map((order) => ({
        id: `service-${order.id}`,
        kind: "服务" as const,
        orderNo: order.orderNo,
        amount: order.amount,
        party: orgNameById(data, order.customerOrgId),
        direct: false,
      })),
  ];
}

function invoiceLineLinkedOrder(data: AppData, invoice: Invoice, item: InvoiceLineItem) {
  const orderType = invoice.type === "销项" ? "sales" : "purchase";
  const orderId = invoiceLineAssignedOrderId(item, orderType);
  if (!orderId) return undefined;
  return orderType === "sales"
    ? data.salesOrders.find((order) => order.id === orderId)
    : data.purchaseOrders.find((order) => order.id === orderId);
}

function isConfirmedInvoice(invoice: Pick<Invoice, "status">) {
  return invoice.status === "已确认";
}

function buildOrderNoById(data: Pick<AppData, "salesOrders" | "purchaseOrders" | "serviceOrders">) {
  const map: Record<string, string> = {};
  for (const order of data.salesOrders) map[order.id] = order.orderNo;
  for (const order of data.purchaseOrders) map[order.id] = order.orderNo;
  for (const order of data.serviceOrders) map[order.id] = order.orderNo;
  return map;
}

function financeIssueIgnoreKey(issue: Pick<FinanceValidationIssue, "code" | "targetType" | "targetId">) {
  return `${issue.code}:${issue.targetType}:${issue.targetId ?? ""}`;
}

function canIgnoreFinanceIssue(issue: FinanceValidationIssue) {
  return issue.level === "warning";
}

function mergeFinanceIssueDetails(issue: FinanceValidationIssue, data: AppData): FinanceValidationDetails {
  const local: FinanceValidationDetails = {};
  const projectOf = (projectId?: string) => data.projects.find((item) => item.id === projectId);

  if (issue.targetType === "销售订单" || issue.targetType === "服务订单") {
    const kind = issue.targetType === "服务订单" ? "service" : "sales";
    const orders = kind === "service" ? data.serviceOrders : data.salesOrders;
    const order = orders.find((item) => item.id === issue.targetId) ?? orders.find((item) => item.orderNo === issue.targetName);
    if (order) {
      const project = projectOf(order.projectId);
      local.orderNo = order.orderNo;
      local.orderStatus = order.status;
      local.projectName = project?.name;
      local.projectNo = project?.projectNo;
      local.buyerName = orgNameById(data, order.customerOrgId || project?.customerOrgId);
      local.sellerName = orgNameById(data, ("ownCompanyOrgId" in order ? order.ownCompanyOrgId : undefined) || project?.ownCompanyOrgId);
      local.orderAmount = order.receivableAmount ?? order.amount;
      local.receivedAmount = order.receivedAmount;
      local.txTotal = collectionTxTotalForOrder(data.transactions, order.id, kind);
    }
  } else if (issue.targetType === "采购订单") {
    const order = data.purchaseOrders.find((item) => item.id === issue.targetId) ?? data.purchaseOrders.find((item) => item.orderNo === issue.targetName);
    if (order) {
      const project = projectOf(order.projectId);
      local.orderNo = order.orderNo;
      local.orderStatus = order.status;
      local.projectName = project?.name;
      local.projectNo = project?.projectNo;
      local.buyerName = orgNameById(data, order.ownCompanyOrgId || project?.ownCompanyOrgId);
      local.sellerName = orgNameById(data, order.supplierOrgId);
      local.orderAmount = order.amount;
    }
  } else if (issue.targetType === "项目") {
    const project = data.projects.find((item) => item.id === issue.targetId) ?? data.projects.find((item) => item.name === issue.targetName);
    if (project) {
      local.projectName = project.name;
      local.projectNo = project.projectNo;
      local.buyerName = orgNameById(data, project.customerOrgId);
      local.sellerName = orgNameById(data, project.ownCompanyOrgId);
      local.orderStatus = project.status;
      local.projectAmount = project.totalAmount;
      local.projectCost = projectPurchaseAmount(data, project.id);
      local.projectId = project.id;
      const revenueOrders = project.type === "服务项目"
        ? data.serviceOrders
        : project.type === "商品项目"
          ? data.salesOrders
          : (data.serviceOrders.some((order) => order.projectId === project.id) ? data.serviceOrders : data.salesOrders);
      local.orderTotal = roundMoney(
        revenueOrders
          .filter((order) => order.projectId === project.id && order.status !== "取消" && order.status !== "退款")
          .reduce((sum, order) => sum + (Number(order.receivableAmount ?? order.amount) || 0), 0),
      );
      local.purchaseTotal = roundMoney(
        data.purchaseOrders
          .filter((order) => order.projectId === project.id && order.status !== "已取消")
          .reduce((sum, order) => sum + (Number(order.amount) || 0), 0),
      );
    }
  } else if (issue.targetType === "发票") {
    const invoice = data.invoices.find((item) => item.id === issue.targetId) ?? data.invoices.find((item) => item.invoiceNo === issue.targetName);
    if (invoice) {
      const relatedProjects = invoiceRelatedProjects(data, invoice);
      local.orderNo = invoice.invoiceNo;
      local.orderStatus = invoice.status;
      local.projectName = relatedProjects.map((project) => project.name).join(" / ") || projectOf(invoice.projectId)?.name;
      local.projectNo = relatedProjects[0]?.projectNo || projectOf(invoice.projectId)?.projectNo;
      local.projectId = relatedProjects[0]?.id || invoice.projectId;
      local.buyerName = invoice.buyerName || orgNameById(data, invoice.buyerOrgId || invoice.counterpartyOrgId);
      local.sellerName = invoice.sellerName || orgNameById(data, invoice.sellerOrgId);
      local.invoiceAmount = invoice.amount;
      local.orderAmount = invoice.amount;
    }
  }

  const merged = { ...local, ...issue.details };
  if (issue.targetType === "项目" && typeof local.purchaseTotal === "number") {
    merged.purchaseTotal = local.purchaseTotal;
    merged.projectCost = local.purchaseTotal;
  }
  return merged;
}

function financeIssueDetailRows(issue: FinanceValidationIssue, details: FinanceValidationDetails) {
  const buyerLabel = issue.targetType === "采购订单" ? "本公司" : issue.targetType === "项目" ? "客户" : "购方";
  const sellerLabel = issue.targetType === "采购订单" ? "供应商" : issue.targetType === "项目" ? "本公司" : "销方";
  const rows: Array<{ label: string; value: string; copy?: boolean; open?: "project" | "invoice" }> = [];
  if (issue.targetType === "项目") {
    if (details.projectNo) rows.push({ label: "项目编号", value: details.projectNo, copy: true, open: "project" });
  } else if (details.projectName) {
    rows.push({
      label: "项目",
      value: details.projectNo ? `${details.projectName}（${details.projectNo}）` : details.projectName,
      copy: true,
      open: "project",
    });
  }
  if (details.buyerName) rows.push({ label: buyerLabel, value: details.buyerName, copy: true });
  if (details.sellerName) rows.push({ label: sellerLabel, value: details.sellerName, copy: true });
  if (details.orderStatus) rows.push({ label: "状态", value: details.orderStatus });
  if (issue.targetType === "项目") {
    if (issue.code === "project_cost_mismatch") {
      if (typeof details.projectCost === "number") rows.push({ label: "项目成本", value: money(details.projectCost) });
      if (typeof details.purchaseTotal === "number") rows.push({ label: "采购合计", value: money(details.purchaseTotal) });
    } else {
      if (typeof details.projectAmount === "number") rows.push({ label: "项目金额", value: money(details.projectAmount) });
      if (typeof details.orderTotal === "number") rows.push({ label: "订单合计", value: money(details.orderTotal) });
    }
  } else if (issue.targetType === "发票") {
    const invoiceAmount = details.invoiceAmount ?? details.orderAmount;
    if (typeof invoiceAmount === "number") rows.push({ label: "发票金额", value: money(invoiceAmount), open: "invoice" });
    for (const row of details.orderAllocations ?? []) {
      rows.push({
        label: row.orderNo || "订单",
        value: `订单金额 ${money(row.orderAmount)} / 已分摊 ${money(row.allocatedAmount)}`,
        copy: true,
      });
    }
    if (typeof details.unallocatedAmount === "number" && details.unallocatedAmount > 0.009) {
      rows.push({ label: "未分摊金额", value: money(details.unallocatedAmount) });
    }
    if (typeof details.receivedAmount === "number") rows.push({ label: "实收", value: money(details.receivedAmount) });
    if (typeof details.txTotal === "number") rows.push({ label: "流水合计", value: money(details.txTotal) });
    if (typeof details.invoicedAmount === "number") rows.push({ label: "已开票", value: money(details.invoicedAmount) });
  } else {
    if (typeof details.orderAmount === "number") {
      rows.push({ label: "订单金额", value: money(details.orderAmount) });
    }
    if (typeof details.receivedAmount === "number") rows.push({ label: "实收", value: money(details.receivedAmount) });
    if (typeof details.txTotal === "number") rows.push({ label: "流水合计", value: money(details.txTotal) });
    if (typeof details.invoicedAmount === "number") rows.push({ label: "已开票", value: money(details.invoicedAmount) });
  }
  return rows;
}

function latestSupplierPrice(prices: SupplierPrice[], productId: string, supplierOrgId: string) {
  return prices
    .filter((price) => price.productId === productId && price.supplierOrgId === supplierOrgId)
    .sort((a, b) => (b.effectiveDate || "").localeCompare(a.effectiveDate || ""))[0];
}

function salesOrderLinkedItems(data: AppData, orderId: string) {
  return salesOrderLineItems(data.projectItems, orderId);
}

function salesOrderQuantity(data: AppData, orderId: string) {
  return salesOrderLinkedItems(data, orderId).reduce((sum, item) => sum + (Number(item.quantity) || 0), 0);
}

function projectSalesQuantityForProduct(data: AppData, projectId: string, productId: string) {
  return data.projectItems
    .filter((item) => item.projectId === projectId && item.productId === productId && item.salesOrderId && !isPurchaseLineItem(item))
    .reduce((sum, item) => sum + (Number(item.quantity) || 0), 0);
}

function projectPurchasedQuantityForProduct(data: AppData, projectId: string, productId: string) {
  return data.projectItems
    .filter((item) => item.projectId === projectId && item.productId === productId && !!item.purchaseOrderId && isPurchaseLineItem(item))
    .reduce((sum, item) => sum + (Number(item.quantity) || 0), 0);
}

function projectPurchaseRemainingQuantity(data: AppData, projectId: string, productId: string) {
  return Math.max(0, projectSalesQuantityForProduct(data, projectId, productId) - projectPurchasedQuantityForProduct(data, projectId, productId));
}

function isPurchaseLineItem(item: { salesOrderId?: string; purchaseOrderId?: string; actualPrice?: number; costPrice?: number }) {
  if (!item.salesOrderId) return true;
  return Number(item.actualPrice) === 0 && Number(item.costPrice) > 0;
}

/** 商品明细：只展示销售侧商品，不把渠道采购行再算成一套数量。 */
function productProjectDetailItems(data: AppData, projectId: string) {
  const all = data.projectItems.filter((item) => item.projectId === projectId);
  const salesLines = all.filter((item) => !isPurchaseLineItem(item));
  const source = salesLines.length > 0 ? salesLines : all.filter((item) => Number(item.actualPrice) > 0);
  const rows = source.length > 0 ? source : all;
  return rows.map((item) => {
    if ((Number(item.costPrice) > 0 && item.supplierOrgId) || isPurchaseLineItem(item)) return item;
    const purchaseMatch = all.find(
      (other) => isPurchaseLineItem(other) && other.productId === item.productId,
    );
    if (!purchaseMatch) return item;
    return {
      ...item,
      costPrice: Number(item.costPrice) > 0 ? item.costPrice : purchaseMatch.costPrice,
      supplierOrgId: item.supplierOrgId || purchaseMatch.supplierOrgId,
      supplierPriceId: item.supplierPriceId || purchaseMatch.supplierPriceId,
    };
  });
}

function purchaseOrderLinkedItems(data: AppData, orderId: string) {
  const linked = data.projectItems.filter((item) => item.purchaseOrderId === orderId);
  const purchaseLines = linked.filter((item) => isPurchaseLineItem(item));
  if (purchaseLines.length > 0) return purchaseLines;
  if (linked.length > 0) return linked;
  const order = data.purchaseOrders.find((item) => item.id === orderId);
  if (!order) return [];
  const projectPurchaseOrders = data.purchaseOrders.filter((item) => item.projectId === order.projectId);
  // 自动生成的采购订单可能尚未回写 purchaseOrderId，仅在该项目只有一笔采购单时回退到采购明细。
  if (projectPurchaseOrders.length !== 1) return [];
  return data.projectItems.filter((item) => item.projectId === order.projectId && isPurchaseLineItem(item));
}

function purchaseOrderItemUnitCost(data: AppData, item: { productId: string; costPrice?: number; supplierOrgId?: string }, supplierOrgId?: string) {
  if (item.costPrice && item.costPrice > 0) return Number(item.costPrice) || 0;
  const supplierId = supplierOrgId || item.supplierOrgId || "";
  if (supplierId) {
    const price = latestSupplierPrice(data.supplierPrices, item.productId, supplierId);
    if (price?.purchasePrice) return Number(price.purchasePrice) || 0;
  }
  return Number(data.products.find((product) => product.id === item.productId)?.costPrice) || 0;
}

function purchaseOrderQuantity(data: AppData, orderId: string) {
  return purchaseOrderLinkedItems(data, orderId).reduce((sum, item) => sum + (Number(item.quantity) || 0), 0);
}

function purchaseOrderDisplayAmount(data: AppData, order: PurchaseOrder) {
  if (order.amount && order.amount > 0) return order.amount;
  return purchaseOrderLinkedItems(data, order.id).reduce(
    (sum, item) => sum + (Number(item.quantity) || 0) * purchaseOrderItemUnitCost(data, item, order.supplierOrgId),
    0,
  );
}

type OrderInvoicePickLine = {
  productName: string;
  quantity: number;
  unitPrice: number;
  lineAmount: number;
};

export function orderInvoicePickSummary(data: AppData, orderId: string, type: "sales" | "purchase") {
  if (type === "sales") {
    const order = data.salesOrders.find((item) => item.id === orderId);
    const items = salesOrderLinkedItems(data, orderId).map((item) => {
      const quantity = Number(item.quantity) || 0;
      const unitPrice = Number(item.actualPrice) || 0;
      return { productName: item.productName, quantity, unitPrice, lineAmount: roundMoney(quantity * unitPrice) };
    });
    const amount = items.length > 0
      ? roundMoney(items.reduce((sum, item) => sum + item.lineAmount, 0))
      : roundMoney(order?.receivableAmount ?? order?.amount ?? 0);
    return { orderNo: order?.orderNo ?? "", amount, items };
  }
  const order = data.purchaseOrders.find((item) => item.id === orderId);
  const items = purchaseOrderLinkedItems(data, orderId).map((item) => {
    const quantity = Number(item.quantity) || 0;
    const unitPrice = purchaseOrderItemUnitCost(data, item, order?.supplierOrgId);
    return { productName: item.productName, quantity, unitPrice, lineAmount: roundMoney(quantity * unitPrice) };
  });
  const amount = order ? roundMoney(purchaseOrderDisplayAmount(data, order)) : roundMoney(items.reduce((sum, item) => sum + item.lineAmount, 0));
  return { orderNo: order?.orderNo ?? "", amount, items };
}

function projectRevenue(data: AppData, projectId: string) {
  return projectSalesAmount(data, projectId);
}

function projectCost(data: AppData, projectId: string) {
  return projectPurchaseAmount(data, projectId);
}

function orderInvoiceCap(data: AppData, order: SalesOrder | PurchaseOrder, type: "sales" | "purchase") {
  return type === "purchase"
    ? roundMoney(purchaseOrderDisplayAmount(data, order as PurchaseOrder))
    : roundMoney(order.amount);
}

function orderInvoicedAmount(data: AppData, orderId: string, type: "sales" | "purchase", excludingInvoiceId?: string) {
  return roundMoney(data.invoices
    .filter((invoice) => invoice.id !== excludingInvoiceId && invoice.status !== "作废")
    .reduce((sum, invoice) => sum + invoiceAmountForOrder(invoice, orderId, type), 0));
}

function applyInvoiceLineIndexes(
  invoice: Invoice,
  type: "sales" | "purchase",
  lineIndexes: number[],
  orderId: string,
  lineQuantities?: Record<number, number>,
): Invoice {
  return applyInvoiceLineAllocations(
    invoice,
    type,
    lineIndexes.map((index) => ({ index, quantity: lineQuantities?.[index] })),
    orderId,
  );
}

function orderLinkedInvoices(data: AppData, orderId: string, type: "sales" | "purchase") {
  return invoicesForOrder(data, orderId, type);
}

function invoiceTaxRateText(invoice: Invoice) {
  const rates = Array.from(new Set(
    (invoice.lineItems ?? [])
      .map((item) => (item.taxRate ?? "").trim())
      .filter(Boolean),
  ));
  if (rates.length > 0) return rates.join(" / ");
  if ((invoice.amountWithoutTax ?? 0) > 0 && (invoice.taxAmount ?? 0) >= 0) {
    const rate = ((invoice.taxAmount ?? 0) / (invoice.amountWithoutTax ?? 1)) * 100;
    if (Number.isFinite(rate)) return `${rate.toFixed(rate % 1 === 0 ? 0 : 2)}%`;
  }
  return "未录入";
}

type InvoicePartyDraft = { id?: string; name?: string; taxNo?: string };

type InvoiceQuickPayload = {
  invoiceNo: string;
  invoiceDate: string;
  amountWithoutTax: string;
  taxAmount: string;
  buyer: InvoicePartyDraft;
  seller: InvoicePartyDraft;
  file: File | null;
  lineItems: InvoiceLineItem[];
  lineIndexes?: number[];
  lineQuantities?: Record<number, number>;
};

function InvoiceQuickAddForm({
  invoices,
  organizations,
  defaultBuyer,
  defaultSeller,
  canManage,
  existingHint,
  ocrNewHint,
  expectedInvoiceType,
  onLinkExisting,
  onCreateNew,
}: {
  invoices: Invoice[];
  organizations: Organization[];
  defaultBuyer: InvoicePartyDraft;
  defaultSeller: InvoicePartyDraft;
  canManage: boolean;
  existingHint: string;
  ocrNewHint: string;
  expectedInvoiceType?: Invoice["type"];
  onLinkExisting: (invoice: Invoice, lineIndexes?: number[]) => Promise<boolean>;
  onCreateNew: (payload: InvoiceQuickPayload) => Promise<boolean>;
}) {
  const [invoiceNo, setInvoiceNo] = useState("");
  const [invoiceDate, setInvoiceDate] = useState(todayDate());
  const [amountWithoutTax, setAmountWithoutTax] = useState("");
  const [taxAmount, setTaxAmount] = useState("");
  const [buyer, setBuyer] = useState(defaultBuyer);
  const [seller, setSeller] = useState(defaultSeller);
  const [file, setFile] = useState<File | null>(null);
  const [ocrStatus, setOcrStatus] = useState("");
  const [lineItems, setLineItems] = useState<InvoiceLineItem[]>([]);
  const matched = findInvoiceByNo(invoices, invoiceNo);
  const matchedTypeMismatch = Boolean(matched && expectedInvoiceType && matched.type !== expectedInvoiceType);

  useEffect(() => {
    setBuyer(defaultBuyer);
    setSeller(defaultSeller);
  }, [defaultBuyer.id, defaultBuyer.name, defaultSeller.id, defaultSeller.name]);

  function resetForm() {
    setInvoiceNo("");
    setInvoiceDate(todayDate());
    setAmountWithoutTax("");
    setTaxAmount("");
    setBuyer(defaultBuyer);
    setSeller(defaultSeller);
    setFile(null);
    setOcrStatus("");
    setLineItems([]);
  }

  async function fillFromOcr() {
    if (!file) {
      setOcrStatus("请先选择发票 PDF 文件。");
      return;
    }
    setOcrStatus("正在识别 PDF 发票...");
    try {
      const formData = new FormData();
      formData.append("file", file);
      const response = await fetch(ocrServiceUrl("/api/ocr/invoice"), {
        method: "POST",
        body: formData,
      });
      if (!response.ok) {
        const errorText = await response.text();
        throw new Error(errorText || "发票识别失败");
      }
      const result = await response.json();
      if (result.status !== "recognized" || !result.data) {
        setOcrStatus(result.message || "该 PDF 暂未识别到文本层，需要图片 OCR。");
        return;
      }
      const parsed = result.data as {
        invoice_no?: string;
        invoice_date?: string;
        buyer_name?: string;
        buyer_tax_no?: string;
        seller_name?: string;
        seller_tax_no?: string;
        amount_without_tax?: number;
        tax_amount?: number;
        line_items?: Array<{
          product_name?: string;
          specification?: string;
          unit?: string;
          quantity?: number;
          unit_price?: number;
          amount?: number;
          tax_rate?: string;
          tax_amount?: number;
          raw?: string;
        }>;
      };
      const buyerMatched = findOrganizationByInvoiceParty(organizations, parsed.buyer_tax_no, parsed.buyer_name);
      const sellerMatched = findOrganizationByInvoiceParty(organizations, parsed.seller_tax_no, parsed.seller_name);
      if (parsed.invoice_no) setInvoiceNo(parsed.invoice_no);
      if (parsed.invoice_date) setInvoiceDate(parsed.invoice_date);
      if (parsed.amount_without_tax != null) setAmountWithoutTax(String(parsed.amount_without_tax));
      if (parsed.tax_amount != null) setTaxAmount(String(parsed.tax_amount));
      setBuyer({
        id: buyerMatched?.id ?? defaultBuyer.id,
        name: parsed.buyer_name?.trim() || buyerMatched?.name || defaultBuyer.name,
        taxNo: parsed.buyer_tax_no?.trim() || buyerMatched?.unifiedCreditCode || defaultBuyer.taxNo,
      });
      setSeller({
        id: sellerMatched?.id ?? defaultSeller.id,
        name: parsed.seller_name?.trim() || sellerMatched?.name || defaultSeller.name,
        taxNo: parsed.seller_tax_no?.trim() || sellerMatched?.unifiedCreditCode || defaultSeller.taxNo,
      });
      setLineItems((parsed.line_items ?? []).map((item) => ({
        productName: item.product_name ?? "",
        specification: item.specification,
        unit: item.unit,
        quantity: item.quantity,
        unitPrice: item.unit_price,
        amount: item.amount,
        taxRate: item.tax_rate,
        taxAmount: item.tax_amount,
        raw: item.raw,
      })).filter((item) => item.productName));
      const existing = parsed.invoice_no ? findInvoiceByNo(invoices, parsed.invoice_no) : undefined;
      const itemCount = (parsed.line_items ?? []).length;
      const itemHint = itemCount > 0 ? `已识别 ${itemCount} 个商品明细。` : "未识别到商品明细，可手工核对。";
      setOcrStatus(existing
        ? `识别完成：发票 ${existing.invoiceNo} 已在库中，保存时将直接关联。${itemHint}`
        : (ocrNewHint ? `${ocrNewHint}${itemHint}` : (result.message || `识别完成。${itemHint}`)));
    } catch (error) {
      setOcrStatus(error instanceof Error ? error.message : "发票识别失败");
    }
  }

  async function submit() {
    if (matchedTypeMismatch && matched && expectedInvoiceType) {
      window.alert(`发票 ${matched.invoiceNo || invoiceNo} 是${matched.type}，此处只能关联${expectedInvoiceType}发票。`);
      return;
    }
    const ok = matched
      ? await onLinkExisting(matched)
      : await onCreateNew({
          invoiceNo,
          invoiceDate,
          amountWithoutTax,
          taxAmount,
          buyer,
          seller,
          file,
          lineItems,
        });
    if (ok) resetForm();
  }

  if (!canManage) return null;
  return (
    <div className="create-project project-invoice-add-form">
      <div className="project-invoice-add-row">
        <input value={invoiceNo} onChange={(event) => setInvoiceNo(event.target.value)} placeholder="发票号码" aria-label="发票号码" />
        <DateTimeField value={invoiceDate} onChange={setInvoiceDate} ariaLabel="发票日期" placeholder="发票日期" />
        <input type="number" value={amountWithoutTax} onChange={(event) => setAmountWithoutTax(event.target.value)} placeholder="不含税金额" aria-label="不含税金额" />
        <input type="number" value={taxAmount} onChange={(event) => setTaxAmount(event.target.value)} placeholder="税额" aria-label="税额" />
        <button className="primary" onClick={() => void submit()} disabled={matchedTypeMismatch}>
          {matched ? "关联已有发票" : "添加并关联"}
        </button>
      </div>
      {matchedTypeMismatch && matched && expectedInvoiceType && (
        <p className="form-error">该发票是{matched.type}，此处只能关联{expectedInvoiceType}发票。</p>
      )}
      <div className="project-invoice-add-row">
        <FilePicker
          accept=".pdf,application/pdf"
          fileName={file?.name}
          placeholder="未选择发票 PDF"
          buttonLabel="选择发票"
          ariaLabel="选择发票文件"
          onFile={(next) => {
            setFile(next ?? null);
            setOcrStatus("");
          }}
        />
        <button className="ghost" onClick={() => void fillFromOcr()}><FileScan size={16} />OCR 识别</button>
      </div>
      {matched && <div className="copy-tip">库中已有发票 {matched.invoiceNo}，保存时将直接关联{existingHint}。</div>}
      {ocrStatus && <div className="copy-tip">{ocrStatus}</div>}
      {lineItems.length > 0 && (
        <div className="invoice-items">
          {lineItems.map((item, index) => (
            <span key={`${item.productName}-${index}`}>
              {item.productName}
              <em>{item.specification || "无规格"} / {money(item.amount ?? 0)}</em>
            </span>
          ))}
        </div>
      )}
    </div>
  );
}

export function OrderInvoiceAssociationPanel({
  linkedInvoices,
  invoiceSelectOptions,
  selectedInvoiceId,
  canManage,
  invoices,
  organizations,
  defaultBuyer,
  defaultSeller,
  existingHint,
  ocrNewHint,
  expectedInvoiceType,
  orderId,
  orderType,
  orderSummary,
  orderNoById,
  onSelectInvoice,
  onLink,
  onUnlink,
  onLinkExisting,
  onCreateNew,
}: {
  linkedInvoices: Invoice[];
  invoiceSelectOptions: SearchableSelectOption[];
  selectedInvoiceId: string;
  canManage: boolean;
  invoices: Invoice[];
  organizations: Organization[];
  defaultBuyer: InvoicePartyDraft;
  defaultSeller: InvoicePartyDraft;
  existingHint: string;
  ocrNewHint: string;
  expectedInvoiceType: Invoice["type"];
  orderId: string;
  orderType: "sales" | "purchase";
  orderSummary: { orderNo: string; amount: number; items: OrderInvoicePickLine[] };
  orderNoById?: Record<string, string>;
  onSelectInvoice: (invoiceId: string) => void;
  onLink: (lineIndexes?: number[], lineQuantities?: Record<number, number>) => void;
  onUnlink: (invoice: Invoice) => void;
  onLinkExisting: (invoice: Invoice, lineIndexes?: number[], lineQuantities?: Record<number, number>) => Promise<boolean>;
  onCreateNew: (payload: InvoiceQuickPayload) => Promise<boolean>;
}) {
  const [pickingInvoice, setPickingInvoice] = useState<Invoice | null>(null);
  const [pickingPayload, setPickingPayload] = useState<InvoiceQuickPayload | null>(null);
  const [pickingIndexes, setPickingIndexes] = useState<number[]>([]);
  const [pickingQuantities, setPickingQuantities] = useState<Record<number, number>>({});
  const [formResetKey, setFormResetKey] = useState(0);
  const pickingLines = pickingPayload?.lineItems ?? pickingInvoice?.lineItems ?? [];
  const pickingTitle = pickingInvoice?.invoiceNo || pickingPayload?.invoiceNo || "未录入发票号";

  function quantitiesForIndexes(lines: InvoiceLineItem[], indexes: number[]) {
    return Object.fromEntries(indexes.map((index) => [index, Number(lines[index]?.quantity) || 0]));
  }

  function startPick(invoice: Invoice) {
    const lines = invoice.lineItems ?? [];
    let indexes = defaultInvoiceLinePickIndexes(lines, orderSummary.items, orderId, orderType);
    // 单商品也要弹出勾选/数量；金额对不上时默认勾选未占用行，方便改关联数量。
    if (indexes.length === 0 && lines.length === 1 && !invoiceLineAssignedOrderId(lines[0], orderType)) {
      indexes = [0];
    }
    setPickingPayload(null);
    setPickingInvoice(invoice);
    setPickingIndexes(indexes);
    setPickingQuantities(quantitiesForIndexes(lines, indexes));
  }

  function closePick() {
    setPickingInvoice(null);
    setPickingPayload(null);
    setPickingQuantities({});
  }

  async function confirmPick() {
    const quantities = Object.fromEntries(
      pickingIndexes
        .filter((index) => !invoiceLineAssignedOrderId(pickingLines[index] ?? {}, orderType))
        .map((index) => [index, pickingQuantities[index] ?? (Number(pickingLines[index]?.quantity) || 0)] as const)
        .filter(([, quantity]) => quantity > 0),
    );
    const indexes = Object.keys(quantities).map(Number);
    if (pickingPayload) {
      const ok = await onCreateNew({ ...pickingPayload, lineIndexes: indexes, lineQuantities: quantities });
      if (ok) setFormResetKey((value) => value + 1);
      closePick();
      return;
    }
    if (!pickingInvoice) return;
    if (pickingInvoice.id === selectedInvoiceId) onLink(indexes, quantities);
    else void onLinkExisting(pickingInvoice, indexes, quantities);
    closePick();
  }

  function handleLink() {
    const invoice = invoices.find((item) => item.id === selectedInvoiceId);
    if (invoice && (invoice.lineItems?.length ?? 0) > 0) {
      startPick(invoice);
      return;
    }
    onLink();
  }

  async function handleLinkExisting(invoice: Invoice) {
    if ((invoice.lineItems?.length ?? 0) > 0) {
      startPick(invoice);
      return false;
    }
    return onLinkExisting(invoice);
  }

  async function handleCreateNew(payload: InvoiceQuickPayload) {
    if ((payload.lineItems?.length ?? 0) > 0 && payload.lineIndexes == null) {
      let indexes = defaultInvoiceLinePickIndexes(payload.lineItems, orderSummary.items, orderId, orderType);
      if (indexes.length === 0 && payload.lineItems.length === 1 && !invoiceLineAssignedOrderId(payload.lineItems[0], orderType)) {
        indexes = [0];
      }
      setPickingInvoice(null);
      setPickingPayload(payload);
      setPickingIndexes(indexes);
      setPickingQuantities(quantitiesForIndexes(payload.lineItems, indexes));
      return false;
    }
    return onCreateNew(payload);
  }

  return (
    <div className="order-invoice-panel fulfillment-remark">
      {linkedInvoices.length > 0 ? (
        <div className="linked-invoice-list">
          {linkedInvoices.map((invoice) => (
            <div key={invoice.id} className="linked-invoice-card">
              <div className="linked-invoice-card-head">
                <strong>{invoice.invoiceNo || "未录入发票号"}</strong>
                <em>{invoice.type} · {invoice.status}</em>
                {canManage && (
                  <button
                    type="button"
                    className="linked-invoice-unlink"
                    aria-label={`取消关联发票 ${invoice.invoiceNo || "未录入"}`}
                    title="取消关联"
                    onClick={() => onUnlink(invoice)}
                  >
                    ×
                  </button>
                )}
              </div>
              <div className="linked-invoice-card-grid">
                <span>开票日期<em>{invoice.invoiceDate || invoice.date || "未录入"}</em></span>
                <span>购方<em>{invoice.buyerName || "未录入"}</em></span>
                <span>销方<em>{invoice.sellerName || "未录入"}</em></span>
                <span>税率<em>{invoiceTaxRateText(invoice)}</em></span>
                <span>不含税<em>{money(invoice.amountWithoutTax ?? 0)}</em></span>
                <span>税额<em>{money(invoice.taxAmount ?? 0)}</em></span>
                <span>价税合计<em>{money(invoice.amount)}</em></span>
              </div>
              {(invoice.lineItems ?? []).length > 0 && (
                <div className="invoice-line-chips">
                  {((invoice.lineItems ?? []).filter((item) => (
                    orderType === "sales" ? item.salesOrderId === orderId : item.purchaseOrderId === orderId
                  )).length
                    ? (invoice.lineItems ?? []).filter((item) => (
                      orderType === "sales" ? item.salesOrderId === orderId : item.purchaseOrderId === orderId
                    ))
                    : (invoice.lineItems ?? [])
                  ).map((item, index) => (
                    <em key={`${item.productName}-${index}`}>{item.productName} {money(invoiceLineGrossAmount(item))}</em>
                  ))}
                  <strong>本单 {money(invoiceAmountForOrder(invoice, orderId, orderType))}</strong>
                </div>
              )}
            </div>
          ))}
        </div>
      ) : (
        <div className="empty-line">暂未关联发票</div>
      )}
      <div className="invoice-link-bar">
        <SearchableSelect
          value={selectedInvoiceId}
          options={invoiceSelectOptions}
          onChange={onSelectInvoice}
          placeholder="搜索发票号、买卖方或金额"
          ariaLabel="搜索并选择已有发票关联到订单"
        />
        {canManage && <button type="button" className="ghost" onClick={handleLink}>关联发票</button>}
      </div>
      <InvoiceQuickAddForm
        key={formResetKey}
        invoices={invoices}
        organizations={organizations}
        defaultBuyer={defaultBuyer}
        defaultSeller={defaultSeller}
        canManage={canManage}
        existingHint={existingHint}
        ocrNewHint={ocrNewHint}
        expectedInvoiceType={expectedInvoiceType}
        onLinkExisting={handleLinkExisting}
        onCreateNew={handleCreateNew}
      />
      {(pickingInvoice || pickingPayload) && (
        <div className="modal-backdrop is-nested-2" role="presentation">
          <div className="modal invoice-line-pick-modal" role="dialog" aria-modal="true" aria-label="选择发票商品">
            <div className="modal-head">
              <div>
                <h2>选择关联商品</h2>
                <p>发票 {pickingTitle} 含 {pickingLines.length} 个商品行，对照当前订单勾选并填写关联数量。同一张发票可按数量拆到多个订单。</p>
              </div>
              <button className="icon-button" onClick={closePick} aria-label="关闭">×</button>
            </div>
            <div className="invoice-line-pick-order">
              <p className="invoice-line-pick-total is-order">
                当前订单 {orderSummary.orderNo || "未录入订单号"} · 订单总价 {money(orderSummary.amount)}
              </p>
              {orderSummary.items.length > 0 ? (
                <div className="invoice-line-pick-order-table">
                  <div className="invoice-line-pick-order-row head"><span>商品</span><span>数量</span><span>单价</span><span>数量×单价</span></div>
                  {orderSummary.items.map((item, index) => (
                    <div className="invoice-line-pick-order-row" key={`${item.productName}-${index}`}>
                      <span>
                        <CopyableLine text={item.productName} label="商品名称">{item.productName}</CopyableLine>
                      </span>
                      <span>{item.quantity}</span>
                      <span>{money(item.unitPrice)}</span>
                      <span>{money(item.lineAmount)}</span>
                    </div>
                  ))}
                </div>
              ) : (
                <div className="empty-line">当前订单暂无商品明细</div>
              )}
            </div>
            <p className="invoice-line-pick-total">
              已选发票价税合计 {money(pickingIndexes.reduce((sum, index) => sum + allocatedInvoiceLineGross(pickingLines[index] ?? {}, pickingQuantities[index]), 0))}
              <em>订单总价 {money(orderSummary.amount)}</em>
            </p>
            <div className="invoice-line-pick-list invoice-line-pick-order-table">
              <div className="invoice-line-pick-order-row invoice-line-pick-invoice-row head">
                <span></span><span>发票商品</span><span>发票数量</span><span>关联数量</span><span>单价</span><span>数量×单价</span><span>价税合计</span>
              </div>
              {pickingLines.map((item, index) => {
                const assignedId = invoiceLineAssignedOrderId(item, orderType);
                const locked = Boolean(assignedId);
                const selected = !locked && pickingIndexes.includes(index);
                const linkedQty = locked
                  ? (Number(item.quantity) || 0)
                  : selected ? (pickingQuantities[index] ?? (Number(item.quantity) || 0)) : 0;
                const hasQtyPrice = item.quantity != null && item.unitPrice != null;
                const qtyAmount = hasQtyPrice ? roundMoney(linkedQty * (item.unitPrice ?? 0)) : null;
                const linkedOrderNo = assignedId ? (orderNoById?.[assignedId] || assignedId) : "";
                return (
                  <div key={`${item.productName}-${index}`} className={`invoice-line-pick-order-row invoice-line-pick-invoice-row${locked ? " is-linked" : ""}`}>
                    <span>
                      <input
                        type="checkbox"
                        checked={selected}
                        disabled={locked}
                        onChange={(event) => {
                          const checked = event.target.checked;
                          setPickingIndexes((current) => (
                            checked ? Array.from(new Set([...current, index])) : current.filter((value) => value !== index)
                          ));
                          setPickingQuantities((current) => {
                            if (!checked) {
                              const next = { ...current };
                              delete next[index];
                              return next;
                            }
                            return { ...current, [index]: Number(item.quantity) || 0 };
                          });
                        }}
                        aria-label={locked ? `${item.productName}已关联` : `选择 ${item.productName}`}
                      />
                    </span>
                    <span>
                      <CopyableLine text={item.productName} label="发票商品">{item.productName}</CopyableLine>
                      {locked ? <em className="invoice-line-linked-tag">已关联 {linkedOrderNo}</em> : null}
                    </span>
                    <span>{item.quantity ?? "-"}{item.unit || ""}</span>
                    <span>
                      <input
                        className="invoice-line-pick-qty"
                        type="number"
                        min="0"
                        step="any"
                        max={item.quantity ?? undefined}
                        disabled={locked || !selected}
                        value={locked ? (item.quantity ?? "") : selected ? (pickingQuantities[index] ?? "") : ""}
                        aria-label={`${item.productName}关联数量`}
                        onChange={(event) => {
                          const raw = Number(event.target.value);
                          const maxQty = Number(item.quantity) || raw;
                          const nextQty = Number.isFinite(raw) ? Math.max(0, Math.min(raw, maxQty)) : 0;
                          setPickingQuantities((current) => ({ ...current, [index]: nextQty }));
                          if (nextQty > 0) {
                            setPickingIndexes((current) => Array.from(new Set([...current, index])));
                          }
                        }}
                      />
                    </span>
                    <span>{item.unitPrice != null ? money(item.unitPrice) : "未录入"}</span>
                    <span>{qtyAmount != null ? money(qtyAmount) : "—"}</span>
                    <span>{money(allocatedInvoiceLineGross(item, locked || selected ? linkedQty : undefined))}</span>
                  </div>
                );
              })}
            </div>
            <div className="modal-actions">
              <button className="ghost" onClick={closePick}>取消</button>
              <button className="primary" onClick={() => void confirmPick()}>确认关联</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

function projectHasActiveInvoice(data: AppData, projectId: string) {
  return data.invoices.some((invoice) =>
    invoice.status !== "作废" && invoiceBelongsToProject(data, invoice, projectId),
  );
}

function projectInvoiceStatusText(data: AppData, project: Project) {
  if (projectHasActiveInvoice(data, project.id)) return "已开全部";
  return project.invoiceStatus;
}

function sortByCreatedDesc<T>(items: T[]) {
  return items
    .map((item, index) => ({ item, index }))
    .sort((left, right) => {
      const leftCreatedAt = (left.item as { createdAt?: string }).createdAt ?? "";
      const rightCreatedAt = (right.item as { createdAt?: string }).createdAt ?? "";
      return rightCreatedAt.localeCompare(leftCreatedAt) || left.index - right.index;
    })
    .map(({ item }) => item);
}

function isMaskedSecret(value?: string) {
  if (!value) return true;
  if (value === "已保存") return true;
  return /^(?:\*{4}|.{2}\*{3}.{2})$/.test(value);
}

function didChangeSecret(previous?: string, next?: string) {
  if (!next || isMaskedSecret(next)) return false;
  return next !== (previous ?? "");
}

function platformAccountLog(previous: PlatformAccount | undefined, next: PlatformAccount, customerName?: string) {
  const targetName = customerName || next.accountName || next.platform || "平台账号";
  const identity = [next.platform, next.accountName].filter(Boolean).join(" / ");
  const passwordChanged = didChangeSecret(previous?.accountPasswordMasked, next.accountPasswordMasked);
  if (!previous) {
    return { action: "新增平台账号", targetName, detail: identity || next.platform };
  }
  const changes: string[] = [];
  if (passwordChanged) changes.push("修改密码");
  if ((previous.accountName || "") !== (next.accountName || "")) {
    changes.push(`账号 ${previous.accountName || "未录入"} -> ${next.accountName || "未录入"}`);
  }
  if (previous.platform !== next.platform) changes.push(`平台 ${previous.platform} -> ${next.platform}`);
  if (previous.customerOrgId !== next.customerOrgId) changes.push("更换客户");
  if ((previous.merchantId || "") !== (next.merchantId || "")) {
    changes.push(`商家ID ${previous.merchantId || "未录入"} -> ${next.merchantId || "未录入"}`);
  }
  if ((previous.shopId || "") !== (next.shopId || "")) {
    changes.push(`店铺ID ${previous.shopId || "未录入"} -> ${next.shopId || "未录入"}`);
  }
  if ((previous.shopName || "") !== (next.shopName || "")) {
    changes.push(`店铺名称 ${previous.shopName || "未录入"} -> ${next.shopName || "未录入"}`);
  }
  if ((previous.cloudAccount || "") !== (next.cloudAccount || "")) changes.push("修改云账号");
  if ((previous.currentStatus || "") !== (next.currentStatus || "")) {
    changes.push(`状态 ${previous.currentStatus || "未录入"} -> ${next.currentStatus || "未录入"}`);
  }
  const action = passwordChanged && changes.length === 1 ? "修改平台账号密码" : "编辑平台账号";
  return {
    action,
    targetName,
    detail: [identity, changes.join("；") || "保存账号信息"].filter(Boolean).join("；"),
  };
}

function organizationRelatedLogs(data: AppData, organization: Organization) {
  const relatedProjects = data.projects.filter((project) =>
    project.customerOrgId === organization.id
    || project.usageUnitOrgId === organization.id
    || project.ownCompanyOrgId === organization.id
    || project.name.includes(organization.name),
  );
  const relatedProjectIds = new Set(relatedProjects.map((project) => project.id));
  const relatedNames = new Set<string>([
    organization.name,
    ...relatedProjects.map((project) => project.name),
    ...relatedProjects.map((project) => project.projectNo).filter(Boolean) as string[],
    ...data.serviceOrders.filter((order) => relatedProjectIds.has(order.projectId)).map((order) => order.orderNo),
    ...data.salesOrders.filter((order) => relatedProjectIds.has(order.projectId)).map((order) => order.orderNo),
    ...data.purchaseOrders.filter((order) => relatedProjectIds.has(order.projectId)).map((order) => order.orderNo),
  ]);

  return sortByCreatedDesc(data.operationLogs.filter((log) => {
    if (relatedNames.has(log.targetName)) return true;
    const haystack = `${log.targetName} ${log.detail ?? ""} ${log.action}`;
    if (haystack.includes(organization.name)) return true;
    for (const name of relatedNames) {
      if (name && name !== organization.name && haystack.includes(name)) return true;
    }
    return false;
  }));
}

function paymentLogDetail(params: {
  orderNo: string;
  fromStatus: string;
  toStatus: string;
  payment?: PaymentFormResult | null;
  receivedAmount?: number;
  customerName?: string;
  kind?: "collect" | "pay";
}) {
  const parts = [`订单 ${params.orderNo}`, `${params.fromStatus} -> ${params.toStatus}`];
  if (params.payment) {
    const isRefund = params.toStatus === "退款";
    const isPay = params.kind === "pay" || params.payment.paymentMethod === "付款";
    parts.push(`${isRefund ? "退款" : isPay ? "付款" : "收款"} ${money(params.payment.amount)}`);
    if (params.receivedAmount !== undefined) parts.push(`${isRefund ? "退后实收" : isPay ? "已付" : "实收"} ${money(params.receivedAmount)}`);
    if (params.payment.collectionAccount) parts.push(`${isRefund ? "打款账户" : isPay ? "付款银行" : "收款账户"} ${params.payment.collectionAccount}`);
    if (params.payment.remark) parts.push(`备注 ${params.payment.remark}`);
  }
  if (params.customerName) parts.push(`客户：${params.customerName}`);
  return parts.join("；");
}

function formatInvoiceLabel(data: AppData, invoice: Invoice) {
  const buyer = invoice.buyerName || data.organizations.find((org) => org.id === invoice.buyerOrgId)?.name || "买方未录入";
  const seller = invoice.sellerName || data.organizations.find((org) => org.id === invoice.sellerOrgId)?.name || "卖方未录入";
  const remaining = invoiceRemainingAmount(data, invoice);
  const amountText = remaining + 0.009 < (Number(invoice.amount) || 0) && remaining > 0.009
    ? `${money(invoice.amount)}（剩余 ${money(remaining)}）`
    : money(invoice.amount);
  return `${invoice.invoiceNo || "未录入发票号"}｜${invoice.invoiceDate || invoice.date || "未录入日期"}｜${invoice.type}｜${buyer} → ${seller}｜${amountText}｜${invoice.status}`;
}

function promptServiceInvoiceAllocationAmount(params: {
  data: AppData;
  invoice: Invoice;
  projectId: string;
  serviceOrderId?: string;
}): number | null {
  const remaining = invoiceRemainingAmount(params.data, params.invoice);
  let defaultAmount = remaining;
  if (params.serviceOrderId) {
    const order = params.data.serviceOrders.find((item) => item.id === params.serviceOrderId);
    if (order) {
      const orderAmount = Number(order.receivableAmount ?? order.amount) || 0;
      const already = serviceOrderInvoicedAmount(params.data, order.id);
      const orderRemaining = Math.max(Math.round((orderAmount - already) * 100) / 100, 0);
      defaultAmount = Math.min(remaining, orderRemaining);
    }
  }
  const input = window.prompt(
    `请输入关联金额（发票剩余 ${money(remaining)}）`,
    String(defaultAmount),
  );
  if (input == null) return null;
  const amount = Math.round((Number(input.replace(/,/g, "")) || 0) * 100) / 100;
  if (!Number.isFinite(amount) || amount <= 0) {
    window.alert("请输入大于 0 的关联金额。");
    return null;
  }
  if (amount > remaining + 0.009) {
    window.alert(`关联金额不能超过发票剩余额度 ${money(remaining)}。`);
    return null;
  }
  if (params.serviceOrderId) {
    const order = params.data.serviceOrders.find((item) => item.id === params.serviceOrderId);
    if (order) {
      const orderAmount = Number(order.receivableAmount ?? order.amount) || 0;
      const already = serviceOrderInvoicedAmount(params.data, order.id);
      const orderRemaining = Math.max(Math.round((orderAmount - already) * 100) / 100, 0);
      if (amount > orderRemaining + 0.009) {
        window.alert(`关联金额不能超过该订单未开票金额 ${money(orderRemaining)}。`);
        return null;
      }
    }
  }
  return amount;
}

function pickDefaultServiceOrderIdForInvoiceLink(data: AppData, projectId: string) {
  const unpaid = data.serviceOrders.filter((order) => {
    if (order.projectId !== projectId || order.status === "取消") return false;
    const orderAmount = Number(order.receivableAmount ?? order.amount) || 0;
    if (orderAmount <= 0) return false;
    return serviceOrderInvoicedAmount(data, order.id) + 0.009 < orderAmount;
  });
  return unpaid.length === 1 ? unpaid[0].id : undefined;
}

function invoiceLinkSelectOptions(data: AppData, target: Parameters<typeof invoicesEligibleToLink>[1]) {
  return invoicesEligibleToLink(data, target).map((invoice) => ({ value: invoice.id, label: formatInvoiceLabel(data, invoice) }));
}

async function linkInvoiceToOrderRecord(params: {
  data: AppData;
  commit: (data: AppData, log?: Omit<OperationLog, "id" | "createdAt">) => Promise<void>;
  invoiceId: string;
  order: SalesOrder | PurchaseOrder;
  type: "sales" | "purchase";
  lineIndexes?: number[];
  lineQuantities?: Record<number, number>;
}) {
  const project = params.data.projects.find((item) => item.id === params.order.projectId);
  const invoice = params.data.invoices.find((item) => item.id === params.invoiceId);
  if (!project || !invoice) return false;
  const blocked = invoiceLinkBlockReason(params.data, invoice, {
    kind: params.type,
    projectId: project.id,
    orderId: params.order.id,
  });
  if (blocked) {
    window.alert(blocked);
    return false;
  }
  const lines = invoice.lineItems ?? [];
  let nextInvoice = invoice;
  if (lines.length > 0) {
    const indexes = params.lineIndexes;
    if (indexes == null) {
      window.alert("请选择要关联到此订单的商品及数量。");
      return false;
    }
    if (indexes.length === 0) {
      window.alert("请至少选择一个商品。");
      return false;
    }
    nextInvoice = applyInvoiceLineIndexes(invoice, params.type, indexes, params.order.id, params.lineQuantities);
  } else if (invoiceLinkedToOrder(invoice, params.order.id, params.type)) {
    window.alert("该发票已经关联到这个订单。");
    return false;
  } else {
    nextInvoice = {
      ...invoice,
      salesOrderIds: params.type === "sales" ? Array.from(new Set([...(invoice.salesOrderIds ?? []), params.order.id])) : invoice.salesOrderIds ?? [],
      purchaseOrderIds: params.type === "purchase" ? Array.from(new Set([...(invoice.purchaseOrderIds ?? []), params.order.id])) : invoice.purchaseOrderIds ?? [],
    };
  }
  nextInvoice = reconcileInvoiceProjectIds(params.data, nextInvoice, project.id);
  const nextData = {
    ...params.data,
    invoices: params.data.invoices.map((item) => item.id === params.invoiceId ? nextInvoice : item),
    projects: params.data.projects.map((item) => item.id === project.id && item.type === "服务项目" ? { ...item, invoiceStatus: "已开全部" as const } : item),
  };
  const synced = project.type === "商品项目" ? applyProductProjectSync(nextData, project.id) : { data: nextData };
  const lineNames = (nextInvoice.lineItems ?? [])
    .filter((item) => params.type === "sales" ? item.salesOrderId === params.order.id : item.purchaseOrderId === params.order.id)
    .map((item) => `${item.productName} ${money(item.amount ?? 0)}`)
    .join("；");
  await params.commit(
    synced.data,
    { action: "关联发票到订单", targetType: "发票", targetName: invoice.invoiceNo || params.order.orderNo, operator: "当前用户", detail: `${params.order.orderNo} / ${project.name}${lineNames ? `；${lineNames}` : ""}` },
  );
  return true;
}

async function unlinkServiceInvoiceRecord(params: {
  data: AppData;
  commit: (data: AppData, log?: Omit<OperationLog, "id" | "createdAt">) => Promise<void>;
  invoice: Invoice;
  projectId: string;
  serviceOrderId?: string;
  label: string;
}) {
  const invoiceNo = params.invoice.invoiceNo || "未录入发票号";
  if (!window.confirm(`确定取消发票「${invoiceNo}」与「${params.label}」的关联吗？`)) return false;
  const nextInvoice = removeServiceInvoiceAllocation(params.data, params.invoice, {
    projectId: params.projectId,
    serviceOrderId: params.serviceOrderId,
  });
  const nextData = {
    ...params.data,
    invoices: params.data.invoices.map((item) => item.id === params.invoice.id ? nextInvoice : item),
  };
  await params.commit(
    {
      ...nextData,
      projects: nextData.projects.map((project) => project.id === params.projectId
        ? { ...project, invoiceStatus: deriveServiceProjectInvoiceStatus(nextData, params.projectId) }
        : project),
    },
    {
      action: "取消服务发票关联",
      targetType: "发票",
      targetName: invoiceNo,
      operator: "当前用户",
      detail: params.label,
    },
  );
  return true;
}

async function unlinkInvoiceFromOrderRecord(params: {
  data: AppData;
  commit: (data: AppData, log?: Omit<OperationLog, "id" | "createdAt">) => Promise<void>;
  invoice: Invoice;
  order: SalesOrder | PurchaseOrder;
  type: "sales" | "purchase";
}) {
  const project = params.data.projects.find((item) => item.id === params.order.projectId);
  if (!project) return;
  const invoiceNo = params.invoice.invoiceNo || "未录入发票号";
  if (!window.confirm(`确定取消发票「${invoiceNo}」与订单「${params.order.orderNo}」的关联吗？`)) return;
  const nextInvoices = params.data.invoices.map((item) => {
    if (item.id !== params.invoice.id) return item;
    const clearedLines = (item.lineItems ?? []).map((line) => (
      params.type === "sales" && line.salesOrderId === params.order.id
        ? { ...line, salesOrderId: undefined }
        : params.type === "purchase" && line.purchaseOrderId === params.order.id
          ? { ...line, purchaseOrderId: undefined }
          : line
    ));
    return {
      ...item,
      lineItems: clearedLines,
      salesOrderIds: clearedLines.some((line) => line.salesOrderId)
        ? Array.from(new Set(clearedLines.map((line) => line.salesOrderId).filter((id): id is string => Boolean(id))))
        : (item.salesOrderIds ?? []).filter((id) => id !== params.order.id),
      purchaseOrderIds: clearedLines.some((line) => line.purchaseOrderId)
        ? Array.from(new Set(clearedLines.map((line) => line.purchaseOrderId).filter((id): id is string => Boolean(id))))
        : (item.purchaseOrderIds ?? []).filter((id) => id !== params.order.id),
    };
  }).map((item) => item.id === params.invoice.id ? reconcileInvoiceProjectIds(params.data, item) : item);
  const base = { ...params.data, invoices: nextInvoices };
  const synced = project.type === "商品项目" ? applyProductProjectSync(base, params.order.projectId) : { data: base };
  await params.commit(
    synced.data,
    {
      action: "取消发票订单关联",
      targetType: "发票",
      targetName: invoiceNo,
      operator: "当前用户",
      detail: `${params.order.orderNo} / ${project.name}${synced.autoDetail ? `；${synced.autoDetail}` : ""}`,
    },
  );
}

async function createLinkedInvoiceRecord(params: {
  data: AppData;
  commit: (data: AppData, log?: Omit<OperationLog, "id" | "createdAt">) => Promise<void>;
  can: CanAccess;
  project: Project;
  payload: InvoiceQuickPayload;
  options: {
    type: "销项" | "进项";
    salesOrderId?: string;
    purchaseOrderId?: string;
    defaultProductName: string;
    logDetail: string;
  };
  customer?: Organization;
  ownCompany?: Organization;
}): Promise<boolean> {
  const { data, commit, project, payload, options } = params;
  if (!params.can("invoice.manage")) return false;
  const invoiceNo = payload.invoiceNo.trim();
  if (!invoiceNo) {
    window.alert("请输入发票号码。");
    return false;
  }
  const existing = findInvoiceByNo(data.invoices, invoiceNo);
  if (existing) {
    if (existing.type !== options.type) {
      window.alert(`发票 ${existing.invoiceNo || invoiceNo} 是${existing.type}，此处只能关联${options.type}发票。`);
      return false;
    }
    if (options.salesOrderId) {
      const order = data.salesOrders.find((item) => item.id === options.salesOrderId);
      return order ? linkInvoiceToOrderRecord({ data, commit, invoiceId: existing.id, order, type: "sales", lineIndexes: payload.lineIndexes, lineQuantities: payload.lineQuantities }) : false;
    }
    if (options.purchaseOrderId) {
      const order = data.purchaseOrders.find((item) => item.id === options.purchaseOrderId);
      return order ? linkInvoiceToOrderRecord({ data, commit, invoiceId: existing.id, order, type: "purchase", lineIndexes: payload.lineIndexes, lineQuantities: payload.lineQuantities }) : false;
    }
    return false;
  }
  const withoutTax = Number(payload.amountWithoutTax);
  const tax = Number(payload.taxAmount || 0);
  if (!payload.amountWithoutTax.trim() || Number.isNaN(withoutTax) || Number.isNaN(tax)) {
    window.alert("请填写不含税金额和税额。");
    return false;
  }
  const invoiceAmount = roundMoney(withoutTax + tax);
  const targetOrder = options.salesOrderId
    ? data.salesOrders.find((item) => item.id === options.salesOrderId)
    : options.purchaseOrderId
      ? data.purchaseOrders.find((item) => item.id === options.purchaseOrderId)
      : undefined;
  const draftLines = payload.lineItems.length > 0
    ? payload.lineItems
    : [{
        productName: options.defaultProductName,
        amount: invoiceAmount,
      }];
  const selectedIndexes = payload.lineIndexes ?? draftLines.map((_, index) => index);
  let nextOrganizations = [...data.organizations];
  function ensureOrganization(
    selectedOrgId: string,
    name: string,
    taxNo: string,
    role: OrganizationRole,
  ) {
    const selected = nextOrganizations.find((org) => org.id === selectedOrgId);
    const matched = nextOrganizations.find((org) => taxNo && org.unifiedCreditCode === taxNo)
      ?? nextOrganizations.find((org) => name && org.name === name)
      ?? (selected && (!taxNo || !selected.unifiedCreditCode || selected.unifiedCreditCode === taxNo) ? selected : undefined);
    if (matched) {
      nextOrganizations = nextOrganizations.map((org) =>
        org.id === matched.id
          ? {
              ...org,
              name: name || org.name,
              unifiedCreditCode: taxNo || org.unifiedCreditCode,
              roles: Array.from(new Set([...org.roles, role])) as OrganizationRole[],
            }
          : org,
      );
      return { ...matched, name: name || matched.name, unifiedCreditCode: taxNo || matched.unifiedCreditCode, roles: Array.from(new Set([...matched.roles, role])) as OrganizationRole[] };
    }
    const organization: Organization = {
      id: createId("org"),
      name,
      entityType: "企业",
      roles: [role],
      unifiedCreditCode: taxNo || undefined,
      status: "正常",
      createdAt: today(),
    };
    nextOrganizations = [organization, ...nextOrganizations];
    return organization;
  }
  const buyerRole: OrganizationRole = options.type === "销项" ? "客户" : "本方主体";
  const sellerRole: OrganizationRole = options.type === "销项" ? "本方主体" : "供应商";
  const defaultBuyer = options.type === "销项" ? params.customer : params.ownCompany;
  const defaultSeller = options.type === "销项"
    ? params.ownCompany
    : data.organizations.find((org) => org.id === (targetOrder && "supplierOrgId" in targetOrder ? targetOrder.supplierOrgId : ""));
  const buyerName = payload.buyer.name?.trim() || defaultBuyer?.name || "";
  const sellerName = payload.seller.name?.trim() || defaultSeller?.name || "";
  if (!buyerName || !sellerName) {
    window.alert("请完善买方、卖方后再添加发票。");
    return false;
  }
  const buyer = ensureOrganization(payload.buyer.id || defaultBuyer?.id || "", buyerName, payload.buyer.taxNo?.trim() || "", buyerRole);
  const seller = ensureOrganization(payload.seller.id || defaultSeller?.id || "", sellerName, payload.seller.taxNo?.trim() || "", sellerRole);
  const allocatedDraft = targetOrder
    ? applyInvoiceLineAllocations(
      { id: "draft", type: options.type, counterpartyOrgId: "", amount: invoiceAmount, status: "待确认", lineItems: draftLines },
      options.salesOrderId ? "sales" : "purchase",
      selectedIndexes.map((index) => ({ index, quantity: payload.lineQuantities?.[index] })),
      options.salesOrderId || options.purchaseOrderId || "",
    ).lineItems ?? draftLines
    : draftLines;
  const lineItems = allocatedDraft;
  const assignedSales = Boolean(options.salesOrderId && selectedIndexes.length > 0);
  const assignedPurchase = Boolean(options.purchaseOrderId && selectedIndexes.length > 0);
  const invoiceId = createId("inv");
  try {
    const savedFile = payload.file
      ? await uploadBusinessDocument(payload.file, "invoice", invoiceId)
      : undefined;
    const invoice: Invoice = {
      id: invoiceId,
      createdAt: new Date().toISOString(),
      projectId: project.id,
      projectIds: [project.id],
      salesOrderIds: assignedSales ? [options.salesOrderId!] : [],
      purchaseOrderIds: assignedPurchase ? [options.purchaseOrderId!] : [],
      type: options.type,
      counterpartyOrgId: options.type === "销项" ? buyer.id : seller.id,
      invoiceNo,
      invoiceDate: payload.invoiceDate,
      buyerOrgId: buyer.id,
      buyerName: buyer.name,
      buyerTaxNo: buyer.unifiedCreditCode,
      sellerOrgId: seller.id,
      sellerName: seller.name,
      sellerTaxNo: seller.unifiedCreditCode,
      amountWithoutTax: withoutTax,
      taxAmount: tax,
      amount: invoiceAmount,
      status: "待确认",
      date: payload.invoiceDate,
      lineItems,
      fileId: savedFile?.id,
      fileName: savedFile?.fileName,
    };
    const savedInvoice = reconcileInvoiceProjectIds(data, invoice);
    let nextInvoice = savedInvoice;
    if (project.type === "服务项目" && options.type === "销项" && !options.salesOrderId && !options.purchaseOrderId) {
      const serviceOrderId = pickDefaultServiceOrderIdForInvoiceLink(data, project.id);
      nextInvoice = applyServiceInvoiceAllocation(data, savedInvoice, {
        projectId: project.id,
        serviceOrderId,
        amount: invoiceAmount,
      });
    }
    const nextData = {
      ...data,
      organizations: nextOrganizations,
      invoices: [nextInvoice, ...data.invoices],
    };
    const withStatus = {
      ...nextData,
      projects: nextData.projects.map((item) => item.id === project.id && item.type === "服务项目"
        ? { ...item, invoiceStatus: deriveServiceProjectInvoiceStatus(nextData, project.id) }
        : item),
    };
    const synced = project.type === "商品项目" ? applyProductProjectSync(withStatus, project.id) : { data: withStatus };
    await commit(
      synced.data,
      { action: "新增发票", targetType: "发票", targetName: invoiceNo, operator: "当前用户", detail: options.logDetail },
    );
    return true;
  } catch (error) {
    window.alert(error instanceof Error ? error.message : "保存发票失败");
    return false;
  }
}

function canBackfillCollection(can: CanAccess, kind: "sales" | "service") {
  if (kind === "service") return can("project.edit") || can("onboarding.manage") || can("finance.manage");
  return can("project.edit") || can("finance.manage");
}

function canRegisterPurchasePayment(can: CanAccess) {
  return can("purchase.manage") || can("finance.manage");
}

async function registerPurchasePayment(params: {
  data: AppData;
  commit: (data: AppData, log?: Omit<OperationLog, "id" | "createdAt">) => Promise<void>;
  requestPayment: (request: PaymentDialogRequest) => Promise<PaymentFormResult | null>;
  order: PurchaseOrder;
  payable: number;
  targetStatus: OrderPaymentStatus;
  operator: string;
}) {
  const paid = purchaseOrderPaidAmount(params.order, params.data.transactions);
  const payment = await params.requestPayment({
    orderNo: params.order.orderNo,
    receivable: params.payable,
    received: paid,
    targetStatus: params.targetStatus,
    mode: "pay",
    defaultCollectionAccount: params.order.collectionAccount,
  });
  if (!payment) return false;
  const now = today();
  const applied = applyPurchasePaymentToData(params.data, params.order, payment, now, params.payable);
  const synced = applyProductProjectSync(applied.data, params.order.projectId);
  const project = synced.data.projects.find((item) => item.id === params.order.projectId);
  await params.commit(synced.data, {
    action: "采购订单付款",
    targetType: "项目",
    targetName: project?.name ?? params.order.orderNo,
    operator: params.operator,
    detail: `${paymentLogDetail({
      orderNo: params.order.orderNo,
      fromStatus: params.order.paymentStatus ?? DEFAULT_ORDER_PAYMENT_STATUS,
      toStatus: applied.paymentStatus,
      payment,
      receivedAmount: applied.paidAmount,
      kind: "pay",
    })}${synced.autoDetail ? `；${synced.autoDetail}` : ""}`,
  });
  return true;
}

async function patchPurchaseOrderRecord(params: {
  data: AppData;
  commit: (data: AppData, log?: Omit<OperationLog, "id" | "createdAt">) => Promise<void>;
  order: PurchaseOrder;
  patch: Partial<PurchaseOrder>;
  action?: string;
}) {
  const { data, commit, order, patch, action = "修改采购订单" } = params;
  const project = data.projects.find((item) => item.id === order.projectId);
  const now = today();
  const nextPurchaseOrders = data.purchaseOrders.map((item) => item.id === order.id ? { ...item, ...patch, updatedAt: now } : item);
  const synced = applyProductProjectSync({ ...data, purchaseOrders: nextPurchaseOrders }, order.projectId);
  const detailParts = Object.entries(patch).map(([key, value]) => `${key}=${value ?? ""}`);
  await commit(synced.data, {
    action,
    targetType: "项目",
    targetName: project?.name ?? order.orderNo,
    operator: "当前用户",
    detail: `${order.orderNo}：${detailParts.join("；")}${synced.autoDetail ? `；${synced.autoDetail}` : ""}`,
  });
}

async function deletePurchaseOrderRecord(params: {
  data: AppData;
  commit: (data: AppData, log?: Omit<OperationLog, "id" | "createdAt">) => Promise<void>;
  order: PurchaseOrder;
  action?: string;
}) {
  const { data, commit, order, action = "删除采购订单" } = params;
  if (order.status !== "待下单" && order.status !== "草稿") {
    window.alert("仅「待下单」或「草稿」状态的采购订单可以删除。");
    return false;
  }
  if (!window.confirm(`确定删除采购订单「${order.orderNo}」吗？`)) return false;
  const project = data.projects.find((item) => item.id === order.projectId);
  const nextPurchaseOrders = data.purchaseOrders.filter((item) => item.id !== order.id);
  const nextProjectItems = data.projectItems.filter((item) => item.purchaseOrderId !== order.id);
  const nextCost = nextPurchaseOrders
    .filter((item) => item.projectId === order.projectId)
    .reduce((sum, item) => sum + item.amount, 0);
  const nextProjects = data.projects.map((item) => item.id === order.projectId
    ? { ...item, totalCost: nextCost, updatedAt: today() }
    : item);
  let invoicesChanged = false;
  const nextInvoices = data.invoices.map((invoice) => {
    const linked = invoice.purchaseOrderIds ?? [];
    if (!linked.includes(order.id)) return invoice;
    invoicesChanged = true;
    return { ...invoice, purchaseOrderIds: linked.filter((id) => id !== order.id) };
  });
  const base = {
    ...data,
    projects: nextProjects,
    purchaseOrders: nextPurchaseOrders,
    projectItems: nextProjectItems,
    invoices: invoicesChanged ? nextInvoices : data.invoices,
  };
  const synced = applyProductProjectSync(base, order.projectId);
  await commit(synced.data, {
    action,
    targetType: "项目",
    targetName: project?.name ?? order.orderNo,
    operator: "当前用户",
    detail: `删除 ${order.orderNo}，并重算项目采购成本和毛利`,
  });
  return true;
}

async function backfillMissingCollectionTx(params: {
  data: AppData;
  commit: (data: AppData, log?: Omit<OperationLog, "id" | "createdAt">) => Promise<void>;
  requestPayment: (request: PaymentDialogRequest) => Promise<PaymentFormResult | null>;
  kind: "sales" | "service";
  order: SalesOrder | ServiceOrder;
  operator: string;
}) {
  const txTotal = collectionTxTotalForOrder(params.data.transactions, params.order.id, params.kind);
  const missing = missingCollectionAmount(params.order.receivedAmount, txTotal);
  if (missing <= 0) {
    window.alert("该订单实收与收款流水已一致，无需补录。");
    return false;
  }
  const voucher = resolveOrderCollectionVoucher(params.order, params.data.transactions, params.order.id, params.kind);
  const payment = await params.requestPayment({
    orderNo: params.order.orderNo,
    receivable: params.order.receivableAmount ?? params.order.amount,
    received: params.order.receivedAmount ?? 0,
    targetStatus: params.order.status,
    mode: "backfill",
    txTotal,
    missingAmount: missing,
    defaultCollectionAccount: params.order.collectionAccount,
    defaultOccurredAt: latestCollectionOccurredAt(params.data.transactions, params.order.id, params.kind, params.order.paidAt),
    existingVoucherFileId: voucher?.voucherFileId,
    existingVoucherName: voucher?.voucherName,
  });
  if (!payment) return false;
  const occurredAt = payment.occurredAt || today();
  const tx = params.kind === "service"
    ? buildServiceCollectionTransaction(params.order as ServiceOrder, occurredAt, payment)
    : buildSalesCollectionTransaction(params.order as SalesOrder, occurredAt, payment);
  await params.commit(
    { ...params.data, transactions: [tx, ...params.data.transactions] },
    {
      action: "补录收款流水",
      targetType: "流水",
      targetName: params.order.orderNo,
      operator: params.operator,
      detail: `订单 ${params.order.orderNo} 补录收款 ${money(payment.amount)}；实收保持 ${money(params.order.receivedAmount ?? 0)}，不改订单状态`,
    },
  );
  return true;
}

function usePagedItems<T>(items: T[], pageSize = 10, preserveOrder = false) {
  const [page, setPage] = useState(1);
  const totalPages = Math.max(1, Math.ceil(items.length / pageSize));
  useEffect(() => {
    setPage((current) => Math.min(Math.max(current, 1), totalPages));
  }, [totalPages]);
  const start = (page - 1) * pageSize;
  return {
    page,
    pageSize,
    total: items.length,
    totalPages,
    items: (preserveOrder ? items : sortByCreatedDesc(items)).slice(start, start + pageSize),
    setPage,
  };
}

function useDebouncedValue<T>(value: T, delayMs = 300): T {
  const [debounced, setDebounced] = useState(value);
  useEffect(() => {
    const timer = window.setTimeout(() => setDebounced(value), delayMs);
    return () => window.clearTimeout(timer);
  }, [value, delayMs]);
  return debounced;
}

/** 将 refreshKey 收成可放入 effect 依赖的稳定值，避免 `[collA, collB]` 每次 render 新数组导致死循环请求。 */
function stabilizeRefreshKey(key: unknown): unknown {
  if (key == null || typeof key !== "object") return key;
  if (!Array.isArray(key)) return key;
  // 包装多份集合：`[data.projects, data.purchaseOrders]` —— 外层数组每帧都新，按内容指纹比较。
  if (key.length > 0 && key.every((item) => Array.isArray(item))) {
    return key
      .map((arr) => {
        const list = arr as Array<{ id?: string }>;
        return `${list.length}:${list[0]?.id ?? ""}:${list[list.length - 1]?.id ?? ""}`;
      })
      .join("|");
  }
  // 单集合引用（如 `data.projects`）保持引用相等，commit 换数组时再刷新。
  return key;
}

function useServerPagedList<T>(options: {
  collection: string;
  search?: string;
  filters?: Record<string, string | number | boolean | undefined | null>;
  pageSize?: number;
  enabled?: boolean;
  refreshKey?: unknown;
}) {
  const pageSize = options.pageSize ?? 10;
  const enabled = options.enabled !== false;
  const [page, setPage] = useState(1);
  const [items, setItems] = useState<T[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [reloadTick, setReloadTick] = useState(0);
  const debouncedSearch = useDebouncedValue(options.search ?? "", 300);
  const filtersKey = JSON.stringify(options.filters ?? {});
  const refreshToken = stabilizeRefreshKey(options.refreshKey);

  useEffect(() => {
    setPage(1);
  }, [debouncedSearch, filtersKey, options.collection]);

  useEffect(() => {
    if (!enabled) return;
    let cancelled = false;
    setLoading(true);
    setError("");
    const filters = filtersKey === "{}" ? undefined : (JSON.parse(filtersKey) as Record<string, string | number | boolean | null>);
    void queryCollection<T>(options.collection, {
      page,
      pageSize,
      search: debouncedSearch,
      filters,
    })
      .then((result) => {
        if (cancelled) return;
        setItems(result.items);
        setTotal(result.total);
        const nextTotalPages = Math.max(1, Math.ceil(result.total / pageSize));
        if (page > nextTotalPages) setPage(nextTotalPages);
      })
      .catch((err) => {
        if (cancelled) return;
        if (err instanceof AuthExpiredError) return;
        setItems([]);
        setTotal(0);
        setError(err instanceof Error ? err.message : "列表加载失败");
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [enabled, options.collection, page, pageSize, debouncedSearch, filtersKey, refreshToken, reloadTick]);

  const totalPages = Math.max(1, Math.ceil(total / pageSize));
  return {
    page,
    setPage,
    pageSize,
    items,
    total,
    totalPages,
    loading,
    error,
    reload: () => setReloadTick((value) => value + 1),
  };
}

function userRoleNames(data: AppData, user: User) {
  return user.roleIds.map((id) => data.roles.find((role) => role.id === id)?.name).filter(Boolean).join("、") || "未分配角色";
}

function userPermissionSet(data: AppData, user: User) {
  return new Set(
    user.roleIds.flatMap((roleId) => data.roles.find((role) => role.id === roleId)?.permissions ?? []),
  );
}

function requiredPermissionForLog(log: Omit<OperationLog, "id" | "createdAt">): PermissionKey | null {
  if (log.targetType === "用户" || log.targetType === "权限") return "user.manage";
  if (log.targetType === "发票") return "invoice.manage";
  if (log.targetType === "流水") return log.action.includes("补录") ? null : "finance.manage";
  if (log.targetType === "商品") return "product.manage";
  if (log.targetType === "实体") return log.action.includes("新增") || log.action.includes("合并") || log.action.includes("删除") ? "entity.create" : "entity.view";
  if (log.targetType === "系统") {
    if (log.action.includes("跟进提醒") || log.action.includes("项目备忘")) return null;
    if (log.action.includes("官网留言")) return "lead.manage";
    if (log.action.includes("平台账号")) return "platformAccount.manage";
    if (log.action.includes("商标注册")) return "trademarkCertificate.manage";
    if (log.action.includes("日志")) return "user.manage";
    return "user.manage";
  }
  if (log.targetType === "项目") {
    if (log.action.includes("新建项目")) return "project.create";
    if (log.action.includes("订单列表") && log.action.includes("销售")) return "salesOrder.manage";
    if (log.action.includes("订单列表") && log.action.includes("服务")) return "serviceOrder.manage";
    if (log.action.includes("服务订单退款")) return "serviceOrder.manage";
    if (log.action.includes("订单列表") && log.action.includes("采购")) return "purchaseOrder.manage";
    if (log.action.includes("采购")) return "purchase.manage";
    if (log.action.includes("发票")) return "invoice.manage";
    return "project.edit";
  }
  return null;
}

function canAccessView(permissionSet: Set<PermissionKey>, view: View, navItems: ResolvedNavItem[] = []) {
  const item = navItems.find((nav) => nav.id === view) || (() => {
    const catalog = catalogEntryForView(view);
    return catalog
      ? { id: view, label: catalog.label, icon: resolveNavIcon(catalog.iconKey), permission: catalog.permission, categoryKey: "", groupKey: "", sortOrder: 0 }
      : null;
  })();
  return item ? hasPermission(permissionSet, item.permission) : false;
}

function projectViewFor(project?: Project): View {
  return project?.type === "服务项目" ? "serviceProjects" : "productProjects";
}

const SERVICE_CUSTOMER_KINDS: ServiceCustomerKind[] = ["首次服务", "续费客户"];
const QINGHUICAI_PLATFORM = "青慧采";

function isServiceCustomerKind(value: string): value is ServiceCustomerKind {
  return SERVICE_CUSTOMER_KINDS.includes(value as ServiceCustomerKind);
}

function serviceCustomerKindForPlatform(platform: string, current: "" | ServiceCustomerKind = ""): "" | ServiceCustomerKind {
  return platform === QINGHUICAI_PLATFORM ? "首次服务" : current;
}

function projectOptionLabel(project: Project) {
  return `${project.projectNo} · ${project.name}`;
}

function optionValues(data: AppData, key: string, fallback: string[]) {
  const group = data.optionGroups.find((item) => item.key === key);
  const values = group?.items
    .filter((item) => item.enabled)
    .sort((a, b) => a.sortOrder - b.sortOrder)
    .map((item) => item.value) ?? [];
  return values.length > 0 ? values : fallback;
}

function enabledCollectionAccounts(data: AppData) {
  return data.optionGroups.find((group) => group.key === "collection_account")?.items
    .filter((item) => item.enabled && item.accountNumber)
    .sort((a, b) => a.sortOrder - b.sortOrder) ?? [];
}

function collectionAccountOptionLabel(data: AppData, item: { ownCompanyOrgId?: string; bankName?: string; accountNumber?: string }) {
  const company = data.organizations.find((org) => org.id === item.ownCompanyOrgId)?.name;
  return `${company || "未设置主体"}｜${item.bankName || "未设置银行"}｜${item.accountNumber || "未设置账号"}`;
}

function findCollectionAccountItem(data: AppData, account?: string) {
  if (!account) return undefined;
  const items = data.optionGroups.find((group) => group.key === "collection_account")?.items ?? [];
  const byId = items.find((item) => item.id === account);
  if (byId) return byId;
  const byNumber = items.filter((item) => item.accountNumber && (account === item.accountNumber || account.includes(item.accountNumber)));
  if (byNumber.length <= 1) return byNumber[0];
  return byNumber.find((item) => {
    const company = data.organizations.find((org) => org.id === item.ownCompanyOrgId)?.name;
    return Boolean(company && account.includes(company));
  }) ?? byNumber[0];
}

function transactionProjectName(data: AppData, tx: Transaction) {
  const remark = tx.remark || "";
  const serviceOrderNo = remark.match(/SV-[A-Za-z0-9-]+/)?.[0];
  const salesOrderNo = remark.match(/SO-[A-Za-z0-9-]+/)?.[0];
  const projectId = tx.projectId
    || data.salesOrders.find((order) => order.id === tx.salesOrderId)?.projectId
    || data.serviceOrders.find((order) => order.id === tx.serviceOrderId)?.projectId
    || data.purchaseOrders.find((order) => order.id === tx.purchaseOrderId)?.projectId
    || data.serviceOrders.find((order) => order.orderNo === serviceOrderNo)?.projectId
    || data.salesOrders.find((order) => order.orderNo === salesOrderNo)?.projectId
    || "";
  return data.projects.find((item) => item.id === projectId)?.name || tx.projectName || "";
}

function transactionsForOrder(
  transactions: Transaction[],
  orderId: string,
  kind: "销售订单" | "采购订单" | "服务订单",
  orderNo?: string,
) {
  return sortByCreatedDesc(transactions.filter((tx) => {
    if (kind === "销售订单" && tx.salesOrderId === orderId) return true;
    if (kind === "服务订单" && tx.serviceOrderId === orderId) return true;
    if (kind === "采购订单" && tx.purchaseOrderId === orderId) return true;
    if (
      orderNo
      && !tx.salesOrderId
      && !tx.serviceOrderId
      && !tx.purchaseOrderId
      && (tx.remark || "").includes(orderNo)
    ) return true;
    return false;
  }));
}

function OrderTransactionList({ data, transactions }: { data: AppData; transactions: Transaction[] }) {
  const active = transactions.filter((tx) => (tx.status as string) !== "作废");
  const collectionTotal = active.filter((tx) => tx.type === "收款").reduce((sum, tx) => sum + (Number(tx.amount) || 0), 0);
  const paymentTotal = active.filter((tx) => tx.type === "付款" || tx.type === "垫付").reduce((sum, tx) => sum + (Number(tx.amount) || 0), 0);
  const refundTotal = active.filter((tx) => tx.type === "退款").reduce((sum, tx) => sum + (Number(tx.amount) || 0), 0);
  return (
    <div className="order-tx-list">
      <div className="order-tx-list-head">
        <h3>关联流水</h3>
        <p>
          {transactions.length} 笔
          {collectionTotal > 0 ? ` · 收款 ${money(collectionTotal)}` : ""}
          {paymentTotal > 0 ? ` · 付款 ${money(paymentTotal)}` : ""}
          {refundTotal > 0 ? ` · 退款 ${money(refundTotal)}` : ""}
        </p>
      </div>
      <div className="table">
        <div className="table-row order-tx-table head">
          <span>交易单号</span><span>类型</span><span>金额</span><span>账户</span><span>状态</span><span>交易时间</span><span>凭证</span>
        </div>
        {transactions.length === 0 ? (
          <div className="table-empty">该订单暂无流水</div>
        ) : transactions.map((tx) => (
          <div className="table-row order-tx-table" key={tx.id}>
            <span>
              <CopyableLine text={tx.transactionNo || tx.id} label="交易单号">
                {tx.transactionNo || tx.id}
              </CopyableLine>
            </span>
            <span>{tx.type}</span>
            <span>{money(tx.amount)}</span>
            <span className="collection-account-cell">{collectionAccountText(data, tx.account)}</span>
            <span>{tx.status}</span>
            <span>{formatDateTimeValue(tx.occurredAt || tx.date)}<em>创建 {formatDateTimeValue(tx.createdAt)}</em></span>
            <span>
              {tx.voucherFileId
                ? <button type="button" className="copy-link" onClick={() => openBusinessDocument(tx.voucherFileId)}>{tx.voucherName || "查看"}</button>
                : "无"}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}

function collectionAccountText(data: AppData, account?: string) {
  if (!account) return "未录入";
  const option = findCollectionAccountItem(data, account);
  if (!option) return account;
  const company = data.organizations.find((org) => org.id === option.ownCompanyOrgId)?.name;
  return [company || "未设置主体", option.bankName || "未设置银行", option.accountNumber || account].join("\n");
}

function CollectionAccountSelect({
  data,
  value,
  onChange,
  placeholder,
  ariaLabel,
}: {
  data: AppData;
  value: string;
  onChange: (value: string) => void;
  placeholder?: string;
  ariaLabel?: string;
}) {
  const options = enabledCollectionAccounts(data).map((item) => ({
    value: item.id,
    label: collectionAccountOptionLabel(data, item),
  }));
  return (
    <SearchableSelect
      value={value}
      options={options}
      onChange={onChange}
      placeholder={placeholder ?? "请选择收款账号"}
      ariaLabel={ariaLabel ?? "选择收款账号"}
    />
  );
}

type PaymentFormResult = {
  amount: number;
  paymentMethod: string;
  collectionAccount: string;
  payerAccount: string;
  occurredAt: string;
  transactionNo: string;
  voucherName?: string;
  voucherFileId?: string;
  remark?: string;
};

type PaymentDialogRequest = {
  orderNo: string;
  receivable: number;
  received: number;
  targetStatus: string;
  mode?: "collect" | "pay" | "backfill" | "refund";
  txTotal?: number;
  missingAmount?: number;
  defaultCollectionAccount?: string;
  defaultOccurredAt?: string;
  existingVoucherFileId?: string;
  existingVoucherName?: string;
};

function usePaymentDialog(data: AppData) {
  const resolverRef = useRef<((value: PaymentFormResult | null) => void) | null>(null);
  const [request, setRequest] = useState<PaymentDialogRequest | null>(null);
  const [draft, setDraft] = useState({
    amount: "",
    paymentMethod: "银行卡",
    collectionAccount: "",
    payerAccount: "",
    occurredAt: localDateTimeInputValue(),
    transactionNo: "",
    voucherName: "",
    voucherFileId: "",
    voucherFile: null as File | null,
    remark: "",
  });
  function close(result: PaymentFormResult | null) {
    resolverRef.current?.(result);
    resolverRef.current = null;
    setRequest(null);
  }

  function requestPayment(nextRequest: PaymentDialogRequest) {
    const remaining = Math.max(nextRequest.receivable - nextRequest.received, 0);
    const refundDefault = defaultServiceRefundAmount({
      amount: nextRequest.receivable,
      receivableAmount: nextRequest.receivable,
      receivedAmount: nextRequest.received,
    });
    const defaultAccount = findCollectionAccountItem(data, nextRequest.defaultCollectionAccount)?.id ?? "";
    setRequest(nextRequest);
    setDraft({
      amount: nextRequest.mode === "backfill"
        ? String(nextRequest.missingAmount ?? remaining)
        : nextRequest.mode === "refund"
          ? String(refundDefault)
          : nextRequest.mode === "pay" || nextRequest.targetStatus === "已付款" ? String(remaining || nextRequest.receivable) : "",
      paymentMethod: nextRequest.mode === "refund" ? "退款" : "银行卡",
      collectionAccount: defaultAccount,
      payerAccount: "",
      occurredAt: nextRequest.mode === "backfill"
        ? toDateTimeLocalInput(nextRequest.defaultOccurredAt)
        : localDateTimeInputValue(),
      transactionNo: "",
      voucherName: nextRequest.mode === "backfill" ? (nextRequest.existingVoucherName || "") : "",
      voucherFileId: nextRequest.mode === "backfill" ? (nextRequest.existingVoucherFileId || "") : "",
      voucherFile: null,
      remark: "",
    });
    return new Promise<PaymentFormResult | null>((resolve) => {
      resolverRef.current = resolve;
    });
  }

  async function submitPayment(event: FormEvent) {
    event.preventDefault();
    if (!request) return;
    const isRefund = request.mode === "refund";
    const amount = Number(draft.amount);
    if (!amount || amount <= 0) {
      window.alert(isRefund ? "退款金额必须大于 0。" : request.mode === "pay" ? "本次付款金额必须大于 0。" : "本次收款金额必须大于 0。");
      return;
    }
    if (isRefund) {
      const maxRefund = defaultServiceRefundAmount({
        amount: request.receivable,
        receivableAmount: request.receivable,
        receivedAmount: request.received,
      });
      if (amount - maxRefund > 0.01) {
        window.alert(request.received > 0 ? "退款金额不能大于已收金额。" : "退款金额不能大于订单金额。");
        return;
      }
    } else if (request.mode === "backfill") {
      const missing = request.missingAmount ?? 0;
      if (amount - missing > 0.01) {
        window.alert("补录金额不能大于待补差额。");
        return;
      }
    } else if (request.targetStatus === "已付款" && request.received + amount < request.receivable) {
      window.alert(request.mode === "pay" ? "选择已付款时，实付金额需要达到应付金额。" : "选择已付款时，实收金额需要达到应收金额。");
      return;
    }
    if (!draft.collectionAccount) {
      window.alert(isRefund ? "请选择打款账号。" : request.mode === "pay" ? "请选择付款银行。" : "请选择收款账号。");
      return;
    }
    let savedVoucher: { id: string; fileName: string } | undefined;
    if (draft.voucherFile) {
      try {
        savedVoucher = await uploadBusinessDocument(draft.voucherFile, "payment_voucher", request.orderNo);
      } catch (error) {
        window.alert(error instanceof Error ? error.message : (isRefund ? "打款凭证上传失败。" : request.mode === "pay" ? "付款凭证上传失败。" : "收款凭证上传失败。"));
        return;
      }
    }
    close({
      amount,
      paymentMethod: isRefund ? "退款" : request.mode === "pay" ? "付款" : "银行卡",
      collectionAccount: draft.collectionAccount,
      payerAccount: draft.payerAccount,
      occurredAt: fromDateTimeLocalValue(draft.occurredAt),
      transactionNo: draft.transactionNo,
      voucherName: savedVoucher?.fileName || draft.voucherName || undefined,
      voucherFileId: savedVoucher?.id || draft.voucherFileId || undefined,
      remark: draft.remark.trim() || undefined,
    });
  }

  const isRefund = request?.mode === "refund";
  const isBackfill = request?.mode === "backfill";
  const isPay = request?.mode === "pay";
  const paymentDialog = request ? (
    <div className="modal-backdrop is-nested-2" role="presentation">
      <form className="modal payment-modal" role="dialog" aria-modal="true" aria-label={isRefund ? "退款信息" : isBackfill ? "补录收款流水" : isPay ? "付款信息" : "收款信息"} onSubmit={submitPayment}>
        <div className="modal-head">
          <div>
            <h2>{isRefund ? "确认退款" : isBackfill ? "补录收款流水" : isPay ? "确认付款" : "确认收款"}</h2>
            <p>{isRefund ? `${request.orderNo} · 默认全额退款，可改金额；项目状态请手动调整` : isBackfill ? `${request.orderNo} · 只补流水，不改订单实收和状态` : request.orderNo}</p>
          </div>
          <button className="icon-button" type="button" onClick={() => close(null)} aria-label={isRefund ? "关闭退款信息" : isBackfill ? "关闭补录收款流水" : isPay ? "关闭付款信息" : "关闭收款信息"}><X size={18} /></button>
        </div>
        <div className="info-grid">
          {isRefund ? (
            <>
              <Info label="订单金额" value={money(request.receivable)} />
              <Info label="已收金额" value={money(request.received)} />
              <Info label="默认全退" value={money(defaultServiceRefundAmount({ amount: request.receivable, receivableAmount: request.receivable, receivedAmount: request.received }))} />
              <Info label="目标状态" value={request.targetStatus} />
            </>
          ) : isBackfill ? (
            <>
              <Info label="订单实收" value={money(request.received)} />
              <Info label="已有收款流水" value={money(request.txTotal ?? 0)} />
              <Info label="待补差额" value={money(request.missingAmount ?? 0)} />
              <Info label="订单状态" value={request.targetStatus} />
            </>
          ) : (
            <>
              <Info label={isPay ? "应付金额" : "应收金额"} value={money(request.receivable)} />
              <Info label={isPay ? "已付金额" : "已收金额"} value={money(request.received)} />
              <Info label="剩余金额" value={money(Math.max(request.receivable - request.received, 0))} />
              <Info label="目标状态" value={request.targetStatus} />
            </>
          )}
        </div>
        <div className="payment-form-grid">
          <label><span>{isRefund ? "退款金额" : isPay ? "付款金额" : "本次收款金额"}</span><input type="number" min="0" step="0.01" value={draft.amount} onChange={(event) => setDraft({ ...draft, amount: event.target.value })} /></label>
          <label><span>{isRefund ? "退款时间" : isPay ? "付款时间" : "收款时间"}</span>
            <DateTimeField mode="datetime" value={draft.occurredAt} onChange={(occurredAt) => setDraft({ ...draft, occurredAt })} ariaLabel={isRefund ? "退款时间" : isPay ? "付款时间" : "收款时间"} />
          </label>
          <label><span>交易单号</span><input value={draft.transactionNo} onChange={(event) => setDraft({ ...draft, transactionNo: event.target.value })} placeholder="选填" /></label>
          <label><span>{isRefund ? "打款账号" : isPay ? "付款银行" : "收款账号"}</span>
            <CollectionAccountSelect
              data={data}
              value={draft.collectionAccount}
              onChange={(collectionAccount) => setDraft({ ...draft, collectionAccount })}
              placeholder={isRefund ? "请选择打款账号" : isPay ? "请选择付款银行" : "请选择收款账号"}
              ariaLabel={isRefund ? "选择打款账号" : isPay ? "选择付款银行" : "选择收款账号"}
            />
          </label>
          {!isPay && (
            <label><span>{isRefund ? "对方收款账号" : "付款账号"}</span><input value={draft.payerAccount} onChange={(event) => setDraft({ ...draft, payerAccount: event.target.value })} placeholder={isRefund ? "客户收款账号（选填）" : "客户付款账号（选填）"} /></label>
          )}
          {(isRefund || isPay) && (
            <label className="payment-remark-field"><span>备注</span><textarea value={draft.remark} onChange={(event) => setDraft({ ...draft, remark: event.target.value })} placeholder={isPay ? "付款说明（选填）" : "退款原因或说明（选填）"} /></label>
          )}
          <div className="file-field payment-voucher-field">
            <span>{isRefund ? "打款凭证" : isPay ? "付款凭证" : "收款凭证"}{draft.voucherFileId && !draft.voucherFile ? "（已有，可不重新上传）" : "（选填）"}</span>
            {draft.voucherFileId && !draft.voucherFile && (
              <p className="payment-voucher-existing">
                将使用现有凭证：{draft.voucherName || "已保存"}
                <button type="button" className="copy-link" onClick={() => openBusinessDocument(draft.voucherFileId)}>查看</button>
              </p>
            )}
            {draft.voucherFile && <p className="payment-voucher-existing">本次将上传：{draft.voucherName}</p>}
            <FilePicker
              accept="image/*,.pdf"
              fileName={draft.voucherFile?.name}
              placeholder={isRefund ? "未选择打款凭证" : isPay ? "未选择付款凭证" : "未选择收款凭证"}
              buttonLabel="选择凭证"
              ariaLabel={isRefund ? "选择打款凭证" : isPay ? "选择付款凭证" : "选择收款凭证"}
              onFile={(file) => setDraft({
                ...draft,
                voucherName: file?.name || (request.existingVoucherName ?? ""),
                voucherFile: file ?? null,
                voucherFileId: file ? draft.voucherFileId : (request.existingVoucherFileId || draft.voucherFileId),
              })}
            />
          </div>
        </div>
        <div className="modal-actions">
          <button className="ghost" type="button" onClick={() => close(null)}>取消</button>
          <button className="primary" type="submit"><Banknote size={16} />{isRefund ? "确认退款" : isBackfill ? "补录流水" : isPay ? "确认付款" : "确认收款"}</button>
        </div>
      </form>
    </div>
  ) : null;

  return { requestPayment, paymentDialog };
}

function LoginScreen({ onLogin, notice }: { onLogin: (identifier: string, password: string) => Promise<void>; notice?: string }) {
  const [phone, setPhone] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState(notice ?? "");
  const [isSubmitting, setIsSubmitting] = useState(false);

  async function submitLogin(event?: FormEvent) {
    event?.preventDefault();
    if (isSubmitting) return;
    const identifier = phone.trim();
    if (!identifier || !password) {
      setError("请输入账号和密码。");
      return;
    }
    try {
      setIsSubmitting(true);
      setError("");
      await onLogin(identifier, password);
    } catch (error) {
      setError(error instanceof Error ? error.message : "登录失败，请稍后重试。");
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <div className="login-page">
      <form className="login-card" onSubmit={submitLogin}>
        <div className="brand login-brand">
          <div className="brand-mark">壹</div>
          <div>
            <strong>壹采 ERP</strong>
            <span>产品验证版</span>
          </div>
        </div>
        <div>
          <h1>登录系统</h1>
          <p>请输入账号和密码登录系统。</p>
        </div>
        <label>
          <span>手机号或姓名</span>
          <input value={phone} onChange={(event) => setPhone(event.target.value)} placeholder="请输入手机号或姓名" autoFocus autoComplete="username" />
        </label>
        <label>
          <span>密码</span>
          <input value={password} onChange={(event) => setPassword(event.target.value)} type="password" placeholder="请输入密码" autoComplete="current-password" />
        </label>
        {error && <div className="form-error">{error}</div>}
        <button className="primary" type="submit" disabled={isSubmitting}>{isSubmitting ? "登录中..." : "登录"}</button>
      </form>
    </div>
  );
}

export default function App() {
  const [data, setData] = useState<AppData | null>(null);
  const [loadError, setLoadError] = useState("");
  const [view, setViewState] = useState<View>(() => readStoredView());
  const [selectedProjectId, setSelectedProjectId] = useState<string | null>(null);
  const [orderFocus, setOrderFocus] = useState<OrderFocus>({});
  const [currentUserId, setCurrentUserId] = useState(() => window.localStorage.getItem(SESSION_USER_KEY) ?? "");
  const [openNavGroups, setOpenNavGroups] = useState<Record<string, boolean>>({});
  const [showHelp, setShowHelp] = useState(false);
  const [notice, setNotice] = useState<{ type: "success" | "error"; message: string } | null>(null);
  const [loginNotice, setLoginNotice] = useState("");
  const [smsDraftContacts, setSmsDraftContacts] = useState<LibraryContact[] | undefined>(undefined);

  function setView(next: View) {
    setViewState(next);
    persistActiveView(next);
  }

  useEffect(() => {
    persistActiveView(view);
  }, []);

  useEffect(() => {
    const onHashChange = () => {
      const next = window.location.hash.replace(/^#\/?/, "").trim();
      if (next && isCatalogView(next) && next !== view) {
        setViewState(next);
        try {
          window.sessionStorage.setItem(VIEW_STORAGE_KEY, next);
          window.localStorage.setItem(VIEW_STORAGE_KEY, next);
        } catch {
          // ignore
        }
      }
    };
    window.addEventListener("hashchange", onHashChange);
    return () => window.removeEventListener("hashchange", onHashChange);
  }, [view]);

  useEffect(() => {
    if (!notice) return;
    const timer = window.setTimeout(() => setNotice(null), notice.type === "success" ? 2600 : 5000);
    return () => window.clearTimeout(timer);
  }, [notice]);

  async function loadAppData() {
    setLoadError("");
    try {
      const next = await loadData();
      setData(next);
    } catch (error) {
      if (error instanceof AuthExpiredError) return;
      console.error(error);
      setLoadError(error instanceof Error ? error.message : "开发环境数据加载失败。");
    }
  }

  async function resetAppData() {
    if (!window.confirm("确定重置开发环境数据吗？当前浏览器中的测试数据会被初始化数据覆盖。")) return;
    setLoadError("");
    try {
      const next = await resetData();
      setData(next);
    } catch (error) {
      console.error(error);
      setLoadError(error instanceof Error ? error.message : "开发环境数据重置失败。");
    }
  }

  useEffect(() => {
    void loadAppData();
  }, []);

  useEffect(() => {
    const onExpired = () => {
      window.localStorage.removeItem(SESSION_USER_KEY);
      setCurrentUserId("");
      setLoginNotice("登录已过期，请重新登录。");
    };
    window.addEventListener(AUTH_EXPIRED_EVENT, onExpired);
    return () => window.removeEventListener(AUTH_EXPIRED_EVENT, onExpired);
  }, []);

  const userSnapshotReloadRef = useRef(false);

  useEffect(() => {
    if (!data || !currentUserId) return;
    let cancelled = false;
    void probeServerSession().then((probe) => {
      if (cancelled) return;
      // 仅在确认 401 未登录时清会话；5xx/网络抖动不得误踢登录态。
      if (probe.status === "authenticated" && probe.user.id === currentUserId) return;
      if (probe.status !== "unauthenticated") return;
      window.localStorage.removeItem(SESSION_USER_KEY);
      setCurrentUserId("");
      setLoginNotice("登录已过期，请重新登录。");
    });
    return () => { cancelled = true; };
  }, [currentUserId, data]);

  useEffect(() => {
    if (!data || !currentUserId) return;
    const validUser = data.users.find((user) => user.id === currentUserId && user.status === "启用");
    if (!validUser) {
      // 数据快照偶发缺用户时，先向服务端确认，避免保存发票后被误清本地登录态。
      let cancelled = false;
      void probeServerSession().then(async (probe) => {
        if (cancelled) return;
        if (probe.status === "unauthenticated") {
          window.localStorage.removeItem(SESSION_USER_KEY);
          setCurrentUserId("");
          setLoginNotice("登录已过期，请重新登录。");
          return;
        }
        if (probe.status === "authenticated" && !userSnapshotReloadRef.current) {
          userSnapshotReloadRef.current = true;
          try {
            const next = await loadData();
            if (!cancelled) setData(next);
          } catch {
            // 保持现有页面，由下次操作或手动刷新恢复。
          }
        }
      });
      return () => { cancelled = true; };
    }
    userSnapshotReloadRef.current = false;
    const permissionSet = userPermissionSet(data, validUser);
    const { items: resolvedNav } = resolveNavConfig(data);
    const accessibleNav = withCriticalNavItems(resolvedNav, (permission) => hasPermission(permissionSet, permission))
      .filter((item) => hasPermission(permissionSet, item.permission));
    if (!canAccessView(permissionSet, view, accessibleNav)) {
      const fallback = (accessibleNav[0]?.id ?? "dashboard") as View;
      setViewState(fallback);
      persistActiveView(fallback);
    }
  }, [currentUserId, data, view]);

  useEffect(() => {
    if (!data) return;
    const { items } = resolveNavConfig(data);
    const current = items.find((item) => item.id === view);
    if (!current?.groupKey) return;
    setOpenNavGroups((prev) => (prev[current.groupKey] ? prev : { ...prev, [current.groupKey]: true }));
  }, [view, data]);

  async function commit(next: AppData, log?: Omit<OperationLog, "id" | "createdAt">) {
    const previous = data!;
    try {
      let dataToSave = next;
      if (log) {
        const currentUser = next.users.find((user) => user.id === currentUserId);
        const permissionSet = currentUser ? userPermissionSet(next, currentUser) : new Set<PermissionKey>();
        const requiredPermission = requiredPermissionForLog(log);
        if (requiredPermission && !hasPermission(permissionSet, requiredPermission)) {
          throw new Error(`没有权限：${permissionLabels[requiredPermission]}`);
        }
        const normalizedLog = { ...log, operator: log.operator === "当前用户" ? currentUser?.name ?? "未登录用户" : log.operator };
        dataToSave = {
          ...next,
          operationLogs: [{ id: createId("log"), createdAt: today(), ...normalizedLog }, ...next.operationLogs],
        };
      }
      const { upserts, deleteIds } = diffPartialAppData(previous, dataToSave);
      setData(dataToSave);
      const savedData = (Object.keys(upserts).length || Object.keys(deleteIds).length)
        ? await saveData(upserts, true, deleteIds)
        : null;
      if (savedData) {
        // 防止服务端快照偶发缺当前用户时，把本地会话用户踢回登录页。
        const savedKeepsUser = !currentUserId || savedData.users.some((user) => user.id === currentUserId && user.status === "启用");
        setData(savedKeepsUser ? savedData : { ...savedData, users: dataToSave.users, roles: dataToSave.roles });
      }
      setNotice({ type: "success", message: log ? `${log.action}成功` : "保存成功" });
    } catch (error) {
      setData(previous);
      console.error(error);
      const message = error instanceof Error ? error.message : "保存失败，请稍后重试";
      if (error instanceof AuthExpiredError || message.includes("登录已过期")) {
        return;
      } else {
        setNotice({ type: "error", message });
      }
      throw error;
    }
  }

  async function login(identifier: string, password: string) {
    const serverUser = await loginOnServer(identifier, password);
    const next = await loadData();
    setData(next);
    window.localStorage.setItem(SESSION_USER_KEY, serverUser.id);
    setLoginNotice("");
    setCurrentUserId(serverUser.id);
  }

  function logout() {
    void logoutOnServer();
    window.localStorage.removeItem(SESSION_USER_KEY);
    setCurrentUserId("");
    setSelectedProjectId(null);
    setView("dashboard");
  }

  if (!currentUserId) {
    return <LoginScreen onLogin={login} notice={loginNotice} />;
  }

  if (!data && loadError) {
    return (
      <div className="loading">
        <div className="loading-card">
          <AlertTriangle size={28} />
          <h1>系统数据加载失败</h1>
          <p>{import.meta.env.DEV ? loadError : "服务暂时不可用，请稍后重试。"}</p>
          <div className="loading-actions">
            <button className="ghost" type="button" onClick={() => void loadAppData()}>
              <RefreshCw size={16} />重试加载
            </button>
            {import.meta.env.DEV && <button className="primary" type="button" onClick={() => void resetAppData()}>
              重置本地数据
            </button>}
          </div>
        </div>
      </div>
    );
  }

  if (!data) {
    return <div className="loading">正在加载开发环境数据...</div>;
  }

  const currentUser = data.users.find((user) => user.id === currentUserId && user.status === "启用");
  if (!currentUser) {
    return <LoginScreen onLogin={login} notice={loginNotice} />;
  }

  const permissions = userPermissionSet(data, currentUser);
  const can = (permission: PermissionKey) => hasPermission(permissions, permission);
  const { categories: navCategories, groups: navGroups, items: resolvedNavItems } = resolveNavConfig(data);
  const visibleNavItems = withCriticalNavItems(resolvedNavItems, can).filter((item) => can(item.permission));
  const selectedProject = data.projects.find((project) => project.id === selectedProjectId);
  const navCategorySections = navCategories
    .map((category) => {
      const topItems = visibleNavItems.filter((item) => !item.groupKey && item.categoryKey === category.key);
      const groups = navGroups
        .filter((group) => (group.categoryKey || "") === category.key)
        .map((group) => ({
          group,
          items: visibleNavItems.filter((item) => item.groupKey === group.key),
        }))
        .filter((section) => section.items.length > 0);
      return { category, topItems, groups };
    })
    .filter((section) => section.topItems.length > 0 || section.groups.length > 0);
  const knownCategoryKeys = new Set(navCategories.map((category) => category.key));
  const orphanTopItems = visibleNavItems.filter((item) => !item.groupKey && !knownCategoryKeys.has(item.categoryKey));
  const orphanGroupedItems = visibleNavItems.filter(
    (item) => item.groupKey && !navGroups.some((group) => group.key === item.groupKey),
  );
  const openProject = (id: string) => {
    const project = data.projects.find((item) => item.id === id);
    setSelectedProjectId(id);
    setView(projectViewFor(project));
  };

  if (!canAccessView(permissions, view, visibleNavItems)) {
    if (visibleNavItems.length === 0) {
      return (
        <div className="loading">
          <div className="loading-card">
            <AlertTriangle size={28} />
            <h1>当前账号无可用页面权限</h1>
            <p>请确认已分配角色，且角色权限数据已写入 roles 表后重新登录。</p>
            <div className="loading-actions">
              <button className="primary" type="button" onClick={() => void logout()}>重新登录</button>
            </div>
          </div>
        </div>
      );
    }
    return <div className="loading">正在校验页面权限...</div>;
  }

  return (
    <div className="shell">
      {notice && <div className={`app-toast ${notice.type}`} role="status" aria-live="polite">{notice.message}</div>}
      <aside className="sidebar">
        <div className="brand">
          <div className="brand-mark">壹</div>
          <div>
            <strong>壹采 ERP</strong>
            <span>产品验证版</span>
          </div>
        </div>
        <nav>
          {navCategorySections.map(({ category, topItems, groups }, categoryIndex) => (
            <div className="nav-category" key={category.id || category.key}>
              {categoryIndex > 0 && <div className="nav-category-divider" aria-hidden="true" />}
              {topItems.map((item) => {
                const Icon = item.icon;
                return (
                  <button key={item.id} className={view === item.id ? "active" : ""} onClick={() => setView(item.id)}>
                    <Icon size={18} />
                    {item.label}
                  </button>
                );
              })}
              {groups.map(({ group, items }) => {
                const GroupIcon = resolveNavIcon(group.iconKey);
                const groupActive = items.some((item) => item.id === view);
                const isOpen = openNavGroups[group.key] === true;
                return (
                  <div className="nav-group" key={group.id || group.key}>
                    <button
                      className={`nav-group-toggle ${groupActive ? "active" : ""}`}
                      onClick={() => setOpenNavGroups((prev) => ({ ...prev, [group.key]: !isOpen }))}
                      aria-expanded={isOpen}
                    >
                      <GroupIcon size={18} />
                      <span>{group.label}</span>
                      <ChevronDown size={15} className={isOpen ? "open" : ""} />
                    </button>
                    {isOpen && items.map((item) => {
                      const Icon = item.icon;
                      return (
                        <button
                          key={item.id}
                          className={`nav-subitem ${view === item.id ? "active" : ""}`}
                          onClick={() => {
                            if (item.id === "productProjects" || item.id === "serviceProjects" || item.id === "serviceOrders" || item.id === "salesOrders" || item.id === "purchaseOrders") {
                              setSelectedProjectId(null);
                              setOrderFocus({});
                            }
                            setView(item.id);
                          }}
                        >
                          <Icon size={16} />
                          {item.label}
                        </button>
                      );
                    })}
                  </div>
                );
              })}
            </div>
          ))}
          {[...orphanTopItems, ...orphanGroupedItems].map((item) => {
            const Icon = item.icon;
            return (
              <button key={item.id} className={view === item.id ? "active" : ""} onClick={() => setView(item.id)}>
                <Icon size={18} />
                {item.label}
              </button>
            );
          })}
        </nav>
        <div className="sidebar-note">
        </div>
      </aside>

      <main className="main">
        <header className="topbar">
          <div>
            <h1>{visibleNavItems.find((item) => item.id === view)?.label}</h1>
          </div>
          <div className="current-user">
            <div>
              <strong>{currentUser.name}</strong>
              <span>{userRoleNames(data, currentUser)}</span>
            </div>
            <button className="ghost" onClick={() => setShowHelp(true)}><CircleHelp size={16} />帮助</button>
            <button className="ghost" onClick={logout}><LogOut size={16} />退出</button>
          </div>
        </header>

        {view === "dashboard" && <Dashboard data={data} commit={commit} currentUser={currentUser} />}
        {view === "productProjects" && <Projects data={data} commit={commit} currentUser={currentUser} can={can} projectType="商品项目" selectedProject={selectedProject} onSelectProject={setSelectedProjectId} />}
        {view === "serviceProjects" && <Projects data={data} commit={commit} currentUser={currentUser} can={can} projectType="服务项目" selectedProject={selectedProject} onSelectProject={setSelectedProjectId} />}
        {view === "serviceOrders" && <Orders data={data} commit={commit} can={can} onOpenProject={openProject} tab="服务订单" focus={orderFocus} onClearFocus={() => setOrderFocus({})} />}
        {view === "salesOrders" && <Orders data={data} commit={commit} can={can} onOpenProject={openProject} tab="销售订单" focus={orderFocus} onClearFocus={() => setOrderFocus({})} />}
        {view === "purchaseOrders" && <Orders data={data} commit={commit} can={can} onOpenProject={openProject} tab="采购订单" focus={orderFocus} onClearFocus={() => setOrderFocus({})} />}
        {view === "contracts" && <Contracts data={data} commit={commit} can={can} />}
        {view === "entities" && <Entities data={data} commit={commit} applyData={(next) => setData(next)} onNotice={setNotice} can={can} operatorName={currentUser.name} />}
        {view === "products" && <Products data={data} commit={commit} can={can} />}
        {view === "platformAccounts" && <PlatformAccounts data={data} applyData={(next) => setData(next)} onNotice={setNotice} can={can} operatorName={currentUser.name} />}
        {view === "websiteLeads" && <WebsiteLeads data={data} applyData={(next) => setData(next)} onNotice={setNotice} currentUser={currentUser} />}
        {view === "notices" && <Notices onNotice={setNotice} />}
        {view === "noticeStats" && <NoticeStats onNotice={setNotice} />}
        {view === "noticeTags" && <NoticeTags onNotice={setNotice} canManage={can("notice.tag.manage")} />}
        {view === "noticeDict" && (
          <NoticeDictAdmin
            onNotice={setNotice}
            canManageOrgType={can("notice.orgType.manage")}
            canManageNature={can("notice.nature.manage")}
          />
        )}
        {view === "customerAccounts" && <CustomerAccountsPanel onNotice={setNotice} can={can} />}
        {view === "libraryContacts" && (
          <LibraryContactsPanel
            data={data}
            applyData={(next) => setData(next)}
            onNotice={setNotice}
            can={can}
            currentUser={currentUser}
            onSendSms={(contacts) => {
              setSmsDraftContacts(contacts);
              setView("sms");
            }}
          />
        )}
        {view === "sms" && (
          <SmsPanel
            data={data}
            applyData={(next) => setData(next)}
            onNotice={setNotice}
            can={can}
            currentUser={currentUser}
            draftContacts={smsDraftContacts}
            onDraftConsumed={() => setSmsDraftContacts(undefined)}
          />
        )}
        {view === "officialSites" && <OfficialSitesPanel data={data} applyData={(next) => setData(next)} onNotice={setNotice} can={can} />}
        {view === "officialSeo" && <OfficialSeoPanel data={data} applyData={(next) => setData(next)} onNotice={setNotice} can={can} />}
        {view === "reminders" && <Reminders data={data} commit={commit} currentUser={currentUser} />}
        {view === "invoices" && <Invoices data={data} commit={commit} can={can} />}
        {view === "transactions" && <Transactions data={data} commit={commit} applyData={(next) => setData(next)} onNotice={setNotice} can={can} operatorName={currentUser.name} onOpenProject={openProject} />}
        {view === "financeStatements" && <FinanceStatements data={data} onNotice={setNotice} />}
        {view === "receiptStats" && <CashflowStats data={data} kind="receipt" />}
        {view === "paymentStats" && <CashflowStats data={data} kind="payment" />}
        {view === "trademarkCertificates" && <TrademarkCertificates data={data} applyData={(next) => setData(next)} onNotice={setNotice} can={can} operatorName={currentUser.name} />}
        {view === "logs" && <OperationLogs data={data} commit={commit} can={can} />}
        {view === "collectionAccounts" && <OptionSettings data={data} commit={commit} mode="accounts" />}
        {view === "optionSettings" && <OptionSettings data={data} commit={commit} mode="options" />}
        {view === "devOps" && <DevOps onNotice={setNotice} canManage={can("dev.ops.manage")} />}
        {view === "menuSettings" && (
          <MenuSettingsPanel
            data={data}
            applyData={(next) => setData(next)}
            onNotice={setNotice}
            can={can}
          />
        )}
        {view === "access" && <AccessControl data={data} commit={commit} />}
        {showHelp && <HelpModal onClose={() => setShowHelp(false)} />}
      </main>
    </div>
  );
}

function HelpModal({ onClose }: { onClose: () => void }) {
  return (
    <div className="modal-backdrop" role="presentation">
      <div className="modal help-modal" role="dialog" aria-modal="true" aria-label="帮助教程">
        <div className="modal-head">
          <div>
            <h2>帮助教程</h2>
          </div>
          <button className="icon-button" onClick={onClose} aria-label="关闭帮助"><X size={18} /></button>
        </div>
        <div className="help-grid">
          <article>
            <h3>服务项目</h3>
            <ol>
              <li>新建服务项目，选择客户、首次或续费、服务、周期和业务员。</li>
              <li>客户不存在时上传营业执照，系统识别后自动匹配或新增客户。</li>
              <li>保存后自动生成服务订单。</li>
              <li>在项目详情维护平台账号、每日任务、发票和流水。</li>
              <li>项目状态、服务订单和交易流水分别维护，互不自动修改。</li>
              <li>服务订单改为「退款」会弹出退款金额（默认全退，可改金额、备注、时间），并生成退款流水和打款凭证；项目状态请手动调整。</li>
            </ol>
          </article>
          <article>
            <h3>商品项目</h3>
            <ol>
              <li>新建商品项目后状态为「初始化」；项目名称含客户、使用单位、平台、备注和日期。</li>
              <li>在项目详情用弹窗添加销售订单，创建时可自定义下单时间；添加商品时必须关联渠道采购订单。</li>
              <li>进行中维护物流、验收、安装进度；验收/安装可填写备注。</li>
              <li>销售订单在关联采购已发货或已签收后，不可再移除、追加或修改数量。</li>
              <li>销售订单和采购订单始终可在项目详情中分别管理，互不影响。</li>
              <li>独立列表从侧栏「订单」进入：服务订单、销售订单、采购订单分开管理。</li>
              <li>采购订单货款改为「部分付款/已付款」时，需选择付款银行、金额、时间和凭证，并生成付款流水。</li>
              <li>销售/采购订单与物流/交付/验收全部完成后可手动标记「已完成」，系统不会自动完成；已完成后不可再增销售/采购明细。</li>
            </ol>
          </article>
          <article>
            <h3>发票和流水</h3>
            <ol>
              <li>发票可从发票管理、项目详情或订单操作中添加。</li>
              <li>上传 PDF 发票可自动识别并填充表单。</li>
              <li>发票号不能重复。</li>
              <li>一张发票可关联多个订单；关联时不再校验发票金额是否超过单笔订单金额。</li>
              <li>采购付款从收款账户中选择付款银行，保存后生成类型为「付款」的流水。</li>
            </ol>
          </article>
          <article>
            <h3>状态规则</h3>
            <ol>
              <li>状态下拉只显示当前状态和合法下一状态。</li>
              <li>终态不可逆，不能继续编辑。</li>
              <li>服务项目冒烟测试阶段允许在配置状态间自由切换。</li>
              <li>非法状态变更会被系统拦截。</li>
            </ol>
          </article>
        </div>
    </div>
    </div>
  );
}

function Dashboard({ data, commit, currentUser }: { data: AppData; commit: (data: AppData, log?: Omit<OperationLog, "id" | "createdAt">) => Promise<void>; currentUser: User }) {
  const metrics = useMemo(() => {
    return calculateDashboardMetrics(data);
  }, [data]);
  const productDashboardStatuses = Array.from(new Set([
    ...optionValues(data, "project_status", statusColumns),
    ...data.projects.filter((project) => project.type === "商品项目").map((project) => project.status),
  ] as ProjectStatus[]));
  const serviceDashboardStatuses = Array.from(new Set([
    ...optionValues(data, "service_project_status", ["入驻中", "服务中", "服务交付完成", "服务到期结束", "项目终止"]),
    ...data.projects.filter((project) => project.type === "服务项目").map((project) => project.status),
  ] as ProjectStatus[]));
  const serviceProjects = data.projects.filter((project) => project.type === "服务项目");
  const servicePlatformStatuses = Array.from(new Set([
    ...optionValues(data, "service_project_status", ["入驻中", "服务中", "服务交付完成", "服务到期结束", "项目终止"]),
    ...serviceProjects.map((project) => project.status),
  ] as ProjectStatus[]));
  const servicePlatforms = Array.from(new Set(
    serviceProjects.map((project) => project.sourcePlatform || "未设置平台"),
  )).sort((a, b) => a.localeCompare(b, "zh-CN"));
  const ongoingReminders = sortByCreatedDesc(data.projectReminders.filter((reminder) => reminder.status === "进行中")).slice(0, 8);

  return (
    <section className="stack">
      <div className="metric-grid">
        <Metric label="进行中项目" value={metrics.active.toString()} icon={ClipboardList} />
        <Metric label="终止项目" value={metrics.exception.toString()} icon={AlertTriangle} tone="warn" />
        <Metric label="项目金额" value={money(metrics.projectAmount)} icon={Banknote} />
        <Metric label="待开票金额" value={money(metrics.pendingInvoice)} icon={FileText} />
        <Metric label="入驻待办" value={metrics.onboarding.toString()} icon={ShieldCheck} />
        <Metric label="进行中提醒" value={metrics.reminders.toString()} icon={ClipboardList} />
      </div>

      <div className="panel">
          <PanelTitle title="创建每日任务" subtitle="选择项目和需要平台配合的工作内容，任务默认进入进行中。" />
          <ReminderForm data={data} commit={commit} currentUser={currentUser} />
        </div>
      <div className="panel">
          <PanelTitle title="进行中提醒" subtitle="所有仍需平台配合的提醒，任何同事都可以处理。" />
          <ReminderList data={data} commit={commit} reminders={ongoingReminders} />
        </div>
      <div className="two-col">
        <div className="panel">
          <PanelTitle title="项目数量与金额统计" subtitle="按项目类型和当前状态汇总项目数量及项目金额。" />
          <div className="project-count-summary">
            {(["商品项目", "服务项目"] as const).map((type) => {
              const typeProjects = data.projects.filter((project) => project.type === type);
              const typeStatuses = type === "商品项目" ? productDashboardStatuses : serviceDashboardStatuses;
              return (
                <div className="project-count-group" key={type}>
                  <div className="project-count-type">
                    <strong>{type}</strong>
                    <div className="project-count-total">
                      <span>{typeProjects.length} 个</span>
                      <b>{money(typeProjects.reduce((sum, project) => sum + (Number(project.totalAmount) || 0), 0))}</b>
                    </div>
                  </div>
                  <div className="project-count-statuses">
                    {typeStatuses.map((status) => {
                      const statusProjects = typeProjects.filter((project) => project.status === status);
                      return (
                        <div className="project-count-item" key={status}>
                          <span>{status}</span>
                          <div className="project-count-values">
                            <strong>{statusProjects.length} 个</strong>
                            <em>{money(statusProjects.reduce((sum, project) => sum + (Number(project.totalAmount) || 0), 0))}</em>
                          </div>
                        </div>
                      );
                    })}
                  </div>
                </div>
              );
            })}
          </div>
        </div>
        <div className="panel">
          <PanelTitle title="今日待办" subtitle="产品验证版按规则自动生成示例待办。" />
          <TodoList data={data} />
        </div>
      </div>
      <div className="panel">
        <PanelTitle title="服务项目平台统计" subtitle="按所属平台拆分各服务状态的项目数量，并汇总项目金额。" />
        <div className="project-count-summary platform-status-summary">
          {servicePlatforms.map((platform) => {
            const projects = serviceProjects.filter((project) => (project.sourcePlatform || "未设置平台") === platform);
            return (
              <div className="project-count-group" key={platform}>
                <div className="project-count-type">
                  <strong>{platform}</strong>
                  <div className="project-count-total">
                    <span>{projects.length} 个</span>
                    <b>{money(projects.reduce((sum, project) => sum + (Number(project.totalAmount) || 0), 0))}</b>
                  </div>
                </div>
                <div className="project-count-statuses">
                  {servicePlatformStatuses.map((status) => {
                    const count = projects.filter((project) => project.status === status).length;
                    return (
                      <div className="project-count-item" key={`${platform}-${status}`}>
                        <span>{status}</span>
                        <strong>{count} 个</strong>
                      </div>
                    );
                  })}
                </div>
              </div>
            );
          })}
          {servicePlatforms.length === 0 && <div className="empty-state">暂无服务项目统计数据</div>}
        </div>
      </div>
    </section>
  );
}

function Metric({ label, value, icon: Icon, tone }: { label: string; value: string; icon: typeof Home; tone?: "warn" }) {
  return (
    <div className={`metric ${tone ?? ""}`}>
      <Icon size={20} />
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  );
}

function percentLabel(share: number) {
  return `${(share * 100).toFixed(1)}%`;
}

function CashflowStats({ data, kind }: { data: AppData; kind: "receipt" | "payment" }) {
  const [period, setPeriod] = useState<PeriodPreset>("this_month");
  const [customStart, setCustomStart] = useState(() => formatLocalDate(new Date(new Date().getFullYear(), new Date().getMonth(), 1)));
  const [customEnd, setCustomEnd] = useState(() => formatLocalDate(new Date()));
  const [receiptScope, setReceiptScope] = useState<ReceiptScope>("product");
  const [receiptTab, setReceiptTab] = useState<ReceiptDimension>("customer");
  const [paymentTab, setPaymentTab] = useState<PaymentDimension>("company");
  const [display, setDisplay] = useState<"table" | "chart">("table");
  const range = useMemo(() => periodRange(period, new Date(), { start: customStart, end: customEnd }), [period, customStart, customEnd]);
  const receiptStats = useMemo(
    () => (kind === "receipt" ? buildReceiptStats(data, range, receiptScope) : null),
    [kind, data, range, receiptScope],
  );
  const paymentStats = useMemo(() => (kind === "payment" ? buildPaymentStats(data, range) : null), [kind, data, range]);
  const dimension = kind === "receipt"
    ? receiptStats?.[
      receiptTab === "customer"
        ? "byCustomer"
        : receiptTab === "company"
          ? "byCompany"
          : receiptTab === "salesperson"
            ? "bySalesperson"
            : "byBank"
    ]
    : paymentStats?.[
      paymentTab === "company"
        ? "byCompany"
        : paymentTab === "channel"
          ? "byChannel"
          : paymentTab === "project"
            ? "byProject"
            : paymentTab === "product"
              ? "byProduct"
              : "byBank"
    ];
  const rows = dimension?.rows ?? [];
  const chart = chartRows(rows);
  const totalAmount = dimension?.totalAmount ?? 0;
  const totalCount = dimension?.totalCount ?? 0;
  const totalRefund = dimension?.refundAmount ?? 0;
  const receiptTabs: Array<{ id: ReceiptDimension; label: string }> = [
    { id: "customer", label: "客户" },
    { id: "company", label: "主体" },
    { id: "salesperson", label: "业务员" },
    { id: "bank", label: "银行账号" },
  ];
  const paymentTabs: Array<{ id: PaymentDimension; label: string }> = [
    { id: "company", label: "主体" },
    { id: "channel", label: "渠道" },
    { id: "project", label: "项目" },
    { id: "product", label: "商品" },
    { id: "bank", label: "银行账号" },
  ];
  const nameLabel = kind === "receipt"
    ? (receiptTab === "customer" ? "客户" : receiptTab === "company" ? "主体" : receiptTab === "salesperson" ? "业务员" : "银行账号")
    : (paymentTab === "company" ? "主体" : paymentTab === "channel" ? "渠道" : paymentTab === "project" ? "项目" : paymentTab === "product" ? "商品" : "银行账号");

  const receiptScopeTabs: Array<{ id: ReceiptScope; label: string }> = [
    { id: "product", label: "商品" },
    { id: "service", label: "服务" },
  ];

  return (
    <div className="stack">
      {kind === "receipt" && (
        <div className="segmented cashflow-scope-tabs" role="tablist" aria-label="收款业务类型">
          {receiptScopeTabs.map((item) => (
            <button
              key={item.id}
              type="button"
              role="tab"
              aria-selected={receiptScope === item.id}
              className={receiptScope === item.id ? "active" : ""}
              onClick={() => setReceiptScope(item.id)}
            >
              {item.label}
            </button>
          ))}
        </div>
      )}
      <div className="metric-grid compact-metrics">
        {kind === "receipt" && receiptStats && (
          <>
            <Metric label="收款合计" value={money(receiptStats.totals.netAmount)} icon={Banknote} />
            <Metric label="收款笔数" value={String(receiptStats.totals.receiptCount)} icon={ClipboardList} />
            <Metric label="同期退款" value={money(receiptStats.totals.refundAmount)} icon={WalletCards} />
          </>
        )}
        {kind === "payment" && paymentStats && (
          <>
            <Metric label="付款合计" value={money(paymentStats.totals.paymentAmount)} icon={Banknote} />
            <Metric label="付款笔数" value={String(paymentStats.totals.paymentCount)} icon={ClipboardList} />
            <Metric label="垫付（未计入合计）" value={money(paymentStats.totals.advanceAmount)} icon={WalletCards} />
          </>
        )}
      </div>
      <div className="panel">
        <div className="panel-title action-title cashflow-stats-title">
          <div>
            <h2>{kind === "receipt" ? (receiptScope === "product" ? "商品收款统计" : "服务收款统计") : "付款统计"}</h2>
            <p>
              {formatPeriodRange(range)} · 按流水交易时间汇总
              {kind === "receipt"
                ? `，仅统计${receiptScope === "product" ? "商品项目" : "服务项目"}收款，退款已从合计扣除`
                : "，垫付单独展示"}
              。
            </p>
          </div>
          <div className="panel-title-buttons">
            <div className="segmented cashflow-display-toggle">
              <button type="button" className={display === "table" ? "active" : ""} onClick={() => setDisplay("table")}>
                <Table2 size={14} />表格
              </button>
              <button type="button" className={display === "chart" ? "active" : ""} onClick={() => setDisplay("chart")}>
                <BarChart3 size={14} />图表
              </button>
            </div>
          </div>
        </div>
        <div className="segmented cashflow-period-row">
          {PERIOD_PRESETS.map((item) => (
            <button
              key={item.id}
              type="button"
              className={period === item.id ? "active" : ""}
              onClick={() => setPeriod(item.id)}
            >
              {item.label}
            </button>
          ))}
          {period === "custom" && (
            <div className="cashflow-custom-range">
              <DateTimeField mode="date" value={customStart} onChange={setCustomStart} ariaLabel="开始日期" />
              <span>至</span>
              <DateTimeField mode="date" value={customEnd} onChange={setCustomEnd} ariaLabel="结束日期" />
            </div>
          )}
        </div>
        <div className="segmented">
          {kind === "receipt"
            ? receiptTabs.map((item) => (
              <button key={item.id} type="button" className={receiptTab === item.id ? "active" : ""} onClick={() => setReceiptTab(item.id)}>
                {item.label}
              </button>
            ))
            : paymentTabs.map((item) => (
              <button key={item.id} type="button" className={paymentTab === item.id ? "active" : ""} onClick={() => setPaymentTab(item.id)}>
                {item.label}
              </button>
            ))}
        </div>
        {rows.length === 0 ? (
          <div className="table-empty">该周期没有符合条件的流水，可切换时间范围。</div>
        ) : display === "table" ? (
          <div className="table">
            <div className={`table-row cashflow-stats-table head${kind === "receipt" ? " with-refund" : ""}`}>
              <span>{nameLabel}</span>
              <span>金额</span>
              <span>笔数</span>
              <span>占比</span>
              {kind === "receipt" && <span>退款</span>}
            </div>
            {rows.map((row) => (
              <div className={`table-row cashflow-stats-table${kind === "receipt" ? " with-refund" : ""}`} key={row.id}>
                <span>
                  <CopyableLine text={row.name} label={nameLabel}>{row.name}</CopyableLine>
                </span>
                <span>{money(row.amount)}</span>
                <span>{row.count}</span>
                <span>{percentLabel(row.share)}</span>
                {kind === "receipt" && <span>{money(row.refundAmount ?? 0)}</span>}
              </div>
            ))}
            <div className={`table-row cashflow-stats-table total${kind === "receipt" ? " with-refund" : ""}`}>
              <span>合计</span>
              <span>{money(totalAmount)}</span>
              <span>{totalCount}</span>
              <span>100.0%</span>
              {kind === "receipt" && <span>{money(totalRefund)}</span>}
            </div>
          </div>
        ) : (
          <CashflowStatsChart
            rows={chart}
            nameLabel={nameLabel}
            totalAmount={totalAmount}
            totalCount={totalCount}
            refundAmount={kind === "receipt" ? totalRefund : undefined}
            kind={kind}
          />
        )}
      </div>
    </div>
  );
}

function ReminderForm({
  data,
  commit,
  currentUser,
  fixedProjectId,
  compact = false,
}: {
  data: AppData;
  commit: (data: AppData, log?: Omit<OperationLog, "id" | "createdAt">) => Promise<void>;
  currentUser: User;
  fixedProjectId?: string;
  compact?: boolean;
}) {
  const fixedProject = fixedProjectId ? data.projects.find((project) => project.id === fixedProjectId) : undefined;
  const [projectId, setProjectId] = useState(fixedProjectId ?? "");
  const [workContent, setWorkContent] = useState<ReminderWorkContent>("绑定账期");
  const workContentOptions = optionValues(data, "reminder_work_content", reminderWorkContents) as ReminderWorkContent[];
  const projectOptions = data.projects
    .filter((project) => project.type === "服务项目")
    .map((project) => {
      const customer = data.organizations.find((org) => org.id === project.customerOrgId);
      return {
        value: project.id,
        label: project.name,
        detail: [project.projectNo, project.type, customer?.name].filter(Boolean).join(" / "),
      };
    });

  async function createReminder() {
    const project = fixedProject ?? data.projects.find((item) => item.id === projectId);
    if (!project || project.type !== "服务项目") return;
    const reminder: ProjectReminder = {
      id: createId("rem"),
      projectId: project.id,
      workContent,
      status: "进行中",
      createdByUserId: currentUser.id,
      createdByName: currentUser.name,
      createdAt: today(),
      updatedAt: today(),
    };
    await commit(
      { ...data, projectReminders: [reminder, ...data.projectReminders] },
      { action: "新增跟进提醒", targetType: "系统", targetName: project.name, operator: "当前用户", detail: reminder.workContent },
    );
    if (!fixedProject) setProjectId("");
    setWorkContent("绑定账期");
  }

  return (
    <div className={`reminder-form ${compact ? "compact" : ""}`}>
      {fixedProject ? (
        <div className="readonly-field">{projectOptionLabel(fixedProject)}</div>
      ) : (
        <SearchableSelect value={projectId} options={projectOptions} onChange={setProjectId} placeholder="搜索并选择项目" ariaLabel="选择项目" />
      )}
      <select value={workContent} onChange={(event) => setWorkContent(event.target.value as ReminderWorkContent)}>
        {workContentOptions.map((item) => <option key={item}>{item}</option>)}
      </select>
      <button className="primary" onClick={() => void createReminder()}><ClipboardList size={16} />创建提醒</button>
    </div>
  );
}

function ReminderList({
  data,
  commit,
  reminders,
  hideProject = false,
}: {
  data: AppData;
  commit: (data: AppData, log?: Omit<OperationLog, "id" | "createdAt">) => Promise<void>;
  reminders: ProjectReminder[];
  hideProject?: boolean;
}) {
  async function updateReminderStatus(reminder: ProjectReminder, status: ProjectReminder["status"]) {
    const project = data.projects.find((item) => item.id === reminder.projectId);
    await commit(
      {
        ...data,
        projectReminders: data.projectReminders.map((item) =>
          item.id === reminder.id ? { ...item, status, updatedAt: today(), completedAt: status === "已完成" ? today() : undefined } : item,
        ),
      },
      { action: "修改跟进提醒状态", targetType: "系统", targetName: project?.name ?? reminder.workContent, operator: "当前用户", detail: `${reminder.workContent}：${reminder.status} -> ${status}` },
    );
  }

  return (
    <div className="table">
      <div className={`table-row reminder-table head ${hideProject ? "hide-project" : ""}`}>
            {!hideProject && <span>项目</span>}
        <span>工作内容</span><span>创建人</span><span>状态</span><span>更新时间</span><span>操作</span>
      </div>
      {reminders.map((reminder) => {
        const project = data.projects.find((item) => item.id === reminder.projectId);
        const companyName = data.organizations.find((org) => org.id === project?.customerOrgId)?.name || "";
        const platformName = project?.sourcePlatform || "";
        return (
          <div className={`table-row reminder-table ${hideProject ? "hide-project" : ""}`} key={reminder.id}>
            {!hideProject && (
              <span className="reminder-project-cell">
                <CopyableLine text={companyName} label="公司名称">
                  {companyName || "未录入公司"}
                </CopyableLine>
                {platformName ? <em>{platformName}</em> : null}
              </span>
            )}
            <span>{reminder.workContent}</span>
            <span>{reminder.createdByName}</span>
            <span>
              <select value={reminder.status} onChange={(event) => void updateReminderStatus(reminder, event.target.value as ProjectReminder["status"])}>
                <option>进行中</option>
                <option>已完成</option>
              </select>
            </span>
            <span>{new Date(reminder.updatedAt).toLocaleDateString("zh-CN")}<em>{reminder.completedAt ? `完成于 ${new Date(reminder.completedAt).toLocaleDateString("zh-CN")}` : "待平台配合"}</em></span>
            <span>{reminder.status !== "已完成" && <button className="copy-link" onClick={() => void updateReminderStatus(reminder, "已完成")}>标记完成</button>}</span>
          </div>
        );
      })}
      {reminders.length === 0 && (
        <div className={`table-row reminder-table ${hideProject ? "hide-project" : ""}`}>
          <span>暂无提醒</span>{!hideProject && <span></span>}<span></span><span></span><span></span><span></span>
        </div>
      )}
    </div>
  );
}

function TodoList({ data }: { data: AppData }) {
  const todos = [
    ...data.projects.filter((project) => project.contractStatus === "待签").map((project) => ({ title: "合同待签", detail: project.name, owner: project.owner })),
    ...data.projects.filter((project) => projectPendingInvoiceAmount(data, project.id) > 0).map((project) => ({ title: `待开票 ${money(projectPendingInvoiceAmount(data, project.id))}`, detail: project.name, owner: "财务" })),
    ...data.projects.filter((project) => project.type === "服务项目" && project.status === "入驻中").map((project) => ({ title: "待平台入驻", detail: project.name, owner: project.serviceSalesName || project.owner })),
    ...data.onboardingRecords.filter((record) => record.step !== "已完成").map((record) => ({ title: record.step, detail: data.organizations.find((org) => org.id === record.customerOrgId)?.name ?? "入驻客户", owner: record.salesOwner })),
  ].slice(0, 8);

  return (
    <div className="todo-list">
      {todos.map((todo, index) => (
        <div className="todo" key={`${todo.title}-${index}`}>
          <span>{todo.title}</span>
          <strong>{todo.detail}</strong>
          <em>{todo.owner}</em>
        </div>
      ))}
    </div>
  );
}

function LicenseDocumentView({
  file,
  onClose,
  hint = "旋转后可与识别结果对照",
}: {
  file: File;
  onClose: () => void;
  hint?: string;
}) {
  const [previewUrl, setPreviewUrl] = useState("");
  const [rotation, setRotation] = useState(0);
  const [zoom, setZoom] = useState(1);
  const stageRef = useRef<HTMLDivElement | null>(null);
  const [stageSize, setStageSize] = useState({ width: 0, height: 0 });

  useEffect(() => {
    const url = URL.createObjectURL(file);
    setPreviewUrl(url);
    return () => URL.revokeObjectURL(url);
  }, [file]);

  useEffect(() => {
    const stage = stageRef.current;
    if (!stage) return undefined;
    const updateSize = () => setStageSize({
      width: Math.max(1, stage.clientWidth - 24),
      height: Math.max(1, stage.clientHeight - 24),
    });
    updateSize();
    const observer = new ResizeObserver(updateSize);
    observer.observe(stage);
    return () => observer.disconnect();
  }, []);

  useEffect(() => {
    const frame = window.requestAnimationFrame(() => {
      const stage = stageRef.current;
      if (!stage) return;
      stage.scrollLeft = Math.max(0, (stage.scrollWidth - stage.clientWidth) / 2);
      stage.scrollTop = Math.max(0, (stage.scrollHeight - stage.clientHeight) / 2);
    });
    return () => window.cancelAnimationFrame(frame);
  }, [zoom, rotation, stageSize.width, stageSize.height]);

  if (!previewUrl) return null;
  const isPdf = file.type === "application/pdf" || file.name.toLowerCase().endsWith(".pdf");
  const normalizedRotation = ((rotation % 360) + 360) % 360;
  const isQuarterTurn = normalizedRotation === 90 || normalizedRotation === 270;
  const fittedWidth = isQuarterTurn ? stageSize.height : stageSize.width;
  const fittedHeight = isQuarterTurn ? stageSize.width : stageSize.height;
  const mediaStyle = {
    width: fittedWidth ? `${fittedWidth}px` : "100%",
    height: fittedHeight ? `${fittedHeight}px` : "100%",
    transform: `translate(-50%, -50%) rotate(${rotation}deg) scale(${zoom})`,
  };
  const canvasStyle = {
    width: stageSize.width ? `${Math.max(stageSize.width, stageSize.width * zoom)}px` : "100%",
    height: stageSize.height ? `${Math.max(stageSize.height, stageSize.height * zoom)}px` : "100%",
  };

  return (
    <section className="license-document-pane" aria-label={`预览 ${file.name}`}>
      <div className="license-document-head">
        <div><strong>{file.name}</strong><span>{hint}</span></div>
        <button className="icon-button" type="button" onClick={onClose} aria-label="关闭原件"><X size={18} /></button>
      </div>
      <div className="license-rotate-actions">
        <button className="ghost" type="button" onClick={() => setRotation((value) => value - 90)}><RotateCcw size={16} />向左旋转</button>
        <button className="ghost" type="button" onClick={() => setRotation((value) => value + 90)}><RotateCw size={16} />向右旋转</button>
        {rotation !== 0 && <button className="copy-link" type="button" onClick={() => setRotation(0)}>恢复方向</button>}
        <span className="license-toolbar-divider" />
        <button className="ghost" type="button" disabled={zoom <= 0.5} onClick={() => setZoom((value) => Math.max(0.5, value - 0.25))}><ZoomOut size={16} />缩小</button>
        <strong className="license-zoom-value">{Math.round(zoom * 100)}%</strong>
        <input
          className="license-zoom-slider"
          type="range"
          min="50"
          max="400"
          step="25"
          value={Math.round(zoom * 100)}
          aria-label="调整原件缩放比例"
          onChange={(event) => setZoom(Number(event.target.value) / 100)}
        />
        <button className="ghost" type="button" disabled={zoom >= 4} onClick={() => setZoom((value) => Math.min(4, value + 0.25))}><ZoomIn size={16} />放大</button>
        {zoom !== 1 && <button className="copy-link" type="button" onClick={() => setZoom(1)}>适应窗口</button>}
      </div>
      <div className="license-document-stage" ref={stageRef}>
        <div className="license-document-canvas" style={canvasStyle}>
          {isPdf
            ? <iframe className="license-pdf-preview" style={mediaStyle} src={previewUrl} title={file.name} />
            : <img className="license-image-preview" style={mediaStyle} src={previewUrl} alt={file.name} />}
        </div>
      </div>
    </section>
  );
}

function LicenseFilePreview({ file }: { file: File | null }) {
  const [open, setOpen] = useState(false);

  useEffect(() => {
    if (!file) setOpen(false);
  }, [file]);

  if (!file) return null;

  return (
    <>
      <button className="license-preview-trigger" type="button" onClick={() => setOpen(true)} title="点击放大查看原文件">
        <FileText size={15} />查看原件
      </button>
      {open && (
        <div className="modal-backdrop license-preview-backdrop" role="presentation" onClick={() => setOpen(false)}>
          <div className="license-preview-modal" role="dialog" aria-modal="true" aria-label={`预览 ${file.name}`} onClick={(event) => event.stopPropagation()}>
            <LicenseDocumentView file={file} onClose={() => setOpen(false)} />
          </div>
        </div>
      )}
    </>
  );
}

function Projects({
  data,
  commit,
  currentUser,
  can,
  projectType,
  selectedProject,
  onSelectProject,
}: {
  data: AppData;
  commit: (data: AppData, log?: Omit<OperationLog, "id" | "createdAt">) => Promise<void>;
  currentUser: User;
  can: CanAccess;
  projectType: Project["type"];
  selectedProject?: Project;
  onSelectProject: (id: string) => void;
}) {
  const customers = data.organizations.filter((org) => (
    projectType === "商品项目" ? isResellerOrganization(org) : isCustomerOrganization(org)
  ));
  const usageUnits = data.organizations.filter((org) => orgHasRole(org, "使用单位"));
  const suppliers = data.organizations.filter((org) => isSupplierOrganization(org));
  const ownCompanies = data.organizations.filter((org) => isOwnCompanyOrganization(org));
  const [showCreate, setShowCreate] = useState(false);
  const [editingProjectId, setEditingProjectId] = useState("");
  const [isCreatingProject, setIsCreatingProject] = useState(false);
  const [projectSearch, setProjectSearch] = useState("");
  const [projectOwnCompanyFilter, setProjectOwnCompanyFilter] = useState("");
  const [projectStatusFilter, setProjectStatusFilter] = useState("");
  const [projectServiceTypeFilter, setProjectServiceTypeFilter] = useState("");
  const [projectContractStatusFilter, setProjectContractStatusFilter] = useState("");
  const [projectInvoiceStatusFilter, setProjectInvoiceStatusFilter] = useState("");
  const [projectSalesUserFilter, setProjectSalesUserFilter] = useState("");
  const serviceLicenseInputRef = useRef<HTMLInputElement | null>(null);
  const salesOrderSectionRef = useRef<HTMLDivElement | null>(null);
  const purchaseOrderSectionRef = useRef<HTMLDivElement | null>(null);
  const projectTab = projectType;
  const activeProject = selectedProject?.type === projectType ? selectedProject : undefined;
  const [newProject, setNewProject] = useState({
    name: "",
    type: projectType,
    customerOrgId: "",
    usageUnitOrgId: "",
    ownCompanyOrgId: "",
    sourcePlatform: "",
    onboardingPlatform: "" as PlatformAccount["platform"],
    platformOrderNo: "",
    owner: "当前用户",
    productId: "",
    supplierOrgId: "",
    quantity: "1",
    salesUnitPrice: "",
    purchaseUnitPrice: "",
    projectAt: localDateTimeInputValue(),
    serviceType: "周期" as ServiceType,
    serviceCustomerKind: "" as "" | ServiceCustomerKind,
    serviceStartDate: todayDate(),
    serviceEndDate: "",
    servicePeriodUnit: "年" as ServicePeriodUnit,
    servicePeriodValue: "1",
    serviceGiftUnit: "月" as "天" | "月",
    serviceGiftValue: "0",
    serviceSalesUserId: "",
    serviceRemark: "",
    remark: "",
  });
  const [orderDraft, setOrderDraft] = useState({
    productId: data.products[0]?.id ?? "",
    supplierOrgId: suppliers[0]?.id ?? "",
    quantity: "1",
    salesUnitPrice: "",
    purchaseUnitPrice: "",
    platformOrderNo: "",
    note: "",
    directProductName: "",
    directPlatformPrice: "",
  });
  const [salesOrderDraftItems, setSalesOrderDraftItems] = useState<Array<{ productId: string; productName: string; quantity: number; unitPrice: number }>>([]);
  const [salesOrderComposeDrafts, setSalesOrderComposeDrafts] = useState<Record<string, {
    productId: string;
    quantity: string;
    salesUnitPrice: string;
    directProductName: string;
    directPlatformPrice: string;
  }>>({});
  const [salesComposer, setSalesComposer] = useState<SalesComposerDraft | null>(null);
  const [salesProductDraft, setSalesProductDraft] = useState<SalesChannelLineDraft | null>(null);
  const [salesProductMode, setSalesProductMode] = useState<"catalog" | "quick">("catalog");
  const [purchaseOrderedAt, setPurchaseOrderedAt] = useState(() => defaultOrderTimeFromProject());
  const [purchaseOrderDraftItems, setPurchaseOrderDraftItems] = useState<Array<{ productId: string; productName: string; quantity: number; unitPrice: number; supplierPriceId?: string }>>([]);
  const [purchaseSplitMode, setPurchaseSplitMode] = useState(false);
  const [purchaseValidateAgainstSales, setPurchaseValidateAgainstSales] = useState(true);
  const [purchaseSplitLines, setPurchaseSplitLines] = useState<Array<{
    key: string;
    productId: string;
    productName: string;
    quantity: string;
    supplierOrgId: string;
    purchaseUnitPrice: string;
  }>>([]);
  const [editingOrderStatus, setEditingOrderStatus] = useState<{ type: "sales" | "purchase" | "service" | "purchasePayment"; id: string } | null>(null);
  const [projectInvoiceId, setProjectInvoiceId] = useState("");
  const [showContractUpload, setShowContractUpload] = useState(false);
  const [contractFile, setContractFile] = useState<File | null>(null);
  const [contractViewerFileId, setContractViewerFileId] = useState("");
  const [poContractUploadOrderId, setPoContractUploadOrderId] = useState("");
  const [poContractFile, setPoContractFile] = useState<File | null>(null);
  const [productDetailTab, setProductDetailTab] = useState<ProductDetailTab>("basic");
  const [serviceDetailTab, setServiceDetailTab] = useState<ServiceDetailTab>("basic");
  const [quickReminderProjectId, setQuickReminderProjectId] = useState("");
  const [memoDraft, setMemoDraft] = useState("");
  const [memoSearch, setMemoSearch] = useState("");
  const [orderInvoiceIds, setOrderInvoiceIds] = useState<Record<string, string>>({});
  const [salesOrderPanel, setSalesOrderPanel] = useState<{ orderId: string; kind: "invoice" | "transactions" | "purchase" } | null>(null);
  const [purchaseOrderPanel, setPurchaseOrderPanel] = useState<{ orderId: string; kind: "invoice" | "transactions" | "fulfillment" } | null>(null);
  const [serviceLicenseOcrStatus, setServiceLicenseOcrStatus] = useState("");
  const [serviceLicenseFile, setServiceLicenseFile] = useState<File | null>(null);
  const [serviceAccountCopyTip, setServiceAccountCopyTip] = useState("");
  const [editingServiceAccountId, setEditingServiceAccountId] = useState("");
  const [serviceAccountDraft, setServiceAccountDraft] = useState({
    platform: "泉E采" as PlatformAccount["platform"],
    accountName: "",
    accountPasswordMasked: "",
    merchantId: "",
    shopId: "",
    shopName: "",
  });
  const [contractDraftProject, setContractDraftProject] = useState<Project | null>(null);
  const [contractDraft, setContractDraft] = useState<ServiceContractDraft | null>(null);
  const [contractMoreOpen, setContractMoreOpen] = useState(false);
  const [contractFileFormat, setContractFileFormat] = useState<ServiceContractFileFormat>("word");
  const [isGeneratingContract, setIsGeneratingContract] = useState(false);
  const emptyServiceAccountDraft = {
    platform: "泉E采" as PlatformAccount["platform"],
    accountName: "",
    accountPasswordMasked: "",
    merchantId: "",
    shopId: "",
    shopName: "",
  };
  const sourcePlatformOptions = optionValues(data, "platform", ["框架协议", "泉E采", "青慧采", "齐鲁云采", "美云销", "渠道", "直客", "其他"]);
  const onboardingPlatformOptions = optionValues(data, "platform", ["泉E采", "青慧采", "齐鲁云采", "政采云", "公采云", "国铁", "其他"]);
  const projectStatusValues = optionValues(data, "project_status", projectStatusOptions) as ProjectStatus[];
  const logisticsStatusOptions = optionValues(data, "logistics_status", ["待发货", "已发货", "已签收"]) as LogisticsStatus[];
  const acceptanceStatusOptions = optionValues(data, "acceptance_status", ["待验收", "验收中", "已验收"]) as AcceptanceStatus[];
  const deliveryStatusOptions = optionValues(data, "delivery_status", ["待交付", "部分交付", "交付中", "已交付"]) as DeliveryStatus[];
  const orderPaymentStatusOptions = optionValues(data, "order_payment_status", ["待付款", "部分付款", "已付款", "退款", "取消"]) as OrderPaymentStatus[];
  const reconcileStatusOptions = optionValues(data, "reconcile_status", ["待对账", "已对账"]) as ReconcileStatus[];
  const salesOrderStatuses = optionValues(data, "sales_order_status", ["待付款", "部分付款", "已付款", "退款", "取消"]) as SalesOrder["status"][];
  const purchaseOrderStatuses = optionValues(data, "purchase_order_status", ["草稿", "待下单", "已下单", "部分到货", "已完成", "已取消"]) as PurchaseOrder["status"][];
  const serviceProjectStatuses = optionValues(data, "service_project_status", ["入驻中", "服务中", "终止合作", "到期", "结束"]) as ProjectStatus[];
  const contractStatusOptions = optionValues(data, "contract_status", ["无需", "待签", "已签", "已发送"]) as ContractStatus[];
  const serviceTypeOptions = optionValues(data, "service_type", ["周期", "按次"]) as ServiceType[];
  const servicePeriodUnits = optionValues(data, "service_period_unit", ["年", "月"]) as ServicePeriodUnit[];
  const serviceYearOptions = optionValues(data, "service_period_year", ["1年", "2年", "3年"]);
  const serviceMonthOptions = optionValues(data, "service_period_month", ["1个月", "2个月", "3个月", "4个月", "5个月", "6个月"]);
  const serviceOrderStatuses = optionValues(data, "service_order_status", ["待付款", "部分付款", "已付款", "退款", "取消"]) as ServiceOrder["status"][];
  const { requestPayment, paymentDialog } = usePaymentDialog(data);
  useEffect(() => {
    setShowCreate(false);
    setQuickReminderProjectId("");
    setProductDetailTab("basic");
    setServiceDetailTab("basic");
    setMemoDraft("");
    setMemoSearch("");
    setProjectSearch("");
    setProjectOwnCompanyFilter("");
    setProjectStatusFilter("");
    setProjectServiceTypeFilter("");
    setProjectContractStatusFilter("");
    setProjectInvoiceStatusFilter("");
    setProjectSalesUserFilter("");
    setNewProject((current) => ({
      ...current,
      type: projectType,
      productId: "",
      sourcePlatform: projectType === "服务项目" ? current.onboardingPlatform : "框架协议",
      salesUnitPrice: "",
      purchaseUnitPrice: "",
      serviceStartDate: current.serviceStartDate || todayDate(),
      serviceSalesUserId: "",
    }));
  }, [projectType]);

  useEffect(() => {
    setProductDetailTab("basic");
    setServiceDetailTab("basic");
    setPurchaseSplitMode(false);
    setPurchaseSplitLines([]);
    setMemoDraft("");
    setMemoSearch("");
    setPurchaseOrderDraftItems([]);
    setPurchaseOrderedAt(defaultOrderTimeFromProject(activeProject));
    setSalesOrderDraftItems([]);
    setSalesOrderComposeDrafts({});
    setPurchaseValidateAgainstSales(true);
    setProjectInvoiceId("");
    setSalesOrderPanel(null);
    setPurchaseOrderPanel(null);
  }, [activeProject?.id]);

  const filteredPage = useServerPagedList<Project>({
    collection: "projects",
    search: projectSearch,
    filters: projectTab === "服务项目"
      ? {
          type: projectTab,
          ownCompanyOrgId: projectOwnCompanyFilter,
          status: projectStatusFilter,
          serviceType: projectServiceTypeFilter,
          contractStatus: projectContractStatusFilter,
          invoiceStatus: projectInvoiceStatusFilter,
          serviceSalesUserId: projectSalesUserFilter,
        }
      : { type: projectTab },
    pageSize: 10,
    refreshKey: data.projects,
  });
  const customer = activeProject ? data.organizations.find((org) => org.id === activeProject.customerOrgId) : undefined;
  const usageUnit = activeProject ? data.organizations.find((org) => org.id === activeProject.usageUnitOrgId) : undefined;
  const ownCompany = activeProject ? data.organizations.find((org) => org.id === activeProject.ownCompanyOrgId) : undefined;
  const poUploadOrder = data.purchaseOrders.find((item) => item.id === poContractUploadOrderId);
  const items = activeProject
    ? (activeProject.type === "商品项目"
      ? productProjectDetailItems(data, activeProject.id)
      : data.projectItems.filter((item) => item.projectId === activeProject.id))
    : [];
  const salesOrders = activeProject ? sortByCreatedDesc(data.salesOrders.filter((order) => order.projectId === activeProject.id)) : [];
  const salesPanelOrder = salesOrderPanel ? salesOrders.find((order) => order.id === salesOrderPanel.orderId) : undefined;
  const purchaseOrders = activeProject ? sortByCreatedDesc(data.purchaseOrders.filter((order) => order.projectId === activeProject.id)) : [];
  const purchasePanelOrder = purchaseOrderPanel ? purchaseOrders.find((order) => order.id === purchaseOrderPanel.orderId) : undefined;
  const purchaseFulfillmentSummary = useMemo(
    () => aggregateFulfillmentFromPurchaseOrders(purchaseOrders.filter((order) => order.status !== "已取消")),
    [purchaseOrders],
  );
  const serviceOrders = activeProject ? sortByCreatedDesc(data.serviceOrders.filter((order) => order.projectId === activeProject.id)) : [];
  const projectInvoices = activeProject
    ? sortByCreatedDesc(projectVisibleInvoices(data, activeProject))
    : [];
  const projectReminders = activeProject ? sortByCreatedDesc(data.projectReminders.filter((reminder) => reminder.projectId === activeProject.id)) : [];
  const projectMemos = activeProject
    ? sortByCreatedDesc(data.projectMemos.filter((memo) => memo.projectId === activeProject.id))
    : [];
  const projectMemosPage = useServerPagedList<ProjectMemo>({
    collection: "projectMemos",
    search: memoSearch,
    filters: { projectId: activeProject?.id },
    pageSize: 10,
    enabled: Boolean(activeProject?.id),
    refreshKey: data.projectMemos,
  });
  const projectPlatformAccounts = activeProject ? sortByCreatedDesc(data.platformAccounts.filter((account) =>
    account.projectId === activeProject.id
    || (
      account.customerOrgId === activeProject.customerOrgId
      && (!activeProject.sourcePlatform || account.platform === activeProject.sourcePlatform)
    ),
  )) : [];
  const relatedProjectOrderNos = activeProject
    ? [
        ...data.serviceOrders.filter((order) => order.projectId === activeProject.id).map((order) => order.orderNo),
        ...data.salesOrders.filter((order) => order.projectId === activeProject.id).map((order) => order.orderNo),
        ...data.purchaseOrders.filter((order) => order.projectId === activeProject.id).map((order) => order.orderNo),
      ]
    : [];
  const relatedProjectLogs = activeProject ? sortByCreatedDesc(data.operationLogs.filter((log) => {
    const haystack = `${log.targetName}${log.detail ?? ""}`;
    return log.targetName === activeProject.name
      || log.targetName === activeProject.projectNo
      || haystack.includes(activeProject.projectNo)
      || haystack.includes(activeProject.name)
      || relatedProjectOrderNos.includes(log.targetName)
      || relatedProjectOrderNos.some((orderNo) => haystack.includes(orderNo));
  })) : [];
  const selectedProjectRevenue = activeProject ? projectRevenue(data, activeProject.id) : 0;
  const selectedProjectCost = activeProject ? projectCost(data, activeProject.id) : 0;
  const selectedProjectGrossProfit = selectedProjectRevenue - selectedProjectCost;
  const canViewProjectCost = can("profit.view") || can("purchase.manage");
  const onboarding = activeProject ? data.onboardingRecords.find((record) => record.projectId === activeProject.id) : undefined;
  const selectedProduct = data.products.find((product) => product.id === newProject.productId);
  const selectedProductPlatforms = selectedProduct?.platformIds?.length
    ? selectedProduct.platformIds.filter((platform) => onboardingPlatformOptions.includes(platform))
    : onboardingPlatformOptions.filter((platform) => selectedProduct?.name.toLowerCase().includes(platform.toLowerCase()));
  const availableOnboardingPlatforms = selectedProductPlatforms.length > 0 ? selectedProductPlatforms : onboardingPlatformOptions;
  const selectedNewProjectCustomer = data.organizations.find((org) => org.id === newProject.customerOrgId);
  const selectedNewProjectUsageUnit = data.organizations.find((org) => org.id === newProject.usageUnitOrgId);
  const selectedSalesUser = data.users.find((user) => user.id === newProject.serviceSalesUserId);
  const serviceProjectNamePreview = selectedNewProjectCustomer && selectedProduct
    ? `${selectedNewProjectCustomer.name} - ${selectedProduct.name} - ${formatYearMonth(newProject.serviceStartDate)}`
    : "";
  const productProjectNamePreview = selectedNewProjectCustomer
    ? buildProductProjectName({
      customerName: selectedNewProjectCustomer.name,
      usageUnitName: selectedNewProjectUsageUnit?.name,
      platform: newProject.sourcePlatform,
      remark: newProject.remark,
      projectAt: newProject.projectAt,
    })
    : "";
  const newProjectProductOptions = data.products.filter((product) => {
    if (!isCatalogProduct(product)) return false;
    const matchesKind = projectTab === "服务项目" ? product.kind === "虚拟服务" : product.kind === "实体商品";
    const matchesPlatform = projectTab !== "服务项目"
      || !newProject.onboardingPlatform
      || !product.platformIds?.length
      || product.platformIds.includes(newProject.onboardingPlatform);
    return matchesKind && matchesPlatform;
  });
  const customerSelectOptions = sortByCreatedDesc(customers).map((org) => ({ value: org.id, label: org.name, detail: [org.unifiedCreditCode, org.legalPerson, org.phone].filter(Boolean).join(" / ") }));
  const usageUnitSelectOptions = usageUnits.map((org) => ({ value: org.id, label: org.name, detail: org.unifiedCreditCode }));
  const ownCompanySelectOptions = ownCompanies.map((org) => ({ value: org.id, label: org.name, detail: org.unifiedCreditCode }));
  const projectOwnCompanyFilterOptions = [{ value: "", label: "全部" }, ...ownCompanySelectOptions];
  const projectSalesUserFilterOptions = [
    { value: "", label: "全部" },
    ...data.users.filter((user) => user.status === "启用").map((user) => ({ value: user.id, label: user.name })),
  ];
  const serviceInvoiceStatusFilterOptions = ["待开", "已开部分", "已开全部", "无需"];
  const projectProductSelectOptions = newProjectProductOptions.map((product) => ({ value: product.id, label: `${product.name} · ${money(product.quotePrice)}`, detail: product.category }));
  const salesProductOptions = data.products.filter((product) => {
    const matchesKind = activeProject?.type === "服务项目" ? product.kind === "虚拟服务" : product.kind === "实体商品";
    if (!matchesKind) return false;
    if (isProjectScopedProduct(product)) return isProjectScopedProduct(product, activeProject?.id);
    return true;
  });
  const projectSalesProductIds = new Set(
    activeProject
      ? data.projectItems
        .filter((item) => item.projectId === activeProject.id && item.salesOrderId && !isPurchaseLineItem(item))
        .map((item) => item.productId)
      : [],
  );
  const purchaseProductOptions = data.products.filter((product) => {
    if (product.kind !== "实体商品") return false;
    if (isProjectScopedProduct(product) && !isProjectScopedProduct(product, activeProject?.id)) return false;
    if (!activeProject || activeProject.type !== "商品项目") return true;
    if (!purchaseValidateAgainstSales) return true;
    return projectSalesProductIds.has(product.id);
  });
  const salesProductSelectOptions = salesProductOptions.map((product) => ({
    value: product.id,
    label: `${product.name}｜售价 ${money(product.quotePrice)}${product.source === "project" ? "｜项目商品" : ""}`,
    detail: [product.category, product.capacity, product.code].filter(Boolean).join(" / "),
  }));
  const purchaseProductSelectOptions = purchaseProductOptions.map((product) => {
    const remaining = activeProject
      ? projectPurchaseRemainingQuantity(data, activeProject.id, product.id)
      : 0;
    const salesQty = activeProject ? projectSalesQuantityForProduct(data, activeProject.id, product.id) : 0;
    return {
      value: product.id,
      label: `${product.name}｜成本 ${money(product.costPrice)}`,
      detail: purchaseValidateAgainstSales
        ? `销售 ${salesQty} / 可采 ${remaining}${product.category ? `｜${product.category}` : ""}`
        : [product.category, product.code, salesQty > 0 ? `销售 ${salesQty}` : "打包/非销售商品"].filter(Boolean).join("｜"),
    };
  });
  const supplierSelectOptions = suppliers.map((org) => ({
    value: org.id,
    label: org.name,
    detail: [org.unifiedCreditCode, org.legalPerson, org.phone].filter(Boolean).join(" / "),
  }));

  function openCreateProject() {
    setEditingProjectId("");
    setNewProject({
      ...newProject,
      name: "",
      type: projectTab,
      customerOrgId: "",
      productId: "",
      sourcePlatform: "",
      onboardingPlatform: "" as PlatformAccount["platform"],
      serviceSalesUserId: "",
      salesUnitPrice: "",
      purchaseUnitPrice: "",
      projectAt: localDateTimeInputValue(),
      remark: "",
      serviceCustomerKind: "" as "" | ServiceCustomerKind,
    });
    setShowCreate(true);
  }

  function openEditServiceProject(project: Project) {
    setEditingProjectId(project.id);
    setNewProject({
      ...newProject,
      name: project.name,
      type: "服务项目",
      customerOrgId: project.customerOrgId,
      usageUnitOrgId: project.usageUnitOrgId ?? "",
      ownCompanyOrgId: project.ownCompanyOrgId ?? "",
      sourcePlatform: project.sourcePlatform ?? "",
      onboardingPlatform: (project.sourcePlatform || "") as PlatformAccount["platform"],
      productId: project.serviceProductId ?? "",
      salesUnitPrice: String(project.totalAmount ?? 0),
      serviceType: project.serviceType ?? "周期",
      serviceCustomerKind: project.sourcePlatform === QINGHUICAI_PLATFORM && !isServiceCustomerKind(project.serviceCustomerKind ?? "")
        ? "首次服务"
        : (project.serviceCustomerKind && isServiceCustomerKind(project.serviceCustomerKind) ? project.serviceCustomerKind : ""),
      serviceStartDate: project.serviceStartDate ?? todayDate(),
      serviceEndDate: project.serviceEndDate ?? "",
      servicePeriodUnit: project.servicePeriodUnit ?? "年",
      servicePeriodValue: String(project.servicePeriodValue ?? 1),
      serviceGiftUnit: project.serviceGiftUnit ?? "月",
      serviceGiftValue: String(project.serviceGiftValue ?? project.serviceGiftMonths ?? 0),
      serviceSalesUserId: project.serviceSalesUserId ?? "",
      serviceRemark: project.serviceRemark ?? "",
    });
    setShowCreate(true);
  }

  function closeCreateProjectModal() {
    setShowCreate(false);
    setEditingProjectId("");
    setServiceLicenseOcrStatus("");
  }

  function selectServiceLicenseFile() {
    serviceLicenseInputRef.current?.click();
  }

  async function addCustomerFromLicenseFile(file: File | undefined) {
    if (!file) return;
    setServiceLicenseFile(file);
    setServiceLicenseOcrStatus("正在识别营业执照...");
    try {
      const formData = new FormData();
      formData.append("file", await prepareOcrUpload(file));
      const response = await fetch(ocrServiceUrl("/api/ocr/business-license"), {
        method: "POST",
        body: formData,
      });
      if (!response.ok) {
        const errorText = await response.text();
        throw new Error(errorText || "营业执照识别失败");
      }
      const result = await response.json();
      if (result.status !== "recognized" || !result.data) {
        setServiceLicenseOcrStatus(result.message || "暂未识别到营业执照字段。");
        return;
      }
      const parsed = result.data as {
        unified_credit_code?: string;
        name?: string;
        entity_type?: string;
        legal_person?: string;
        address?: string;
      };
      const parsedName = parsed.name?.trim();
      const parsedCreditCode = parsed.unified_credit_code?.trim();
      if (!parsedName) {
        setServiceLicenseOcrStatus("识别完成，但未识别到客户名称。");
        return;
      }

      const existing = data.organizations.find((org) => parsedCreditCode && org.unifiedCreditCode === parsedCreditCode)
        ?? data.organizations.find((org) => org.name === parsedName);
      const customerRoles: OrganizationRole[] = ["客户", "平台入驻客户"];
      const customerOrgId = existing?.id ?? createId("org");
      let nextOrganizations: Organization[];

      if (existing) {
        nextOrganizations = data.organizations.map((org) =>
          org.id === existing.id
            ? {
                ...org,
                name: parsedName || org.name,
                unifiedCreditCode: parsedCreditCode || org.unifiedCreditCode,
                legalPerson: parsed.legal_person || org.legalPerson,
                address: parsed.address || org.address,
                roles: Array.from(new Set([...org.roles, ...customerRoles])) as OrganizationRole[],
              }
            : org,
        );
      } else {
        const organization: Organization = {
          id: customerOrgId,
          name: parsedName,
          entityType: "企业",
          roles: customerRoles,
          unifiedCreditCode: parsedCreditCode || undefined,
          legalPerson: parsed.legal_person || undefined,
          address: parsed.address || undefined,
          status: "正常",
          createdAt: today(),
        };
        nextOrganizations = [organization, ...data.organizations];
      }

      await commit(
        { ...data, organizations: nextOrganizations },
        {
          action: existing ? "营业执照匹配客户" : "营业执照新增客户",
          targetType: "实体",
          targetName: parsedName,
          operator: "当前用户",
          detail: existing ? "创建服务项目时通过营业执照 OCR 匹配并选中客户。" : "创建服务项目时通过营业执照 OCR 新增客户并选中。",
        },
      );
      setNewProject({ ...newProject, customerOrgId, type: "服务项目", sourcePlatform: newProject.onboardingPlatform });
      setServiceLicenseOcrStatus(existing ? `已匹配客户：${parsedName}` : `已新增客户：${parsedName}`);
    } catch (error) {
      setServiceLicenseOcrStatus(error instanceof Error ? error.message : "营业执照识别失败");
    } finally {
      if (serviceLicenseInputRef.current) serviceLicenseInputRef.current.value = "";
    }
  }

  function updateProduct(productId: string) {
    const product = data.products.find((item) => item.id === productId);
    const productPlatforms = product?.platformIds?.length
      ? product.platformIds.filter((platform) => onboardingPlatformOptions.includes(platform))
      : onboardingPlatformOptions.filter((platform) => product?.name.toLowerCase().includes(platform.toLowerCase()));
    const nextPlatform = productPlatforms.length === 1
      ? productPlatforms[0]
      : productPlatforms.includes(newProject.onboardingPlatform) ? newProject.onboardingPlatform : "";
    setNewProject({
      ...newProject,
      productId,
      onboardingPlatform: nextPlatform as PlatformAccount["platform"],
      sourcePlatform: nextPlatform,
      serviceCustomerKind: serviceCustomerKindForPlatform(nextPlatform, newProject.serviceCustomerKind),
      salesUnitPrice: editingProjectId
        ? newProject.salesUnitPrice
        : (product?.quotePrice ? String(product.quotePrice) : ""),
    });
  }

  function serviceDateText(project: Project) {
    return project.serviceEndDate || "未设置";
  }

  function serviceCountdownText(project: Project) {
    if (!project.serviceEndDate) return "-";
    const end = new Date(`${project.serviceEndDate}T23:59:59`).getTime();
    const days = Math.ceil((end - Date.now()) / 86400000);
    return String(days);
  }

  function serviceListName(project: Project) {
    const parts = project.name.split(/\s+-\s+/).map((part) => part.trim()).filter(Boolean);
    return parts.length >= 3 ? `${parts[1]} - ${parts[2]}` : project.serviceProductName || project.name;
  }

  function hasServicePaymentTransaction(order: ServiceOrder, transactions = data.transactions) {
    return transactions.some((tx) => tx.serviceOrderId === order.id && tx.type === "收款");
  }

  function paymentAmountPrompt(orderNo: string, receivable: number, received: number, targetStatus: string) {
    return requestPayment({ orderNo, receivable, received, targetStatus });
  }

  function servicePaymentTransaction(order: ServiceOrder, paidAt: string, amount = order.amount, payment?: PaymentFormResult): Transaction {
    return buildServiceCollectionTransaction(order, paidAt, { amount, ...payment });
  }

  function salesPaymentTransaction(order: SalesOrder, paidAt: string, amount: number, payment: PaymentFormResult): Transaction {
    return buildSalesCollectionTransaction(order, paidAt, { ...payment, amount });
  }

  async function backfillOrderCollection(kind: "sales" | "service", order: SalesOrder | ServiceOrder) {
    if (!canBackfillCollection(can, kind)) return;
    await backfillMissingCollectionTx({
      data,
      commit,
      requestPayment,
      kind,
      order,
      operator: currentUser.name,
    });
  }

  function projectCompletionIssues(project: Project) {
    if (project.type === "商品项目") {
      return productProjectCompletionIssues(project, data);
    }
    const issues: string[] = [];
    const projectServiceOrders = data.serviceOrders.filter((order) => order.projectId === project.id);
    if (projectServiceOrders.length === 0) issues.push("缺少服务订单");
    if (projectServiceOrders.some((order) => order.status === "待付款" || order.status === "部分付款")) issues.push("存在未结清服务订单");
    if (projectPlatformAccounts.length === 0) issues.push("未维护平台账号");
    if (projectServiceOrders.some((order) => order.status === "已付款" && !hasServicePaymentTransaction(order))) issues.push("已付款服务订单缺少收款流水");
    return issues;
  }

  function defaultProjectPlatform(project = activeProject): PlatformAccount["platform"] {
    const platform = project?.sourcePlatform;
    return platform && (onboardingPlatformOptions as string[]).includes(platform)
      ? platform as PlatformAccount["platform"]
      : "泉E采";
  }

  async function addProjectPlatformAccount() {
    if (!activeProject || activeProject.type !== "服务项目") return;
    if (!serviceAccountDraft.platform || !serviceAccountDraft.accountName.trim() || !serviceAccountDraft.accountPasswordMasked) {
      setServiceAccountCopyTip("请完整填写平台、账号和密码。");
      return;
    }
    const existingAccount = data.platformAccounts.find((item) => item.id === editingServiceAccountId);
    const now = new Date().toISOString();
    const account: PlatformAccount = {
      ...existingAccount,
      id: editingServiceAccountId || createId("pa"),
      createdAt: existingAccount?.createdAt ?? now,
      updatedAt: now,
      projectId: activeProject.id,
      customerOrgId: activeProject.customerOrgId,
      platform: serviceAccountDraft.platform,
      accountName: serviceAccountDraft.accountName || undefined,
      accountPasswordMasked: serviceAccountDraft.accountPasswordMasked || undefined,
      merchantId: serviceAccountDraft.merchantId || undefined,
      shopId: serviceAccountDraft.shopId || undefined,
      shopName: serviceAccountDraft.shopName.trim() || undefined,
      licenseDisplayStatus: existingAccount?.licenseDisplayStatus ?? "未处理",
      publicSecurityStatus: existingAccount?.publicSecurityStatus ?? "未处理",
      backendTemplateStatus: existingAccount?.backendTemplateStatus ?? "未录入",
      caStatus: existingAccount?.caStatus ?? "未办理",
      serviceYears: existingAccount?.serviceYears ?? (activeProject.servicePeriodUnit === "年" ? activeProject.servicePeriodValue : undefined),
      expireDate: existingAccount?.expireDate ?? activeProject.serviceEndDate,
      salesOwner: existingAccount?.salesOwner ?? activeProject.serviceSalesName ?? activeProject.owner,
      currentStatus: existingAccount?.currentStatus || "已付款待办理",
      note: existingAccount?.note,
    };
    const nextAccounts = editingServiceAccountId
      ? data.platformAccounts.map((item) => item.id === editingServiceAccountId ? account : item)
      : [account, ...data.platformAccounts];
    const customerName = data.organizations.find((org) => org.id === account.customerOrgId)?.name;
    const log = platformAccountLog(existingAccount, account, customerName || activeProject.name);
    await commit(
      { ...data, platformAccounts: nextAccounts },
      {
        action: editingServiceAccountId
          ? (log.action === "修改平台账号密码" ? "项目修改平台账号密码" : "项目编辑平台账号")
          : "项目维护平台账号",
        targetType: "系统",
        targetName: log.targetName,
        operator: "当前用户",
        detail: log.detail,
      },
    );
    setEditingServiceAccountId("");
    setServiceAccountDraft({ ...emptyServiceAccountDraft, platform: defaultProjectPlatform(activeProject) });
    setServiceAccountCopyTip(editingServiceAccountId ? "平台账号已保存" : "平台账号已新增");
  }

  function editProjectPlatformAccount(account: PlatformAccount) {
    setEditingServiceAccountId(account.id);
    setServiceAccountDraft({
      platform: account.platform,
      accountName: account.accountName || "",
      accountPasswordMasked: account.accountPasswordMasked || "",
      merchantId: account.merchantId || "",
      shopId: account.shopId || "",
      shopName: account.shopName || "",
    });
  }

  async function deleteProjectPlatformAccount(account: PlatformAccount) {
    if (!activeProject || !window.confirm(`确认删除 ${account.platform} 平台账号？`)) return;
    await commit(
      { ...data, platformAccounts: data.platformAccounts.filter((item) => item.id !== account.id) },
      { action: "项目删除平台账号", targetType: "系统", targetName: activeProject.name, operator: "当前用户", detail: `删除 ${account.platform} 平台账号` },
    );
    if (editingServiceAccountId === account.id) {
      setEditingServiceAccountId("");
      setServiceAccountDraft({ ...emptyServiceAccountDraft, platform: defaultProjectPlatform(activeProject) });
    }
  }

  function maskedServiceAccountValue(value?: string) {
    if (!value) return "未录入";
    if (value.length <= 4) return "****";
    return `${value.slice(0, 2)}***${value.slice(-2)}`;
  }

  function resetServiceAccountDraft() {
    setEditingServiceAccountId("");
    setServiceAccountDraft({ ...emptyServiceAccountDraft, platform: defaultProjectPlatform() });
  }

  async function copyServiceAccountText(text: string | undefined, label: string, account?: PlatformAccount, field?: PlatformSensitiveField) {
    if (account && field) {
      try {
        text = await fetchPlatformSensitiveValue(account.id, field);
      } catch {
        setServiceAccountCopyTip(`${label}读取失败，请重新登录后重试`);
        return;
      }
    }
    if (!text) {
      setServiceAccountCopyTip(`${label}未录入`);
      return;
    }
    try {
      await writeClipboardText(text);
      void auditSensitiveAccess({ targetName: account?.accountName || account?.platform || activeProject?.name, fieldLabel: label, platform: account?.platform, source: "项目详情平台账号" });
      setServiceAccountCopyTip(`已复制${label}`);
    } catch {
      setServiceAccountCopyTip(`${label}复制失败，请检查浏览器剪贴板权限`);
    }
  }

  async function updateServiceOrderStatus(order: ServiceOrder, status: ServiceOrder["status"]) {
    if (!canTransition(order.status, status, getAllowedServiceOrderStatuses(order, serviceOrderStatuses))) {
      window.alert(`服务订单状态不能从“${order.status}”变更为“${status}”。`);
      setEditingOrderStatus(null);
      return;
    }
    const project = data.projects.find((item) => item.id === order.projectId);
    const customer = data.organizations.find((org) => org.id === order.customerOrgId || org.id === project?.customerOrgId);
    const now = today();
    const receivableAmount = order.receivableAmount ?? order.amount;
    const receivedAmount = order.receivedAmount ?? 0;
    if (status === "退款") {
      const refund = await requestPayment({
        orderNo: order.orderNo,
        receivable: receivableAmount,
        received: receivedAmount,
        targetStatus: status,
        mode: "refund",
        defaultCollectionAccount: order.collectionAccount,
      });
      if (!refund) {
        setEditingOrderStatus(null);
        return;
      }
      await commit(
        applyServiceRefundToData(data, order, refund, now),
        {
          action: "服务订单退款",
          targetType: "项目",
          targetName: project?.name ?? order.orderNo,
          operator: "当前用户",
          detail: paymentLogDetail({
            orderNo: order.orderNo,
            fromStatus: order.status,
            toStatus: "退款",
            payment: refund,
            receivedAmount: Math.max(0, receivedAmount - refund.amount),
            customerName: customer?.name,
          }),
        },
      );
      setEditingOrderStatus(null);
      return;
    }
    const payment = status === "部分付款" || status === "已付款" ? await paymentAmountPrompt(order.orderNo, receivableAmount, receivedAmount, status) : null;
    if ((status === "部分付款" || status === "已付款") && !payment) {
      setEditingOrderStatus(null);
      return;
    }
    const nextReceivedAmount = payment ? receivedAmount + payment.amount : receivedAmount;
    const normalizedStatus = payment && nextReceivedAmount >= receivableAmount ? "已付款" : status;
    const paymentOccurredAt = payment?.occurredAt || now;
    const nextTransactions = payment
      ? [servicePaymentTransaction(order, paymentOccurredAt, payment.amount, payment), ...data.transactions]
      : data.transactions;
    await commit(
      {
        ...data,
        serviceOrders: data.serviceOrders.map((item) => item.id === order.id ? {
          ...item,
          status: normalizedStatus,
          receivableAmount,
          receivedAmount: nextReceivedAmount,
          paymentMethod: payment?.paymentMethod ?? item.paymentMethod,
          collectionAccount: payment?.collectionAccount ?? item.collectionAccount,
          payerAccount: payment?.payerAccount ?? item.payerAccount,
          voucherName: payment?.voucherName ?? item.voucherName,
          voucherFileId: payment?.voucherFileId ?? item.voucherFileId,
          updatedAt: now,
          paidAt: payment ? paymentOccurredAt : item.paidAt,
          cancelledAt: normalizedStatus === "取消" ? now : item.cancelledAt,
        } : item),
        transactions: nextTransactions,
      },
      {
        action: payment ? "订单收款" : "修改服务订单状态",
        targetType: "项目",
        targetName: project?.name ?? order.orderNo,
        operator: "当前用户",
        detail: paymentLogDetail({
          orderNo: order.orderNo,
          fromStatus: order.status,
          toStatus: normalizedStatus,
          payment,
          receivedAmount: nextReceivedAmount,
          customerName: customer?.name,
        }),
      },
    );
  }

  async function createProject() {
    if (isCreatingProject) return;
    const projectType = projectTab;
    const product = projectType === "服务项目" ? data.products.find((item) => item.id === newProject.productId) : undefined;
    const selectedCustomer = data.organizations.find((org) => org.id === newProject.customerOrgId);
    const generatedServiceProjectName = projectType === "服务项目" && product && selectedCustomer
      ? `${selectedCustomer.name} - ${product.name} - ${formatYearMonth(newProject.serviceStartDate)}`
      : "";
    const selectedUsageUnit = data.organizations.find((org) => org.id === newProject.usageUnitOrgId);
    const projectCreatedAt = fromDateTimeLocalValue(newProject.projectAt);
    const generatedProductProjectName = projectType === "商品项目" && selectedCustomer
      ? buildProductProjectName({
        customerName: selectedCustomer.name,
        usageUnitName: selectedUsageUnit?.name,
        platform: newProject.sourcePlatform,
        remark: newProject.remark,
        projectAt: newProject.projectAt,
      })
      : "";
    if (!newProject.customerOrgId) return;
    if (projectType === "服务项目" && (!product || !selectedCustomer)) return;
    if (projectType === "服务项目" && !newProject.serviceSalesUserId) {
      window.alert("请选择业务员。");
      return;
    }
    if (projectType === "服务项目" && !newProject.onboardingPlatform) {
      window.alert("请选择服务平台。");
      return;
    }
    if (projectType === "服务项目" && !newProject.ownCompanyOrgId) {
      window.alert("请选择签约主体。");
      return;
    }
    const serviceCustomerKind = projectType === "服务项目" && newProject.onboardingPlatform === QINGHUICAI_PLATFORM
      ? (isServiceCustomerKind(newProject.serviceCustomerKind) ? newProject.serviceCustomerKind : "首次服务")
      : (isServiceCustomerKind(newProject.serviceCustomerKind) ? newProject.serviceCustomerKind : undefined);
    if (projectType === "服务项目" && !serviceCustomerKind) {
      window.alert("请选择首次服务或续费客户。");
      return;
    }
    const amountInput = newProject.salesUnitPrice.trim();
    const serviceAmount = amountInput === "" ? product?.quotePrice ?? 0 : Number(amountInput);
    if (!Number.isFinite(serviceAmount) || serviceAmount < 0) {
      window.alert("项目金额必须是大于或等于 0 的数字。");
      return;
    }
    const periodValue = parseOptionNumber(newProject.servicePeriodValue) || 1;
    const giftValue = Math.max(Number(newProject.serviceGiftValue) || 0, 0);
    const serviceEndDate = newProject.serviceType === "周期"
      ? calculateServiceEndDate(newProject.serviceStartDate, newProject.servicePeriodUnit, periodValue, newProject.serviceGiftUnit, giftValue)
      : newProject.serviceEndDate || undefined;
    if (editingProjectId) {
      const existing = data.projects.find((item) => item.id === editingProjectId);
      if (!existing || existing.type !== "服务项目" || !product) return;
      const now = new Date().toISOString();
      const updatedProject: Project = {
        ...existing,
        name: generatedServiceProjectName || existing.name,
        customerOrgId: newProject.customerOrgId,
        ownCompanyOrgId: newProject.ownCompanyOrgId || undefined,
        sourcePlatform: newProject.sourcePlatform,
        owner: selectedSalesUser?.name ?? existing.owner,
        totalAmount: serviceAmount,
        serviceProductId: product.id,
        serviceProductName: product.name,
        serviceType: newProject.serviceType,
        serviceCustomerKind,
        serviceStartDate: newProject.serviceStartDate,
        serviceEndDate,
        servicePeriodUnit: newProject.serviceType === "周期" ? newProject.servicePeriodUnit : undefined,
        servicePeriodValue: newProject.serviceType === "周期" ? periodValue : undefined,
        serviceGiftMonths: newProject.serviceType === "周期" && newProject.serviceGiftUnit === "月" ? giftValue : undefined,
        serviceGiftUnit: newProject.serviceType === "周期" ? newProject.serviceGiftUnit : undefined,
        serviceGiftValue: newProject.serviceType === "周期" ? giftValue : undefined,
        serviceSalesUserId: newProject.serviceSalesUserId,
        serviceSalesName: selectedSalesUser?.name,
        serviceRemark: newProject.serviceRemark || undefined,
        updatedAt: now,
      };
      const projectServiceOrders = [...data.serviceOrders]
        .filter((order) => order.projectId === existing.id)
        .sort((a, b) => a.createdAt.localeCompare(b.createdAt));
      const primaryOrderId = projectServiceOrders[0]?.id;
      const createdServiceOrder: ServiceOrder | null = primaryOrderId || !product ? null : {
        id: createId("svc"),
        projectId: existing.id,
        orderNo: `SV-${existing.projectNo}-01`,
        serviceId: product.id,
        customerOrgId: newProject.customerOrgId,
        amount: serviceAmount,
        receivableAmount: serviceAmount,
        receivedAmount: 0,
        status: "待付款",
        salesUserId: newProject.serviceSalesUserId || undefined,
        salesName: selectedSalesUser?.name,
        createdAt: now,
        updatedAt: now,
        note: newProject.serviceRemark || undefined,
      };
      const nextServiceOrders = [
        ...(createdServiceOrder ? [createdServiceOrder] : []),
        ...data.serviceOrders.map((order) => {
          if (order.projectId !== existing.id) return order;
          const received = Number(order.receivedAmount) || 0;
          const nextOrder = {
            ...order,
            serviceId: product.id,
            customerOrgId: newProject.customerOrgId,
            salesUserId: newProject.serviceSalesUserId || order.salesUserId,
            salesName: selectedSalesUser?.name ?? order.salesName,
            note: newProject.serviceRemark || order.note,
            updatedAt: now,
          };
          if (order.id !== primaryOrderId) return nextOrder;
          return {
            ...nextOrder,
            amount: serviceAmount,
            receivableAmount: Math.max(serviceAmount, received),
          };
        }),
      ];
      const nextProjectItems = data.projectItems.map((item) => {
        if (item.projectId !== existing.id || item.purchaseOrderId) return item;
        if (item.productId !== existing.serviceProductId && item.productId !== product.id) return item;
        return {
          ...item,
          productId: product.id,
          productName: product.name,
          actualPrice: serviceAmount,
        };
      });
      setIsCreatingProject(true);
      try {
        await commit(
          {
            ...data,
            projects: data.projects.map((item) => (item.id === existing.id ? updatedProject : item)),
            serviceOrders: nextServiceOrders,
            projectItems: nextProjectItems,
          },
          {
            action: "编辑项目",
            targetType: "项目",
            targetName: updatedProject.name,
            operator: "当前用户",
            detail: (() => {
              const changes = describeServiceProjectEditChanges(data, existing, updatedProject);
              if (createdServiceOrder) changes.push(`补建服务订单 ${createdServiceOrder.orderNo}`);
              return changes.length > 0 ? changes.join("；") : "无字段变更";
            })(),
          },
        );
        closeCreateProjectModal();
      } finally {
        setIsCreatingProject(false);
      }
      return;
    }

    const projectId = createId("pj");
    const projectNo = `XM${new Date().toISOString().slice(0, 10).replaceAll("-", "")}${String(data.projects.length + 1).padStart(3, "0")}`;
    const createdProject: Project = {
      id: projectId,
      projectNo,
      name: projectType === "服务项目" ? generatedServiceProjectName : generatedProductProjectName,
      type: projectType,
      customerOrgId: newProject.customerOrgId,
      usageUnitOrgId: newProject.usageUnitOrgId || undefined,
      ownCompanyOrgId: newProject.ownCompanyOrgId || undefined,
      sourcePlatform: newProject.sourcePlatform,
      platformOrderNo: newProject.platformOrderNo || undefined,
      owner: projectType === "服务项目" ? selectedSalesUser?.name ?? newProject.owner : newProject.owner || "当前用户",
      status: projectType === "服务项目" ? "入驻中" : "初始化",
      contractStatus: projectType === "服务项目" ? "待签" : "无需",
      paymentStatus: "待付款",
      purchaseStatus: projectType === "服务项目" ? "无需采购" : "待采购",
      invoiceStatus: "待开",
      reconcileStatus: projectType === "商品项目" ? DEFAULT_RECONCILE_STATUS : undefined,
      totalAmount: projectType === "服务项目" ? serviceAmount : 0,
      totalCost: 0,
      logisticsStatus: projectType === "商品项目" ? DEFAULT_LOGISTICS_STATUS : undefined,
      acceptanceStatus: projectType === "商品项目" ? DEFAULT_ACCEPTANCE_STATUS : undefined,
      deliveryStatus: projectType === "商品项目" ? DEFAULT_DELIVERY_STATUS : undefined,
      acceptanceRemark: projectType === "商品项目" ? "" : undefined,
      installationRemark: projectType === "商品项目" ? "" : undefined,
      serviceProductId: projectType === "服务项目" ? product?.id : undefined,
      serviceProductName: projectType === "服务项目" ? product?.name : undefined,
      serviceType: projectType === "服务项目" ? newProject.serviceType : undefined,
      serviceCustomerKind: projectType === "服务项目" ? serviceCustomerKind : undefined,
      serviceStartDate: projectType === "服务项目" ? newProject.serviceStartDate : undefined,
      serviceEndDate: projectType === "服务项目" ? serviceEndDate : undefined,
      servicePeriodUnit: projectType === "服务项目" && newProject.serviceType === "周期" ? newProject.servicePeriodUnit : undefined,
      servicePeriodValue: projectType === "服务项目" && newProject.serviceType === "周期" ? periodValue : undefined,
      serviceGiftMonths: projectType === "服务项目" && newProject.serviceType === "周期" && newProject.serviceGiftUnit === "月" ? giftValue : undefined,
      serviceGiftUnit: projectType === "服务项目" && newProject.serviceType === "周期" ? newProject.serviceGiftUnit : undefined,
      serviceGiftValue: projectType === "服务项目" && newProject.serviceType === "周期" ? giftValue : undefined,
      serviceSalesUserId: projectType === "服务项目" ? newProject.serviceSalesUserId : undefined,
      serviceSalesName: projectType === "服务项目" ? selectedSalesUser?.name : undefined,
      serviceOperatorUserId: projectType === "服务项目" ? currentUser.id : undefined,
      serviceOperatorName: projectType === "服务项目" ? currentUser.name : undefined,
      serviceRemark: projectType === "服务项目" ? newProject.serviceRemark || undefined : undefined,
      remark: projectType === "商品项目" ? newProject.remark.trim() || undefined : undefined,
      currentBlocker: projectType === "服务项目" ? "待平台入驻办理" : "待添加商品与渠道采购",
      createdAt: projectCreatedAt,
      updatedAt: projectCreatedAt,
    };
    const serviceOrder: ServiceOrder | null = projectType === "服务项目" && product
      ? {
          id: createId("svc"),
          projectId,
          orderNo: `SV-${projectNo}-01`,
          serviceId: product.id,
          customerOrgId: newProject.customerOrgId,
          amount: serviceAmount,
          receivableAmount: serviceAmount,
          receivedAmount: 0,
          status: "待付款",
          salesUserId: newProject.serviceSalesUserId || undefined,
          salesName: selectedSalesUser?.name,
          createdAt: projectCreatedAt,
          updatedAt: projectCreatedAt,
          note: newProject.serviceRemark || undefined,
        }
      : null;
    const projectItem = projectType === "服务项目" && product
      ? {
          id: createId("pi"),
          projectId,
          productId: product.id,
          productName: product.name,
          quantity: 1,
          actualPrice: serviceAmount,
          costPrice: 0,
        }
      : null;
    setIsCreatingProject(true);
    try {
      await commit(
        {
          ...data,
          projects: [createdProject, ...data.projects],
          projectItems: projectItem ? [projectItem, ...data.projectItems] : data.projectItems,
          serviceOrders: serviceOrder ? [serviceOrder, ...data.serviceOrders] : data.serviceOrders,
          purchaseOrders: data.purchaseOrders,
        },
        { action: "新建项目", targetType: "项目", targetName: createdProject.name, operator: "当前用户", detail: projectType === "商品项目" ? "商品项目基础信息已录入，待在项目详情补充订单、商品和渠道。" : `服务项目和服务订单已创建；操作员：${currentUser.name}` },
      );
      onSelectProject(projectId);
      closeCreateProjectModal();
      setNewProject({ ...newProject, name: "", customerOrgId: "", platformOrderNo: "", quantity: "1", serviceRemark: "", remark: "", projectAt: localDateTimeInputValue(), serviceCustomerKind: "" });
    } finally {
      setIsCreatingProject(false);
    }
  }

  async function deleteProject(project: Project) {
    const remainingProjects = data.projects.filter((item) => item.id !== project.id);
    await deleteCollectionItem("projects", project.id);
    await commit(
      {
        ...data,
        projects: remainingProjects,
        projectItems: data.projectItems.filter((item) => item.projectId !== project.id),
        salesOrders: data.salesOrders.filter((item) => item.projectId !== project.id),
        purchaseOrders: data.purchaseOrders.filter((item) => item.projectId !== project.id),
        serviceOrders: data.serviceOrders.filter((item) => item.projectId !== project.id),
        onboardingRecords: data.onboardingRecords.filter((item) => item.projectId !== project.id),
        projectReminders: data.projectReminders.filter((item) => item.projectId !== project.id),
        projectMemos: data.projectMemos.filter((item) => item.projectId !== project.id),
        invoices: data.invoices.map((invoice) => ({
          ...invoice,
          projectIds: (invoice.projectIds ?? (invoice.projectId ? [invoice.projectId] : [])).filter((id) => id !== project.id),
          projectId: invoice.projectId === project.id ? undefined : invoice.projectId,
        })).filter((invoice) => invoice.projectId !== project.id),
        transactions: data.transactions.filter((item) => item.projectId !== project.id),
      },
      { action: "删除项目", targetType: "项目", targetName: project.name, operator: "当前用户", detail: "开发环境允许物理删除，正式发布后隐藏入口" },
    );
    onSelectProject(remainingProjects[0]?.id ?? "");
  }

  function updateOrderProduct(productId: string) {
    const product = data.products.find((item) => item.id === productId);
    const supplierPrice = latestSupplierPrice(data.supplierPrices, productId, orderDraft.supplierOrgId);
    const remaining = activeProject && productDetailTab === "purchase"
      ? projectPurchaseRemainingQuantity(data, activeProject.id, productId)
      : undefined;
    setOrderDraft({
      ...orderDraft,
      productId,
      quantity: remaining !== undefined ? String(remaining > 0 ? remaining : 1) : orderDraft.quantity,
      salesUnitPrice: product?.quotePrice ? String(product.quotePrice) : "",
      purchaseUnitPrice: supplierPrice?.purchasePrice ? String(supplierPrice.purchasePrice) : product?.costPrice ? String(product.costPrice) : "",
    });
  }

  function updateOrderSupplier(supplierOrgId: string) {
    const supplierPrice = latestSupplierPrice(data.supplierPrices, orderDraft.productId, supplierOrgId);
    setOrderDraft({
      ...orderDraft,
      supplierOrgId,
      purchaseUnitPrice: supplierPrice?.purchasePrice ? String(supplierPrice.purchasePrice) : orderDraft.purchaseUnitPrice,
    });
  }

  function addSalesOrderDraftItem() {
    const product = data.products.find((item) => item.id === orderDraft.productId);
    if (!product) return;
    const quantity = Number(orderDraft.quantity) || 1;
    const unitPrice = Number(orderDraft.salesUnitPrice) || product.quotePrice;
    setSalesOrderDraftItems([
      ...salesOrderDraftItems,
      { productId: product.id, productName: product.name, quantity, unitPrice },
    ]);
    setOrderDraft({ ...orderDraft, quantity: "1", salesUnitPrice: "" });
  }

  async function addSalesOrder(options?: {
    extraProducts?: Product[];
    items?: Array<{ productId: string; productName: string; quantity: number; unitPrice: number }>;
    keepDraft?: boolean;
    targetOrderId?: string;
    createNew?: boolean;
  }) {
    if (!activeProject) return;
    if (activeProject.status === "已完成") {
      window.alert("已完成的项目不可添加销售订单。");
      return;
    }
    const workingProducts = options?.extraProducts ? [...options.extraProducts, ...data.products] : data.products;
    const appending = Boolean(options?.targetOrderId) && !options?.createNew;
    let draftItems = options?.items ?? (appending ? [] : salesOrderDraftItems);
    if (draftItems.length === 0) {
      const compose = appending && options?.targetOrderId ? salesComposeDraft(options.targetOrderId) : orderDraft;
      const product = workingProducts.find((item) => item.id === compose.productId);
      if (!product) {
        window.alert(appending ? "请选择要追加到本单的商品。" : "请选择商品后再创建销售订单。");
        return;
      }
      draftItems = [{
        productId: product.id,
        productName: product.name,
        quantity: Number(compose.quantity) || 1,
        unitPrice: Number("salesUnitPrice" in compose ? compose.salesUnitPrice : orderDraft.salesUnitPrice) || product.quotePrice,
      }];
    }
    const existingOrder = appending
      ? salesOrders.find((item) => item.id === options?.targetOrderId)
      : undefined;
    if (appending && !existingOrder) {
      window.alert("未找到要追加的销售订单。");
      return;
    }
    if (existingOrder) {
      const blocked = salesOrderItemsEditBlockReason(data, existingOrder);
      if (blocked) {
        window.alert(blocked);
        return;
      }
    }
    const addedAmount = draftItems.reduce((sum, item) => sum + item.unitPrice * item.quantity, 0);
    const orderId = existingOrder?.id ?? createId("so");
    const orderNo = existingOrder?.orderNo ?? nextPrefixedOrderNo(
      data.salesOrders.filter((item) => item.projectId === activeProject.id).map((item) => item.orderNo),
      `SO-${activeProject.projectNo}-`,
    );
    const now = today();
    const newItems: ProjectItem[] = draftItems.map((draftItem) => {
      const product = workingProducts.find((entry) => entry.id === draftItem.productId);
      return {
        id: createId("pi"),
        projectId: activeProject.id,
        salesOrderId: orderId,
        productId: draftItem.productId,
        productName: draftItem.productName,
        quantity: draftItem.quantity,
        actualPrice: draftItem.unitPrice,
        costPrice: product?.costPrice ?? 0,
      };
    });
    const nextProjectItems = [...newItems, ...data.projectItems];
    const lineAmount = salesOrderItemsAmount(salesOrderLineItems(nextProjectItems, orderId));
    const order: SalesOrder = existingOrder ? {
      ...existingOrder,
      amount: lineAmount,
      receivableAmount: lineAmount,
      platformOrderNo: orderDraft.platformOrderNo || existingOrder.platformOrderNo,
      note: orderDraft.note || existingOrder.note,
      updatedAt: now,
    } : {
      id: orderId,
      projectId: activeProject.id,
      orderNo,
      platform: activeProject.sourcePlatform,
      platformOrderNo: orderDraft.platformOrderNo || activeProject.platformOrderNo,
      customerOrgId: activeProject.customerOrgId,
      ownCompanyOrgId: activeProject.ownCompanyOrgId,
      amount: lineAmount,
      receivableAmount: lineAmount,
      receivedAmount: 0,
      status: "待付款",
      createdAt: now,
      updatedAt: now,
      note: orderDraft.note || undefined,
    };
    const nextSalesOrders = existingOrder
      ? data.salesOrders.map((item) => item.id === existingOrder.id ? order : item)
      : [order, ...data.salesOrders];
    const base = { ...data, products: workingProducts, salesOrders: nextSalesOrders, projectItems: nextProjectItems };
    const synced = applyProductProjectSync(base, activeProject.id);
    await commit(
      synced.data,
      { action: existingOrder ? "追加销售订单商品" : "新增销售订单", targetType: "项目", targetName: activeProject.name, operator: "当前用户", detail: `${orderNo} / 新增 ${money(addedAmount)} / ${newItems.length} 个商品${synced.autoDetail ? `；${synced.autoDetail}` : ""}` },
    );
    if (options?.targetOrderId) {
      setSalesOrderComposeDrafts((current) => ({
        ...current,
        [options.targetOrderId!]: {
          productId: current[options.targetOrderId!]?.productId ?? "",
          quantity: "1",
          salesUnitPrice: "",
          directProductName: "",
          directPlatformPrice: "",
        },
      }));
      return;
    }
    if (!options?.keepDraft) {
      setSalesOrderDraftItems([]);
      setOrderDraft({ ...orderDraft, quantity: "1", platformOrderNo: "", note: "", directProductName: "", directPlatformPrice: "" });
    } else {
      setOrderDraft({ ...orderDraft, directProductName: "", directPlatformPrice: "" });
    }
  }

  function salesComposeDraft(orderId: string) {
    return salesOrderComposeDrafts[orderId] ?? {
      productId: "",
      quantity: "1",
      salesUnitPrice: "",
      directProductName: "",
      directPlatformPrice: "",
    };
  }

  function patchSalesComposeDraft(orderId: string, patch: Partial<{
    productId: string;
    quantity: string;
    salesUnitPrice: string;
    directProductName: string;
    directPlatformPrice: string;
  }>) {
    setSalesOrderComposeDrafts((current) => ({
      ...current,
      [orderId]: { ...salesComposeDraft(orderId), ...patch },
    }));
  }

  function updateSalesComposeProduct(orderId: string, productId: string) {
    const product = data.products.find((item) => item.id === productId);
    patchSalesComposeDraft(orderId, {
      productId,
      salesUnitPrice: product?.quotePrice ? String(product.quotePrice) : "",
    });
  }

  async function appendCatalogProductToSalesOrder(order: SalesOrder) {
    const draft = salesComposeDraft(order.id);
    const product = data.products.find((item) => item.id === draft.productId);
    if (!product) {
      window.alert("请选择要追加的商品。");
      return;
    }
    await addSalesOrder({
      items: [{
        productId: product.id,
        productName: product.name,
        quantity: Number(draft.quantity) || 1,
        unitPrice: Number(draft.salesUnitPrice) || product.quotePrice,
      }],
      targetOrderId: order.id,
    });
  }

  async function addDirectProjectProduct(targetOrderId?: string) {
    if (!activeProject) return;
    const draft = targetOrderId ? salesComposeDraft(targetOrderId) : orderDraft;
    const name = (targetOrderId ? draft.directProductName : orderDraft.directProductName).trim();
    const platformPrice = Number(targetOrderId ? draft.directPlatformPrice : orderDraft.directPlatformPrice);
    if (!name) {
      window.alert("请填写商品名称。");
      return;
    }
    if (!Number.isFinite(platformPrice) || platformPrice < 0) {
      window.alert("平台价必须是大于或等于 0 的数字。");
      return;
    }
    const product = buildProjectScopedProduct({
      id: createId("prd"),
      projectId: activeProject.id,
      projectNo: activeProject.projectNo,
      name,
      platformPrice,
      createdAt: new Date().toISOString(),
    });
    await addSalesOrder({
      extraProducts: [product],
      items: [{
        productId: product.id,
        productName: product.name,
        quantity: Number(targetOrderId ? draft.quantity : orderDraft.quantity) || 1,
        unitPrice: platformPrice,
      }],
      keepDraft: !targetOrderId && salesOrderDraftItems.length > 0,
      targetOrderId,
      createNew: !targetOrderId,
    });
  }

  function salesQtyWouldUndercutPurchase(nextItems: AppData["projectItems"], productId: string, productName: string) {
    if (!activeProject) return "";
    const nextData = { ...data, projectItems: nextItems };
    const salesQty = projectSalesQuantityForProduct(nextData, activeProject.id, productId);
    const purchasedQty = projectPurchasedQuantityForProduct(nextData, activeProject.id, productId);
    if (salesQty < purchasedQty) {
      return `商品「${productName}」已采购 ${purchasedQty}，调整后销售数量为 ${salesQty}，不能小于已采购数量。`;
    }
    return "";
  }

  async function commitSalesOrderItems(order: SalesOrder, nextItems: AppData["projectItems"], action: string, detail: string) {
    if (!activeProject) return;
    const now = today();
    const lineAmount = salesOrderItemsAmount(salesOrderLineItems(nextItems, order.id));
    const nextSalesOrders = data.salesOrders.map((item) => item.id === order.id
      ? { ...item, amount: lineAmount, receivableAmount: lineAmount, updatedAt: now }
      : item);
    const synced = applyProductProjectSync({ ...data, salesOrders: nextSalesOrders, projectItems: nextItems }, activeProject.id);
    await commit(
      synced.data,
      { action, targetType: "项目", targetName: activeProject.name, operator: "当前用户", detail: `${order.orderNo} / ${detail}${synced.autoDetail ? `；${synced.autoDetail}` : ""}` },
    );
  }

  async function updateSalesOrderLineQuantity(order: SalesOrder, itemId: string, rawQuantity: string) {
    const blocked = salesOrderItemsEditBlockReason(data, order);
    if (blocked) {
      window.alert(blocked);
      return;
    }
    const quantity = Number(rawQuantity);
    if (!Number.isFinite(quantity) || quantity <= 0) {
      window.alert("数量必须大于 0。若要去掉该商品，请点移除。");
      return;
    }
    const current = data.projectItems.find((item) => item.id === itemId);
    if (!current || current.salesOrderId !== order.id || current.purchaseOrderId) return;
    if (Number(current.quantity) === quantity) return;
    const nextItems = data.projectItems.map((item) => item.id === itemId ? { ...item, quantity } : item);
    const qtyError = salesQtyWouldUndercutPurchase(nextItems, current.productId, current.productName);
    if (qtyError) {
      window.alert(qtyError);
      return;
    }
    await commitSalesOrderItems(order, nextItems, "修改销售订单数量", `${current.productName} ${current.quantity} -> ${quantity}`);
  }

  async function removeSalesOrderLine(order: SalesOrder, itemId: string) {
    const blocked = salesOrderItemsEditBlockReason(data, order);
    if (blocked) {
      window.alert(blocked);
      return;
    }
    const current = data.projectItems.find((item) => item.id === itemId);
    if (!current || current.salesOrderId !== order.id || current.purchaseOrderId) return;
    const remaining = salesOrderLineItems(data.projectItems, order.id).filter((item) => item.id !== itemId);
    if (remaining.length === 0 && !window.confirm(`移除后 ${order.orderNo} 将没有商品，确定移除「${current.productName}」吗？`)) return;
    if (remaining.length > 0 && !window.confirm(`确定从 ${order.orderNo} 移除「${current.productName}」吗？`)) return;
    const nextItems = data.projectItems.filter((item) => item.id !== itemId);
    const qtyError = salesQtyWouldUndercutPurchase(nextItems, current.productId, current.productName);
    if (qtyError) {
      window.alert(qtyError);
      return;
    }
    // 部分保存不会把未出现的 projectItems 当成删除，必须走单条删除接口。
    await deleteCollectionItem("projectItems", itemId);
    await commitSalesOrderItems(order, nextItems, "移除销售订单商品", `移除 ${current.productName}`);
  }

  function blankSalesChannelLine(): SalesChannelLineDraft {
    return createBlankSalesChannelLine(suppliers[0]?.id ?? "");
  }

  function openSalesProductDraft(line?: SalesChannelLineDraft) {
    const next = line ?? blankSalesChannelLine();
    setSalesProductMode(next.directProductName.trim() ? "quick" : "catalog");
    setSalesProductDraft(next);
  }

  function switchSalesProductMode(mode: "catalog" | "quick") {
    setSalesProductMode(mode);
    if (mode === "catalog") patchSalesProductDraft({ directProductName: "", directPlatformPrice: "" });
    else patchSalesProductDraft({ productId: "" });
  }

  function openNewSalesOrderComposer() {
    setSalesComposer({
      orderedAt: defaultOrderTimeFromProject(activeProject),
      platformOrderNo: "",
      note: "",
      ...purchaserDraftFromProject(data, activeProject),
      lines: [],
    });
    setSalesProductDraft(null);
  }

  function openAppendSalesComposer(order: SalesOrder) {
    const blocked = salesOrderItemsEditBlockReason(data, order);
    if (blocked) {
      window.alert(blocked);
      return;
    }
    setSalesOrderPanel(null);
    setSalesComposer({
      targetOrderId: order.id,
      orderedAt: toDateTimeLocalInput(order.createdAt),
      platformOrderNo: order.platformOrderNo ?? "",
      note: order.note ?? "",
      purchaserCompany: order.purchaserCompany ?? "",
      purchaserAddress: order.purchaserAddress ?? "",
      purchaserName: order.purchaserName ?? "",
      purchaserPhone: order.purchaserPhone ?? "",
      lines: [],
    });
    openSalesProductDraft();
  }

  function patchSalesProductDraft(patch: Partial<SalesChannelLineDraft>) {
    setSalesProductDraft((current) => {
      if (!current) return current;
      const next = { ...current, ...patch };
      if (patch.productId) {
        const product = data.products.find((item) => item.id === patch.productId);
        next.salesUnitPrice = product?.quotePrice ? String(product.quotePrice) : "";
        const supplierPrice = next.supplierOrgId
          ? latestSupplierPrice(data.supplierPrices, patch.productId, next.supplierOrgId)
          : undefined;
        next.purchaseUnitPrice = supplierPrice?.purchasePrice ? String(supplierPrice.purchasePrice) : (product?.costPrice ? String(product.costPrice) : next.purchaseUnitPrice);
      }
      if (patch.supplierOrgId !== undefined) {
        const productId = next.productId;
        const supplierPrice = productId
          ? latestSupplierPrice(data.supplierPrices, productId, patch.supplierOrgId)
          : undefined;
        next.purchaseUnitPrice = supplierPrice?.purchasePrice ? String(supplierPrice.purchasePrice) : next.purchaseUnitPrice;
        next.purchaseOrderId = "";
      }
      return next;
    });
  }

  function confirmSalesProductDraft() {
    if (!salesComposer || !salesProductDraft) return;
    const isDirect = salesProductMode === "quick";
    const draft = isDirect
      ? { ...salesProductDraft, productId: "" }
      : { ...salesProductDraft, directProductName: "", directPlatformPrice: "" };
    if (isDirect && !draft.directProductName.trim()) {
      window.alert("请填写快捷商品名称。");
      return;
    }
    if (!isDirect && !draft.productId) {
      window.alert("请选择销售商品。");
      return;
    }
    if (!draft.supplierOrgId) {
      window.alert("请选择渠道供应商，销售商品需要关联采购订单。");
      return;
    }
    const quantity = Number(draft.quantity);
    if (!Number.isFinite(quantity) || quantity <= 0) {
      window.alert("数量必须大于 0。");
      return;
    }
    if (isDirect) {
      const platformPrice = Number(draft.directPlatformPrice);
      if (!Number.isFinite(platformPrice) || platformPrice < 0) {
        window.alert("快捷商品的平台价必须是大于或等于 0 的数字。");
        return;
      }
    }
    if (draft.purchaseOrderId) {
      const po = purchaseOrders.find((item) => item.id === draft.purchaseOrderId);
      if (!po || po.supplierOrgId !== draft.supplierOrgId || !canAppendPurchaseOrderItems(po)) {
        window.alert("只能追加到同一供应商的「待下单/草稿」采购订单。");
        return;
      }
    }
    const nextLines = salesComposer.lines.some((item) => item.key === draft.key)
      ? salesComposer.lines.map((item) => item.key === draft.key ? draft : item)
      : [...salesComposer.lines, draft];
    setSalesComposer({ ...salesComposer, lines: nextLines });
    setSalesProductDraft(null);
  }

  function salesLineChannelText(item: ProjectItem) {
    const po = data.purchaseOrders.find((order) => order.id === item.sourcePurchaseOrderId);
    if (!po) return "未关联渠道";
    const supplier = data.organizations.find((org) => org.id === (item.supplierOrgId || po.supplierOrgId));
    const purchaseQty = data.projectItems
      .filter((entry) => entry.purchaseOrderId === po.id && entry.productId === item.productId)
      .reduce((sum, entry) => sum + (Number(entry.quantity) || 0), 0);
    return `${supplier?.name || "渠道"} / ${po.orderNo} · 采购 ${purchaseQty}`;
  }

  function composerLineLabel(line: SalesChannelLineDraft) {
    const product = data.products.find((item) => item.id === line.productId);
    const name = line.directProductName.trim() || product?.name || "未选择商品";
    const supplier = data.organizations.find((org) => org.id === line.supplierOrgId);
    const po = purchaseOrders.find((item) => item.id === line.purchaseOrderId);
    return `${name} × ${line.quantity || 1} · ${supplier?.name || "未选渠道"} / ${po?.orderNo || "新建采购单"}`;
  }

  async function submitSalesComposer() {
    if (!activeProject || !salesComposer) return;
    const ok = await submitSalesOrderComposer({
      data,
      commit,
      project: activeProject,
      composer: salesComposer,
      latestSupplierPrice,
    });
    if (ok) {
      setSalesComposer(null);
      setSalesProductDraft(null);
    }
  }

  async function addPurchaseOrder(appendToExisting = false) {
    if (!activeProject || activeProject.type !== "商品项目") return;
    if (activeProject.status === "已完成") {
      window.alert("已完成的项目不可添加采购订单。");
      return;
    }
    if (purchaseProductOptions.length === 0) {
      window.alert(purchaseValidateAgainstSales
        ? "请先在销售订单中添加商品，或关闭「按销售校验」后选择打包商品。"
        : "当前没有可采购的实体商品。");
      return;
    }
    if (!orderDraft.supplierOrgId) {
      window.alert("请选择供应商。");
      return;
    }
    let draftItems = purchaseOrderDraftItems;
    if (draftItems.length === 0) {
      const product = data.products.find((item) => item.id === orderDraft.productId);
      if (!product) {
        window.alert("请选择采购商品，或先「加入商品」后再创建订单。");
        return;
      }
      if (purchaseValidateAgainstSales && !projectSalesProductIds.has(product.id)) {
        window.alert("采购商品必须来自当前项目的销售订单。关闭「按销售校验」后可添加打包类商品。");
        return;
      }
      const quantity = Number(orderDraft.quantity) || 1;
      const supplierPrice = latestSupplierPrice(data.supplierPrices, product.id, orderDraft.supplierOrgId);
      const unitPrice = Number(orderDraft.purchaseUnitPrice) || supplierPrice?.purchasePrice || product.costPrice;
      draftItems = [{
        productId: product.id,
        productName: product.name,
        quantity,
        unitPrice,
        supplierPriceId: supplierPrice?.id,
      }];
    }
    if (purchaseValidateAgainstSales) {
      const qtyError = validatePurchaseDraftQuantities(activeProject.id, draftItems);
      if (qtyError) {
        window.alert(qtyError);
        return;
      }
    }
    const appendable = appendToExisting
      ? purchaseOrders.find((order) =>
        order.supplierOrgId === orderDraft.supplierOrgId
        && (order.status === "待下单" || order.status === "草稿"),
      )
      : undefined;
    if (appendToExisting && !appendable) {
      window.alert("未找到可追加的同供应商「待下单/草稿」采购订单。");
      return;
    }
    const lines = draftItems.map((item) => ({
      productId: item.productId,
      productName: item.productName,
      quantity: item.quantity,
      supplierOrgId: orderDraft.supplierOrgId,
      unitPrice: item.unitPrice,
      supplierPriceId: item.supplierPriceId,
      note: orderDraft.note || undefined,
    }));
    const result = appendable
      ? appendProductsToPurchaseOrder(activeProject, appendable, lines)
      : buildGroupedPurchaseOrders(activeProject, lines, purchaseOrders.length, data, fromDateTimeLocalValue(purchaseOrderedAt));
    const synced = applyProductProjectSync(result.data, activeProject.id);
    await commit(
      synced.data,
      {
        action: appendable ? "追加采购订单商品" : "新增采购订单",
        targetType: "项目",
        targetName: activeProject.name,
        operator: "当前用户",
        detail: `${result.orderNos.join("、")} / ${money(result.totalAmount)} / ${draftItems.length} 个商品${synced.autoDetail ? `；${synced.autoDetail}` : ""}`,
      },
    );
    setPurchaseOrderDraftItems([]);
    setOrderDraft({ ...orderDraft, quantity: "1", note: "" });
    if (!appendable) setPurchaseOrderedAt(defaultOrderTimeFromProject(activeProject));
  }

  function validatePurchaseDraftQuantities(
    projectId: string,
    draftItems: Array<{ productId: string; productName: string; quantity: number }>,
  ) {
    const draftQtyByProduct = new Map<string, { name: string; qty: number }>();
    draftItems.forEach((item) => {
      const current = draftQtyByProduct.get(item.productId);
      draftQtyByProduct.set(item.productId, {
        name: item.productName,
        qty: (current?.qty ?? 0) + (Number(item.quantity) || 0),
      });
    });
    for (const [productId, draft] of draftQtyByProduct) {
      const salesQty = projectSalesQuantityForProduct(data, projectId, productId);
      const purchasedQty = projectPurchasedQuantityForProduct(data, projectId, productId);
      const remaining = Math.max(0, salesQty - purchasedQty);
      if (draft.qty > remaining) {
        return `采购数量超出销售可采数量。\n商品：${draft.name}\n销售数量：${salesQty}\n已采购：${purchasedQty}\n本次合计：${draft.qty}\n最多可采：${remaining}`;
      }
    }
    return "";
  }

  function addPurchaseOrderDraftItem() {
    if (!activeProject) return;
    const product = data.products.find((item) => item.id === orderDraft.productId);
    if (!product) return;
    if (purchaseValidateAgainstSales && !projectSalesProductIds.has(product.id)) {
      window.alert("采购商品必须来自当前项目的销售订单。关闭「按销售校验」后可添加打包类商品。");
      return;
    }
    if (!orderDraft.supplierOrgId) {
      window.alert("请先选择供应商，同一采购订单的商品需同一供应商。");
      return;
    }
    const quantity = Number(orderDraft.quantity) || 1;
    const supplierPrice = latestSupplierPrice(data.supplierPrices, product.id, orderDraft.supplierOrgId);
    const unitPrice = Number(orderDraft.purchaseUnitPrice) || supplierPrice?.purchasePrice || product.costPrice;
    const nextDraft = [
      ...purchaseOrderDraftItems,
      {
        productId: product.id,
        productName: product.name,
        quantity,
        unitPrice,
        supplierPriceId: supplierPrice?.id,
      },
    ];
    if (purchaseValidateAgainstSales) {
      const qtyError = validatePurchaseDraftQuantities(activeProject.id, nextDraft);
      if (qtyError) {
        window.alert(qtyError);
        return;
      }
    }
    setPurchaseOrderDraftItems(nextDraft);
    setOrderDraft({ ...orderDraft, quantity: "1", purchaseUnitPrice: "" });
  }

  function buildPurchaseSplitLinesFromSales() {
    if (!activeProject) return [];
    const salesItems = data.projectItems.filter((item) =>
      item.projectId === activeProject.id
      && item.salesOrderId
      && !isPurchaseLineItem(item),
    );
    const aggregated = new Map<string, { productId: string; productName: string; salesQty: number }>();
    salesItems.forEach((item) => {
      const current = aggregated.get(item.productId);
      aggregated.set(item.productId, {
        productId: item.productId,
        productName: item.productName,
        salesQty: (current?.salesQty ?? 0) + (Number(item.quantity) || 0),
      });
    });
    return Array.from(aggregated.values()).flatMap((item) => {
      const remaining = projectPurchaseRemainingQuantity(data, activeProject.id, item.productId);
      if (remaining <= 0) return [];
      const product = data.products.find((entry) => entry.id === item.productId);
      const supplierOrgId = suppliers[0]?.id || "";
      const supplierPrice = supplierOrgId ? latestSupplierPrice(data.supplierPrices, item.productId, supplierOrgId) : undefined;
      return [{
        key: createId("psplit"),
        productId: item.productId,
        productName: item.productName,
        quantity: String(remaining),
        supplierOrgId,
        purchaseUnitPrice: String(supplierPrice?.purchasePrice || product?.costPrice || 0),
      }];
    });
  }

  function togglePurchaseSplitMode(enabled: boolean) {
    if (!enabled) {
      setPurchaseSplitMode(false);
      setPurchaseSplitLines([]);
      return;
    }
    const lines = buildPurchaseSplitLinesFromSales();
    if (lines.length === 0) {
      window.alert("当前项目暂无销售订单商品，无法按销售拆单。请先在销售订单中添加商品。");
      setPurchaseSplitMode(false);
      setPurchaseSplitLines([]);
      return;
    }
    setPurchaseSplitMode(true);
    setPurchaseSplitLines(lines);
  }

  function updatePurchaseSplitLine(key: string, patch: Partial<{ productId: string; quantity: string; supplierOrgId: string; purchaseUnitPrice: string }>) {
    setPurchaseSplitLines((current) => current.map((line) => {
      if (line.key !== key) return line;
      const next = { ...line, ...patch };
      if (patch.productId !== undefined) {
        const product = data.products.find((item) => item.id === patch.productId);
        next.productName = product?.name || line.productName;
        const supplierOrgId = next.supplierOrgId || suppliers[0]?.id || "";
        next.supplierOrgId = supplierOrgId;
        const supplierPrice = supplierOrgId ? latestSupplierPrice(data.supplierPrices, patch.productId, supplierOrgId) : undefined;
        next.purchaseUnitPrice = supplierPrice?.purchasePrice
          ? String(supplierPrice.purchasePrice)
          : (product?.costPrice ? String(product.costPrice) : "");
        if (activeProject) {
          const remaining = projectPurchaseRemainingQuantity(data, activeProject.id, patch.productId);
          next.quantity = String(remaining > 0 ? remaining : 1);
        }
      }
      if (patch.supplierOrgId !== undefined) {
        const supplierPrice = latestSupplierPrice(data.supplierPrices, next.productId, patch.supplierOrgId);
        const product = data.products.find((item) => item.id === next.productId);
        next.purchaseUnitPrice = supplierPrice?.purchasePrice
          ? String(supplierPrice.purchasePrice)
          : (product?.costPrice ? String(product.costPrice) : next.purchaseUnitPrice);
      }
      return next;
    }));
  }

  function removePurchaseSplitLine(key: string) {
    setPurchaseSplitLines((current) => current.filter((line) => line.key !== key));
  }

  function addPurchaseSplitLine(productId?: string) {
    const product = data.products.find((item) => item.id === (productId || purchaseProductOptions[0]?.id));
    if (!product) {
      window.alert("当前项目销售订单中暂无可采购商品，请先添加销售商品。");
      return;
    }
    const supplierOrgId = suppliers[0]?.id || "";
    const supplierPrice = supplierOrgId ? latestSupplierPrice(data.supplierPrices, product.id, supplierOrgId) : undefined;
    setPurchaseSplitLines((current) => [
      ...current,
      {
        key: createId("psplit"),
        productId: product.id,
        productName: product.name,
        quantity: "1",
        supplierOrgId,
        purchaseUnitPrice: String(supplierPrice?.purchasePrice || product.costPrice || 0),
      },
    ]);
    if (!purchaseSplitMode) setPurchaseSplitMode(true);
  }

  function buildGroupedPurchaseOrders(
    project: Project,
    lines: Array<{
      productId: string;
      productName: string;
      quantity: number;
      supplierOrgId: string;
      unitPrice: number;
      supplierPriceId?: string;
      note?: string;
    }>,
    startIndex: number,
    sourceData: AppData = data,
    orderedAt?: string,
  ) {
    return createGroupedPurchaseOrders(project, lines, startIndex, sourceData, orderedAt);
  }

  function appendProductsToPurchaseOrder(
    project: Project,
    order: PurchaseOrder,
    lines: Array<{
      productId: string;
      productName: string;
      quantity: number;
      supplierOrgId: string;
      unitPrice: number;
      supplierPriceId?: string;
      note?: string;
    }>,
    sourceData: AppData = data,
  ) {
    return appendLinesToPurchaseOrder(project, order, lines, sourceData, orderDraft.note);
  }

  function buildPurchaseOrders(
    project: Project,
    lines: Array<{
      productId: string;
      productName: string;
      quantity: number;
      supplierOrgId: string;
      unitPrice: number;
      supplierPriceId?: string;
      note?: string;
    }>,
    startIndex: number,
    orderedAt?: string,
  ) {
    // 拆单模式：按行各自成单（不同渠道）；同供应商可多商品时走 buildGroupedPurchaseOrders
    return buildGroupedPurchaseOrders(project, lines, startIndex, data, orderedAt);
  }

  async function addSplitPurchaseOrders() {
    if (!activeProject || activeProject.type !== "商品项目") return;
    if (activeProject.status === "已完成") {
      window.alert("已完成的项目不可添加采购订单。");
      return;
    }
    if (purchaseSplitLines.length === 0) {
      window.alert("请至少保留一行拆单商品。");
      return;
    }
    const invalid = purchaseSplitLines.find((line) => !line.supplierOrgId || !(Number(line.quantity) > 0));
    if (invalid) {
      window.alert("请为每行拆单商品选择供应商，并填写大于 0 的数量。");
      return;
    }
    if (purchaseValidateAgainstSales) {
      const draftQtyByProduct = new Map<string, { name: string; qty: number }>();
      purchaseSplitLines.forEach((line) => {
        const current = draftQtyByProduct.get(line.productId);
        draftQtyByProduct.set(line.productId, {
          name: line.productName,
          qty: (current?.qty ?? 0) + (Number(line.quantity) || 0),
        });
      });
      for (const [productId, draft] of draftQtyByProduct) {
        const salesQty = projectSalesQuantityForProduct(data, activeProject.id, productId);
        const purchasedQty = projectPurchasedQuantityForProduct(data, activeProject.id, productId);
        const remaining = Math.max(0, salesQty - purchasedQty);
        if (draft.qty > remaining) {
          window.alert(`采购数量超出销售可采数量。\n商品：${draft.name}\n销售数量：${salesQty}\n已采购：${purchasedQty}\n本次填写合计：${draft.qty}\n最多可采：${remaining}`);
          return;
        }
      }
    }
    const lines = purchaseSplitLines.map((line) => {
      const product = data.products.find((item) => item.id === line.productId);
      const supplierPrice = latestSupplierPrice(data.supplierPrices, line.productId, line.supplierOrgId);
      const unitPrice = Number(line.purchaseUnitPrice) || supplierPrice?.purchasePrice || product?.costPrice || 0;
      return {
        productId: line.productId,
        productName: line.productName,
        quantity: Number(line.quantity) || 1,
        supplierOrgId: line.supplierOrgId,
        unitPrice,
        supplierPriceId: supplierPrice?.id,
      };
    });
    const result = buildPurchaseOrders(activeProject, lines, purchaseOrders.length, fromDateTimeLocalValue(purchaseOrderedAt));
    const synced = applyProductProjectSync(result.data, activeProject.id);
    await commit(
      synced.data,
      {
        action: "按销售商品拆单采购",
        targetType: "项目",
        targetName: activeProject.name,
        operator: "当前用户",
        detail: `生成 ${result.orderNos.length} 笔：${result.orderNos.join("、")} / ${money(result.totalAmount)}${synced.autoDetail ? `；${synced.autoDetail}` : ""}`,
      },
    );
    setPurchaseSplitMode(false);
    setPurchaseSplitLines([]);
    setPurchaseOrderedAt(defaultOrderTimeFromProject(activeProject));
  }

  async function deletePurchaseOrder(order: PurchaseOrder) {
    await deletePurchaseOrderRecord({ data, commit, order });
  }

  async function updateSalesOrderStatus(order: SalesOrder, status: SalesOrder["status"]) {
    if (!canTransition(order.status, status, getAllowedSalesOrderStatuses(order, salesOrderStatuses))) {
      window.alert(`销售订单状态不能从“${order.status}”变更为“${status}”。`);
      setEditingOrderStatus(null);
      return;
    }
    const project = data.projects.find((item) => item.id === order.projectId);
    const now = today();
    const receivableAmount = order.receivableAmount ?? order.amount;
    const receivedAmount = order.receivedAmount ?? 0;
    const payment = status === "部分付款" || status === "已付款" ? await paymentAmountPrompt(order.orderNo, receivableAmount, receivedAmount, status) : null;
    if ((status === "部分付款" || status === "已付款") && !payment) {
      setEditingOrderStatus(null);
      return;
    }
    const nextReceivedAmount = payment ? receivedAmount + payment.amount : receivedAmount;
    const normalizedStatus = payment && nextReceivedAmount >= receivableAmount ? "已付款" : status;
    const paymentOccurredAt = payment?.occurredAt || now;
    const nextSalesOrders = data.salesOrders.map((item) => item.id === order.id ? {
      ...item,
      status: normalizedStatus,
      receivableAmount,
      receivedAmount: nextReceivedAmount,
      paymentMethod: payment?.paymentMethod ?? item.paymentMethod,
      collectionAccount: payment?.collectionAccount ?? item.collectionAccount,
      payerAccount: payment?.payerAccount ?? item.payerAccount,
      voucherName: payment?.voucherName ?? item.voucherName,
      voucherFileId: payment?.voucherFileId ?? item.voucherFileId,
      updatedAt: now,
      paidAt: payment ? paymentOccurredAt : item.paidAt,
      refundedAt: normalizedStatus === "退款" ? now : item.refundedAt,
      cancelledAt: normalizedStatus === "取消" ? now : item.cancelledAt,
    } : item);
    const nextTransactions = payment ? [salesPaymentTransaction(order, paymentOccurredAt, payment.amount, payment), ...data.transactions] : data.transactions;
    const synced = applyProductProjectSync({ ...data, salesOrders: nextSalesOrders, transactions: nextTransactions }, order.projectId);
    await commit(
      synced.data,
      {
        action: payment ? "订单收款" : "修改销售订单状态",
        targetType: "项目",
        targetName: project?.name ?? order.orderNo,
        operator: "当前用户",
        detail: `${paymentLogDetail({
          orderNo: order.orderNo,
          fromStatus: order.status,
          toStatus: normalizedStatus,
          payment,
          receivedAmount: nextReceivedAmount,
          customerName: data.organizations.find((org) => org.id === order.customerOrgId)?.name,
        })}${synced.autoDetail ? `；${synced.autoDetail}` : ""}`,
      },
    );
    setEditingOrderStatus(null);
  }

  async function updatePurchaseOrderStatus(order: PurchaseOrder, status: PurchaseOrder["status"]) {
    if (!canTransition(order.status, status, getAllowedPurchaseOrderStatuses(order, purchaseOrderStatuses))) {
      window.alert(`采购订单状态不能从“${order.status}”变更为“${status}”。`);
      setEditingOrderStatus(null);
      return;
    }
    const project = data.projects.find((item) => item.id === order.projectId);
    const now = today();
    const nextPurchaseOrders = data.purchaseOrders.map((item) => item.id === order.id ? { ...item, status, updatedAt: now } : item);
    const synced = applyProductProjectSync({ ...data, purchaseOrders: nextPurchaseOrders }, order.projectId);
    await commit(
      synced.data,
      { action: "修改采购订单状态", targetType: "项目", targetName: project?.name ?? order.orderNo, operator: "当前用户", detail: `${order.orderNo}：${order.status} -> ${status}${synced.autoDetail ? `；${synced.autoDetail}` : ""}` },
    );
    setEditingOrderStatus(null);
  }

  async function updatePurchaseOrderPaymentStatus(order: PurchaseOrder, status: OrderPaymentStatus) {
    const current = order.paymentStatus ?? DEFAULT_ORDER_PAYMENT_STATUS;
    if (!canTransition(current, status, getAllowedOrderPaymentStatuses(current, orderPaymentStatusOptions))) {
      window.alert(`采购货款状态不能从“${current}”变更为“${status}”。`);
      setEditingOrderStatus(null);
      return;
    }
    if (status === "部分付款" || status === "已付款") {
      if (!canRegisterPurchasePayment(can)) {
        window.alert("没有采购付款权限。");
        setEditingOrderStatus(null);
        return;
      }
      await registerPurchasePayment({
        data,
        commit,
        requestPayment,
        order,
        payable: purchaseOrderDisplayAmount(data, order),
        targetStatus: status,
        operator: currentUser.name,
      });
      setEditingOrderStatus(null);
      return;
    }
    await updatePurchaseOrderFields(order, { paymentStatus: status }, "修改采购货款状态");
    setEditingOrderStatus(null);
  }

  async function updateProjectPlatformOrderNo(platformOrderNo: string) {
    if (!activeProject || activeProject.type !== "商品项目") return;
    const nextValue = platformOrderNo.trim();
    if ((activeProject.platformOrderNo ?? "") === nextValue) return;
    await commit(
      {
        ...data,
        projects: data.projects.map((project) => project.id === activeProject.id
          ? { ...project, platformOrderNo: nextValue || undefined, updatedAt: today() }
          : project),
      },
      {
        action: "修改平台订单号",
        targetType: "项目",
        targetName: activeProject.name,
        operator: "当前用户",
        detail: `${activeProject.platformOrderNo || "未录入"} -> ${nextValue || "未录入"}`,
      },
    );
  }

  async function updateProjectStatus(status: ProjectStatus) {
    if (!activeProject) return;
    const allowedProjectStatuses = getAllowedProjectStatuses(activeProject, activeProject.type === "服务项目" ? serviceProjectStatuses : projectStatusValues);
    if (!canTransition(activeProject.status, status, allowedProjectStatuses)) {
      window.alert(`项目状态不能从“${activeProject.status}”变更为“${status}”。`);
      return;
    }
    if (activeProject.type === "商品项目" && status === "已完成") {
      const issues = projectCompletionIssues(activeProject);
      if (issues.length > 0) {
        window.alert(`项目暂不满足完成条件：\n${issues.map((issue) => `- ${issue}`).join("\n")}`);
        return;
      }
    }
    if (activeProject.type === "商品项目" && status === "进行中") {
      if (!hasProductSalesOrder(data, activeProject.id) || !hasProductPurchaseOrder(data, activeProject.id)) {
        window.alert("进入进行中前，请先添加商品（销售订单）和渠道采购订单。");
        return;
      }
    }
    const now = today();
    const nextProjects = data.projects.map((project) => project.id === activeProject.id
      ? {
          ...project,
          status,
          updatedAt: now,
          currentBlocker: activeProject.type === "商品项目"
            ? (status === "终止" ? "项目已终止" : status === "已完成" ? "无阻塞" : project.currentBlocker)
            : project.currentBlocker,
        }
      : project);
    const base = { ...data, projects: nextProjects };
    const synced = activeProject.type === "商品项目" ? applyProductProjectSync(base, activeProject.id) : { data: base };
    await commit(
      synced.data,
      {
        action: "修改项目状态",
        targetType: "项目",
        targetName: activeProject.name,
        operator: "当前用户",
        detail: `${activeProject.status} -> ${status}${synced.autoDetail ? `；${synced.autoDetail}` : ""}`,
      },
    );
  }

  async function updatePurchaseOrderFields(order: PurchaseOrder, patch: Partial<PurchaseOrder>, action = "修改采购订单") {
    await patchPurchaseOrderRecord({ data, commit, order, patch, action });
  }

  async function updatePurchaseOrderContractStatus(order: PurchaseOrder, contractStatus: ContractStatus) {
    if (contractStatus === order.contractStatus) return;
    if (contractStatus === "已签" && !order.contractFileId) {
      setPoContractUploadOrderId(order.id);
      setPoContractFile(null);
      return;
    }
    await updatePurchaseOrderFields(order, { contractStatus, contractUpdatedAt: today() }, "修改采购合同状态");
  }

  async function savePoSignedContract() {
    const order = data.purchaseOrders.find((item) => item.id === poContractUploadOrderId);
    if (!order || !poContractFile) {
      window.alert("请选择 PDF 合同文件。");
      return;
    }
    if (!isPdfContractFile(poContractFile)) {
      window.alert("合同文件仅支持 PDF 格式。");
      return;
    }
    const replacing = Boolean(order.contractFileId);
    const saved = await uploadBusinessDocument(poContractFile, "contract", order.id);
    await updatePurchaseOrderFields(order, {
      contractStatus: "已签",
      contractFileId: saved.id,
      contractFileName: saved.fileName,
      contractUpdatedAt: today(),
    }, replacing ? "替换采购合同" : "上传采购合同");
    setPoContractUploadOrderId("");
    setPoContractFile(null);
  }

  async function updateProjectReconcileStatus(next: ReconcileStatus) {
    if (!activeProject || activeProject.type !== "商品项目" || !can("project.edit")) return;
    const current = activeProject.reconcileStatus ?? DEFAULT_RECONCILE_STATUS;
    if (next === current) return;
    const now = today();
    const nextProjects = data.projects.map((project) => project.id === activeProject.id ? { ...project, reconcileStatus: next, updatedAt: now } : project);
    const synced = applyProductProjectSync({ ...data, projects: nextProjects }, activeProject.id);
    await commit(
      synced.data,
      {
        action: "修改对账状态",
        targetType: "项目",
        targetName: activeProject.name,
        operator: "当前用户",
        detail: `${current} -> ${next}${synced.autoDetail ? `；${synced.autoDetail}` : ""}`,
      },
    );
  }

  async function updateContractStatus(contractStatus: ContractStatus) {
    if (!activeProject || contractStatus === activeProject.contractStatus) return;
    if (contractStatus === "已签" && !activeProject.contractFileId) {
      setContractFile(null);
      setShowContractUpload(true);
      return;
    }
    const now = today();
    await commit(
      {
        ...data,
        projects: data.projects.map((project) =>
          project.id === activeProject.id ? { ...project, contractStatus, updatedAt: now, contractUpdatedAt: now } : project,
        ),
      },
      {
        action: "修改合同签约状态",
        targetType: "项目",
        targetName: activeProject.name,
        operator: "当前用户",
        detail: `${activeProject.contractStatus} -> ${contractStatus}`,
      },
    );
  }

  async function saveSignedContract() {
    if (!activeProject || !contractFile) {
      window.alert("请选择 PDF 合同文件。");
      return;
    }
    if (!isPdfContractFile(contractFile)) {
      window.alert("合同文件仅支持 PDF 格式。");
      return;
    }
    const replacing = Boolean(activeProject.contractFileId);
    const saved = await uploadBusinessDocument(contractFile, "contract", activeProject.id);
    const now = today();
    await commit(
      {
        ...data,
        projects: data.projects.map((project) => project.id === activeProject.id ? {
          ...project,
          contractStatus: "已签",
          contractFileId: saved.id,
          contractFileName: saved.fileName,
          updatedAt: now,
          contractUpdatedAt: now,
        } : project),
      },
      {
        action: replacing ? "替换项目合同" : "上传项目合同",
        targetType: "项目",
        targetName: activeProject.name,
        operator: "当前用户",
        detail: replacing ? `${activeProject.contractFileName || "原合同"} -> ${saved.fileName}` : saved.fileName,
      },
    );
    setShowContractUpload(false);
    setContractFile(null);
  }

  async function createProjectMemo() {
    if (!activeProject || activeProject.type !== "商品项目") return;
    const content = memoDraft.trim();
    if (!content) {
      window.alert("请输入备忘内容。");
      return;
    }
    if (content.length > PROJECT_MEMO_MAX_LENGTH) {
      window.alert(`备忘内容最多 ${PROJECT_MEMO_MAX_LENGTH} 字。`);
      return;
    }
    const memo: ProjectMemo = {
      id: createId("memo"),
      projectId: activeProject.id,
      content,
      createdBy: currentUser.name,
      createdAt: today(),
    };
    await commit(
      { ...data, projectMemos: [memo, ...data.projectMemos] },
      { action: "新增项目备忘", targetType: "系统", targetName: activeProject.name, operator: "当前用户", detail: content },
    );
    setMemoDraft("");
  }

  async function linkInvoiceToProject(invoiceId: string, serviceOrderId?: string) {
    if (!activeProject || !invoiceId) return false;
    const invoice = data.invoices.find((item) => item.id === invoiceId);
    if (!invoice) return false;
    const resolvedServiceOrderId = activeProject.type === "服务项目"
      ? (serviceOrderId || pickDefaultServiceOrderIdForInvoiceLink(data, activeProject.id))
      : undefined;
    const target = activeProject.type === "服务项目"
      ? { kind: "service" as const, projectId: activeProject.id, orderId: resolvedServiceOrderId }
      : { kind: invoice.type === "进项" ? "purchase" as const : "sales" as const, projectId: activeProject.id };
    const blocked = invoiceLinkBlockReason(data, invoice, target);
    if (blocked) {
      window.alert(blocked);
      return false;
    }
    if (activeProject.type === "服务项目") {
      const amount = promptServiceInvoiceAllocationAmount({
        data,
        invoice,
        projectId: activeProject.id,
        serviceOrderId: resolvedServiceOrderId,
      });
      if (amount == null) return false;
      const nextInvoice = applyServiceInvoiceAllocation(data, invoice, {
        projectId: activeProject.id,
        serviceOrderId: resolvedServiceOrderId,
        amount,
      });
      const nextData = {
        ...data,
        invoices: data.invoices.map((item) => item.id === invoiceId ? nextInvoice : item),
      };
      await commit(
        {
          ...nextData,
          projects: nextData.projects.map((project) => project.id === activeProject.id
            ? { ...project, invoiceStatus: deriveServiceProjectInvoiceStatus(nextData, activeProject.id) }
            : project),
        },
        {
          action: "关联发票到项目",
          targetType: "发票",
          targetName: invoice.invoiceNo || activeProject.name,
          operator: "当前用户",
          detail: `关联项目：${activeProject.name}；关联金额：${money(amount)}${resolvedServiceOrderId ? `；服务订单：${data.serviceOrders.find((item) => item.id === resolvedServiceOrderId)?.orderNo ?? resolvedServiceOrderId}` : ""}`,
        },
      );
      setProjectInvoiceId("");
      return true;
    }
    const matchingOrders = invoice.type === "销项" ? salesOrders : purchaseOrders;
    const autoLinkedOrder = activeProject.type === "商品项目" && matchingOrders.length === 1 ? matchingOrders[0] : undefined;
    const salesOrderIds = invoice.type === "销项" && autoLinkedOrder
      ? Array.from(new Set([...(invoice.salesOrderIds ?? []), autoLinkedOrder.id]))
      : invoice.salesOrderIds ?? [];
    const purchaseOrderIds = invoice.type === "进项" && autoLinkedOrder
      ? Array.from(new Set([...(invoice.purchaseOrderIds ?? []), autoLinkedOrder.id]))
      : invoice.purchaseOrderIds ?? [];
    const nextInvoice = reconcileInvoiceProjectIds(data, {
      ...invoice,
      salesOrderIds,
      purchaseOrderIds,
    }, activeProject.id);
    await commit(
      {
        ...data,
        invoices: data.invoices.map((item) => item.id === invoiceId ? nextInvoice : item),
      },
      { action: "关联发票到项目", targetType: "发票", targetName: invoice.invoiceNo || activeProject.name, operator: "当前用户", detail: `关联项目：${activeProject.name}${autoLinkedOrder ? `，关联订单：${autoLinkedOrder.orderNo}` : ""}` },
    );
    if (activeProject.type === "商品项目" && matchingOrders.length > 1 && salesOrderIds.length + purchaseOrderIds.length === 0) {
      window.alert("项目关联成功。该项目有多个订单，请在具体订单行或发票详情中选择需要关联的订单。");
    }
    setProjectInvoiceId("");
    return true;
  }

  async function unlinkServiceInvoice(invoice: Invoice, target: { projectId: string; serviceOrderId?: string; label: string }) {
    if (!can("invoice.manage")) return;
    await unlinkServiceInvoiceRecord({
      data,
      commit,
      invoice,
      projectId: target.projectId,
      serviceOrderId: target.serviceOrderId,
      label: target.label,
    });
  }

  async function createLinkedInvoice(
    payload: InvoiceQuickPayload,
    options: {
      type: "销项" | "进项";
      salesOrderId?: string;
      purchaseOrderId?: string;
      defaultProductName: string;
      logDetail: string;
    },
  ): Promise<boolean> {
    if (!activeProject) return false;
    const existing = findInvoiceByNo(data.invoices, payload.invoiceNo.trim());
    if (existing && !options.salesOrderId && !options.purchaseOrderId) {
      if (existing.type !== options.type) {
        window.alert(`发票 ${existing.invoiceNo || payload.invoiceNo} 是${existing.type}，此处只能关联${options.type}发票。`);
        return false;
      }
      return linkInvoiceToProject(existing.id);
    }
    return createLinkedInvoiceRecord({
      data,
      commit,
      can,
      project: activeProject,
      payload,
      options,
      customer,
      ownCompany,
    });
  }

  async function linkInvoiceToOrder(invoiceId: string, order: SalesOrder | PurchaseOrder, type: "sales" | "purchase", lineIndexes?: number[], lineQuantities?: Record<number, number>) {
    const ok = await linkInvoiceToOrderRecord({ data, commit, invoiceId, order, type, lineIndexes, lineQuantities });
    if (ok) setOrderInvoiceIds({ ...orderInvoiceIds, [order.id]: "" });
    return ok;
  }

  async function unlinkInvoiceFromOrder(invoice: Invoice, order: SalesOrder | PurchaseOrder, type: "sales" | "purchase") {
    await unlinkInvoiceFromOrderRecord({ data, commit, invoice, order, type });
  }

  function openServiceContractModal(project: Project) {
    setContractDraftProject(project);
    setContractDraft(buildServiceContractDraft(data, project));
    setContractMoreOpen(false);
    setContractFileFormat("word");
  }

  function closeServiceContractModal() {
    setContractDraftProject(null);
    setContractDraft(null);
    setContractMoreOpen(false);
    setContractFileFormat("word");
  }

  function toggleContractShopCategory(value: string) {
    if (!contractDraft) return;
    const selected = contractDraft.shopCategories.includes(value)
      ? contractDraft.shopCategories.filter((item) => item !== value)
      : [...contractDraft.shopCategories, value];
    setContractDraft({
      ...contractDraft,
      shopCategories: selected,
      shopCategory: formatShopCategories(selected),
    });
  }

  async function submitServiceContract() {
    if (!contractDraftProject || !contractDraft) return;
    const missing = serviceContractDraftErrors(contractDraft, contractDraftProject.sourcePlatform);
    if (missing.length > 0) {
      window.alert("请先补全合同信息后再生成。");
      return;
    }
    setIsGeneratingContract(true);
    try {
      await downloadServiceContract(contractDraftProject.id, contractDraft, contractFileFormat);
      closeServiceContractModal();
    } catch (error) {
      if (error instanceof AuthExpiredError) return;
      window.alert(error instanceof Error ? error.message : "生成合同失败，请稍后重试");
    } finally {
      setIsGeneratingContract(false);
    }
  }

  return (
    <>
      <div className="panel list-panel project-list-page">
        <div className="panel-title action-title">
          <div>
            <h2>{projectTab}列表</h2>
            <p>{projectTab}汇总客户、使用单位、商品、供应商、发票、负责人和流程。</p>
          </div>
          {can("project.create") && <button className="primary" onClick={openCreateProject}><PackagePlus size={16} />新建{projectTab}</button>}
        </div>
        {filteredPage.error && <div className="form-error">{filteredPage.error}</div>}
        {projectTab === "服务项目" ? (
          <form className="orders-search-form projects-search-form" onSubmit={(event) => event.preventDefault()}>
            <div className="orders-filter-field">
              <span>签约主体</span>
              <SearchableSelect
                value={projectOwnCompanyFilter}
                options={projectOwnCompanyFilterOptions}
                onChange={setProjectOwnCompanyFilter}
                placeholder="全部"
                ariaLabel="按签约主体筛选"
              />
            </div>
            <label className="orders-filter-field">
              <span>项目状态</span>
              <select
                value={projectStatusFilter}
                aria-label="按项目状态筛选"
                onChange={(event) => setProjectStatusFilter(event.target.value)}
              >
                <option value="">全部</option>
                {serviceProjectStatuses.map((item) => <option key={item} value={item}>{item}</option>)}
              </select>
            </label>
            <label className="orders-filter-field">
              <span>类型</span>
              <select
                value={projectServiceTypeFilter}
                aria-label="按类型筛选"
                onChange={(event) => setProjectServiceTypeFilter(event.target.value)}
              >
                <option value="">全部</option>
                {serviceTypeOptions.map((item) => <option key={item} value={item}>{item}</option>)}
              </select>
            </label>
            <label className="orders-filter-field">
              <span>合同状态</span>
              <select
                value={projectContractStatusFilter}
                aria-label="按合同状态筛选"
                onChange={(event) => setProjectContractStatusFilter(event.target.value)}
              >
                <option value="">全部</option>
                {contractStatusOptions.map((item) => <option key={item} value={item}>{item}</option>)}
              </select>
            </label>
            <label className="orders-filter-field">
              <span>发票状态</span>
              <select
                value={projectInvoiceStatusFilter}
                aria-label="按发票状态筛选"
                onChange={(event) => setProjectInvoiceStatusFilter(event.target.value)}
              >
                <option value="">全部</option>
                {serviceInvoiceStatusFilterOptions.map((item) => <option key={item} value={item}>{item}</option>)}
              </select>
            </label>
            <div className="orders-filter-field">
              <span>业务员</span>
              <SearchableSelect
                value={projectSalesUserFilter}
                options={projectSalesUserFilterOptions}
                onChange={setProjectSalesUserFilter}
                placeholder="全部"
                ariaLabel="按业务员筛选"
              />
            </div>
            <label className="orders-filter-field orders-filter-search">
              <span>搜索条件</span>
              <SearchField
                value={projectSearch}
                onChange={setProjectSearch}
                placeholder="搜索平台、客户、服务项目；可用空格组合条件"
                ariaLabel="搜索条件"
              />
            </label>
          </form>
        ) : (
          <SearchField
            value={projectSearch}
            onChange={setProjectSearch}
            placeholder={`搜索${projectTab}、客户、使用单位、平台订单号`}
          />
        )}
        {showCreate && (
          <div className="modal-backdrop" role="presentation">
            <div className="modal project-create-modal" role="dialog" aria-modal="true" aria-label={editingProjectId ? `编辑${projectTab}` : `新建${projectTab}`}>
              <div className="modal-head">
                <div>
                  <h2>{editingProjectId ? `编辑${projectTab}` : `新建${projectTab}`}</h2>
                  <p>{projectTab === "服务项目"
                    ? (editingProjectId ? "可修改客户、首次或续费、服务、周期、业务员和项目金额；金额会同步到对应服务订单。" : "选择客户、首次或续费、服务、周期和业务员；保存后自动创建服务订单。")
                    : "创建项目基础信息，商品和渠道在项目详情中继续维护。"}</p>
                </div>
                <button className="icon-button" onClick={closeCreateProjectModal} aria-label={editingProjectId ? "关闭编辑项目" : "关闭新建项目"}><X size={18} /></button>
              </div>
              <div className="create-project create-project-modal-form">
                {projectTab === "商品项目" ? (
                  <input value={productProjectNamePreview} readOnly aria-label="自动生成商品项目名称" placeholder="项目名称自动生成" />
                ) : (
                  <input value={serviceProjectNamePreview} readOnly aria-label="自动生成服务项目名称" placeholder="项目名称自动生成" />
                )}
                <div className="field-with-action">
                  <SearchableSelect
                    value={newProject.customerOrgId}
                    options={customerSelectOptions}
                    onChange={(value) => setNewProject({ ...newProject, customerOrgId: value })}
                    placeholder={projectTab === "商品项目" ? "搜索并选择中间销售商" : "搜索并选择客户"}
                    ariaLabel={projectTab === "商品项目" ? "选择中间销售商" : "选择客户"}
                  />
                </div>
                {projectTab === "服务项目" && (
                  <select
                    value={newProject.serviceCustomerKind}
                    onChange={(event) => setNewProject({ ...newProject, serviceCustomerKind: event.target.value as "" | ServiceCustomerKind })}
                    aria-label="首次服务或续费客户"
                  >
                    <option value="">请选择首次服务或续费客户</option>
                    {SERVICE_CUSTOMER_KINDS.map((item) => <option key={item} value={item}>{item}</option>)}
                  </select>
                )}
                {projectTab === "商品项目" && (
                  <>
                    <SearchableSelect
                      value={newProject.usageUnitOrgId}
                      options={[{ value: "", label: "无使用单位" }, ...usageUnitSelectOptions]}
                      onChange={(value) => setNewProject({ ...newProject, usageUnitOrgId: value })}
                      placeholder="搜索并选择使用单位"
                      ariaLabel="选择使用单位"
                    />
                    <SearchableSelect
                      value={newProject.ownCompanyOrgId}
                      options={ownCompanySelectOptions}
                      onChange={(value) => setNewProject({ ...newProject, ownCompanyOrgId: value })}
                      placeholder="搜索并选择对接公司"
                      ariaLabel="选择对接公司"
                    />
                  </>
                )}
                {projectTab === "服务项目" && (
                  <>
                    <SearchableSelect
                      value={newProject.ownCompanyOrgId}
                      options={ownCompanySelectOptions}
                      onChange={(value) => setNewProject({ ...newProject, ownCompanyOrgId: value })}
                      placeholder="搜索并选择签约主体"
                      ariaLabel="选择签约主体"
                    />
                    <SearchableSelect
                      value={newProject.productId}
                      options={projectProductSelectOptions}
                      onChange={updateProduct}
                      placeholder="搜索并选择服务"
                      ariaLabel="选择服务"
                    />
                    <select
                      value={newProject.onboardingPlatform}
                      disabled={availableOnboardingPlatforms.length === 1}
                      onChange={(event) => {
                        const platform = event.target.value as PlatformAccount["platform"];
                        setNewProject({
                          ...newProject,
                          onboardingPlatform: platform,
                          sourcePlatform: platform,
                          serviceCustomerKind: serviceCustomerKindForPlatform(platform, newProject.serviceCustomerKind),
                        });
                      }}
                    >
                      <option value="">请选择服务平台</option>
                      {availableOnboardingPlatforms.map((item) => <option key={item}>{item}</option>)}
                    </select>
                    <select value={newProject.serviceSalesUserId} onChange={(event) => setNewProject({ ...newProject, serviceSalesUserId: event.target.value })}>
                      <option value="">请选择业务员</option>
                      {data.users.filter((user) => user.status === "启用").map((user) => <option key={user.id} value={user.id}>{user.name}</option>)}
                    </select>
                    <select value={newProject.serviceType} onChange={(event) => setNewProject({ ...newProject, serviceType: event.target.value as ServiceType })}>
                      {serviceTypeOptions.map((item) => <option key={item}>{item}</option>)}
                    </select>
                    <input value={newProject.salesUnitPrice || selectedProduct?.quotePrice || ""} onChange={(event) => setNewProject({ ...newProject, salesUnitPrice: event.target.value })} placeholder="项目金额（必填可改）" />
                    <DateTimeField value={newProject.serviceStartDate} onChange={(serviceStartDate) => setNewProject({ ...newProject, serviceStartDate })} ariaLabel="开始日期" placeholder="开始日期" />
                    {newProject.serviceType === "周期" ? (
                      <>
                        <select value={newProject.servicePeriodUnit} onChange={(event) => setNewProject({ ...newProject, servicePeriodUnit: event.target.value as ServicePeriodUnit, servicePeriodValue: "1" })}>
                          {servicePeriodUnits.map((item) => <option key={item}>{item}</option>)}
                        </select>
                        <select value={newProject.servicePeriodValue} onChange={(event) => setNewProject({ ...newProject, servicePeriodValue: event.target.value })}>
                          {(newProject.servicePeriodUnit === "年" ? serviceYearOptions : serviceMonthOptions).map((item) => <option key={item} value={String(parseOptionNumber(item))}>{item}</option>)}
                        </select>
                        <select value={newProject.serviceGiftUnit} onChange={(event) => setNewProject({ ...newProject, serviceGiftUnit: event.target.value as "天" | "月" })}>
                          <option>月</option>
                          <option>天</option>
                        </select>
                        <input type="number" min="0" value={newProject.serviceGiftValue} onChange={(event) => setNewProject({ ...newProject, serviceGiftValue: event.target.value })} placeholder="赠送数量" />
                        <input value={calculateServiceEndDate(newProject.serviceStartDate, newProject.servicePeriodUnit, Number(newProject.servicePeriodValue) || 1, newProject.serviceGiftUnit, Number(newProject.serviceGiftValue) || 0)} readOnly aria-label="到期日期" />
                      </>
                    ) : (
                      <DateTimeField value={newProject.serviceEndDate} onChange={(serviceEndDate) => setNewProject({ ...newProject, serviceEndDate })} ariaLabel="到期日期" placeholder="到期日期" />
                    )}
                    <input value={currentUser.name} readOnly aria-label="操作员" />
                    <textarea value={newProject.serviceRemark} onChange={(event) => setNewProject({ ...newProject, serviceRemark: event.target.value })} placeholder="备注" />
                  </>
                )}
                {projectTab === "商品项目" && (
                  <>
                    <select value={newProject.sourcePlatform} onChange={(event) => setNewProject({ ...newProject, sourcePlatform: event.target.value })}>
                      {sourcePlatformOptions.map((item) => <option key={item}>{item}</option>)}
                    </select>
                    <textarea value={newProject.remark} onChange={(event) => setNewProject({ ...newProject, remark: event.target.value })} placeholder="备注（自动放到项目名称中日期前）" aria-label="商品项目备注" />
                    <DateTimeField
                      mode="datetime"
                      value={newProject.projectAt}
                      onChange={(projectAt) => setNewProject({ ...newProject, projectAt })}
                      ariaLabel="项目时间"
                      placeholder="项目时间"
                    />
                  </>
                )}
              </div>
              <div className="modal-actions">
                <button className="ghost" onClick={closeCreateProjectModal} disabled={isCreatingProject}>取消</button>
                <button className="primary" onClick={createProject} disabled={isCreatingProject}><PackagePlus size={16} />{isCreatingProject ? "保存中..." : editingProjectId ? "保存修改" : "保存项目"}</button>
              </div>
            </div>
          </div>
        )}
        {projectTab === "服务项目" ? (
          <div className="table">
            <div className="table-row service-project-table head"><span>客户/服务</span><span>签约主体</span><span>到期时间</span><span>项目状态</span><span>类型</span><span>费用</span><span>合同</span><span>发票</span><span>业务</span><span>创建/更新</span><span>操作</span></div>
            {filteredPage.items.map((project) => {
              const rowCustomer = data.organizations.find((org) => org.id === project.customerOrgId);
              const customerName = rowCustomer?.name || "";
              const ownCompanyName = data.organizations.find((org) => org.id === project.ownCompanyOrgId)?.name || "";
              const serviceName = serviceListName(project);
              return (
                <div className="table-row service-project-table" key={project.id}>
                  <div className="service-project-main">
                    <div className="service-project-customer">
                      <CopyableLine text={customerName} label="客户名称" onOpen={() => onSelectProject(project.id)}>
                        <span>{customerName || "未选择客户"}</span>
                      </CopyableLine>
                      {project.serviceCustomerKind ? (
                        <em className={`service-customer-kind ${project.serviceCustomerKind === "续费客户" ? "is-renewal" : "is-first"}`}>
                          {project.serviceCustomerKind}
                        </em>
                      ) : null}
                    </div>
                    <CopyableLine text={serviceName} label="服务名称" className="is-secondary" onOpen={() => onSelectProject(project.id)}>
                      <em>{serviceName}</em>
                    </CopyableLine>
                  </div>
                  <div className="service-project-own">
                    {ownCompanyName ? (
                      <CopyableLine text={ownCompanyName} label="签约主体" onOpen={() => onSelectProject(project.id)}>
                        {ownCompanyShortName(ownCompanyName)}
                      </CopyableLine>
                    ) : "未选择"}
                  </div>
                  <span className="service-project-stack">{serviceDateText(project)}<em>{serviceCountdownText(project)}</em></span>
                  <span>{project.status}</span>
                  <span>{project.serviceType || "周期"}</span>
                  <div className="service-project-stack">
                    <span>{money(project.totalAmount)}</span>
                    <em>实收: {money(projectReceivedAmount(data, project.id))}</em>
                  </div>
                  <span>{project.contractStatus}</span>
                  <span>{projectInvoiceStatusText(data, project)}</span>
                  <span>{project.serviceSalesName || project.owner}</span>
                  <span className="service-project-stack">{formatDateTimeValue(project.createdAt)}<em>更新 {formatDateTimeValue(project.updatedAt)}</em></span>
                  <span className="option-actions">
                    {can("project.edit") && <button className="copy-link" onClick={() => openEditServiceProject(project)}>编辑</button>}
                    {can("project.edit") && canGenerateServiceContract(data, project) && (
                      <button className="copy-link" onClick={() => openServiceContractModal(project)}>生成合同</button>
                    )}
                  </span>
                </div>
              );
            })}
          </div>
        ) : (
          <div className="table">
            <div className="table-row product-project-table head"><span>项目/客户</span><span>项目状态</span><span>订单/合同/发票/对账</span><span>金额</span><span>创建/更新</span><span>操作</span></div>
            {filteredPage.items.map((project) => {
              const rowCustomerName = data.organizations.find((org) => org.id === project.customerOrgId)?.name ?? "";
              const orderStatusLines = productProjectOrderStatusLines(data, project);
              const salesAmount = projectSalesAmount(data, project.id) || Number(project.totalAmount) || 0;
              const receivedAmount = projectReceivedAmount(data, project.id);
              const costAmount = projectPurchaseAmount(data, project.id) || Number(project.totalCost) || 0;
              const paidAmount = projectPaidAmount(data, project.id);
              const grossProfit = salesAmount - costAmount;
              const grossMarginText = salesAmount > 0
                ? `${((grossProfit / salesAmount) * 100).toFixed(1)}%`
                : "—";
              return (
                <div className="table-row product-project-table" key={project.id}>
                  <div className="product-project-main">
                    <span>{project.projectNo}</span>
                    <CopyableLine text={project.name} label="项目名称" onOpen={() => onSelectProject(project.id)}>
                      <strong>{project.name}</strong>
                    </CopyableLine>
                    {rowCustomerName ? (
                      <CopyableLine text={rowCustomerName} label="客户名称" className="is-secondary" onOpen={() => onSelectProject(project.id)}>
                        <em>{rowCustomerName}</em>
                      </CopyableLine>
                    ) : null}
                  </div>
                  <span>{project.status}<em>{project.currentBlocker || "无阻塞"}</em></span>
                  <div className="product-project-stack">
                    <span>{orderStatusLines.salesLine}</span>
                    <em>{orderStatusLines.purchaseLine}</em>
                  </div>
                  <div className="product-project-stack">
                    <span>{`金额${money(salesAmount)}/实收 ${money(receivedAmount)}`}</span>
                    {canViewProjectCost ? (
                      <em>{`成本 ${money(costAmount)}/实付 ${money(paidAmount)}`}</em>
                    ) : null}
                    {can("profit.view") ? (
                      <em>{`毛利 ${money(grossProfit)} · 毛利率 ${grossMarginText}`}</em>
                    ) : null}
                  </div>
                  <span>{formatDateTimeValue(project.createdAt)}<em>更新 {formatDateTimeValue(project.updatedAt)}</em></span>
                  <span className="option-actions">
                    <button className="copy-link" onClick={() => onSelectProject(project.id)}>详情</button>
                    {/* 临时恢复，后续可能再隐藏 */}
                    {can("project.edit") && project.type === "商品项目" && (
                      <button
                        className="copy-link danger-action"
                        onClick={() => {
                          if (!window.confirm(`确定删除商品项目「${project.name}」吗？相关订单、明细、备忘等将一并移除。`)) return;
                          void deleteProject(project);
                        }}
                      >
                        删除
                      </button>
                    )}
                  </span>
                </div>
              );
            })}
          </div>
        )}
        <Pagination {...filteredPage} onPageChange={filteredPage.setPage} />
      </div>
      {contractDraftProject && contractDraft && (
        <div className="modal-backdrop" role="presentation">
          <div className="modal service-contract-modal" role="dialog" aria-modal="true" aria-label="生成服务合同">
            <div className="modal-head">
              <div>
                <h2>生成服务合同</h2>
                <p>按 {contractDraftProject.sourcePlatform || "当前平台"} 模板下载 Word 或 PDF，盖章扫描后仍走原来的上传合同。服务费默认泉E采 3000、青慧采 4000，签订日期默认服务开始日；授权代表在合同中留空签字。</p>
              </div>
              <button className="icon-button" onClick={closeServiceContractModal} aria-label="关闭生成合同" disabled={isGeneratingContract}><X size={18} /></button>
            </div>
            <div className="payment-form-grid">
              <label className={normalizeContractPlatform(contractDraftProject.sourcePlatform) === "泉E采" ? "span-2" : undefined}><span>店铺名称</span><input value={contractDraft.shopName} onChange={(event) => setContractDraft({ ...contractDraft, shopName: event.target.value })} /></label>
              <label><span>店铺主营</span>
                <div className="shop-category-checkboxes">
                  {SHOP_CATEGORY_OPTIONS.map((option) => (
                    <label key={option.value}>
                      <input
                        type="checkbox"
                        checked={contractDraft.shopCategories.includes(option.value)}
                        onChange={() => toggleContractShopCategory(option.value)}
                      />
                      {option.label}
                    </label>
                  ))}
                </div>
              </label>
              {normalizeContractPlatform(contractDraftProject.sourcePlatform) === "泉E采" && (
                <label><span>上架上限</span><input value={contractDraft.listingLimit} onChange={(event) => setContractDraft({ ...contractDraft, listingLimit: event.target.value })} /></label>
              )}
              <label><span>服务开始日</span>
                <DateTimeField value={contractDraft.startDate} onChange={(startDate) => setContractDraft({ ...contractDraft, startDate })} ariaLabel="服务开始日" />
              </label>
              <label><span>服务到期日</span>
                <DateTimeField value={contractDraft.endDate} onChange={(endDate) => setContractDraft({ ...contractDraft, endDate })} ariaLabel="服务到期日" />
              </label>
              <label><span>签订日期</span>
                <DateTimeField value={contractDraft.signDate} onChange={(signDate) => setContractDraft({ ...contractDraft, signDate })} ariaLabel="签订日期" />
              </label>
              <label><span>服务费金额</span>
                <input type="number" min="0" step="0.01" value={contractDraft.amount} onChange={(event) => setContractDraft({ ...contractDraft, amount: event.target.value })} />
                <em className="service-contract-amount-cn">大写：{amountToChinese(contractDraft.amount)}</em>
              </label>
            </div>
            <button type="button" className="ghost service-contract-more-toggle" onClick={() => setContractMoreOpen((open) => !open)}>
              {contractMoreOpen
                ? (contractNeedsCollectionAccount(contractDraftProject.sourcePlatform) ? "收起甲乙方与账户信息" : "收起甲乙方信息")
                : (contractNeedsCollectionAccount(contractDraftProject.sourcePlatform) ? "展开甲乙方与账户信息" : "展开甲乙方信息")}
            </button>
            {contractMoreOpen && (
              <div className="payment-form-grid service-contract-more">
                <label><span>甲方名称</span><input value={contractDraft.partyAName} onChange={(event) => setContractDraft({ ...contractDraft, partyAName: event.target.value })} /></label>
                <label><span>甲方地址</span><input value={contractDraft.partyAAddress} onChange={(event) => setContractDraft({ ...contractDraft, partyAAddress: event.target.value })} /></label>
                <label><span>甲方电话</span><input value={contractDraft.partyAPhone} onChange={(event) => setContractDraft({ ...contractDraft, partyAPhone: event.target.value })} /></label>
                <label><span>乙方名称</span><input value={contractDraft.partyBName} onChange={(event) => setContractDraft({ ...contractDraft, partyBName: event.target.value, accountName: event.target.value })} /></label>
                <label><span>乙方地址</span><input value={contractDraft.partyBAddress} onChange={(event) => setContractDraft({ ...contractDraft, partyBAddress: event.target.value })} /></label>
                <label><span>乙方电话</span><input value={contractDraft.partyBPhone} onChange={(event) => setContractDraft({ ...contractDraft, partyBPhone: event.target.value })} /></label>
                {normalizeContractPlatform(contractDraftProject.sourcePlatform) !== "泉E采" && (
                  <label><span>上架上限</span><input value={contractDraft.listingLimit} onChange={(event) => setContractDraft({ ...contractDraft, listingLimit: event.target.value })} /></label>
                )}
                {contractNeedsCollectionAccount(contractDraftProject.sourcePlatform) && (
                  <label><span>户名</span><input value={contractDraft.accountName} onChange={(event) => setContractDraft({ ...contractDraft, accountName: event.target.value })} /></label>
                )}
              </div>
            )}
            <div className="modal-actions">
              <ContractFormatPicker name="project-contract-format" value={contractFileFormat} onChange={setContractFileFormat} disabled={isGeneratingContract} />
              <button className="ghost" onClick={closeServiceContractModal} disabled={isGeneratingContract}>取消</button>
              <button className="primary" onClick={() => void submitServiceContract()} disabled={isGeneratingContract}>
                {isGeneratingContract ? "生成中..." : `下载${contractFileFormat === "pdf" ? " PDF" : " Word"}`}
              </button>
            </div>
          </div>
        </div>
      )}
      {activeProject && (
        <div className="modal-backdrop" role="presentation">
          <div className="modal project-detail-modal" role="dialog" aria-modal="true" aria-label="项目详情">
            <div className="modal-head">
              <div>
                <h2>项目详情</h2>
                <p>{activeProject.type === "商品项目" ? "查看和处理项目下的发票、销售订单、采购订单、备忘和商品明细。" : "查看和处理项目下的基本信息、平台账号、服务明细、订单、发票、提醒和日志。"}</p>
              </div>
              <button className="icon-button" onClick={() => onSelectProject("")} aria-label="关闭项目详情"><X size={18} /></button>
            </div>
            <div className="project-detail-sticky">
            <div className="detail-head">
              <div>
                <span className="tag">{activeProject.type}</span>
                <h2>
                  <CopyableLine text={activeProject.name} label="项目名称">
                    {activeProject.name}
                  </CopyableLine>
                </h2>
                <p>{activeProject.projectNo} · {activeProject.owner} · {activeProject.sourcePlatform || "无平台"}</p>
              </div>
              <div className="project-detail-actions">
                <button className="ghost" onClick={() => {
                  if (activeProject.type === "商品项目") setProductDetailTab("logs");
                  else setServiceDetailTab("logs");
                }}>项目日志</button>
                <strong className="amount">{money(selectedProjectRevenue)}</strong>
              </div>
            </div>
            {activeProject.type === "商品项目" && (
              <div className="segmented project-detail-tabs" role="tablist" aria-label="商品项目详情页签">
                {PRODUCT_DETAIL_TABS.map((tab) => (
                  <button
                    key={tab.id}
                    type="button"
                    role="tab"
                    aria-selected={productDetailTab === tab.id}
                    className={productDetailTab === tab.id ? "active" : undefined}
                    onClick={() => setProductDetailTab(tab.id)}
                  >
                    {tab.label}
                  </button>
                ))}
              </div>
            )}
            {activeProject.type === "服务项目" && (
              <div className="segmented project-detail-tabs" role="tablist" aria-label="服务项目详情页签">
                {SERVICE_DETAIL_TABS.map((tab) => (
                  <button
                    key={tab.id}
                    type="button"
                    role="tab"
                    aria-selected={serviceDetailTab === tab.id}
                    className={serviceDetailTab === tab.id ? "active" : undefined}
                    onClick={() => setServiceDetailTab(tab.id)}
                  >
                    {tab.label}
                  </button>
                ))}
              </div>
            )}
            </div>
            <div className="project-detail-body">
            {(activeProject.type === "商品项目" ? productDetailTab === "basic" : serviceDetailTab === "basic") && (
            <div className="info-grid">
              <Info label="客户" value={customer?.name} />
              {activeProject.type === "商品项目" && <Info label="使用单位" value={usageUnit?.name ?? "无"} />}
              {activeProject.type === "服务项目" && <Info label="签约主体" value={ownCompany?.name ?? "未选择"} />}
              {activeProject.type === "服务项目" && <Info label="客户类型" value={activeProject.serviceCustomerKind || "未标记"} />}
              {activeProject.type === "商品项目" && <Info label="对接公司" value={ownCompany?.name ?? "未选择"} />}
              {activeProject.type === "商品项目" && activeProject.sourcePlatform && <Info label="所属平台" value={activeProject.sourcePlatform} />}
              {activeProject.type === "商品项目" && activeProject.sourcePlatform && (
                <div className="info editable-info">
                  <span>平台订单号</span>
                  <input
                    defaultValue={activeProject.platformOrderNo ?? ""}
                    key={`platform-order-${activeProject.id}-${activeProject.platformOrderNo ?? ""}`}
                    disabled={!can("project.edit")}
                    placeholder="请输入平台订单号"
                    onBlur={(event) => {
                      if (can("project.edit")) void updateProjectPlatformOrderNo(event.target.value);
                    }}
                  />
                </div>
              )}
              {activeProject.type === "商品项目" && !activeProject.sourcePlatform && <Info label="平台订单号" value={activeProject.platformOrderNo ?? "未录入"} />}
              {activeProject.type === "服务项目" && <Info label="服务" value={activeProject.serviceProductName ?? activeProject.name} />}
              {activeProject.type === "服务项目" && <Info label="入驻平台" value={activeProject.sourcePlatform ?? "未选择"} />}
              {activeProject.type === "服务项目" && <Info label="服务类型" value={activeProject.serviceType ?? "周期"} />}
              {activeProject.type === "服务项目" && <Info label="开始日期" value={activeProject.serviceStartDate ?? "未录入"} />}
              {activeProject.type === "服务项目" && <Info label="到期时间" value={serviceDateText(activeProject)} />}
              <div className="info editable-info">
                <span>项目状态</span>
                <select value={activeProject.status} disabled={!can("project.edit") || getAllowedProjectStatuses(activeProject, activeProject.type === "服务项目" ? serviceProjectStatuses : projectStatusValues).length <= 1} onChange={(event) => void updateProjectStatus(event.target.value as ProjectStatus)}>
                  {getAllowedProjectStatuses(activeProject, activeProject.type === "服务项目" ? serviceProjectStatuses : projectStatusValues).map((status) => <option key={status}>{status}</option>)}
                </select>
              </div>
              <div className="info editable-info">
                <span>合同</span>
                <select value={activeProject.contractStatus} disabled={!can("project.edit")} onChange={(event) => void updateContractStatus(event.target.value as ContractStatus)}>
                  {contractStatusOptions.map((status) => <option key={status}>{status}</option>)}
                </select>
              </div>
              <div className="info editable-info">
                <span>合同文件</span>
                <ContractFileActions
                  fileId={activeProject.contractFileId}
                  canReplace={can("project.edit")}
                  onView={() => setContractViewerFileId(activeProject.contractFileId!)}
                  onReplace={() => { setContractFile(null); setShowContractUpload(true); }}
                />
              </div>
              {activeProject.type === "商品项目" && <Info label="货款状态" value={activeProject.paymentStatus} />}
              {activeProject.type === "商品项目" && (
                <div className="info editable-info">
                  <span>对账状态</span>
                  <select
                    value={activeProject.reconcileStatus ?? DEFAULT_RECONCILE_STATUS}
                    disabled={!can("project.edit")}
                    onChange={(event) => void updateProjectReconcileStatus(event.target.value as ReconcileStatus)}
                  >
                    {reconcileStatusOptions.map((status) => <option key={status}>{status}</option>)}
                  </select>
                </div>
              )}
              {activeProject.type === "商品项目" && <Info label="开票状态" value={projectInvoiceStatusText(data, activeProject)} />}
              {activeProject.type === "商品项目" && (
                <>
                  <Info label="物流汇总" value={purchaseFulfillmentSummary.logisticsStatus} />
                  <Info label="验收汇总" value={purchaseFulfillmentSummary.acceptanceStatus} />
                  <Info label="交付汇总" value={purchaseFulfillmentSummary.deliveryStatus} />
                </>
              )}
              {activeProject.type === "商品项目" && <Info label="采购状态" value={activeProject.purchaseStatus} />}
              {activeProject.type === "服务项目" && <Info label="业务员" value={activeProject.serviceSalesName ?? activeProject.owner} />}
              {activeProject.type === "服务项目" && <Info label="操作员" value={activeProject.serviceOperatorName ?? "未记录"} />}
              <Info label="销售金额" value={money(selectedProjectRevenue)} />
              <Info label="实收金额" value={money(projectReceivedAmount(data, activeProject.id))} />
              {canViewProjectCost && <Info label="采购成本" value={money(selectedProjectCost)} />}
              {can("profit.view") && <Info label="毛利" value={money(selectedProjectGrossProfit)} />}
              <Info label={activeProject.type === "服务项目" ? "备注" : "当前阻塞"} value={activeProject.type === "服务项目" ? activeProject.serviceRemark ?? "无" : activeProject.currentBlocker ?? "无"} />
            </div>
            )}
            {(activeProject.type !== "商品项目" || productDetailTab === "basic") && activeProject.type === "商品项目" && activeProject.status === "初始化" && (
              <div className="project-guide-banner">
                <div>
                  <strong>初始化引导</strong>
                  <p>请先补充商品与渠道采购，完成后项目将自动进入「进行中」。</p>
                </div>
                <div className="project-guide-actions">
                  {!hasProductSalesOrder(data, activeProject.id) && (
                    <button className="primary" onClick={() => setProductDetailTab("sales")}>
                      去添加商品
                    </button>
                  )}
                  {!hasProductPurchaseOrder(data, activeProject.id) && (
                    <button className="ghost" onClick={() => setProductDetailTab("purchase")}>
                      去添加渠道采购
                    </button>
                  )}
                </div>
              </div>
            )}
            {(activeProject.type === "商品项目" && productDetailTab === "basic") && (
            <>
            <h3>商品明细</h3>
            <div className="table">
              <div className={`table-row project-item-table head ${canViewProjectCost ? "" : "no-cost"} ${can("profit.view") ? "" : "no-profit"}`}><span>名称</span>{canViewProjectCost && <span>供应商/渠道价</span>}<span>数量</span><span>销售价</span>{can("profit.view") && <span>成本</span>}</div>
              {items.map((item) => (
                <div className={`table-row project-item-table ${canViewProjectCost ? "" : "no-cost"} ${can("profit.view") ? "" : "no-profit"}`} key={item.id}>
                  {(() => {
                    const supplier = data.organizations.find((org) => org.id === item.supplierOrgId);
                    const supplierPrice = data.supplierPrices.find((price) => price.id === item.supplierPriceId);
                    return (
                      <>
                        <span>
                          {item.productName}
                          {item.salesOrderId ? (
                            <em>{data.salesOrders.find((order) => order.id === item.salesOrderId)?.orderNo || "未关联销售单"}</em>
                          ) : null}
                        </span>
                        {canViewProjectCost && <span>{supplier?.name || "无"}<em>{supplierPrice ? `渠道价 ${money(supplierPrice.purchasePrice)} / ${supplierPrice.effectiveDate || "无日期"}` : "无渠道价记录"}</em></span>}
                      </>
                    );
                  })()}
                  <span>{item.quantity}</span>
                  <span>{money(item.actualPrice)}</span>
                  {can("profit.view") && <span>{money(item.costPrice)}</span>}
                </div>
              ))}
            </div>
            </>
            )}
            {activeProject.type === "服务项目" && serviceDetailTab === "basic" && onboarding && (
              <>
                <h3>平台入驻</h3>
                <div className="info-grid">
                  <Info label="平台" value={onboarding.platform} />
                  <Info label="步骤" value={onboarding.step} />
                  <Info label="营业执照编号" value={onboarding.businessLicenseNo} />
                  <Info label="域名" value={onboarding.domain ?? "未录入"} />
                  <Info label="亮照" value={onboarding.licenseDisplayStatus} />
                  <Info label="公安备案" value={onboarding.publicSecurityStatus} />
                </div>
              </>
            )}
            {activeProject.type === "服务项目" && serviceDetailTab === "overview" && (
            <>
            <h3>商品/服务明细</h3>
            <div className="table">
              <div className={`table-row project-item-table head ${canViewProjectCost ? "" : "no-cost"} ${can("profit.view") ? "" : "no-profit"}`}><span>名称</span>{canViewProjectCost && <span>供应商/渠道价</span>}<span>数量</span><span>销售价</span>{can("profit.view") && <span>成本</span>}</div>
              {items.map((item) => (
                <div className={`table-row project-item-table ${canViewProjectCost ? "" : "no-cost"} ${can("profit.view") ? "" : "no-profit"}`} key={item.id}>
                  {(() => {
                    const supplier = data.organizations.find((org) => org.id === item.supplierOrgId);
                    const supplierPrice = data.supplierPrices.find((price) => price.id === item.supplierPriceId);
                    return (
                      <>
                        <span>{item.productName}</span>
                        {canViewProjectCost && <span>{supplier?.name || "无"}<em>{supplierPrice ? `渠道价 ${money(supplierPrice.purchasePrice)} / ${supplierPrice.effectiveDate || "无日期"}` : "无渠道价记录"}</em></span>}
                      </>
                    );
                  })()}
                  <span>{item.quantity}</span>
                  <span>{money(item.actualPrice)}</span>
                  {can("profit.view") && <span>{money(item.costPrice)}</span>}
                </div>
              ))}
            </div>
            </>
            )}
            {activeProject.type === "服务项目" && serviceDetailTab === "overview" && (
              <>
                <h3>服务订单</h3>
                <div className="table">
                  <div className="table-row service-order-table head"><span>订单号</span><span>服务</span><span>金额</span><span>收款方式</span><span>状态</span><span>时间</span></div>
                  {serviceOrders.map((order) => (
                    <div className="table-row service-order-table" key={order.id}>
                      <span>
                        <CopyableLine text={order.orderNo} label="服务订单号">{order.orderNo}</CopyableLine>
                        <em>{order.note || "无备注"}</em>
                      </span>
                      <span>{activeProject.serviceProductName ?? "服务"}</span>
                      <span>{money(order.receivableAmount ?? order.amount)}<em>已收 {money(order.receivedAmount ?? 0)}</em>{canBackfillCollection(can, "service") && missingCollectionAmount(order.receivedAmount, collectionTxTotalForOrder(data.transactions, order.id, "service")) > 0 && <button type="button" className="copy-link" onClick={() => void backfillOrderCollection("service", order)}>补录流水</button>}</span>
                      <span className="collection-account-cell">{collectionAccountText(data, order.collectionAccount)}</span>
                      <span className="editable-status" onDoubleClick={() => can("project.edit") && getAllowedServiceOrderStatuses(order, serviceOrderStatuses).length > 1 && setEditingOrderStatus({ type: "service", id: order.id })}>
                        {editingOrderStatus?.type === "service" && editingOrderStatus.id === order.id ? (
                          <select value={order.status} autoFocus onBlur={() => setEditingOrderStatus(null)} onChange={(event) => void updateServiceOrderStatus(order, event.target.value as ServiceOrder["status"])}>
                            {getAllowedServiceOrderStatuses(order, serviceOrderStatuses).map((status) => <option key={status}>{status}</option>)}
                          </select>
                        ) : order.status}
                      </span>
                      <span>{order.createdAt}<em>{order.paidAt ? `付款 ${order.paidAt}` : order.refundedAt ? `退款 ${order.refundedAt}` : order.cancelledAt ? `取消 ${order.cancelledAt}` : `更新 ${order.updatedAt}`}</em></span>
                    </div>
                  ))}
                </div>
              </>
            )}
            {((activeProject.type === "商品项目" && productDetailTab === "invoices") || (activeProject.type === "服务项目" && serviceDetailTab === "overview")) && (
            <>
            <h3>项目发票</h3>
            <div className="table">
              <div className="table-row project-invoice-table head"><span>发票号/日期</span><span>类型</span><span>买方</span><span>卖方</span><span>金额</span><span>状态</span><span>操作</span></div>
              {projectInvoices.length > 0 ? projectInvoices.map((invoice) => {
                const linkedAmount = activeProject.type === "服务项目"
                  ? (normalizeServiceAllocations(invoice.serviceAllocations)
                      .filter((item) => item.projectId === activeProject.id)
                      .reduce((sum, item) => sum + item.amount, 0)
                    || (invoiceDirectProjectIds(invoice).includes(activeProject.id) ? Number(invoice.amount) || 0 : 0))
                  : Number(invoice.amount) || 0;
                return (
                <div className="table-row project-invoice-table" key={invoice.id}>
                  <span>{invoice.invoiceNo || "未录入"}<em>{invoice.invoiceDate || invoice.date || "未录入日期"}</em></span>
                  <span>{invoice.type}</span>
                  <span>{invoice.buyerName || "未录入"}</span>
                  <span>{invoice.sellerName || "未录入"}</span>
                  <span>{money(linkedAmount > 0 ? linkedAmount : invoice.amount)}{activeProject.type === "服务项目" && linkedAmount > 0 && linkedAmount + 0.009 < (Number(invoice.amount) || 0) ? <em>票面 {money(invoice.amount)}</em> : null}</span>
                  <span>{invoice.status}</span>
                  <span>
                    {activeProject.type === "服务项目" && can("invoice.manage") && (
                      <button
                        type="button"
                        className="copy-link danger-action"
                        onClick={() => void unlinkServiceInvoice(invoice, {
                          projectId: activeProject.id,
                          label: activeProject.name,
                        })}
                      >
                        取消关联
                      </button>
                    )}
                  </span>
                </div>
                );
              }) : (
                <div className="empty-line">暂无关联发票</div>
              )}
            </div>
            {activeProject.type === "服务项目" && (
              <>
                <div className="invoice-link-bar">
                  <SearchableSelect
                    value={projectInvoiceId}
                    options={invoiceLinkSelectOptions(data, {
                      kind: "service",
                      projectId: activeProject.id,
                      orderId: pickDefaultServiceOrderIdForInvoiceLink(data, activeProject.id),
                    })}
                    onChange={setProjectInvoiceId}
                    placeholder="搜索发票号、买卖方或金额"
                    ariaLabel="搜索并选择已有发票关联到项目"
                  />
                  {can("invoice.manage") && <button className="ghost" onClick={() => void linkInvoiceToProject(projectInvoiceId)}>关联发票</button>}
                </div>
                <p className="copy-tip">仅显示销项发票；可按金额拆分关联。额度已用尽、已完全匹配其他项目，或已关联商品订单的发票不会出现在待关联列表中。</p>
                <InvoiceQuickAddForm
                  invoices={data.invoices}
                  organizations={data.organizations}
                  defaultBuyer={{ id: customer?.id, name: customer?.name, taxNo: customer?.unifiedCreditCode }}
                  defaultSeller={{ id: ownCompany?.id, name: ownCompany?.name, taxNo: ownCompany?.unifiedCreditCode }}
                  canManage={can("invoice.manage")}
                  existingHint="到本项目（销项 / 服务类）"
                  ocrNewHint="识别完成，保存时将新增销项发票并关联本项目。"
                  expectedInvoiceType="销项"
                  onLinkExisting={(invoice) => linkInvoiceToProject(invoice.id)}
                  onCreateNew={(payload) => createLinkedInvoice(payload, {
                    type: "销项",
                    defaultProductName: activeProject.serviceProductName ?? activeProject.name,
                    logDetail: `服务项目销项发票关联：${activeProject.name}`,
                  })}
                />
              </>
            )}
            </>
            )}
            {activeProject.type === "服务项目" && serviceDetailTab === "reminders" && (
            <div className="reminder-project-panel">
              <ReminderForm data={data} commit={commit} currentUser={currentUser} fixedProjectId={activeProject.id} compact />
              <ReminderList data={data} commit={commit} reminders={projectReminders} hideProject />
            </div>
            )}
            {activeProject.type === "服务项目" && serviceDetailTab === "basic" && (
              <>
                <h3 id="project-platform-accounts">平台账号</h3>
                {serviceAccountCopyTip && <div className="copy-tip">{serviceAccountCopyTip}</div>}
                <div className="table">
                  <div className="table-row service-account-table head"><span>平台</span><span>账号</span><span>密码</span><span>商家ID</span><span>店铺ID</span><span>店铺名称</span><span>操作</span></div>
                  {projectPlatformAccounts.length > 0 ? projectPlatformAccounts.map((account) => (
                    <div className="table-row service-account-table" key={account.id}>
                      <span>{account.platform}</span>
                      <span><button className="copy-link" onClick={() => void copyServiceAccountText(account.accountName, "平台账号", account, "accountName")}>{maskedServiceAccountValue(account.accountName)}</button></span>
                      <span>{can("sensitive.view") ? <button className="copy-secret" onClick={() => void copyServiceAccountText(account.accountPasswordMasked, "平台密码", account, "accountPasswordMasked")}>{maskedServiceAccountValue(account.accountPasswordMasked)}</button> : account.accountPasswordMasked ? "已保存" : "未录入"}</span>
                      <span>{account.merchantId || "未录入"}</span>
                      <span>
                        {account.shopId ? (
                          <CopyableLine text={account.shopId} label="店铺ID">{account.shopId}</CopyableLine>
                        ) : "未录入"}
                      </span>
                      <span>
                        {account.shopName ? (
                          <CopyableLine text={account.shopName} label="店铺名称">{account.shopName}</CopyableLine>
                        ) : "未录入"}
                      </span>
                      <span className="order-actions">
                        {can("platformAccount.manage") && <button className="copy-link" onClick={() => editProjectPlatformAccount(account)}>编辑</button>}
                        {can("platformAccount.manage") && <button className="copy-link danger-action" onClick={() => void deleteProjectPlatformAccount(account)}>删除</button>}
                      </span>
                    </div>
                  )) : (
                    <div className="empty-line">暂无平台账号，可在下方维护，或到“平台账号”菜单统一管理。</div>
                  )}
                </div>
                {can("platformAccount.manage") && (
                  <div className="create-project project-platform-account-row">
                    <select value={serviceAccountDraft.platform} onChange={(event) => setServiceAccountDraft({ ...serviceAccountDraft, platform: event.target.value as PlatformAccount["platform"] })} aria-label="平台">
                      {onboardingPlatformOptions.map((item) => <option key={item}>{item}</option>)}
                    </select>
                    <input value={serviceAccountDraft.accountName} onChange={(event) => setServiceAccountDraft({ ...serviceAccountDraft, accountName: event.target.value })} placeholder="账号" />
                    <input type="text" value={serviceAccountDraft.accountPasswordMasked} onChange={(event) => setServiceAccountDraft({ ...serviceAccountDraft, accountPasswordMasked: event.target.value })} placeholder="密码" autoComplete="off" />
                    <input value={serviceAccountDraft.merchantId} onChange={(event) => setServiceAccountDraft({ ...serviceAccountDraft, merchantId: event.target.value })} placeholder="商家ID（可选）" />
                    <input value={serviceAccountDraft.shopId} onChange={(event) => setServiceAccountDraft({ ...serviceAccountDraft, shopId: event.target.value })} placeholder="店铺ID（可选）" />
                    <input value={serviceAccountDraft.shopName} onChange={(event) => setServiceAccountDraft({ ...serviceAccountDraft, shopName: event.target.value })} placeholder="店铺名称（可选）" />
                    <button className="primary" onClick={() => void addProjectPlatformAccount()}>{editingServiceAccountId ? "保存修改" : "保存账号"}</button>
                    {editingServiceAccountId && <button className="ghost" onClick={resetServiceAccountDraft}>取消</button>}
                  </div>
                )}
              </>
            )}
            {activeProject.type === "商品项目" && productDetailTab === "sales" && (
              <div ref={salesOrderSectionRef} className="project-sales-tab">
                <h3 id="project-sales-orders">销售订单{salesOrders.length > 0 ? `（${salesOrders.length}）` : ""}</h3>
                {can("project.edit") && activeProject.status !== "已完成" && (
                  <div className="sales-order-create-panel">
                    <p className="sales-order-compose-title">添加销售订单</p>
                    <p className="sales-order-compose-hint">用弹窗添加商品，每个商品必须关联渠道采购订单；不会写入已有订单。</p>
                    <button className="primary" type="button" onClick={openNewSalesOrderComposer}>添加销售订单</button>
                  </div>
                )}
                <div className="table sales-order-list">
                  <div className="table-row sales-order-table head"><span>订单号</span><span>商品信息</span><span>数量</span><span>单价</span><span>总价</span><span>订单价</span><span>状态</span><span>操作</span></div>
                  {salesOrders.map((order) => {
                    const items = salesOrderLinkedItems(data, order.id);
                    const lineItems = items.length > 0 ? items : [null];
                    const rowCount = lineItems.length;
                    const orderPrice = items.length > 0
                      ? items.reduce((sum, item) => sum + (Number(item.quantity) || 0) * (Number(item.actualPrice) || 0), 0)
                      : (order.receivableAmount ?? order.amount);
                    const canAppend = can("project.edit") && activeProject.status !== "已完成" && canEditSalesOrderItems(data, order);
                    const logisticsLocked = isSalesOrderLogisticsLocked(data, order);
                    return (
                      <div key={order.id} className="sales-order-entry">
                        <div
                          className="sales-order-block"
                          style={{ gridTemplateRows: `repeat(${rowCount}, auto)` }}
                        >
                          <span className="sales-order-span" style={{ gridColumn: 1, gridRow: `1 / span ${rowCount}` }}>
                            <CopyableLine text={order.orderNo} label="销售订单号">{order.orderNo}</CopyableLine>
                            <em>{order.platform ? `${order.platform}${order.platformOrderNo ? ` / ${order.platformOrderNo}` : ""}` : (order.note || "无备注")}</em>
                            {(() => {
                              const profit = salesOrderProfit(data, order);
                              const purchaseNos = profit.purchaseOrders.map((item) => item.orderNo).filter(Boolean);
                              return (
                                <>
                                  {purchaseNos.length > 0 && <em>关联采购 {purchaseNos.join("、")}</em>}
                                  {can("profit.view") && <em>{`毛利 ${money(profit.profit)} · 毛利率 ${grossMarginText(profit.margin)}`}</em>}
                                </>
                              );
                            })()}
                            <em>下单 {formatDateTimeValue(order.createdAt)}</em>
                            <em>更新 {formatDateTimeValue(order.updatedAt)}</em>
                            {logisticsLocked && <em>已发货/已签收，不可改商品</em>}
                          </span>
                          {lineItems.map((item, index) => {
                            const lineQty = item ? Number(item.quantity) || 0 : 0;
                            const unitPrice = item ? Number(item.actualPrice) || 0 : 0;
                            const lineTotal = item ? lineQty * unitPrice : (order.receivableAmount ?? order.amount);
                            const row = index + 1;
                            return (
                              <Fragment key={`${order.id}-${item?.id ?? "empty"}-${index}`}>
                                <span className="sales-order-line-cell" style={{ gridColumn: 2, gridRow: row }} title={item?.productName || ""}>
                                  {item ? (
                                    <CopyableLine text={item.productName} label="商品名称">
                                      {item.productName}
                                    </CopyableLine>
                                  ) : "未添加明细"}
                                  <ProjectProductMark product={item ? data.products.find((entry) => entry.id === item.productId) : undefined} />
                                  {item && <em className="sales-line-channel">{salesLineChannelText(item)}</em>}
                                  {canAppend && item && (
                                    <button type="button" className="copy-link danger-action" onClick={() => void removeSalesOrderLine(order, item.id)}>移除</button>
                                  )}
                                </span>
                                <span className="sales-order-line-cell" style={{ gridColumn: 3, gridRow: row }}>
                                  {canAppend && item ? (
                                    <input
                                      className="sales-order-qty-input"
                                      defaultValue={String(lineQty)}
                                      key={`${item.id}-${item.quantity}`}
                                      aria-label={`${item.productName} 数量`}
                                      onBlur={(event) => void updateSalesOrderLineQuantity(order, item.id, event.target.value)}
                                    />
                                  ) : (item ? lineQty : "—")}
                                </span>
                                <span className="sales-order-line-cell" style={{ gridColumn: 4, gridRow: row }}>
                                  {item ? money(unitPrice) : "—"}
                                </span>
                                <span className="sales-order-line-cell" style={{ gridColumn: 5, gridRow: row }}>
                                  {money(item ? lineTotal : (order.receivableAmount ?? order.amount))}
                                </span>
                              </Fragment>
                            );
                          })}
                          <span className="sales-order-span" style={{ gridColumn: 6, gridRow: `1 / span ${rowCount}` }}>
                            {money(orderPrice)}
                            <em>已收 {money(order.receivedAmount ?? 0)} / 应收 {money(orderPrice)}</em>
                            {can("profit.view") && (
                              <em>成本 {money(salesOrderProfit(data, order).costAmount)}</em>
                            )}
                          </span>
                          <span
                            className="sales-order-span editable-status"
                            style={{ gridColumn: 7, gridRow: `1 / span ${rowCount}` }}
                            onDoubleClick={() => can("project.edit") && activeProject.status !== "已完成" && getAllowedSalesOrderStatuses(order, salesOrderStatuses).length > 1 && setEditingOrderStatus({ type: "sales", id: order.id })}
                          >
                            {editingOrderStatus?.type === "sales" && editingOrderStatus.id === order.id ? (
                              <select value={order.status} autoFocus onBlur={() => setEditingOrderStatus(null)} onChange={(event) => void updateSalesOrderStatus(order, event.target.value as SalesOrder["status"])}>
                                {getAllowedSalesOrderStatuses(order, salesOrderStatuses).map((status) => <option key={status}>{status}</option>)}
                              </select>
                            ) : order.status}
                          </span>
                          <span className="sales-order-ops" style={{ gridColumn: 8, gridRow: `1 / span ${rowCount}` }}>
                            {canAppend && (
                              <button className="copy-link" type="button" onClick={() => openAppendSalesComposer(order)}>追加商品</button>
                            )}
                            <button className="copy-link" type="button" onClick={() => setSalesOrderPanel({ orderId: order.id, kind: "purchase" })}>关联采购</button>
                            <button className="copy-link" type="button" onClick={() => setSalesOrderPanel({ orderId: order.id, kind: "invoice" })}>发票管理</button>
                            <button className="copy-link" type="button" onClick={() => setSalesOrderPanel({ orderId: order.id, kind: "transactions" })}>查看流水</button>
                          </span>
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>
            )}
            {activeProject.type === "商品项目" && canViewProjectCost && productDetailTab === "purchase" && (
              <div ref={purchaseOrderSectionRef}>
                <div className="section-heading purchase-orders-heading">
                  <h3 id="project-purchase-orders">采购订单</h3>
                  <strong className="purchase-orders-total">
                    合计 {money(purchaseOrders.reduce((sum, order) => sum + purchaseOrderDisplayAmount(data, order), 0))}
                  </strong>
                </div>
                <div className="table sales-order-list">
                  <div className="table-row sales-order-table head"><span>订单号</span><span>商品信息</span><span>数量</span><span>单价</span><span>总价</span><span>订单价</span><span>状态</span><span>操作</span></div>
                  {purchaseOrders.map((order) => {
                    const supplier = data.organizations.find((org) => org.id === order.supplierOrgId);
                    const items = purchaseOrderLinkedItems(data, order.id);
                    const lineItems = items.length > 0 ? items : [null];
                    const rowCount = lineItems.length;
                    const orderAmount = purchaseOrderDisplayAmount(data, order);
                    const paidAmount = purchaseOrderPaidAmount(order, data.transactions);
                    const paymentStatus = order.paymentStatus ?? DEFAULT_ORDER_PAYMENT_STATUS;
                    const canPay = canRegisterPurchasePayment(can) && activeProject.status !== "已完成";
                    return (
                      <div key={order.id} className="sales-order-entry">
                        <div
                          className="sales-order-block"
                          style={{ gridTemplateRows: `repeat(${rowCount}, auto)` }}
                        >
                          <span className="sales-order-span" style={{ gridColumn: 1, gridRow: `1 / span ${rowCount}` }}>
                            <CopyableLine text={order.orderNo} label="采购订单号">{order.orderNo}</CopyableLine>
                            {supplier?.name ? (
                              <CopyableLine text={supplier.name} label="供应商">{supplier.name}</CopyableLine>
                            ) : <em>未选择供应商</em>}
                            <em>执行 {order.status}</em>
                            {order.batchNo && <em>批次 {order.batchNo}</em>}
                            <em>{order.note || "无备注"}</em>
                            <em>下单 {formatDateTimeValue(order.createdAt)}</em>
                          </span>
                          {lineItems.map((item, index) => {
                            const lineQty = item ? Number(item.quantity) || 0 : purchaseOrderQuantity(data, order.id);
                            const unitCost = item
                              ? purchaseOrderItemUnitCost(data, item, order.supplierOrgId)
                              : 0;
                            const lineTotal = item ? lineQty * unitCost : orderAmount;
                            const row = index + 1;
                            return (
                              <Fragment key={`${order.id}-${item?.id ?? "empty"}-${index}`}>
                                <span className="sales-order-line-cell" style={{ gridColumn: 2, gridRow: row }} title={item?.productName || ""}>
                                  {item ? (
                                    <CopyableLine text={item.productName} label="商品名称">
                                      {item.productName}
                                    </CopyableLine>
                                  ) : "未添加明细"}
                                  <ProjectProductMark product={item ? data.products.find((entry) => entry.id === item.productId) : undefined} />
                                </span>
                                <span className="sales-order-line-cell" style={{ gridColumn: 3, gridRow: row }}>
                                  {lineQty > 0 ? lineQty : "—"}
                                </span>
                                <span className="sales-order-line-cell" style={{ gridColumn: 4, gridRow: row }}>
                                  {item ? money(unitCost) : "—"}
                                </span>
                                <span className="sales-order-line-cell" style={{ gridColumn: 5, gridRow: row }}>
                                  {money(item ? lineTotal : orderAmount)}
                                </span>
                              </Fragment>
                            );
                          })}
                          <span className="sales-order-span" style={{ gridColumn: 6, gridRow: `1 / span ${rowCount}` }}>
                            {money(orderAmount)}
                            <em>已付 {money(paidAmount)} / 应付 {money(orderAmount)}</em>
                          </span>
                          <span
                            className="sales-order-span editable-status"
                            style={{ gridColumn: 7, gridRow: `1 / span ${rowCount}` }}
                            onDoubleClick={() => canPay && getAllowedOrderPaymentStatuses(paymentStatus, orderPaymentStatusOptions).length > 1 && setEditingOrderStatus({ type: "purchasePayment", id: order.id })}
                          >
                            {editingOrderStatus?.type === "purchasePayment" && editingOrderStatus.id === order.id ? (
                              <select value={paymentStatus} autoFocus onBlur={() => setEditingOrderStatus(null)} onChange={(event) => void updatePurchaseOrderPaymentStatus(order, event.target.value as OrderPaymentStatus)}>
                                {getAllowedOrderPaymentStatuses(paymentStatus, orderPaymentStatusOptions).map((status) => <option key={status}>{status}</option>)}
                              </select>
                            ) : paymentStatus}
                          </span>
                          <span className="sales-order-ops" style={{ gridColumn: 8, gridRow: `1 / span ${rowCount}` }}>
                            <button className="copy-link" type="button" onClick={() => setPurchaseOrderPanel({ orderId: order.id, kind: "fulfillment" })}>履约详情</button>
                            <button className="copy-link" type="button" onClick={() => setPurchaseOrderPanel({ orderId: order.id, kind: "invoice" })}>发票管理</button>
                            <button className="copy-link" type="button" onClick={() => setPurchaseOrderPanel({ orderId: order.id, kind: "transactions" })}>查看流水</button>
                            {canPay && paymentStatus !== "已付款" && paymentStatus !== "取消" && paymentStatus !== "退款" && (
                              <button
                                className="copy-link"
                                type="button"
                                onClick={() => void registerPurchasePayment({
                                  data,
                                  commit,
                                  requestPayment,
                                  order,
                                  payable: orderAmount,
                                  targetStatus: "部分付款",
                                  operator: currentUser.name,
                                })}
                              >
                                登记付款
                              </button>
                            )}
                            {(can("purchase.manage") || can("project.edit"))
                              && (order.status === "待下单" || order.status === "草稿")
                              && activeProject.status !== "已完成"
                              && <button className="copy-link danger-action" type="button" onClick={() => void deletePurchaseOrder(order)}>删除</button>}
                          </span>
                        </div>
                      </div>
                    );
                  })}
                </div>
                {can("purchase.manage") && activeProject.status !== "已完成" && (
                  <div className="purchase-create-panel">
                    <div className="purchase-create-toggles">
                      <label className="purchase-split-toggle">
                        <input
                          type="checkbox"
                          checked={purchaseValidateAgainstSales}
                          onChange={(event) => setPurchaseValidateAgainstSales(event.target.checked)}
                        />
                        按销售订单校验商品与数量（关闭后可添加打包类采购，不限制销售可采数量）
                      </label>
                      <label className="purchase-split-toggle">
                        <input
                          type="checkbox"
                          checked={purchaseSplitMode}
                          onChange={(event) => togglePurchaseSplitMode(event.target.checked)}
                        />
                        根据销售订单商品拆单（默认不拆单；勾选后按销售 SKU 分别生成采购订单）
                      </label>
                    </div>
                    <label className="order-time-field">
                      <span>下单时间</span>
                      <DateTimeField
                        mode="datetime"
                        value={purchaseOrderedAt}
                        onChange={setPurchaseOrderedAt}
                        ariaLabel="下单时间"
                        placeholder="下单时间"
                      />
                    </label>
                    {purchaseSplitMode ? (
                      <div className="purchase-split-table">
                        <div className="purchase-split-row head">
                          <span>{purchaseValidateAgainstSales ? "商品（销售订单内）" : "商品"}</span>
                          <span>数量</span>
                          <span>供应商</span>
                          <span>采购单价</span>
                          <span>操作</span>
                        </div>
                        {purchaseSplitLines.map((line) => (
                          <div className="purchase-split-row" key={line.key}>
                            <SearchableSelect
                              value={line.productId}
                              options={purchaseProductSelectOptions}
                              onChange={(productId) => updatePurchaseSplitLine(line.key, { productId })}
                              placeholder="选择销售商品"
                              ariaLabel="选择采购商品"
                            />
                            <input
                              value={line.quantity}
                              onChange={(event) => updatePurchaseSplitLine(line.key, { quantity: event.target.value })}
                              placeholder="数量"
                            />
                            <SearchableSelect
                              value={line.supplierOrgId}
                              options={supplierSelectOptions}
                              onChange={(supplierOrgId) => updatePurchaseSplitLine(line.key, { supplierOrgId })}
                              placeholder={supplierSelectOptions.length ? "搜索并选择供应商" : "暂无供应商"}
                              ariaLabel="选择供应商"
                            />
                            <input
                              value={line.purchaseUnitPrice}
                              onChange={(event) => updatePurchaseSplitLine(line.key, { purchaseUnitPrice: event.target.value })}
                              placeholder="采购单价"
                            />
                            <button type="button" className="copy-link danger-action" onClick={() => removePurchaseSplitLine(line.key)}>删除</button>
                          </div>
                        ))}
                        <div className="order-create">
                          <button type="button" className="ghost" onClick={() => addPurchaseSplitLine()}>添加采购行（可同商品不同渠道）</button>
                          <button type="button" className="ghost" onClick={() => togglePurchaseSplitMode(true)}>按销售商品重新载入</button>
                          <button type="button" className="primary" onClick={() => void addSplitPurchaseOrders()}>生成拆单采购订单</button>
                        </div>
                      </div>
                    ) : (
                      <>
                        <div className="create-project order-create">
                          <SearchableSelect
                            value={orderDraft.productId}
                            options={purchaseProductSelectOptions}
                            onChange={updateOrderProduct}
                            placeholder={
                              purchaseProductSelectOptions.length
                                ? (purchaseValidateAgainstSales ? "搜索销售订单中的商品" : "搜索实体商品（含打包）")
                                : (purchaseValidateAgainstSales ? "请先添加销售订单商品，或关闭按销售校验" : "暂无实体商品")
                            }
                            ariaLabel="选择采购商品"
                          />
                          <SearchableSelect
                            value={orderDraft.supplierOrgId}
                            options={supplierSelectOptions}
                            onChange={updateOrderSupplier}
                            placeholder={supplierSelectOptions.length ? "搜索并选择供应商" : "暂无供应商"}
                            ariaLabel="选择供应商"
                          />
                          <input value={orderDraft.quantity} onChange={(event) => setOrderDraft({ ...orderDraft, quantity: event.target.value })} placeholder="数量" />
                          <input value={orderDraft.purchaseUnitPrice} onChange={(event) => setOrderDraft({ ...orderDraft, purchaseUnitPrice: event.target.value })} placeholder="采购单价" />
                          <input value={orderDraft.note} onChange={(event) => setOrderDraft({ ...orderDraft, note: event.target.value })} placeholder="备注" />
                          <button className="ghost" onClick={addPurchaseOrderDraftItem} disabled={purchaseProductSelectOptions.length === 0}>加入商品</button>
                          <button className="ghost" onClick={() => void addPurchaseOrder(false)} disabled={purchaseProductSelectOptions.length === 0}>创建采购订单</button>
                          {purchaseOrders.some((order) => order.supplierOrgId === orderDraft.supplierOrgId && (order.status === "待下单" || order.status === "草稿")) && (
                            <button className="ghost" onClick={() => void addPurchaseOrder(true)} disabled={purchaseProductSelectOptions.length === 0}>追加到同供应商订单</button>
                          )}
                        </div>
                        {purchaseOrderDraftItems.length > 0 && (
                          <div className="invoice-items">
                            {purchaseOrderDraftItems.map((item, index) => (
                              <span key={`${item.productId}-${index}`}>
                                {item.productName}
                                <em>{item.quantity} 件 / {money(item.unitPrice)} / 小计 {money(item.quantity * item.unitPrice)}
                                  <button className="copy-link danger-action" onClick={() => setPurchaseOrderDraftItems(purchaseOrderDraftItems.filter((_, itemIndex) => itemIndex !== index))}>移除</button>
                                </em>
                              </span>
                            ))}
                          </div>
                        )}
                      </>
                    )}
                  </div>
                )}
              </div>
            )}
            {((activeProject.type === "商品项目" && productDetailTab === "logs") || (activeProject.type === "服务项目" && serviceDetailTab === "logs")) && (
              <div className="log-list related-log-list project-detail-logs">
                {relatedProjectLogs.length > 0 ? relatedProjectLogs.map((log) => (
                  <article className="log-card" key={log.id}>
                    <div><span className="tag">{log.targetType}</span><strong>{log.action}</strong><p>{log.targetName}</p></div>
                    <div><span>{log.operator}</span><em>{formatDateTimeValue(log.createdAt)}</em></div>
                    <p>{log.detail || "无详情"}</p>
                  </article>
                )) : <div className="empty-state">暂无相关日志</div>}
              </div>
            )}
            {activeProject.type === "商品项目" && productDetailTab === "memos" && (
              <div className="project-memo-panel">
                <div className="project-memo-form">
                  <label className="project-memo-field">
                    <span>备忘内容</span>
                    <textarea
                      value={memoDraft}
                      maxLength={PROJECT_MEMO_MAX_LENGTH}
                      onChange={(event) => setMemoDraft(event.target.value.slice(0, PROJECT_MEMO_MAX_LENGTH))}
                      placeholder={`填写备忘内容，最多 ${PROJECT_MEMO_MAX_LENGTH} 字`}
                      rows={3}
                    />
                    <em>{memoDraft.trim().length}/{PROJECT_MEMO_MAX_LENGTH}</em>
                  </label>
                  <button className="primary" onClick={() => void createProjectMemo()} disabled={!memoDraft.trim()}>
                    <ClipboardList size={16} />添加备忘
                  </button>
                </div>
                <SearchField
                  className="memo-search"
                  value={memoSearch}
                  onChange={setMemoSearch}
                  placeholder="搜索备忘内容"
                />
                <div className="table">
                  <div className="table-row project-memo-table head"><span>备忘内容</span><span>添加人</span><span>创建时间</span></div>
                  {projectMemosPage.items.map((memo) => (
                    <div className="table-row project-memo-table" key={memo.id}>
                      <span>{memo.content}</span>
                      <span>{memo.createdBy}</span>
                      <span>{formatDateTimeValue(memo.createdAt)}</span>
                    </div>
                  ))}
                  {projectMemosPage.total === 0 && (
                    <div className="table-row project-memo-table"><span>暂无备忘</span><span></span><span></span></div>
                  )}
                </div>
                <Pagination {...projectMemosPage} onPageChange={projectMemosPage.setPage} />
              </div>
            )}
            </div>
          </div>
        </div>
      )}
      {activeProject && salesPanelOrder && salesOrderPanel?.kind === "purchase" && (
        <div className="modal-backdrop is-nested" role="presentation">
          <div className="modal order-tx-modal" role="dialog" aria-modal="true" aria-label="关联采购订单">
            <div className="modal-head">
              <div>
                <h2>关联采购订单</h2>
                <p>{salesPanelOrder.orderNo} · 可手动关联本项目的多张采购订单，毛利按订单计算</p>
              </div>
              <button className="icon-button" onClick={() => setSalesOrderPanel(null)} aria-label="关闭关联采购"><X size={18} /></button>
            </div>
            <SalesOrderPurchaseLinker
              data={data}
              order={salesPanelOrder}
              canManage={(can("salesOrder.manage") || can("project.edit")) && activeProject.status !== "已完成"}
              canViewProfit={can("profit.view")}
              onSave={async (purchaseOrderIds) => {
                await commit(
                  applySalesOrderPurchaseLinks(data, salesPanelOrder.id, purchaseOrderIds),
                  {
                    action: "关联销售订单采购",
                    targetType: "项目",
                    targetName: activeProject.name,
                    operator: "当前用户",
                    detail: `${salesPanelOrder.orderNo} 关联采购 ${purchaseOrderIds.length} 笔`,
                  },
                );
              }}
            />
            <div className="modal-actions">
              <button className="ghost" type="button" onClick={() => setSalesOrderPanel(null)}>关闭</button>
            </div>
          </div>
        </div>
      )}
      {activeProject && salesPanelOrder && salesOrderPanel?.kind === "invoice" && (
        <div className="modal-backdrop is-nested" role="presentation">
          <div className="modal order-invoice-modal" role="dialog" aria-modal="true" aria-label="销售订单发票管理">
            <div className="modal-head">
              <div>
                <h2>发票管理</h2>
                <p>{salesPanelOrder.orderNo} · 关联已有发票、手工添加或 OCR 识别后关联到本单</p>
              </div>
              <button className="icon-button" onClick={() => setSalesOrderPanel(null)} aria-label="关闭发票管理"><X size={18} /></button>
            </div>
            <OrderInvoiceAssociationPanel
              linkedInvoices={orderLinkedInvoices(data, salesPanelOrder.id, "sales")}
              invoiceSelectOptions={invoiceLinkSelectOptions(data, { kind: "sales", projectId: salesPanelOrder.projectId, orderId: salesPanelOrder.id })}
              selectedInvoiceId={orderInvoiceIds[salesPanelOrder.id] ?? ""}
              canManage={can("invoice.manage")}
              invoices={data.invoices}
              organizations={data.organizations}
              defaultBuyer={{ id: customer?.id, name: customer?.name, taxNo: customer?.unifiedCreditCode }}
              defaultSeller={{ id: ownCompany?.id, name: ownCompany?.name, taxNo: ownCompany?.unifiedCreditCode }}
              existingHint={`到本销售订单 ${salesPanelOrder.orderNo}（销项）`}
              ocrNewHint={`识别完成，保存时将新增销项发票并关联 ${salesPanelOrder.orderNo}。`}
              expectedInvoiceType="销项"
              orderId={salesPanelOrder.id}
              orderType="sales"
              orderSummary={orderInvoicePickSummary(data, salesPanelOrder.id, "sales")}
              orderNoById={buildOrderNoById(data)}
              onSelectInvoice={(invoiceId) => setOrderInvoiceIds({ ...orderInvoiceIds, [salesPanelOrder.id]: invoiceId })}
              onLink={(lineIndexes, lineQuantities) => void linkInvoiceToOrder(orderInvoiceIds[salesPanelOrder.id], salesPanelOrder, "sales", lineIndexes, lineQuantities)}
              onUnlink={(invoice) => void unlinkInvoiceFromOrder(invoice, salesPanelOrder, "sales")}
              onLinkExisting={async (invoice, lineIndexes, lineQuantities) => linkInvoiceToOrder(invoice.id, salesPanelOrder, "sales", lineIndexes, lineQuantities)}
              onCreateNew={(payload) => createLinkedInvoice(payload, {
                type: "销项",
                salesOrderId: salesPanelOrder.id,
                defaultProductName: salesOrderLinkedItems(data, salesPanelOrder.id)[0]?.productName ?? activeProject.name,
                logDetail: `销售订单销项发票关联：${salesPanelOrder.orderNo}`,
              })}
            />
            <div className="modal-actions">
              <button className="ghost" type="button" onClick={() => setSalesOrderPanel(null)}>关闭</button>
            </div>
          </div>
        </div>
      )}
      {activeProject && salesPanelOrder && salesOrderPanel?.kind === "transactions" && (
        <div className="modal-backdrop is-nested" role="presentation">
          <div className="modal order-tx-modal" role="dialog" aria-modal="true" aria-label="销售订单流水">
            <div className="modal-head">
              <div>
                <h2>查看流水</h2>
                <p>{salesPanelOrder.orderNo} · 已收 {money(salesPanelOrder.receivedAmount ?? 0)} / 应收 {money(salesPanelOrder.receivableAmount ?? salesPanelOrder.amount)}</p>
              </div>
              <button className="icon-button" onClick={() => setSalesOrderPanel(null)} aria-label="关闭流水"><X size={18} /></button>
            </div>
            <OrderTransactionList
              data={data}
              transactions={transactionsForOrder(data.transactions, salesPanelOrder.id, "销售订单", salesPanelOrder.orderNo)}
            />
            <div className="modal-actions">
              {canBackfillCollection(can, "sales") && missingCollectionAmount(salesPanelOrder.receivedAmount, collectionTxTotalForOrder(data.transactions, salesPanelOrder.id, "sales")) > 0 && (
                <button className="ghost" type="button" onClick={() => void backfillOrderCollection("sales", salesPanelOrder)}><Banknote size={16} />补录流水</button>
              )}
              <button className="ghost" type="button" onClick={() => setSalesOrderPanel(null)}>关闭</button>
            </div>
          </div>
        </div>
      )}
      {activeProject && purchasePanelOrder && purchaseOrderPanel?.kind === "fulfillment" && (
        <div className="modal-backdrop is-nested" role="presentation">
          <div className="modal order-fulfillment-modal" role="dialog" aria-modal="true" aria-label="采购订单履约详情">
            <div className="modal-head">
              <div>
                <h2>履约详情</h2>
                <p>{purchasePanelOrder.orderNo} · 执行 {purchasePanelOrder.status} · 货款 {purchasePanelOrder.paymentStatus ?? DEFAULT_ORDER_PAYMENT_STATUS}</p>
              </div>
              <button className="icon-button" onClick={() => setPurchaseOrderPanel(null)} aria-label="关闭履约详情"><X size={18} /></button>
            </div>
            <div className="fulfillment-grid">
              <label>
                <span>执行状态</span>
                <select
                  value={purchasePanelOrder.status}
                  disabled={!can("purchase.manage")}
                  onChange={(event) => void updatePurchaseOrderStatus(purchasePanelOrder, event.target.value as PurchaseOrder["status"])}
                >
                  {getAllowedPurchaseOrderStatuses(purchasePanelOrder, purchaseOrderStatuses).map((status) => <option key={status}>{status}</option>)}
                </select>
              </label>
              <label>
                <span>物流状态</span>
                <select
                  value={purchasePanelOrder.logisticsStatus ?? DEFAULT_LOGISTICS_STATUS}
                  disabled={!can("purchase.manage")}
                  onChange={(event) => void updatePurchaseOrderFields(purchasePanelOrder, { logisticsStatus: event.target.value as LogisticsStatus })}
                >
                  {logisticsStatusOptions.map((status) => <option key={status}>{status}</option>)}
                </select>
              </label>
              {(purchasePanelOrder.logisticsStatus ?? DEFAULT_LOGISTICS_STATUS) === "已发货" && (
                <label>
                  <span>物流单号</span>
                  <input
                    defaultValue={purchasePanelOrder.logisticsNo ?? ""}
                    key={`logistics-no-${purchasePanelOrder.id}-${purchasePanelOrder.updatedAt}`}
                    disabled={!can("purchase.manage")}
                    placeholder="请输入物流单号"
                    onBlur={(event) => {
                      if ((purchasePanelOrder.logisticsNo ?? "") !== event.target.value.trim()) {
                        void updatePurchaseOrderFields(purchasePanelOrder, { logisticsNo: event.target.value.trim() || undefined });
                      }
                    }}
                  />
                </label>
              )}
              <label>
                <span>验收状态</span>
                <select
                  value={purchasePanelOrder.acceptanceStatus ?? DEFAULT_ACCEPTANCE_STATUS}
                  disabled={!can("purchase.manage")}
                  onChange={(event) => void updatePurchaseOrderFields(purchasePanelOrder, { acceptanceStatus: event.target.value as AcceptanceStatus })}
                >
                  {acceptanceStatusOptions.map((status) => <option key={status}>{status}</option>)}
                </select>
              </label>
              <label>
                <span>交付状态</span>
                <select
                  value={purchasePanelOrder.deliveryStatus ?? DEFAULT_DELIVERY_STATUS}
                  disabled={!can("purchase.manage")}
                  onChange={(event) => void updatePurchaseOrderFields(purchasePanelOrder, { deliveryStatus: event.target.value as DeliveryStatus })}
                >
                  {deliveryStatusOptions.map((status) => <option key={status}>{status}</option>)}
                </select>
              </label>
              <label>
                <span>合同状态</span>
                <select
                  value={purchasePanelOrder.contractStatus ?? DEFAULT_CONTRACT_STATUS}
                  disabled={!can("purchase.manage")}
                  onChange={(event) => void updatePurchaseOrderContractStatus(purchasePanelOrder, event.target.value as ContractStatus)}
                >
                  {contractStatusOptions.map((status) => <option key={status}>{status}</option>)}
                </select>
              </label>
              {((purchasePanelOrder.contractStatus ?? DEFAULT_CONTRACT_STATUS) === "已签" || purchasePanelOrder.contractFileId) && (
                <label>
                  <span>合同文件</span>
                  <ContractFileActions
                    fileId={purchasePanelOrder.contractFileId}
                    canReplace={can("purchase.manage")}
                    onView={() => setContractViewerFileId(purchasePanelOrder.contractFileId!)}
                    onReplace={() => { setPoContractUploadOrderId(purchasePanelOrder.id); setPoContractFile(null); }}
                  />
                </label>
              )}
              <label>
                <span>对账状态</span>
                <select
                  value={purchasePanelOrder.reconcileStatus ?? DEFAULT_RECONCILE_STATUS}
                  disabled={!can("purchase.manage")}
                  onChange={(event) => {
                    const next = event.target.value as ReconcileStatus;
                    if (next === (purchasePanelOrder.reconcileStatus ?? DEFAULT_RECONCILE_STATUS)) return;
                    void updatePurchaseOrderFields(purchasePanelOrder, { reconcileStatus: next }, "修改采购对账状态");
                  }}
                >
                  {reconcileStatusOptions.map((status) => <option key={status}>{status}</option>)}
                </select>
              </label>
            </div>
            <div className="modal-actions">
              <button className="ghost" type="button" onClick={() => setPurchaseOrderPanel(null)}>关闭</button>
            </div>
          </div>
        </div>
      )}
      {activeProject && purchasePanelOrder && purchaseOrderPanel?.kind === "invoice" && (
        <div className="modal-backdrop is-nested" role="presentation">
          <div className="modal order-invoice-modal" role="dialog" aria-modal="true" aria-label="采购订单发票管理">
            <div className="modal-head">
              <div>
                <h2>发票管理</h2>
                <p>{purchasePanelOrder.orderNo} · 关联已有发票、手工添加或 OCR 识别后关联到本单</p>
              </div>
              <button className="icon-button" onClick={() => setPurchaseOrderPanel(null)} aria-label="关闭发票管理"><X size={18} /></button>
            </div>
            <OrderInvoiceAssociationPanel
              linkedInvoices={orderLinkedInvoices(data, purchasePanelOrder.id, "purchase")}
              invoiceSelectOptions={invoiceLinkSelectOptions(data, { kind: "purchase", projectId: purchasePanelOrder.projectId, orderId: purchasePanelOrder.id })}
              selectedInvoiceId={orderInvoiceIds[purchasePanelOrder.id] ?? ""}
              canManage={can("invoice.manage")}
              invoices={data.invoices}
              organizations={data.organizations}
              defaultBuyer={{ id: ownCompany?.id, name: ownCompany?.name, taxNo: ownCompany?.unifiedCreditCode }}
              defaultSeller={{
                id: data.organizations.find((org) => org.id === purchasePanelOrder.supplierOrgId)?.id,
                name: data.organizations.find((org) => org.id === purchasePanelOrder.supplierOrgId)?.name,
                taxNo: data.organizations.find((org) => org.id === purchasePanelOrder.supplierOrgId)?.unifiedCreditCode,
              }}
              existingHint={`到本采购订单 ${purchasePanelOrder.orderNo}（进项）`}
              ocrNewHint={`识别完成，保存时将新增进项发票并关联 ${purchasePanelOrder.orderNo}。`}
              expectedInvoiceType="进项"
              orderId={purchasePanelOrder.id}
              orderType="purchase"
              orderSummary={orderInvoicePickSummary(data, purchasePanelOrder.id, "purchase")}
              orderNoById={buildOrderNoById(data)}
              onSelectInvoice={(invoiceId) => setOrderInvoiceIds({ ...orderInvoiceIds, [purchasePanelOrder.id]: invoiceId })}
              onLink={(lineIndexes, lineQuantities) => void linkInvoiceToOrder(orderInvoiceIds[purchasePanelOrder.id], purchasePanelOrder, "purchase", lineIndexes, lineQuantities)}
              onUnlink={(invoice) => void unlinkInvoiceFromOrder(invoice, purchasePanelOrder, "purchase")}
              onLinkExisting={async (invoice, lineIndexes, lineQuantities) => linkInvoiceToOrder(invoice.id, purchasePanelOrder, "purchase", lineIndexes, lineQuantities)}
              onCreateNew={(payload) => createLinkedInvoice(payload, {
                type: "进项",
                purchaseOrderId: purchasePanelOrder.id,
                defaultProductName: data.projectItems.find((item) => item.purchaseOrderId === purchasePanelOrder.id)?.productName ?? activeProject.name,
                logDetail: `采购订单进项发票关联：${purchasePanelOrder.orderNo}`,
              })}
            />
            <div className="modal-actions">
              <button className="ghost" type="button" onClick={() => setPurchaseOrderPanel(null)}>关闭</button>
            </div>
          </div>
        </div>
      )}
      {activeProject && purchasePanelOrder && purchaseOrderPanel?.kind === "transactions" && (
        <div className="modal-backdrop is-nested" role="presentation">
          <div className="modal order-tx-modal" role="dialog" aria-modal="true" aria-label="采购订单流水">
            <div className="modal-head">
              <div>
                <h2>查看流水</h2>
                <p>{purchasePanelOrder.orderNo} · 已付 {money(purchaseOrderPaidAmount(purchasePanelOrder, data.transactions))} / 应付 {money(purchaseOrderDisplayAmount(data, purchasePanelOrder))}</p>
              </div>
              <button className="icon-button" onClick={() => setPurchaseOrderPanel(null)} aria-label="关闭流水"><X size={18} /></button>
            </div>
            <OrderTransactionList
              data={data}
              transactions={transactionsForOrder(data.transactions, purchasePanelOrder.id, "采购订单", purchasePanelOrder.orderNo)}
            />
            <div className="modal-actions">
              {canRegisterPurchasePayment(can) && (purchasePanelOrder.paymentStatus ?? DEFAULT_ORDER_PAYMENT_STATUS) !== "已付款" && (
                <button
                  className="ghost"
                  type="button"
                  onClick={() => void registerPurchasePayment({
                    data,
                    commit,
                    requestPayment,
                    order: purchasePanelOrder,
                    payable: purchaseOrderDisplayAmount(data, purchasePanelOrder),
                    targetStatus: (purchasePanelOrder.paymentStatus ?? DEFAULT_ORDER_PAYMENT_STATUS) === "待付款" ? "部分付款" : "已付款",
                    operator: currentUser.name,
                  })}
                >
                  <Banknote size={16} />登记付款
                </button>
              )}
              <button className="ghost" type="button" onClick={() => setPurchaseOrderPanel(null)}>关闭</button>
            </div>
          </div>
        </div>
      )}
      {salesComposer && activeProject && (
        <div className="modal-backdrop is-nested" role="presentation">
          <div className="modal sales-composer-modal" role="dialog" aria-modal="true" aria-label={salesComposer.targetOrderId ? "追加销售商品" : "添加销售订单"}>
            <div className="modal-head">
              <div>
                <h2>{salesComposer.targetOrderId ? "追加商品到销售订单" : "添加销售订单"}</h2>
                <p>{salesComposer.targetOrderId ? "追加商品不会改原销售单的下单时间。" : "填写采购人后添加商品；每个商品都要选择渠道供应商，保存时会同时创建或追加对应采购订单。"}</p>
              </div>
              <button className="icon-button" onClick={() => { setSalesComposer(null); setSalesProductDraft(null); }} aria-label="关闭销售订单弹窗"><X size={18} /></button>
            </div>
            {!salesComposer.targetOrderId && (
              <div className="sales-composer-fields">
                <label className="sales-composer-field">
                  <span>下单时间</span>
                  <DateTimeField
                    mode="datetime"
                    value={salesComposer.orderedAt}
                    onChange={(orderedAt) => setSalesComposer({ ...salesComposer, orderedAt })}
                    ariaLabel="下单时间"
                    placeholder="下单时间"
                  />
                </label>
                <label className="sales-composer-field">
                  <span>平台订单编号</span>
                  <input
                    value={salesComposer.platformOrderNo}
                    onChange={(event) => setSalesComposer({ ...salesComposer, platformOrderNo: event.target.value })}
                    placeholder="可选"
                  />
                </label>
                <label className="sales-composer-field sales-composer-field-full">
                  <span>备注 可选</span>
                  <input
                    value={salesComposer.note}
                    onChange={(event) => setSalesComposer({ ...salesComposer, note: event.target.value })}
                    placeholder="可选"
                  />
                </label>
                <span className="sales-composer-field sales-composer-field-full">采购人</span>
                <PurchaserQuickPaste onFill={(parsed) => setSalesComposer({ ...salesComposer, ...parsed })} />
                <label className="sales-composer-field">
                  <span>公司名称</span>
                  <input value={salesComposer.purchaserCompany} onChange={(event) => setSalesComposer({ ...salesComposer, purchaserCompany: event.target.value })} placeholder="采购人公司名称" aria-label="采购人公司名称" />
                </label>
                <label className="sales-composer-field">
                  <span>地址（收货地址）</span>
                  <input value={salesComposer.purchaserAddress} onChange={(event) => setSalesComposer({ ...salesComposer, purchaserAddress: event.target.value })} placeholder="采购人收货地址" aria-label="采购人收货地址" />
                </label>
                <label className="sales-composer-field">
                  <span>姓名</span>
                  <input value={salesComposer.purchaserName} onChange={(event) => setSalesComposer({ ...salesComposer, purchaserName: event.target.value })} placeholder="采购人姓名" aria-label="采购人姓名" />
                </label>
                <label className="sales-composer-field">
                  <span>电话</span>
                  <input value={salesComposer.purchaserPhone} onChange={(event) => setSalesComposer({ ...salesComposer, purchaserPhone: event.target.value })} placeholder="采购人电话" aria-label="采购人电话" />
                </label>
              </div>
            )}
            <div className="sales-composer-lines">
              {salesComposer.lines.length === 0 ? (
                <div className="empty-line">还没有商品，请点击「添加商品」。</div>
              ) : salesComposer.lines.map((line) => (
                <div className="sales-composer-line" key={line.key}>
                  <span>{composerLineLabel(line)}</span>
                  <span className="order-actions">
                    <button className="copy-link" type="button" onClick={() => openSalesProductDraft({ ...line })}>编辑</button>
                    <button className="copy-link danger-action" type="button" onClick={() => setSalesComposer({ ...salesComposer, lines: salesComposer.lines.filter((item) => item.key !== line.key) })}>移除</button>
                  </span>
                </div>
              ))}
            </div>
            <div className="modal-actions">
              <button className="ghost" type="button" onClick={() => openSalesProductDraft()}>添加商品</button>
              <button className="ghost" type="button" onClick={() => { setSalesComposer(null); setSalesProductDraft(null); }}>取消</button>
              <button className="primary" type="button" onClick={() => void submitSalesComposer()}>{salesComposer.targetOrderId ? "保存追加" : "创建销售订单"}</button>
            </div>
          </div>
        </div>
      )}
      {salesProductDraft && salesComposer && (
        <div className="modal-backdrop is-nested-2" role="presentation">
          <div className="modal sales-product-modal" role="dialog" aria-modal="true" aria-label="添加销售商品">
            <div className="modal-head">
              <div>
                <h2>添加商品并关联渠道</h2>
                <p>商品需要关联渠道采购订单：选择供应商后可追加已有待下单采购单，或自动新建。</p>
              </div>
              <button className="icon-button" onClick={() => setSalesProductDraft(null)} aria-label="关闭添加商品"><X size={18} /></button>
            </div>
            <div className="segmented sales-product-tabs" role="tablist" aria-label="添加商品方式">
              <button type="button" role="tab" aria-selected={salesProductMode === "catalog"} className={salesProductMode === "catalog" ? "active" : undefined} onClick={() => switchSalesProductMode("catalog")}>选择商品</button>
              <button type="button" role="tab" aria-selected={salesProductMode === "quick"} className={salesProductMode === "quick" ? "active" : undefined} onClick={() => switchSalesProductMode("quick")}>快捷添加</button>
            </div>
            <p className="sales-order-compose-hint">
              {salesProductMode === "quick" ? "快捷商品仅本项目使用，不进入商品及价格体系。" : "从商品库选择后会带出销售价和采购价，可再修改。"}
            </p>
            <div className="create-project create-project-modal-form">
              {salesProductMode === "catalog" ? (
                <>
                  <SearchableSelect
                    value={salesProductDraft.productId}
                    options={salesProductSelectOptions}
                    onChange={(productId) => patchSalesProductDraft({ productId, directProductName: "", directPlatformPrice: "" })}
                    placeholder="搜索并选择销售商品"
                    ariaLabel="选择销售商品"
                  />
                  <input value={salesProductDraft.quantity} onChange={(event) => patchSalesProductDraft({ quantity: event.target.value })} placeholder="数量" />
                  <input value={salesProductDraft.salesUnitPrice} onChange={(event) => patchSalesProductDraft({ salesUnitPrice: event.target.value })} placeholder="销售单价" />
                </>
              ) : (
                <>
                  <input className="sales-product-name-field" value={salesProductDraft.directProductName} onChange={(event) => patchSalesProductDraft({ directProductName: event.target.value, productId: "" })} placeholder="快捷商品名称" aria-label="快捷商品名称" />
                  <input value={salesProductDraft.directPlatformPrice} onChange={(event) => patchSalesProductDraft({ directPlatformPrice: event.target.value })} placeholder="平台价" aria-label="平台价" />
                  <input value={salesProductDraft.quantity} onChange={(event) => patchSalesProductDraft({ quantity: event.target.value })} placeholder="数量" />
                  <input value={salesProductDraft.salesUnitPrice} onChange={(event) => patchSalesProductDraft({ salesUnitPrice: event.target.value })} placeholder="销售单价" />
                </>
              )}
              <select value={salesProductDraft.supplierOrgId} onChange={(event) => patchSalesProductDraft({ supplierOrgId: event.target.value })} aria-label="渠道供应商">
                <option value="">请选择渠道供应商</option>
                {suppliers.map((org) => <option key={org.id} value={org.id}>{org.name}</option>)}
              </select>
              <select
                value={salesProductDraft.purchaseOrderId}
                onChange={(event) => patchSalesProductDraft({ purchaseOrderId: event.target.value })}
                aria-label="关联采购订单"
                disabled={!salesProductDraft.supplierOrgId}
              >
                <option value="">新建该供应商采购订单</option>
                {purchaseOrders
                  .filter((order) => order.supplierOrgId === salesProductDraft.supplierOrgId && canAppendPurchaseOrderItems(order) && (order.id === salesProductDraft.purchaseOrderId || !purchaseOrderIdsTakenBySalesOrders(data).has(order.id)))
                  .map((order) => (
                    <option key={order.id} value={order.id}>{order.orderNo} · {order.status}</option>
                  ))}
              </select>
              <input value={salesProductDraft.purchaseUnitPrice} onChange={(event) => patchSalesProductDraft({ purchaseUnitPrice: event.target.value })} placeholder="采购单价（可改）" />
            </div>
            <div className="modal-actions">
              <button className="ghost" type="button" onClick={() => setSalesProductDraft(null)}>取消</button>
              <button className="primary" type="button" onClick={confirmSalesProductDraft}>加入本单</button>
            </div>
          </div>
        </div>
      )}
      {quickReminderProjectId && data.projects.find((project) => project.id === quickReminderProjectId)?.type === "服务项目" && (
        <div className="modal-backdrop" role="presentation">
          <div className="modal" role="dialog" aria-modal="true" aria-label="添加跟进提醒">
            <div className="modal-head">
              <div>
                <h2>添加跟进提醒</h2>
                <p>{data.projects.find((project) => project.id === quickReminderProjectId)?.name || "选择项目后创建提醒"}</p>
              </div>
              <button className="icon-button" onClick={() => setQuickReminderProjectId("")} aria-label="关闭提醒"><X size={18} /></button>
            </div>
            <ReminderForm
              data={data}
              commit={async (next, log) => {
                await commit(next, log);
                setQuickReminderProjectId("");
              }}
              currentUser={currentUser}
              fixedProjectId={quickReminderProjectId}
            />
            <div className="modal-actions">
              <button className="ghost" onClick={() => setQuickReminderProjectId("")}>取消</button>
            </div>
          </div>
        </div>
      )}
      {showContractUpload && activeProject && (
        <div className="modal-backdrop is-nested-2" role="presentation">
          <div className="modal" role="dialog" aria-modal="true" aria-label={activeProject.contractFileId ? "替换合同" : "上传合同"}>
            <div className="modal-head">
              <div>
                <h2>{activeProject.contractFileId ? "替换合同" : "上传已签合同"}</h2>
                <p>{activeProject.name}{activeProject.contractFileName ? ` · 当前 ${activeProject.contractFileName}` : ""}</p>
              </div>
              <button className="icon-button" onClick={() => setShowContractUpload(false)} aria-label="关闭上传合同"><X size={18} /></button>
            </div>
            <div className="upload-strip">
              <FilePicker
                accept=".pdf,application/pdf"
                fileName={contractFile?.name}
                placeholder="请选择单个 PDF 合同文件"
                buttonLabel="选择合同"
                ariaLabel="选择合同文件"
                onFile={(file) => setContractFile(file ?? null)}
              />
            </div>
            <div className="modal-actions">
              <button className="ghost" onClick={() => setShowContractUpload(false)}>取消</button>
              <button className="primary" onClick={() => void saveSignedContract()}>
                <FileText size={16} />{activeProject.contractFileId ? "上传并替换" : "上传并标记已签"}
              </button>
            </div>
          </div>
        </div>
      )}
      {poContractUploadOrderId && poUploadOrder && (
        <div className="modal-backdrop is-nested-2" role="presentation">
          <div className="modal" role="dialog" aria-modal="true" aria-label={poUploadOrder.contractFileId ? "替换采购合同" : "上传采购合同"}>
            <div className="modal-head">
              <div>
                <h2>{poUploadOrder.contractFileId ? "替换采购合同" : "上传采购合同"}</h2>
                <p>{poUploadOrder.orderNo}{poUploadOrder.contractFileName ? ` · 当前 ${poUploadOrder.contractFileName}` : ""}</p>
              </div>
              <button className="icon-button" onClick={() => setPoContractUploadOrderId("")} aria-label="关闭上传采购合同"><X size={18} /></button>
            </div>
            <div className="upload-strip">
              <FilePicker
                accept=".pdf,application/pdf"
                fileName={poContractFile?.name}
                placeholder="请选择单个 PDF 合同文件"
                buttonLabel="选择合同"
                ariaLabel="选择采购合同文件"
                onFile={(file) => setPoContractFile(file ?? null)}
              />
            </div>
            <div className="modal-actions">
              <button className="ghost" onClick={() => setPoContractUploadOrderId("")}>取消</button>
              <button className="primary" onClick={() => void savePoSignedContract()}>
                <FileText size={16} />{poUploadOrder.contractFileId ? "上传并替换" : "上传并标记已签"}
              </button>
            </div>
          </div>
        </div>
      )}
      {contractViewerFileId && (
        <div className="modal-backdrop is-nested-2" role="presentation">
          <div className="modal contract-viewer-modal" role="dialog" aria-modal="true" aria-label="查看合同">
            <div className="modal-head">
              <div><h2>合同预览</h2><p>{activeProject?.contractFileId === contractViewerFileId ? activeProject.contractFileName : data.purchaseOrders.find((order) => order.contractFileId === contractViewerFileId)?.contractFileName || activeProject?.contractFileName || "PDF 合同"}</p></div>
              <div className="contract-viewer-actions">
                {(() => {
                  const viewerPurchaseOrder = data.purchaseOrders.find((order) => order.contractFileId === contractViewerFileId);
                  const canReplaceViewer = viewerPurchaseOrder ? can("purchase.manage") : can("project.edit");
                  if (!canReplaceViewer) return null;
                  return (
                    <button
                      className="ghost"
                      onClick={() => {
                        const purchaseOrder = data.purchaseOrders.find((order) => order.contractFileId === contractViewerFileId);
                        setContractViewerFileId("");
                        if (purchaseOrder) {
                          setPoContractUploadOrderId(purchaseOrder.id);
                          setPoContractFile(null);
                          return;
                        }
                        setContractFile(null);
                        setShowContractUpload(true);
                      }}
                    >
                      替换合同
                    </button>
                  );
                })()}
                <button className="ghost" onClick={() => openBusinessDocument(contractViewerFileId)}>新窗口打开</button>
                <button className="icon-button" onClick={() => setContractViewerFileId("")} aria-label="关闭合同预览"><X size={18} /></button>
              </div>
            </div>
            <iframe src={businessDocumentUrl(contractViewerFileId)} title="合同内容" />
          </div>
        </div>
      )}
      {paymentDialog}
    </>
  );
}
type ContractListItem = {
  id: string;
  kind: "项目合同" | "采购合同";
  source: "project" | "purchaseOrder";
  sourceId: string;
  projectId: string;
  projectName: string;
  projectNo: string;
  projectType: string;
  customerOrgId: string;
  counterpartyOrgId: string;
  ownCompanyOrgId?: string;
  orderNo?: string;
  contractStatus: string;
  contractFileId?: string;
  contractFileName?: string;
  createdAt?: string;
  updatedAt?: string;
};

function TemporaryContractDialog({
  data,
  formatName,
  onClose,
}: {
  data: AppData;
  formatName: string;
  onClose: () => void;
}) {
  const defaultPartyBId = data.organizations.find(isOwnCompanyOrganization)?.id ?? "";
  const [platform, setPlatform] = useState<ServiceContractPlatform>("青慧采");
  const [partyAId, setPartyAId] = useState("");
  const [partyBId, setPartyBId] = useState(defaultPartyBId);
  const [draft, setDraft] = useState<ServiceContractDraft>(() => buildStandaloneContractDraft(
    data,
    "青慧采",
    undefined,
    data.organizations.find((org) => org.id === defaultPartyBId),
  ));
  const [moreOpen, setMoreOpen] = useState(true);
  const [fileFormat, setFileFormat] = useState<ServiceContractFileFormat>("word");
  const [isGenerating, setIsGenerating] = useState(false);
  const partyAOptions = sortByCreatedDesc(data.organizations).map((org) => ({
    value: org.id,
    label: org.name,
    detail: [org.unifiedCreditCode, org.legalPerson, org.phone].filter(Boolean).join(" / "),
  }));
  const ownCompanyOptions = data.organizations.filter(isOwnCompanyOrganization).map((org) => ({
    value: org.id,
    label: org.name,
    detail: [org.unifiedCreditCode, org.phone].filter(Boolean).join(" / "),
  }));
  const partyBOptions = [
    ...ownCompanyOptions,
    ...partyAOptions.filter((item) => !ownCompanyOptions.some((own) => own.value === item.value)),
  ];

  function applyDraft(
    nextPlatform: ServiceContractPlatform,
    nextPartyAId: string,
    nextPartyBId: string,
    options?: { resetPlatformDefaults?: boolean },
  ) {
    return mergeStandaloneDraft(
      data,
      nextPlatform,
      data.organizations.find((org) => org.id === nextPartyAId),
      data.organizations.find((org) => org.id === nextPartyBId),
      draft,
      options,
    );
  }

  function toggleShopCategory(value: string) {
    const selected = draft.shopCategories.includes(value)
      ? draft.shopCategories.filter((item) => item !== value)
      : [...draft.shopCategories, value];
    setDraft({
      ...draft,
      shopCategories: selected,
      shopCategory: formatShopCategories(selected),
    });
  }

  async function submit() {
    if (serviceContractDraftErrors(draft, platform).length > 0) {
      window.alert("请先补全合同信息后再生成。");
      return;
    }
    setIsGenerating(true);
    try {
      await downloadStandaloneServiceContract(platform, draft, fileFormat);
      onClose();
    } catch (error) {
      if (error instanceof AuthExpiredError) return;
      window.alert(error instanceof Error ? error.message : "生成合同失败，请稍后重试");
    } finally {
      setIsGenerating(false);
    }
  }

  return (
    <div className="modal-backdrop" role="presentation">
      <div className="modal service-contract-modal" role="dialog" aria-modal="true" aria-label="生成临时合同">
        <div className="modal-head">
          <div>
            <h2>生成临时合同</h2>
            <p>选择平台匹配模板后填写甲乙方；可从企业库选择，也可手填。生成后仅下载，不入库、不进入合同列表、不绑定项目。</p>
          </div>
          <button className="icon-button" onClick={onClose} aria-label="关闭生成临时合同" disabled={isGenerating}><X size={18} /></button>
        </div>
        <div className="payment-form-grid">
          <label className="span-2"><span>入驻平台</span>
            <select
              value={platform}
              onChange={(event) => {
                const nextPlatform = event.target.value as ServiceContractPlatform;
                setPlatform(nextPlatform);
                setDraft(applyDraft(nextPlatform, partyAId, partyBId, { resetPlatformDefaults: true }));
              }}
            >
              {SERVICE_CONTRACT_PLATFORMS.map((item) => <option key={item}>{item}</option>)}
            </select>
          </label>
          <div className="contract-select-field">
            <span>甲方</span>
            <SearchableSelect
              value={partyAId}
              options={partyAOptions}
              onChange={(value) => {
                setPartyAId(value);
                setDraft(applyDraft(platform, value, partyBId));
              }}
              placeholder="搜索并选择甲方，也可下方手填"
              ariaLabel="选择甲方"
            />
          </div>
          <div className="contract-select-field">
            <span>乙方</span>
            <SearchableSelect
              value={partyBId}
              options={partyBOptions}
              onChange={(value) => {
                setPartyBId(value);
                setDraft(applyDraft(platform, partyAId, value));
              }}
              placeholder="搜索并选择乙方，也可下方手填"
              ariaLabel="选择乙方"
            />
          </div>
          <label className={platform === "泉E采" ? "span-2" : undefined}><span>店铺名称</span><input value={draft.shopName} onChange={(event) => setDraft({ ...draft, shopName: event.target.value })} /></label>
          <label><span>店铺主营</span>
            <div className="shop-category-checkboxes">
              {SHOP_CATEGORY_OPTIONS.map((option) => (
                <label key={option.value}>
                  <input
                    type="checkbox"
                    checked={draft.shopCategories.includes(option.value)}
                    onChange={() => toggleShopCategory(option.value)}
                  />
                  {option.label}
                </label>
              ))}
            </div>
          </label>
          {platform === "泉E采" && (
            <label><span>上架上限</span><input value={draft.listingLimit} onChange={(event) => setDraft({ ...draft, listingLimit: event.target.value })} /></label>
          )}
          <label><span>服务开始日</span>
            <DateTimeField value={draft.startDate} onChange={(startDate) => setDraft({ ...draft, startDate })} ariaLabel="服务开始日" />
          </label>
          <label><span>服务到期日</span>
            <DateTimeField value={draft.endDate} onChange={(endDate) => setDraft({ ...draft, endDate })} ariaLabel="服务到期日" />
          </label>
          <label><span>签订日期</span>
            <DateTimeField value={draft.signDate} onChange={(signDate) => setDraft({ ...draft, signDate })} ariaLabel="签订日期" />
          </label>
          <label><span>服务费金额</span>
            <input type="number" min="0" step="0.01" value={draft.amount} onChange={(event) => setDraft({ ...draft, amount: event.target.value })} />
            <em className="service-contract-amount-cn">大写：{amountToChinese(draft.amount)}</em>
          </label>
        </div>
        <button type="button" className="ghost service-contract-more-toggle" onClick={() => setMoreOpen((open) => !open)}>
          {moreOpen
            ? (contractNeedsCollectionAccount(platform) ? "收起甲乙方与账户信息" : "收起甲乙方信息")
            : (contractNeedsCollectionAccount(platform) ? "展开甲乙方与账户信息" : "展开甲乙方信息")}
        </button>
        {moreOpen && (
          <div className="payment-form-grid service-contract-more">
            <label><span>甲方名称</span><input value={draft.partyAName} onChange={(event) => {
              const partyAName = event.target.value;
              setDraft({
                ...draft,
                partyAName,
                shopName: partyAId ? draft.shopName : shopNameFromCompany(partyAName),
              });
            }} /></label>
            <label><span>甲方地址</span><input value={draft.partyAAddress} onChange={(event) => setDraft({ ...draft, partyAAddress: event.target.value })} /></label>
            <label><span>甲方电话</span><input value={draft.partyAPhone} onChange={(event) => setDraft({ ...draft, partyAPhone: event.target.value })} /></label>
            <label><span>乙方名称</span><input value={draft.partyBName} onChange={(event) => setDraft({ ...draft, partyBName: event.target.value, accountName: event.target.value })} /></label>
            <label><span>乙方地址</span><input value={draft.partyBAddress} onChange={(event) => setDraft({ ...draft, partyBAddress: event.target.value })} /></label>
            <label><span>乙方电话</span><input value={draft.partyBPhone} onChange={(event) => setDraft({ ...draft, partyBPhone: event.target.value })} /></label>
            {platform !== "泉E采" && (
              <label><span>上架上限</span><input value={draft.listingLimit} onChange={(event) => setDraft({ ...draft, listingLimit: event.target.value })} /></label>
            )}
            {contractNeedsCollectionAccount(platform) && (
              <label><span>户名</span><input value={draft.accountName} onChange={(event) => setDraft({ ...draft, accountName: event.target.value })} /></label>
            )}
          </div>
        )}
        <div className="modal-actions">
          <ContractFormatPicker name={formatName} value={fileFormat} onChange={setFileFormat} disabled={isGenerating} />
          <button className="ghost" onClick={onClose} disabled={isGenerating}>取消</button>
          <button className="primary" onClick={() => void submit()} disabled={isGenerating}>
            {isGenerating ? "生成中..." : `下载${fileFormat === "pdf" ? " PDF" : " Word"}`}
          </button>
        </div>
      </div>
    </div>
  );
}

function Contracts({
  data,
  commit,
  can,
}: {
  data: AppData;
  commit: (data: AppData, log?: Omit<OperationLog, "id" | "createdAt">) => Promise<void>;
  can: CanAccess;
}) {
  const [search, setSearch] = useState("");
  const [showTemporaryContract, setShowTemporaryContract] = useState(false);
  const [viewerFileId, setViewerFileId] = useState("");
  const [replaceTarget, setReplaceTarget] = useState<ContractListItem | null>(null);
  const [replaceFile, setReplaceFile] = useState<File | null>(null);
  const contractStamp = [
    ...data.projects.map((project) => `${project.id}:${project.contractFileId ?? ""}:${project.contractFileName ?? ""}`),
    ...data.purchaseOrders.map((order) => `${order.id}:${order.contractFileId ?? ""}:${order.contractFileName ?? ""}`),
  ].join("|");
  // 统一列表：服务/商品项目合同 + 已上传文件的采购订单合同；搜索与分页走服务端。
  const contractsPage = useServerPagedList<ContractListItem>({
    collection: "contracts",
    search,
    pageSize: 10,
    refreshKey: contractStamp,
  });
  const viewerFromPage = contractsPage.items.find((item) => item.contractFileId === viewerFileId)
    ?? (replaceTarget?.contractFileId === viewerFileId ? replaceTarget : undefined);
  const viewerFromProject = data.projects.find((project) => project.contractFileId === viewerFileId);
  const viewerFromOrder = data.purchaseOrders.find((order) => order.contractFileId === viewerFileId);
  const viewerRow = viewerFromPage
    ?? (viewerFromOrder
      ? { kind: "采购合同" as const, source: "purchaseOrder" as const, sourceId: viewerFromOrder.id, contractFileId: viewerFromOrder.contractFileId, contractFileName: viewerFromOrder.contractFileName }
      : viewerFromProject
        ? { kind: "项目合同" as const, source: "project" as const, sourceId: viewerFromProject.id, contractFileId: viewerFromProject.contractFileId, contractFileName: viewerFromProject.contractFileName }
        : undefined);
  const viewerTitle = viewerFromPage?.contractFileName
    || viewerFromPage?.projectName
    || viewerFromProject?.contractFileName
    || viewerFromProject?.name
    || viewerFromOrder?.contractFileName
    || viewerFromOrder?.orderNo
    || "PDF 合同";
  const canReplaceViewer = viewerRow?.source === "purchaseOrder" ? can("purchase.manage") : can("project.edit");

  function canReplaceRow(row: ContractListItem) {
    return row.source === "purchaseOrder" ? can("purchase.manage") : can("project.edit");
  }

  function openReplace(row: ContractListItem) {
    setViewerFileId("");
    setReplaceFile(null);
    setReplaceTarget(row);
  }

  function openReplaceFromViewer() {
    const fromPage = contractsPage.items.find((item) => item.contractFileId === viewerFileId);
    if (fromPage) {
      openReplace(fromPage);
      return;
    }
    if (viewerFromOrder) {
      const project = data.projects.find((item) => item.id === viewerFromOrder.projectId);
      openReplace({
        id: viewerFromOrder.id,
        kind: "采购合同",
        source: "purchaseOrder",
        sourceId: viewerFromOrder.id,
        projectId: viewerFromOrder.projectId,
        projectName: project?.name ?? "",
        projectNo: project?.projectNo ?? "",
        projectType: project?.type ?? "",
        customerOrgId: project?.customerOrgId ?? "",
        counterpartyOrgId: viewerFromOrder.supplierOrgId,
        ownCompanyOrgId: viewerFromOrder.ownCompanyOrgId,
        orderNo: viewerFromOrder.orderNo,
        contractStatus: viewerFromOrder.contractStatus ?? "",
        contractFileId: viewerFromOrder.contractFileId,
        contractFileName: viewerFromOrder.contractFileName,
      });
      return;
    }
    if (viewerFromProject) {
      openReplace({
        id: viewerFromProject.id,
        kind: "项目合同",
        source: "project",
        sourceId: viewerFromProject.id,
        projectId: viewerFromProject.id,
        projectName: viewerFromProject.name,
        projectNo: viewerFromProject.projectNo,
        projectType: viewerFromProject.type,
        customerOrgId: viewerFromProject.customerOrgId,
        counterpartyOrgId: viewerFromProject.customerOrgId,
        ownCompanyOrgId: viewerFromProject.ownCompanyOrgId,
        contractStatus: viewerFromProject.contractStatus,
        contractFileId: viewerFromProject.contractFileId,
        contractFileName: viewerFromProject.contractFileName,
      });
    }
  }

  async function saveReplacedContract() {
    if (!replaceTarget || !replaceFile) {
      window.alert("请选择 PDF 合同文件。");
      return;
    }
    if (!isPdfContractFile(replaceFile)) {
      window.alert("合同文件仅支持 PDF 格式。");
      return;
    }
    const saved = await uploadBusinessDocument(replaceFile, "contract", replaceTarget.sourceId);
    const now = today();
    if (replaceTarget.source === "purchaseOrder") {
      const order = data.purchaseOrders.find((item) => item.id === replaceTarget.sourceId);
      if (!order) return;
      const synced = applyProductProjectSync({
        ...data,
        purchaseOrders: data.purchaseOrders.map((item) => item.id === order.id ? {
          ...item,
          contractStatus: "已签",
          contractFileId: saved.id,
          contractFileName: saved.fileName,
          updatedAt: now,
          contractUpdatedAt: now,
        } : item),
      }, order.projectId);
      await commit(
        synced.data,
        {
          action: "替换采购合同",
          targetType: "项目",
          targetName: replaceTarget.projectName || order.orderNo,
          operator: "当前用户",
          detail: `${order.orderNo}：${order.contractFileName || "原合同"} -> ${saved.fileName}${synced.autoDetail ? `；${synced.autoDetail}` : ""}`,
        },
      );
    } else {
      const project = data.projects.find((item) => item.id === replaceTarget.sourceId);
      if (!project) return;
      await commit(
        {
          ...data,
          projects: data.projects.map((item) => item.id === project.id ? {
            ...item,
            contractStatus: "已签",
            contractFileId: saved.id,
            contractFileName: saved.fileName,
            updatedAt: now,
            contractUpdatedAt: now,
          } : item),
        },
        {
          action: "替换项目合同",
          targetType: "项目",
          targetName: project.name,
          operator: "当前用户",
          detail: `${project.contractFileName || "原合同"} -> ${saved.fileName}`,
        },
      );
    }
    setReplaceTarget(null);
    setReplaceFile(null);
  }

  return (
    <div className="panel">
      <div className="panel-title action-title">
        <div>
          <h2>合同管理</h2>
          <p>含项目合同与采购合同；传错文件时可在列表中直接替换。临时合同仅下载，不入库、不进列表。</p>
        </div>
        {can("project.edit") && (
          <div className="panel-title-buttons">
            <button className="primary" type="button" onClick={() => setShowTemporaryContract(true)}>
              <FileText size={16} />生成临时合同
            </button>
          </div>
        )}
      </div>
      {contractsPage.error && <div className="form-error">{contractsPage.error}</div>}
      <div className="orders-toolbar">
        <SearchField
          value={search}
          onChange={setSearch}
          placeholder="搜索项目、编号、客户、供应商、订单号、合同文件名"
        />
      </div>
      <div className="table contract-list-table">
        <div className="table-row contract-table head">
          <span>项目/订单</span>
          <span>对方</span>
          <span>合同类型</span>
          <span>签约主体</span>
          <span>合同状态</span>
          <span>合同文件</span>
          <span>更新时间</span>
        </div>
        {contractsPage.items.map((row) => {
          const counterpartyName = data.organizations.find((org) => org.id === row.counterpartyOrgId)?.name || "";
          const ownCompanyName = data.organizations.find((org) => org.id === row.ownCompanyOrgId)?.name || "";
          const title = row.kind === "采购合同"
            ? (row.orderNo || row.projectName || "采购合同")
            : (row.projectName || "未命名项目");
          const subtitle = row.kind === "采购合同"
            ? [row.projectName, row.projectNo].filter(Boolean).join(" · ") || "未关联项目"
            : (row.projectNo || "");
          return (
            <div className="table-row contract-table" key={row.id}>
              <span>
                <CopyableLine text={title} label={row.kind === "采购合同" ? "采购订单号" : "项目名称"}>
                  {title}
                </CopyableLine>
                {subtitle ? <em>{subtitle}</em> : null}
              </span>
              <span>
                {counterpartyName ? (
                  <CopyableLine text={counterpartyName} label={row.kind === "采购合同" ? "供应商" : "客户名称"}>
                    {counterpartyName}
                  </CopyableLine>
                ) : "未选择"}
              </span>
              <span>{row.kind}{row.projectType ? <em>{row.projectType}</em> : null}</span>
              <span>{ownCompanyName || "未选择"}</span>
              <span>{row.contractStatus || "待签"}</span>
              <span>
                <ContractFileActions
                  fileId={row.contractFileId}
                  canReplace={canReplaceRow(row)}
                  onView={() => row.contractFileId && setViewerFileId(row.contractFileId)}
                  onReplace={() => openReplace(row)}
                />
              </span>
              <span>{formatDateTimeValue(row.updatedAt)}</span>
            </div>
          );
        })}
        {contractsPage.total === 0 && (
          <div className="table-row contract-table"><span>暂无合同数据</span><span></span><span></span><span></span><span></span><span></span><span></span></div>
        )}
      </div>
      <Pagination {...contractsPage} onPageChange={contractsPage.setPage} />
      {viewerFileId && (
        <div className="modal-backdrop" role="presentation">
          <div className="modal contract-viewer-modal" role="dialog" aria-modal="true" aria-label="查看合同">
            <div className="modal-head">
              <div><h2>合同预览</h2><p>{viewerTitle}</p></div>
              <div className="contract-viewer-actions">
                {canReplaceViewer && viewerRow && (
                  <button className="ghost" onClick={openReplaceFromViewer}>替换合同</button>
                )}
                <button className="ghost" onClick={() => openBusinessDocument(viewerFileId)}>新窗口打开</button>
                <button className="icon-button" onClick={() => setViewerFileId("")} aria-label="关闭合同预览"><X size={18} /></button>
              </div>
            </div>
            <iframe src={businessDocumentUrl(viewerFileId)} title="合同内容" />
          </div>
        </div>
      )}
      {replaceTarget && (
        <div className="modal-backdrop" role="presentation">
          <div className="modal" role="dialog" aria-modal="true" aria-label="替换合同">
            <div className="modal-head">
              <div>
                <h2>{replaceTarget.contractFileId ? "替换合同" : "上传合同"}</h2>
                <p>
                  {replaceTarget.kind === "采购合同" ? (replaceTarget.orderNo || replaceTarget.projectName) : replaceTarget.projectName}
                  {replaceTarget.contractFileName ? ` · 当前 ${replaceTarget.contractFileName}` : ""}
                </p>
              </div>
              <button className="icon-button" onClick={() => { setReplaceTarget(null); setReplaceFile(null); }} aria-label="关闭替换合同"><X size={18} /></button>
            </div>
            <div className="upload-strip">
              <FilePicker
                accept=".pdf,application/pdf"
                fileName={replaceFile?.name}
                placeholder="请选择单个 PDF 合同文件"
                buttonLabel="选择合同"
                ariaLabel="选择合同文件"
                onFile={(file) => setReplaceFile(file ?? null)}
              />
            </div>
            <div className="modal-actions">
              <button className="ghost" onClick={() => { setReplaceTarget(null); setReplaceFile(null); }}>取消</button>
              <button className="primary" onClick={() => void saveReplacedContract()}>
                <FileText size={16} />{replaceTarget.contractFileId ? "上传并替换" : "上传并标记已签"}
              </button>
            </div>
          </div>
        </div>
      )}
      {showTemporaryContract && (
        <TemporaryContractDialog
          data={data}
          formatName="contracts-temp-format"
          onClose={() => setShowTemporaryContract(false)}
        />
      )}
    </div>
  );
}

function salesProductSelectOptionsForProject(data: AppData, project?: Project) {
  return data.products
    .filter((product) => {
      const matchesKind = project?.type === "服务项目" ? product.kind === "虚拟服务" : product.kind === "实体商品";
      if (!matchesKind) return false;
      if (isProjectScopedProduct(product)) return isProjectScopedProduct(product, project?.id);
      return true;
    })
    .map((product) => ({
      value: product.id,
      label: `${product.name}｜售价 ${money(product.quotePrice)}`,
      detail: [product.category === "项目商品" ? "" : product.category, product.capacity, product.code].filter(Boolean).join(" / "),
    }));
}

function SalesOrderComposerModals({
  data,
  commit,
  open,
  allowSelectProject,
  initialProject,
  targetOrder,
  onClose,
  onSubmitted,
}: {
  data: AppData;
  commit: (data: AppData, log?: Omit<OperationLog, "id" | "createdAt">) => Promise<void>;
  open: boolean;
  allowSelectProject?: boolean;
  initialProject?: Project;
  targetOrder?: SalesOrder;
  onClose: () => void;
  onSubmitted: () => void;
}) {
  const suppliers = data.organizations.filter((org) => isSupplierOrganization(org));
  const productProjects = data.projects.filter((project) => project.type === "商品项目" && project.status !== "已完成");
  const [projectId, setProjectId] = useState(initialProject?.id ?? "");
  const [composer, setComposer] = useState<SalesComposerDraft | null>(null);
  const [productDraft, setProductDraft] = useState<SalesChannelLineDraft | null>(null);
  const [productMode, setProductMode] = useState<"catalog" | "quick">("catalog");

  const project = data.projects.find((item) => item.id === projectId);
  const purchaseOrders = data.purchaseOrders.filter((order) => order.projectId === project?.id);
  const productOptions = salesProductSelectOptionsForProject(data, project);
  const projectOptions = productProjects.map((item) => ({
    value: item.id,
    label: `${item.name}｜${item.projectNo}`,
    detail: [data.organizations.find((org) => org.id === item.customerOrgId)?.name, item.sourcePlatform].filter(Boolean).join(" / "),
  }));

  useEffect(() => {
    if (!open) {
      setComposer(null);
      setProductDraft(null);
      return;
    }
    const openingProject = data.projects.find((item) => item.id === (initialProject?.id ?? "")) ?? initialProject;
    setProjectId(initialProject?.id ?? "");
    setComposer({
      targetOrderId: targetOrder?.id,
      orderedAt: targetOrder ? toDateTimeLocalInput(targetOrder.createdAt) : defaultOrderTimeFromProject(openingProject),
      platformOrderNo: targetOrder?.platformOrderNo ?? "",
      note: targetOrder?.note ?? "",
      ...(targetOrder
        ? {
            purchaserCompany: targetOrder.purchaserCompany ?? "",
            purchaserAddress: targetOrder.purchaserAddress ?? "",
            purchaserName: targetOrder.purchaserName ?? "",
            purchaserPhone: targetOrder.purchaserPhone ?? "",
          }
        : purchaserDraftFromProject(data, openingProject)),
      lines: [],
    });
    setProductDraft(targetOrder ? createBlankSalesChannelLine(suppliers[0]?.id ?? "") : null);
    setProductMode("catalog");
  }, [open, initialProject?.id, targetOrder?.id]);

  if (!open || !composer) return null;
  const currentComposer = composer;

  function patchProductDraft(patch: Partial<SalesChannelLineDraft>) {
    setProductDraft((current) => {
      if (!current) return current;
      const next = { ...current, ...patch };
      if (patch.productId) {
        const product = data.products.find((item) => item.id === patch.productId);
        next.salesUnitPrice = product?.quotePrice ? String(product.quotePrice) : "";
        const supplierPrice = next.supplierOrgId
          ? latestSupplierPrice(data.supplierPrices, patch.productId, next.supplierOrgId)
          : undefined;
        next.purchaseUnitPrice = supplierPrice?.purchasePrice ? String(supplierPrice.purchasePrice) : (product?.costPrice ? String(product.costPrice) : next.purchaseUnitPrice);
      }
      if (patch.supplierOrgId !== undefined) {
        const productId = next.productId;
        const supplierPrice = productId
          ? latestSupplierPrice(data.supplierPrices, productId, patch.supplierOrgId)
          : undefined;
        next.purchaseUnitPrice = supplierPrice?.purchasePrice ? String(supplierPrice.purchasePrice) : next.purchaseUnitPrice;
        next.purchaseOrderId = "";
      }
      return next;
    });
  }

  function switchProductMode(mode: "catalog" | "quick") {
    setProductMode(mode);
    if (mode === "catalog") patchProductDraft({ directProductName: "", directPlatformPrice: "" });
    else patchProductDraft({ productId: "" });
  }

  function confirmProductDraft() {
    if (!productDraft) return;
    const isDirect = productMode === "quick";
    const draft = isDirect
      ? { ...productDraft, productId: "" }
      : { ...productDraft, directProductName: "", directPlatformPrice: "" };
    if (isDirect && !draft.directProductName.trim()) {
      window.alert("请填写快捷商品名称。");
      return;
    }
    if (!isDirect && !draft.productId) {
      window.alert("请选择销售商品。");
      return;
    }
    if (!draft.supplierOrgId) {
      window.alert("请选择渠道供应商，销售商品需要关联采购订单。");
      return;
    }
    const quantity = Number(draft.quantity);
    if (!Number.isFinite(quantity) || quantity <= 0) {
      window.alert("数量必须大于 0。");
      return;
    }
    if (isDirect) {
      const platformPrice = Number(draft.directPlatformPrice);
      if (!Number.isFinite(platformPrice) || platformPrice < 0) {
        window.alert("快捷商品的平台价必须是大于或等于 0 的数字。");
        return;
      }
    }
    if (draft.purchaseOrderId) {
      const po = purchaseOrders.find((item) => item.id === draft.purchaseOrderId);
      if (!po || po.supplierOrgId !== draft.supplierOrgId || !canAppendPurchaseOrderItems(po)) {
        window.alert("只能追加到同一供应商的「待下单/草稿」采购订单。");
        return;
      }
    }
    const nextLines = currentComposer.lines.some((item) => item.key === draft.key)
      ? currentComposer.lines.map((item) => item.key === draft.key ? draft : item)
      : [...currentComposer.lines, draft];
    setComposer({ ...currentComposer, lines: nextLines });
    setProductDraft(null);
  }

  function composerLineLabel(line: SalesChannelLineDraft) {
    const product = data.products.find((item) => item.id === line.productId);
    const name = line.directProductName.trim() || product?.name || "未选择商品";
    const supplier = data.organizations.find((org) => org.id === line.supplierOrgId);
    const po = purchaseOrders.find((item) => item.id === line.purchaseOrderId);
    return `${name} × ${line.quantity || 1} · ${supplier?.name || "未选渠道"} / ${po?.orderNo || "新建采购单"}`;
  }

  async function handleSubmit() {
    if (!project) {
      window.alert("请选择商品项目。");
      return;
    }
    const ok = await submitSalesOrderComposer({
      data,
      commit,
      project,
      composer: currentComposer,
      latestSupplierPrice,
    });
    if (ok) onSubmitted();
  }

  return (
    <>
      <div className="modal-backdrop" role="presentation">
        <div className="modal sales-composer-modal" role="dialog" aria-modal="true" aria-label={composer.targetOrderId ? "追加销售商品" : "新建订单"}>
          <div className="modal-head">
            <div>
              <h2>{composer.targetOrderId ? "追加商品到销售订单" : "新建订单"}</h2>
              <p>{composer.targetOrderId ? "追加商品不会改原销售单的下单时间。" : "选择项目后填写采购人，再添加商品。每个商品都要选择渠道供应商，保存时会同时创建或追加对应采购订单。"}</p>
            </div>
            <button className="icon-button" onClick={onClose} aria-label="关闭新建订单"><X size={18} /></button>
          </div>
          {!composer.targetOrderId && (
            <div className="sales-composer-fields">
              {allowSelectProject && (
                <label className="sales-composer-field sales-composer-field-full">
                  <span>选择项目</span>
                    <SearchableSelect
                    value={projectId}
                    options={projectOptions}
                    onChange={(nextId) => {
                      setProjectId(nextId);
                      if (!currentComposer.targetOrderId) {
                        const nextProject = data.projects.find((item) => item.id === nextId);
                        setComposer({
                          ...currentComposer,
                          orderedAt: defaultOrderTimeFromProject(nextProject),
                          ...purchaserDraftFromProject(data, nextProject),
                        });
                      }
                    }}
                    placeholder="搜索并选择商品项目"
                    ariaLabel="选择商品项目"
                  />
                </label>
              )}
              <label className="sales-composer-field">
                <span>下单时间</span>
                <DateTimeField
                  mode="datetime"
                  value={composer.orderedAt}
                  onChange={(orderedAt) => setComposer({ ...composer, orderedAt })}
                  ariaLabel="下单时间"
                  placeholder="下单时间"
                />
              </label>
              <label className="sales-composer-field">
                <span>平台订单编号</span>
                <input
                  value={composer.platformOrderNo}
                  onChange={(event) => setComposer({ ...composer, platformOrderNo: event.target.value })}
                  placeholder="可选"
                />
              </label>
              <label className="sales-composer-field sales-composer-field-full">
                <span>备注 可选</span>
                <input
                  value={composer.note}
                  onChange={(event) => setComposer({ ...composer, note: event.target.value })}
                  placeholder="可选"
                />
              </label>
              <span className="sales-composer-field sales-composer-field-full">采购人</span>
              <PurchaserQuickPaste onFill={(parsed) => setComposer({ ...composer, ...parsed })} />
              <label className="sales-composer-field">
                <span>公司名称</span>
                <input
                  value={composer.purchaserCompany}
                  onChange={(event) => setComposer({ ...composer, purchaserCompany: event.target.value })}
                  placeholder="采购人公司名称"
                  aria-label="采购人公司名称"
                />
              </label>
              <label className="sales-composer-field">
                <span>地址（收货地址）</span>
                <input
                  value={composer.purchaserAddress}
                  onChange={(event) => setComposer({ ...composer, purchaserAddress: event.target.value })}
                  placeholder="采购人收货地址"
                  aria-label="采购人收货地址"
                />
              </label>
              <label className="sales-composer-field">
                <span>姓名</span>
                <input
                  value={composer.purchaserName}
                  onChange={(event) => setComposer({ ...composer, purchaserName: event.target.value })}
                  placeholder="采购人姓名"
                  aria-label="采购人姓名"
                />
              </label>
              <label className="sales-composer-field">
                <span>电话</span>
                <input
                  value={composer.purchaserPhone}
                  onChange={(event) => setComposer({ ...composer, purchaserPhone: event.target.value })}
                  placeholder="采购人电话"
                  aria-label="采购人电话"
                />
              </label>
            </div>
          )}
          <div className="sales-composer-lines">
            {composer.lines.length === 0 ? (
              <div className="empty-line">还没有商品，请点击「添加商品」。</div>
            ) : composer.lines.map((line) => (
              <div className="sales-composer-line" key={line.key}>
                <span>{composerLineLabel(line)}</span>
                <span className="order-actions">
                  <button className="copy-link" type="button" onClick={() => { setProductMode(line.directProductName.trim() ? "quick" : "catalog"); setProductDraft({ ...line }); }}>编辑</button>
                  <button className="copy-link danger-action" type="button" onClick={() => setComposer({ ...composer, lines: composer.lines.filter((item) => item.key !== line.key) })}>移除</button>
                </span>
              </div>
            ))}
          </div>
          <div className="modal-actions">
            <button className="ghost" type="button" onClick={() => { setProductMode("catalog"); setProductDraft(createBlankSalesChannelLine(suppliers[0]?.id ?? "")); }} disabled={!project}>添加商品</button>
            <button className="ghost" type="button" onClick={onClose}>取消</button>
            <button className="primary" type="button" onClick={() => void handleSubmit()}>{composer.targetOrderId ? "保存追加" : "创建销售订单"}</button>
          </div>
        </div>
      </div>
      {productDraft && (
        <div className="modal-backdrop is-nested" role="presentation">
          <div className="modal sales-product-modal" role="dialog" aria-modal="true" aria-label="添加销售商品">
            <div className="modal-head">
              <div>
                <h2>添加商品并关联渠道</h2>
                <p>商品需要关联渠道采购订单：选择供应商后可追加已有待下单采购单，或自动新建。</p>
              </div>
              <button className="icon-button" onClick={() => setProductDraft(null)} aria-label="关闭添加商品"><X size={18} /></button>
            </div>
            <div className="segmented sales-product-tabs" role="tablist" aria-label="添加商品方式">
              <button type="button" role="tab" aria-selected={productMode === "catalog"} className={productMode === "catalog" ? "active" : undefined} onClick={() => switchProductMode("catalog")}>选择商品</button>
              <button type="button" role="tab" aria-selected={productMode === "quick"} className={productMode === "quick" ? "active" : undefined} onClick={() => switchProductMode("quick")}>快捷添加</button>
            </div>
            <p className="sales-order-compose-hint">
              {productMode === "quick" ? "快捷商品仅本项目使用，不进入商品及价格体系。" : "从商品库选择后会带出销售价和采购价，可再修改。"}
            </p>
            <div className="create-project create-project-modal-form">
              {productMode === "catalog" ? (
                <>
                  <SearchableSelect
                    value={productDraft.productId}
                    options={productOptions}
                    onChange={(productId) => patchProductDraft({ productId, directProductName: "", directPlatformPrice: "" })}
                    placeholder="搜索并选择销售商品"
                    ariaLabel="选择销售商品"
                  />
                  <input value={productDraft.quantity} onChange={(event) => patchProductDraft({ quantity: event.target.value })} placeholder="数量" />
                  <input value={productDraft.salesUnitPrice} onChange={(event) => patchProductDraft({ salesUnitPrice: event.target.value })} placeholder="销售单价" />
                </>
              ) : (
                <>
                  <input className="sales-product-name-field" value={productDraft.directProductName} onChange={(event) => patchProductDraft({ directProductName: event.target.value, productId: "" })} placeholder="快捷商品名称" aria-label="快捷商品名称" />
                  <input value={productDraft.directPlatformPrice} onChange={(event) => patchProductDraft({ directPlatformPrice: event.target.value })} placeholder="平台价" aria-label="平台价" />
                  <input value={productDraft.quantity} onChange={(event) => patchProductDraft({ quantity: event.target.value })} placeholder="数量" />
                  <input value={productDraft.salesUnitPrice} onChange={(event) => patchProductDraft({ salesUnitPrice: event.target.value })} placeholder="销售单价" />
                </>
              )}
              <select value={productDraft.supplierOrgId} onChange={(event) => patchProductDraft({ supplierOrgId: event.target.value })} aria-label="渠道供应商">
                <option value="">请选择渠道供应商</option>
                {suppliers.map((org) => <option key={org.id} value={org.id}>{org.name}</option>)}
              </select>
              <select
                value={productDraft.purchaseOrderId}
                onChange={(event) => patchProductDraft({ purchaseOrderId: event.target.value })}
                aria-label="关联采购订单"
                disabled={!productDraft.supplierOrgId}
              >
                <option value="">新建该供应商采购订单</option>
                {purchaseOrders
                  .filter((order) => order.supplierOrgId === productDraft.supplierOrgId && canAppendPurchaseOrderItems(order) && (order.id === productDraft.purchaseOrderId || !purchaseOrderIdsTakenBySalesOrders(data).has(order.id)))
                  .map((order) => (
                    <option key={order.id} value={order.id}>{order.orderNo} · {order.status}</option>
                  ))}
              </select>
              <input value={productDraft.purchaseUnitPrice} onChange={(event) => patchProductDraft({ purchaseUnitPrice: event.target.value })} placeholder="采购单价（可改）" />
            </div>
            <div className="modal-actions">
              <button className="ghost" type="button" onClick={() => setProductDraft(null)}>取消</button>
              <button className="primary" type="button" onClick={confirmProductDraft}>加入本单</button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}

function SalesOrderPurchaseLinker({
  data,
  order,
  canManage,
  canViewProfit,
  onSave,
}: {
  data: AppData;
  order: SalesOrder;
  canManage: boolean;
  canViewProfit: boolean;
  onSave: (purchaseOrderIds: string[]) => Promise<void>;
}) {
  const linked = salesOrderLinkedPurchaseOrders(data, order);
  const linkedIds = linked.map((item) => item.id);
  const lineLinkedIds = new Set(
    data.projectItems
      .filter((item) => item.salesOrderId === order.id && item.sourcePurchaseOrderId)
      .map((item) => item.sourcePurchaseOrderId as string),
  );
  const profit = salesOrderProfit(data, order);
  const takenPurchaseIds = purchaseOrderIdsTakenBySalesOrders(data);
  const candidates = data.purchaseOrders.filter((item) => (
    item.status !== "已取消"
    && item.projectId === order.projectId
    && !linkedIds.includes(item.id)
    && !takenPurchaseIds.has(item.id)
  ));
  const candidateOptions = candidates.map((item) => {
    const supplier = data.organizations.find((org) => org.id === item.supplierOrgId);
    return {
      value: item.id,
      label: `${item.orderNo}｜${supplier?.name || "未选择供应商"}｜${money(purchaseOrderDisplayAmount(data, item))}`,
      detail: item.status,
    };
  });

  async function addPurchase(purchaseOrderId: string) {
    if (!purchaseOrderId || linkedIds.includes(purchaseOrderId)) return;
    await onSave([...linkedIds, purchaseOrderId]);
  }

  async function removePurchase(purchaseOrder: PurchaseOrder) {
    if (lineLinkedIds.has(purchaseOrder.id)) {
      const confirmed = window.confirm(`采购订单「${purchaseOrder.orderNo}」还挂在商品明细上，取消关联后这些商品不再指向该采购单。确定取消吗？`);
      if (!confirmed) return;
    }
    await onSave(linkedIds.filter((id) => id !== purchaseOrder.id));
  }

  return (
    <div className="sales-purchase-linker">
      {canViewProfit && (
        <div className="order-profit-summary">
          <span>销售额 <strong>{money(profit.salesAmount)}</strong></span>
          <span>分摊采购成本 <strong>{money(profit.costAmount)}</strong></span>
          <span>订单毛利 <strong>{money(profit.profit)}</strong></span>
          <span>毛利率 <strong>{grossMarginText(profit.margin)}</strong></span>
        </div>
      )}
      <p className="copy-tip">已经关联到销售订单的采购订单不会出现在备选项中。同一张采购订单若已关联多张销售订单，采购成本仍按销售金额比例分摊；已取消、已退款的销售订单不计入订单毛利，其采购订单可以重新关联。</p>
      <div className="table">
        <div className="table-row sales-purchase-link-table head">
          <span>采购单号</span><span>供应商</span><span>金额</span><span>操作</span>
        </div>
        {linked.length === 0 ? (
          <div className="table-empty">暂无关联采购订单</div>
        ) : linked.map((purchaseOrder) => {
          const supplier = data.organizations.find((org) => org.id === purchaseOrder.supplierOrgId);
          return (
            <div className="table-row sales-purchase-link-table" key={purchaseOrder.id}>
              <span>
                <CopyableLine text={purchaseOrder.orderNo} label="采购单号">{purchaseOrder.orderNo}</CopyableLine>
                <em>{purchaseOrder.status}</em>
              </span>
              <span>
                <CopyableLine text={supplier?.name || "未选择供应商"} label="供应商">{supplier?.name || "未选择供应商"}</CopyableLine>
              </span>
              <span>{money(purchaseOrderDisplayAmount(data, purchaseOrder))}</span>
              <span>
                {canManage && (
                  <button className="copy-link danger-action" type="button" onClick={() => void removePurchase(purchaseOrder)}>取消关联</button>
                )}
              </span>
            </div>
          );
        })}
      </div>
      {canManage && (
        <SearchableSelect
          value=""
          options={candidateOptions}
          onChange={(purchaseOrderId) => void addPurchase(purchaseOrderId)}
          placeholder={candidateOptions.length > 0 ? "搜索并添加采购订单" : "本项目没有可继续关联的采购订单"}
          ariaLabel="添加采购订单"
        />
      )}
    </div>
  );
}

function Orders({ data, commit, can, onOpenProject, tab, focus, onClearFocus }: { data: AppData; commit: (data: AppData, log?: Omit<OperationLog, "id" | "createdAt">) => Promise<void>; can: CanAccess; onOpenProject: (id: string) => void; tab: OrderListTab; focus?: OrderFocus; onClearFocus?: () => void }) {
  type OrderTab = OrderListTab;
  type OrderRow = {
    id: string;
    kind: OrderTab;
    project?: Project;
    orderNo: string;
    counterparty: string;
    products: string;
    platform?: string;
    platformOrderNo?: string;
    quantity?: number;
    amount: number;
    status: string;
    type: Project["type"] | "商品项目";
    timeLabel: string;
    timeValue: string;
    timeSub?: string;
    note?: string;
    raw: SalesOrder | PurchaseOrder | ServiceOrder;
    searchable: string;
    lineItems?: Array<{
      id: string;
      productName: string;
      productCode?: string;
      spec?: string;
      quantity: number;
      unitPrice: number;
    }>;
    partyPhone?: string;
    partyAddress?: string;
    purchaserCompany?: string;
    purchaserName?: string;
    purchaserPhone?: string;
    purchaserAddress?: string;
    tag?: string;
    platformOrderNoText?: string;
  };
  const pageCopy = ORDER_PAGE_COPY[tab];
  const [search, setSearch] = useState("");
  const [platformFilter, setPlatformFilter] = useState("全部");
  const [statusFilter, setStatusFilter] = useState("全部");
  const [invoiceStatusFilter, setInvoiceStatusFilter] = useState("全部");
  const invoiceStatusFilterOptions = tab === "采购订单"
    ? ["未收票", "已收部分", "已收全部"]
    : ["未开票", "已开部分", "已开全部"];
  const [selectedOrder, setSelectedOrder] = useState<OrderRow | null>(null);
  const [purchaserDraft, setPurchaserDraft] = useState({ purchaserCompany: "", purchaserAddress: "", purchaserName: "", purchaserPhone: "" });
  useEffect(() => {
    if (!selectedOrder || selectedOrder.kind !== "销售订单") return;
    const order = data.salesOrders.find((item) => item.id === selectedOrder.id) ?? (selectedOrder.raw as SalesOrder);
    setPurchaserDraft({
      purchaserCompany: order.purchaserCompany ?? "",
      purchaserAddress: order.purchaserAddress ?? "",
      purchaserName: order.purchaserName ?? "",
      purchaserPhone: order.purchaserPhone ?? "",
    });
  }, [selectedOrder?.id, selectedOrder?.kind]);
  const [editingOrderStatus, setEditingOrderStatus] = useState<{ kind: OrderTab; id: string } | null>(null);
  const salesOrderStatuses = optionValues(data, "sales_order_status", ["待付款", "部分付款", "已付款", "退款", "取消"]) as SalesOrder["status"][];
  const purchaseOrderStatuses = optionValues(data, "purchase_order_status", ["草稿", "待下单", "已下单", "部分到货", "已完成", "已取消"]) as PurchaseOrder["status"][];
  const serviceOrderStatuses = optionValues(data, "service_order_status", ["待付款", "部分付款", "已付款", "退款", "取消"]) as ServiceOrder["status"][];
  const logisticsStatusOptions = optionValues(data, "logistics_status", ["待发货", "已发货", "已签收"]) as LogisticsStatus[];
  const acceptanceStatusOptions = optionValues(data, "acceptance_status", ["待验收", "验收中", "已验收"]) as AcceptanceStatus[];
  const deliveryStatusOptions = optionValues(data, "delivery_status", ["待交付", "部分交付", "交付中", "已交付"]) as DeliveryStatus[];
  const contractStatusOptions = optionValues(data, "contract_status", ["无需", "待签", "已签", "已发送"]) as ContractStatus[];
  const reconcileStatusOptions = optionValues(data, "reconcile_status", ["待对账", "已对账"]) as ReconcileStatus[];
  const orderPlatformOptions = optionValues(data, "platform", ["框架协议", "泉E采", "青慧采", "齐鲁云采", "美云销", "渠道", "直客", "其他"]);
  const orderStatusFilterOptions = tab === "采购订单" ? purchaseOrderStatuses : tab === "服务订单" ? serviceOrderStatuses : salesOrderStatuses;
  const { requestPayment, paymentDialog } = usePaymentDialog(data);
  const [salesComposerOpen, setSalesComposerOpen] = useState(false);
  const [appendSalesOrder, setAppendSalesOrder] = useState<SalesOrder | null>(null);
  const [salesOrderPanel, setSalesOrderPanel] = useState<{ orderId: string; kind: "invoice" | "transactions" | "purchase" } | null>(null);
  const [orderInvoiceIds, setOrderInvoiceIds] = useState<Record<string, string>>({});
  const [purchaseOrderPanel, setPurchaseOrderPanel] = useState<{ orderId: string; kind: "invoice" | "transactions" | "fulfillment" } | null>(null);
  const [poContractUploadOrderId, setPoContractUploadOrderId] = useState("");
  const [poContractFile, setPoContractFile] = useState<File | null>(null);
  const [contractViewerFileId, setContractViewerFileId] = useState("");

  function formatDateTime(value?: string) {
    if (!value) return "未记录";
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) return value;
    return date.toLocaleString("zh-CN", { hour12: false });
  }

  function normalTime(createdAt?: string, updatedAt?: string) {
    return {
      label: "创建/更新",
      value: formatDateTime(createdAt),
      sub: updatedAt && updatedAt !== createdAt ? `更新 ${formatDateTime(updatedAt)}` : undefined,
    };
  }

  function salesOrderTime(order: SalesOrder) {
    if (order.status === "待付款") return { label: "下单时间", value: formatDateTime(order.createdAt), sub: order.updatedAt ? `更新 ${formatDateTime(order.updatedAt)}` : undefined };
    if (order.status === "部分付款") return { label: "最近付款时间", value: formatDateTime(order.paidAt ?? order.updatedAt), sub: `已收 ${money(order.receivedAmount ?? 0)} / 应收 ${money(order.receivableAmount ?? order.amount)}` };
    if (order.status === "已付款") return { label: "付款时间", value: formatDateTime(order.paidAt ?? order.updatedAt), sub: `下单 ${formatDateTime(order.createdAt)}` };
    if (order.status === "退款") return { label: "退款时间", value: formatDateTime(order.refundedAt ?? order.updatedAt), sub: `已收 ${money(order.receivedAmount ?? 0)} / 应收 ${money(order.receivableAmount ?? order.amount)}` };
    if (order.status === "取消") return { label: "取消时间", value: formatDateTime(order.cancelledAt ?? order.updatedAt), sub: `下单 ${formatDateTime(order.createdAt)}` };
    return normalTime(order.createdAt, order.updatedAt);
  }

  function purchaseOrderTime(order: PurchaseOrder) {
    const paid = purchaseOrderPaidAmount(order, data.transactions);
    const payable = purchaseOrderDisplayAmount(data, order);
    const paymentStatus = order.paymentStatus ?? DEFAULT_ORDER_PAYMENT_STATUS;
    if (paymentStatus === "部分付款") return { label: "最近付款时间", value: formatDateTime(order.paidAt ?? order.updatedAt), sub: `已付 ${money(paid)} / 应付 ${money(payable)}` };
    if (paymentStatus === "已付款") return { label: "付款时间", value: formatDateTime(order.paidAt ?? order.updatedAt), sub: `下单 ${formatDateTime(order.createdAt)}` };
    if (order.status === "待下单" || order.status === "草稿") return { label: "下单时间", value: formatDateTime(order.createdAt), sub: order.updatedAt ? `更新 ${formatDateTime(order.updatedAt)}` : undefined };
    if (order.status === "已完成") return { label: "完成时间", value: formatDateTime(order.updatedAt ?? order.createdAt), sub: `下单 ${formatDateTime(order.createdAt)}` };
    if (order.status === "已取消") return { label: "取消时间", value: formatDateTime(order.updatedAt ?? order.createdAt), sub: `下单 ${formatDateTime(order.createdAt)}` };
    return normalTime(order.createdAt, order.updatedAt);
  }

  function serviceOrderTime(order: ServiceOrder) {
    if (order.status === "待付款") return { label: "创建时间", value: formatDateTime(order.createdAt), sub: order.updatedAt && order.updatedAt !== order.createdAt ? `更新 ${formatDateTime(order.updatedAt)}` : undefined };
    if (order.status === "部分付款") return { label: "最近付款时间", value: formatDateTime(order.paidAt ?? order.updatedAt), sub: `已收 ${money(order.receivedAmount ?? 0)} / 应收 ${money(order.receivableAmount ?? order.amount)}` };
    if (order.status === "已付款") return { label: "付款时间", value: formatDateTime(order.paidAt ?? order.updatedAt), sub: `创建 ${formatDateTime(order.createdAt)}` };
    if (order.status === "退款") return { label: "退款时间", value: formatDateTime(order.refundedAt ?? order.updatedAt), sub: `已收 ${money(order.receivedAmount ?? 0)} / 应收 ${money(order.receivableAmount ?? order.amount)}` };
    if (order.status === "取消") return { label: "取消时间", value: formatDateTime(order.cancelledAt ?? order.updatedAt), sub: `创建 ${formatDateTime(order.createdAt)}` };
    return normalTime(order.createdAt, order.updatedAt);
  }

  function canEditOrderStatus(row: OrderRow) {
    if (row.kind === "采购订单") return can("purchaseOrder.manage");
    if (row.kind === "服务订单") return can("serviceOrder.manage");
    return can("salesOrder.manage");
  }

  function allowedOrderStatuses(row: OrderRow) {
    if (row.kind === "销售订单") return getAllowedSalesOrderStatuses(row.raw as SalesOrder, salesOrderStatuses);
    if (row.kind === "采购订单") return getAllowedPurchaseOrderStatuses(row.raw as PurchaseOrder, purchaseOrderStatuses);
    return getAllowedServiceOrderStatuses(row.raw as ServiceOrder, serviceOrderStatuses);
  }

  function orderPaymentPrompt(orderNo: string, receivable: number, received: number, targetStatus: string) {
    return requestPayment({ orderNo, receivable, received, targetStatus });
  }

  function servicePaymentTransaction(order: ServiceOrder, paidAt: string, amount: number, payment: PaymentFormResult): Transaction {
    return buildServiceCollectionTransaction(order, paidAt, { ...payment, amount });
  }

  function salesPaymentTransaction(order: SalesOrder, paidAt: string, amount: number, payment: PaymentFormResult): Transaction {
    return buildSalesCollectionTransaction(order, paidAt, { ...payment, amount });
  }

  async function backfillSelectedOrder() {
    if (!selectedOrder || (selectedOrder.kind !== "销售订单" && selectedOrder.kind !== "服务订单")) return;
    const kind = selectedOrder.kind === "服务订单" ? "service" : "sales";
    if (!canBackfillCollection(can, kind)) return;
    await backfillMissingCollectionTx({
      data,
      commit,
      requestPayment,
      kind,
      order: selectedOrder.raw as SalesOrder | ServiceOrder,
      operator: "当前用户",
    });
  }

  async function paySelectedPurchaseOrder() {
    if (!selectedOrder || selectedOrder.kind !== "采购订单") return;
    const order = selectedOrder.raw as PurchaseOrder;
    if (!canRegisterPurchasePayment(can)) return;
    const paymentStatus = order.paymentStatus ?? DEFAULT_ORDER_PAYMENT_STATUS;
    const saved = await registerPurchasePayment({
      data,
      commit,
      requestPayment,
      order,
      payable: purchaseOrderDisplayAmount(data, order),
      targetStatus: paymentStatus === "待付款" ? "部分付款" : "已付款",
      operator: "当前用户",
    });
    if (saved) setSelectedOrder(null);
  }

  async function updateListPurchaseOrderFields(order: PurchaseOrder, patch: Partial<PurchaseOrder>, action = "订单列表修改采购订单") {
    await patchPurchaseOrderRecord({ data, commit, order, patch, action });
  }

  async function updateListPurchaseOrderContractStatus(order: PurchaseOrder, contractStatus: ContractStatus) {
    if (contractStatus === (order.contractStatus ?? DEFAULT_CONTRACT_STATUS)) return;
    if (contractStatus === "已签" && !order.contractFileId) {
      setPoContractUploadOrderId(order.id);
      setPoContractFile(null);
      return;
    }
    await updateListPurchaseOrderFields(order, { contractStatus, contractUpdatedAt: today() }, "订单列表修改采购合同状态");
  }

  async function saveListPoSignedContract() {
    const order = data.purchaseOrders.find((item) => item.id === poContractUploadOrderId);
    if (!order || !poContractFile) {
      window.alert("请选择 PDF 合同文件。");
      return;
    }
    if (!isPdfContractFile(poContractFile)) {
      window.alert("合同文件仅支持 PDF 格式。");
      return;
    }
    const replacing = Boolean(order.contractFileId);
    const saved = await uploadBusinessDocument(poContractFile, "contract", order.id);
    await updateListPurchaseOrderFields(order, {
      contractStatus: "已签",
      contractFileId: saved.id,
      contractFileName: saved.fileName,
      contractUpdatedAt: today(),
    }, replacing ? "订单列表替换采购合同" : "订单列表上传采购合同");
    setPoContractUploadOrderId("");
    setPoContractFile(null);
  }

  async function updateOrderStatus(row: OrderRow, nextStatus: string) {
    const now = today();
    if (row.kind === "销售订单") {
      const order = row.raw as SalesOrder;
      const status = nextStatus as SalesOrder["status"];
      if (!canTransition(order.status, status, getAllowedSalesOrderStatuses(order, salesOrderStatuses))) {
        window.alert(`销售订单状态不能从“${order.status}”变更为“${status}”。`);
        setEditingOrderStatus(null);
        return;
      }
      const receivableAmount = order.receivableAmount ?? order.amount;
      const receivedAmount = order.receivedAmount ?? 0;
      const payment = status === "部分付款" || status === "已付款" ? await orderPaymentPrompt(order.orderNo, receivableAmount, receivedAmount, status) : null;
      if ((status === "部分付款" || status === "已付款") && !payment) {
        setEditingOrderStatus(null);
        return;
      }
      const nextReceivedAmount = payment ? receivedAmount + payment.amount : receivedAmount;
      const normalizedStatus = payment && nextReceivedAmount >= receivableAmount ? "已付款" : status;
      const paymentOccurredAt = payment?.occurredAt || now;
      const nextTransactions = payment ? [salesPaymentTransaction(order, paymentOccurredAt, payment.amount, payment), ...data.transactions] : data.transactions;
      const nextSalesOrders = data.salesOrders.map((item) => item.id === order.id ? {
          ...item,
          status: normalizedStatus,
          receivableAmount,
          receivedAmount: nextReceivedAmount,
          paymentMethod: payment?.paymentMethod ?? item.paymentMethod,
          collectionAccount: payment?.collectionAccount ?? item.collectionAccount,
          payerAccount: payment?.payerAccount ?? item.payerAccount,
          voucherName: payment?.voucherName ?? item.voucherName,
          voucherFileId: payment?.voucherFileId ?? item.voucherFileId,
          updatedAt: now,
          paidAt: payment ? paymentOccurredAt : item.paidAt,
          refundedAt: normalizedStatus === "退款" ? now : item.refundedAt,
          cancelledAt: normalizedStatus === "取消" ? now : item.cancelledAt,
        } : item);
      const synced = applyProductProjectSync({ ...data, salesOrders: nextSalesOrders, transactions: nextTransactions }, order.projectId);
      await commit(
        synced.data,
        {
          action: payment ? "订单列表销售收款" : "订单列表修改销售订单状态",
          targetType: "项目",
          targetName: row.project?.name ?? order.orderNo,
          operator: "当前用户",
          detail: `${paymentLogDetail({
            orderNo: order.orderNo,
            fromStatus: order.status,
            toStatus: normalizedStatus,
            payment,
            receivedAmount: nextReceivedAmount,
            customerName: data.organizations.find((org) => org.id === order.customerOrgId)?.name,
          })}${synced.autoDetail ? `；${synced.autoDetail}` : ""}`,
        },
      );
    } else if (row.kind === "采购订单") {
      const order = row.raw as PurchaseOrder;
      const status = nextStatus as PurchaseOrder["status"];
      if (!canTransition(order.status, status, getAllowedPurchaseOrderStatuses(order, purchaseOrderStatuses))) {
        window.alert(`采购订单状态不能从“${order.status}”变更为“${status}”。`);
        setEditingOrderStatus(null);
        return;
      }
      const synced = applyProductProjectSync({
        ...data,
        purchaseOrders: data.purchaseOrders.map((item) => item.id === order.id ? { ...item, status, updatedAt: now } : item),
      }, order.projectId);
      await commit(
        synced.data,
        { action: "订单列表修改采购订单状态", targetType: "项目", targetName: row.project?.name ?? order.orderNo, operator: "当前用户", detail: `${order.status} -> ${status}${synced.autoDetail ? `；${synced.autoDetail}` : ""}` },
      );
    } else {
      const order = row.raw as ServiceOrder;
      const status = nextStatus as ServiceOrder["status"];
      if (!canTransition(order.status, status, getAllowedServiceOrderStatuses(order, serviceOrderStatuses))) {
        window.alert(`服务订单状态不能从“${order.status}”变更为“${status}”。`);
        setEditingOrderStatus(null);
        return;
      }
      const receivableAmount = order.receivableAmount ?? order.amount;
      const receivedAmount = order.receivedAmount ?? 0;
      if (status === "退款") {
        const refundForm = await requestPayment({
          orderNo: order.orderNo,
          receivable: receivableAmount,
          received: receivedAmount,
          targetStatus: status,
          mode: "refund",
          defaultCollectionAccount: order.collectionAccount,
        });
        if (!refundForm) {
          setEditingOrderStatus(null);
          return;
        }
        await commit(
          applyServiceRefundToData(data, order, refundForm, now),
          {
            action: "服务订单退款",
            targetType: "项目",
            targetName: row.project?.name ?? order.orderNo,
            operator: "当前用户",
            detail: paymentLogDetail({
              orderNo: order.orderNo,
              fromStatus: order.status,
              toStatus: "退款",
              payment: refundForm,
              receivedAmount: Math.max(0, receivedAmount - refundForm.amount),
              customerName: data.organizations.find((org) => org.id === order.customerOrgId)?.name,
            }),
          },
        );
        setEditingOrderStatus(null);
        setSelectedOrder(null);
        return;
      }
      const payment = status === "部分付款" || status === "已付款" ? await orderPaymentPrompt(order.orderNo, receivableAmount, receivedAmount, status) : null;
      if ((status === "部分付款" || status === "已付款") && !payment) {
        setEditingOrderStatus(null);
        return;
      }
      const nextReceivedAmount = payment ? receivedAmount + payment.amount : receivedAmount;
      const normalizedStatus = payment && nextReceivedAmount >= receivableAmount ? "已付款" : status;
      const paymentOccurredAt = payment?.occurredAt || now;
      const nextTransactions = payment ? [servicePaymentTransaction(order, paymentOccurredAt, payment.amount, payment), ...data.transactions] : data.transactions;
      await commit(
        {
          ...data,
          serviceOrders: data.serviceOrders.map((item) => item.id === order.id ? {
            ...item,
            status: normalizedStatus,
            receivableAmount,
            receivedAmount: nextReceivedAmount,
            paymentMethod: payment?.paymentMethod ?? item.paymentMethod,
            collectionAccount: payment?.collectionAccount ?? item.collectionAccount,
            payerAccount: payment?.payerAccount ?? item.payerAccount,
            voucherName: payment?.voucherName ?? item.voucherName,
            voucherFileId: payment?.voucherFileId ?? item.voucherFileId,
            updatedAt: now,
            paidAt: payment ? paymentOccurredAt : item.paidAt,
            cancelledAt: normalizedStatus === "取消" ? now : item.cancelledAt,
          } : item),
          transactions: nextTransactions,
        },
        {
          action: payment ? "订单列表服务收款" : "订单列表修改服务订单状态",
          targetType: "项目",
          targetName: row.project?.name ?? order.orderNo,
          operator: "当前用户",
          detail: paymentLogDetail({
            orderNo: order.orderNo,
            fromStatus: order.status,
            toStatus: normalizedStatus,
            payment,
            receivedAmount: nextReceivedAmount,
            customerName: data.organizations.find((org) => org.id === order.customerOrgId)?.name,
          }),
        },
      );
    }
    setEditingOrderStatus(null);
    setSelectedOrder(null);
  }

  async function saveSelectedPurchaser() {
    if (!selectedOrder || selectedOrder.kind !== "销售订单") return;
    const company = purchaserDraft.purchaserCompany.trim();
    const address = purchaserDraft.purchaserAddress.trim();
    const name = purchaserDraft.purchaserName.trim();
    const phone = purchaserDraft.purchaserPhone.trim();
    if (!company || !address || !name || !phone) {
      window.alert("请填写采购人公司名称、地址、姓名和电话。");
      return;
    }
    const order = selectedOrder.raw as SalesOrder;
    await commit(
      {
        ...data,
        salesOrders: data.salesOrders.map((item) => item.id === order.id ? {
          ...item,
          purchaserCompany: company,
          purchaserAddress: address,
          purchaserName: name,
          purchaserPhone: phone,
          updatedAt: today(),
        } : item),
      },
      {
        action: "修改销售订单采购人",
        targetType: "项目",
        targetName: selectedOrder.project?.name ?? order.orderNo,
        operator: "当前用户",
        detail: `${order.orderNo} / ${company} ${name} ${phone}`,
      },
    );
  }

  const orderCollection = tab === "销售订单" ? "salesOrders" : tab === "采购订单" ? "purchaseOrders" : "serviceOrders";
  const orderRefreshKey = tab === "销售订单" ? data.salesOrders : tab === "采购订单" ? data.purchaseOrders : data.serviceOrders;
  const focusProject = data.projects.find((item) => item.id === focus?.projectId);
  const ordersPage = useServerPagedList<SalesOrder | PurchaseOrder | ServiceOrder>({
    collection: orderCollection,
    search,
    pageSize: 10,
    filters: {
      projectId: focus?.projectId,
      platform: tab === "服务订单" || platformFilter === "全部" ? undefined : platformFilter,
      status: statusFilter === "全部" ? undefined : statusFilter,
      invoiceStatus: tab === "服务订单" || invoiceStatusFilter === "全部" ? undefined : invoiceStatusFilter,
    },
    refreshKey: orderRefreshKey,
  });
  const rowsPage = {
    ...ordersPage,
    items: ordersPage.items.map((order): OrderRow => {
      if (tab === "销售订单") {
        const salesOrder = order as SalesOrder;
        const project = data.projects.find((item) => item.id === salesOrder.projectId);
        const customer = data.organizations.find((org) => org.id === salesOrder.customerOrgId);
        const items = salesOrderLinkedItems(data, salesOrder.id);
        const quantity = salesOrderQuantity(data, salesOrder.id);
        const time = salesOrderTime(salesOrder);
        return {
          id: salesOrder.id,
          kind: "销售订单",
          project,
          orderNo: salesOrder.orderNo,
          counterparty: customer?.name ?? "未选择客户",
          products: items.map((item) => `${item.productName}×${item.quantity}`).join(" / ") || "未添加明细",
          platform: salesOrder.platform || project?.sourcePlatform,
          platformOrderNo: collectionAccountText(data, salesOrder.collectionAccount),
          platformOrderNoText: salesOrder.platformOrderNo,
          quantity,
          amount: salesOrder.amount,
          status: salesOrder.status,
          type: project?.type ?? "商品项目",
          timeLabel: time.label,
          timeValue: time.value,
          timeSub: time.sub,
          note: salesOrder.note,
          raw: salesOrder,
          searchable: "",
          partyPhone: salesOrder.purchaserPhone || customer?.phone,
          partyAddress: salesOrder.purchaserAddress || [customer?.city, customer?.district, customer?.address].filter(Boolean).join(""),
          purchaserCompany: salesOrder.purchaserCompany,
          purchaserName: salesOrder.purchaserName,
          purchaserPhone: salesOrder.purchaserPhone,
          purchaserAddress: salesOrder.purchaserAddress,
          tag: salesOrder.platform || project?.sourcePlatform || undefined,
          lineItems: items.map((item) => {
            const product = data.products.find((entry) => entry.id === item.productId);
            return {
              id: item.id,
              productName: item.productName,
              productCode: product?.code,
              spec: productSpecText(product),
              quantity: Number(item.quantity) || 0,
              unitPrice: Number(item.actualPrice) || 0,
            };
          }),
        };
      }
      if (tab === "采购订单") {
        const purchaseOrder = order as PurchaseOrder;
        const project = data.projects.find((item) => item.id === purchaseOrder.projectId);
        const supplier = data.organizations.find((org) => org.id === purchaseOrder.supplierOrgId);
        const items = purchaseOrderLinkedItems(data, purchaseOrder.id);
        const quantity = purchaseOrderQuantity(data, purchaseOrder.id);
        const time = purchaseOrderTime(purchaseOrder);
        return {
          id: purchaseOrder.id,
          kind: "采购订单",
          project,
          orderNo: purchaseOrder.orderNo,
          counterparty: supplier?.name ?? "未选择供应商",
          products: items.map((item) => item.productName).join(" / ") || "未添加明细",
          platform: project?.sourcePlatform,
          platformOrderNo: purchaseOrder.batchNo ? `批次 ${purchaseOrder.batchNo}` : "",
          quantity,
          amount: purchaseOrderDisplayAmount(data, purchaseOrder),
          status: purchaseOrder.status,
          type: project?.type ?? "商品项目",
          timeLabel: time.label,
          timeValue: time.value,
          timeSub: time.sub,
          note: purchaseOrder.note,
          raw: purchaseOrder,
          searchable: "",
          partyPhone: supplier?.phone,
          partyAddress: [supplier?.city, supplier?.district, supplier?.address].filter(Boolean).join(""),
          tag: project?.sourcePlatform || undefined,
          lineItems: items.map((item) => {
            const product = data.products.find((entry) => entry.id === item.productId);
            return {
              id: item.id,
              productName: item.productName,
              productCode: product?.code,
              spec: productSpecText(product),
              quantity: Number(item.quantity) || 0,
              unitPrice: purchaseOrderItemUnitCost(data, item, purchaseOrder.supplierOrgId),
            };
          }),
        };
      }
      const serviceOrder = order as ServiceOrder;
      const project = data.projects.find((item) => item.id === serviceOrder.projectId);
      const customer = data.organizations.find((org) => org.id === serviceOrder.customerOrgId);
      const service = data.products.find((product) => product.id === serviceOrder.serviceId);
      const time = serviceOrderTime(serviceOrder);
      return {
        id: serviceOrder.id,
        kind: "服务订单",
        project,
        orderNo: serviceOrder.orderNo,
        counterparty: customer?.name ?? "未选择客户",
        products: service?.name ?? project?.serviceProductName ?? "未选择服务",
        platform: project?.sourcePlatform,
        platformOrderNo: collectionAccountText(data, serviceOrder.collectionAccount),
        amount: serviceOrder.amount,
        status: serviceOrder.status,
        type: project?.type ?? "服务项目",
        timeLabel: time.label,
        timeValue: time.value,
        timeSub: time.sub,
        note: serviceOrder.note,
        raw: serviceOrder,
        searchable: "",
      };
    }),
  };
  const selectedOrderProject = selectedOrder?.project;
  const isProductOrderList = tab === "销售订单" || tab === "采购订单";

  function renderOrderStatusCell(row: OrderRow) {
    const invoiceKind = row.kind === "销售订单" ? "sales" : row.kind === "采购订单" ? "purchase" : "service";
    const overview = orderInvoiceOverview(data, row.id, invoiceKind, row.amount);
    return (
      <span className="order-status-cell">
        <span
          className="editable-status"
          title={canEditOrderStatus(row) ? "点击修改状态" : "无状态修改权限"}
          onClick={(event) => {
            event.stopPropagation();
            if (canEditOrderStatus(row) && allowedOrderStatuses(row).length > 1) setEditingOrderStatus({ kind: row.kind, id: row.id });
          }}
          onDoubleClick={(event) => {
            event.stopPropagation();
            if (canEditOrderStatus(row) && allowedOrderStatuses(row).length > 1) setEditingOrderStatus({ kind: row.kind, id: row.id });
          }}
        >
          {editingOrderStatus?.kind === row.kind && editingOrderStatus.id === row.id ? (
            <select
              value={row.status}
              autoFocus
              onClick={(event) => event.stopPropagation()}
              onBlur={() => setEditingOrderStatus(null)}
              onChange={(event) => void updateOrderStatus(row, event.target.value)}
            >
              {allowedOrderStatuses(row).map((status) => <option key={status}>{status}</option>)}
            </select>
          ) : row.status}
        </span>
        {!overview.linked ? <em>{overview.statusLabel}</em> : (
          <>
            <em>{overview.statusLabel} · {overview.invoices.length} 张 · {money(overview.invoiced)}</em>
            {overview.invoices.slice(0, 3).map((invoice) => {
              const linkedAmount = invoiceKind === "service"
                ? invoiceAmountForServiceOrder(data, invoice, row.id)
                : invoiceKind === "purchase"
                  ? invoiceAmountForOrder(invoice, row.id, "purchase")
                  : invoiceAmountForOrder(invoice, row.id, "sales");
              return (
                <em key={invoice.id} className="order-invoice-line" onClick={(event) => event.stopPropagation()}>
                  <CopyableLine text={invoice.invoiceNo} label="发票号码">
                    {invoice.invoiceNo || "无票号"}
                  </CopyableLine>
                  {` ${invoice.status} ${money(linkedAmount)}${invoice.invoiceDate || invoice.date ? ` ${invoice.invoiceDate || invoice.date}` : ""}`}
                </em>
              );
            })}
            {overview.invoices.length > 3 && <em>另 {overview.invoices.length - 3} 张</em>}
          </>
        )}
        {row.kind === "采购订单" && (() => {
          const order = row.raw as PurchaseOrder;
          return (
            <div className="product-project-stack">
              <span>合同 {order.contractStatus ?? DEFAULT_CONTRACT_STATUS}</span>
              <em>对账 {order.reconcileStatus ?? DEFAULT_RECONCILE_STATUS}</em>
            </div>
          );
        })()}
      </span>
    );
  }

  async function linkInvoiceToServiceOrder(invoiceId: string, order: ServiceOrder) {
    if (!invoiceId) return false;
    const invoice = data.invoices.find((item) => item.id === invoiceId);
    if (!invoice) return false;
    const target = { kind: "service" as const, projectId: order.projectId, orderId: order.id };
    const blocked = invoiceLinkBlockReason(data, invoice, target);
    if (blocked) {
      window.alert(blocked);
      return false;
    }
    const amount = promptServiceInvoiceAllocationAmount({
      data,
      invoice,
      projectId: order.projectId,
      serviceOrderId: order.id,
    });
    if (amount == null) return false;
    const nextInvoice = applyServiceInvoiceAllocation(data, invoice, {
      projectId: order.projectId,
      serviceOrderId: order.id,
      amount,
    });
    const nextData = {
      ...data,
      invoices: data.invoices.map((item) => item.id === invoiceId ? nextInvoice : item),
    };
    await commit(
      {
        ...nextData,
        projects: nextData.projects.map((project) => project.id === order.projectId
          ? { ...project, invoiceStatus: deriveServiceProjectInvoiceStatus(nextData, order.projectId) }
          : project),
      },
      {
        action: "关联发票到服务订单",
        targetType: "发票",
        targetName: invoice.invoiceNo || order.orderNo,
        operator: "当前用户",
        detail: `${order.orderNo}；关联金额：${money(amount)}`,
      },
    );
    setOrderInvoiceIds({ ...orderInvoiceIds, [order.id]: "" });
    return true;
  }

  function renderProductOrderCard(row: OrderRow) {
    const lines = row.lineItems ?? [];
    const paidHint = row.kind === "采购订单"
      ? `已付 ${money(purchaseOrderPaidAmount(row.raw as PurchaseOrder, data.transactions))}`
      : `已收 ${money((row.raw as SalesOrder).receivedAmount ?? 0)}`;
    return (
      <article className="order-cloud-card">
        <header className="order-cloud-head">
          <div className="order-cloud-head-main">
            {row.tag && <span className="order-cloud-tag">{row.tag}</span>}
            <span className="order-cloud-no">
              订单编号：
              <CopyableLine text={row.orderNo} label="订单号">{row.orderNo}</CopyableLine>
            </span>
            {row.platformOrderNoText && (
              <span className="order-cloud-platform-no">
                平台单号：
                <CopyableLine text={row.platformOrderNoText} label="平台订单号">{row.platformOrderNoText}</CopyableLine>
              </span>
            )}
            <span className="order-cloud-time">{formatOrderStamp(row.raw.createdAt)} 下单</span>
          </div>
        </header>
        <div className="order-cloud-body">
          <div className="order-cloud-products">
            {lines.length === 0 && <div className="order-cloud-empty-sku">未添加明细</div>}
            {lines.map((item) => (
              <div className="order-cloud-sku" key={item.id}>
                <div className="order-cloud-sku-info">
                  <CopyableLine text={item.productName} label="商品名称">
                    <strong>{item.productName}</strong>
                  </CopyableLine>
                  {item.spec && <em>{item.spec}</em>}
                  {item.productCode && (
                    <CopyableLine text={item.productCode} label="商品编码" className="is-secondary">
                      <em>编码 {item.productCode}</em>
                    </CopyableLine>
                  )}
                </div>
                <div className="order-cloud-sku-qty">
                  <span>{money(item.unitPrice)}</span>
                  <strong>x{item.quantity}</strong>
                </div>
              </div>
            ))}
          </div>
          <div className="order-cloud-money">
            <strong>{money(row.amount)}</strong>
            <em>{paidHint}</em>
            {row.kind === "销售订单" && can("profit.view") && (() => {
              const profit = salesOrderProfit(data, row.raw as SalesOrder);
              return <em>{`毛利 ${money(profit.profit)} · ${grossMarginText(profit.margin)}`}</em>;
            })()}
          </div>
          <div className="order-cloud-party">
            <CopyableLine text={row.counterparty} label={tab === "采购订单" ? "供应商" : "客户"}>
              <strong>{row.counterparty}</strong>
            </CopyableLine>
            {row.kind === "销售订单" && (
              <div className="order-cloud-purchaser">
                {row.purchaserCompany ? (
                  <CopyableLine text={row.purchaserCompany} label="采购人公司">
                    <span>{row.purchaserCompany}</span>
                  </CopyableLine>
                ) : <em>采购人公司未录入</em>}
                <em>{[row.purchaserName, row.purchaserPhone].filter(Boolean).join(" ") || "采购人未录入"}</em>
                {row.purchaserAddress && <em className="order-cloud-address">收货地址 {row.purchaserAddress}</em>}
              </div>
            )}
            {row.kind !== "销售订单" && row.partyPhone && (
              <CopyableLine text={row.partyPhone} label="电话" className="is-secondary">
                <em>{row.partyPhone}</em>
              </CopyableLine>
            )}
            {row.kind !== "销售订单" && row.partyAddress && <em className="order-cloud-address">{row.partyAddress}</em>}
            {row.project?.name && (
              <CopyableLine text={row.project.name} label="项目名称" className="is-secondary">
                <span className="order-cloud-project">{row.project.name}</span>
              </CopyableLine>
            )}
          </div>
          <div className="order-cloud-status">{renderOrderStatusCell(row)}</div>
          <div className="order-cloud-actions">
            <button type="button" className="copy-link" onClick={() => setSelectedOrder(row)}>订单详情</button>
            {row.kind === "销售订单" && (() => {
              const order = row.raw as SalesOrder;
              const canAppend = (can("salesOrder.manage") || can("project.edit")) && row.project?.status !== "已完成" && canEditSalesOrderItems(data, order);
              return (
                <>
                  {canAppend && (
                    <button
                      type="button"
                      className="copy-link"
                      onClick={() => {
                        const blocked = salesOrderItemsEditBlockReason(data, order);
                        if (blocked) {
                          window.alert(blocked);
                          return;
                        }
                        setAppendSalesOrder(order);
                        setSalesComposerOpen(true);
                      }}
                    >追加商品</button>
                  )}
                  <button type="button" className="copy-link" onClick={() => setSalesOrderPanel({ orderId: order.id, kind: "purchase" })}>采购订单</button>
                  <button type="button" className="copy-link" onClick={() => setSalesOrderPanel({ orderId: order.id, kind: "invoice" })}>发票关联</button>
                  <button type="button" className="copy-link" onClick={() => setSalesOrderPanel({ orderId: order.id, kind: "transactions" })}>查看流水</button>
                </>
              );
            })()}
            {row.kind === "采购订单" && (() => {
              const order = row.raw as PurchaseOrder;
              const paymentStatus = order.paymentStatus ?? DEFAULT_ORDER_PAYMENT_STATUS;
              const canPay = canRegisterPurchasePayment(can);
              const canDelete = (can("purchase.manage") || can("purchaseOrder.manage") || can("project.edit"))
                && (order.status === "待下单" || order.status === "草稿")
                && row.project?.status !== "已完成";
              return (
                <>
                  <button type="button" className="copy-link" onClick={() => setPurchaseOrderPanel({ orderId: order.id, kind: "fulfillment" })}>履约详情</button>
                  <button type="button" className="copy-link" onClick={() => setPurchaseOrderPanel({ orderId: order.id, kind: "invoice" })}>发票管理</button>
                  <button type="button" className="copy-link" onClick={() => setPurchaseOrderPanel({ orderId: order.id, kind: "transactions" })}>查看流水</button>
                  {canPay && paymentStatus !== "已付款" && paymentStatus !== "取消" && paymentStatus !== "退款" && (
                    <button
                      type="button"
                      className="copy-link"
                      onClick={() => void registerPurchasePayment({
                        data,
                        commit,
                        requestPayment,
                        order,
                        payable: purchaseOrderDisplayAmount(data, order),
                        targetStatus: paymentStatus === "待付款" ? "部分付款" : "已付款",
                        operator: "当前用户",
                      })}
                    >
                      登记付款
                    </button>
                  )}
                  {canDelete && (
                    <button
                      type="button"
                      className="copy-link danger-action"
                      onClick={() => void deletePurchaseOrderRecord({ data, commit, order, action: "订单列表删除采购订单" })}
                    >
                      删除
                    </button>
                  )}
                </>
              );
            })()}
            {row.project && can("project.view") && (
              <button type="button" className="copy-link" onClick={() => onOpenProject(row.project!.id)}>查看项目</button>
            )}
          </div>
        </div>
        {row.note && (
          <footer className="order-cloud-foot">
            <span className="order-cloud-note-tag">{tab === "采购订单" ? "订单备注" : "备注"}</span>
            <span>{row.note}</span>
          </footer>
        )}
      </article>
    );
  }

  return (
    <div className="panel">
      <PanelTitle title={pageCopy.title} subtitle={pageCopy.subtitle} />
      {ordersPage.error && <div className="form-error">{ordersPage.error}</div>}
      {focusProject && (
        <div className="order-overflow-banner">
          <p>当前筛选项目：{focusProject.name}（{focusProject.projectNo}）</p>
          <button className="ghost" type="button" onClick={() => onClearFocus?.()}>查看全部订单</button>
        </div>
      )}
      <div className="orders-toolbar">
        <div className="orders-search-form">
          <label className="orders-filter-field orders-filter-search">
            <span>搜索</span>
            <SearchField
              value={search}
              onChange={setSearch}
              placeholder={pageCopy.search}
            />
          </label>
          {tab !== "服务订单" && (
            <label className="orders-filter-field">
              <span>平台</span>
              <select
                value={platformFilter}
                aria-label="按平台筛选订单"
                onChange={(event) => setPlatformFilter(event.target.value)}
              >
                <option value="全部">全部</option>
                {orderPlatformOptions.map((item) => <option key={item} value={item}>{item}</option>)}
              </select>
            </label>
          )}
          <label className="orders-filter-field">
            <span>订单状态</span>
            <select
              value={statusFilter}
              aria-label="按订单状态筛选"
              onChange={(event) => setStatusFilter(event.target.value)}
            >
              <option value="全部">全部</option>
              {orderStatusFilterOptions.map((item) => <option key={item} value={item}>{item}</option>)}
            </select>
          </label>
          {tab !== "服务订单" && (
            <label className="orders-filter-field">
              <span>{tab === "采购订单" ? "收票状态" : "发票状态"}</span>
              <select
                value={invoiceStatusFilter}
                aria-label={tab === "采购订单" ? "按收票状态筛选" : "按发票状态筛选"}
                onChange={(event) => setInvoiceStatusFilter(event.target.value)}
              >
                <option value="全部">全部</option>
                {invoiceStatusFilterOptions.map((item) => <option key={item} value={item}>{item}</option>)}
              </select>
            </label>
          )}
        </div>
        {tab === "销售订单" && can("salesOrder.manage") && (
          <button
            className="primary"
            type="button"
            onClick={() => {
              setAppendSalesOrder(null);
              setSalesComposerOpen(true);
            }}
          >
            <PackagePlus size={16} />添加订单
          </button>
        )}
      </div>
      {isProductOrderList ? (
        <div className="order-cloud-list">
          {rowsPage.items.length === 0 && !ordersPage.loading && <p className="empty-line">暂无订单</p>}
          {rowsPage.items.map((row) => (
            <Fragment key={`${row.kind}-${row.id}`}>{renderProductOrderCard(row)}</Fragment>
          ))}
        </div>
      ) : (
      <div className="table">
        <div className="table-row order-table head"><span>项目/订单</span><span>客户</span><span>服务</span><span>收款账户/公司</span><span>金额</span><span>状态</span><span>时间</span></div>
        {rowsPage.items.map((row) => (
          <div className="table-row order-table clickable-row" role="button" tabIndex={0} key={`${row.kind}-${row.id}`} onClick={() => setSelectedOrder(row)} onKeyDown={(event) => event.key === "Enter" && setSelectedOrder(row)}>
            <span>
              <CopyableLine text={row.orderNo} label="订单号">{row.orderNo}</CopyableLine>
              <em>{row.project?.name ?? "未关联项目"}</em>
            </span>
            <span>
              <CopyableLine text={row.counterparty} label="客户">
                {row.counterparty}
              </CopyableLine>
            </span>
            <span>{row.products}</span>
            <span className="collection-account-cell">
              {row.platformOrderNo || "未录入"}
            </span>
            <span>{money(row.amount)}<em>已收 {money((row.raw as ServiceOrder).receivedAmount ?? 0)}</em></span>
            {renderOrderStatusCell(row)}
            <span>{row.timeLabel}<em>{row.timeValue}</em>{row.timeSub && <em>{row.timeSub}</em>}</span>
          </div>
        ))}
      </div>
      )}
      <Pagination {...rowsPage} onPageChange={rowsPage.setPage} />
      {selectedOrder && (
        <div className="modal-backdrop" role="presentation">
          <div className="modal order-detail-modal" role="dialog" aria-modal="true" aria-label="订单详情">
            <div className="modal-head">
              <div>
                <h2>订单详情</h2>
                <p>{selectedOrder.kind} · {selectedOrder.orderNo}</p>
              </div>
              <button className="icon-button" onClick={() => setSelectedOrder(null)} aria-label="关闭订单详情"><X size={18} /></button>
            </div>
            <div className="info-grid">
              <Info label="订单号" value={selectedOrder.orderNo} />
              <Info label="订单类型" value={selectedOrder.kind} />
              <Info label="项目" value={selectedOrderProject?.name ?? "未关联项目"} />
              <Info label="项目编号" value={selectedOrderProject?.projectNo ?? "未关联"} />
              <Info label={selectedOrder.kind === "采购订单" ? "供应商" : "客户"} value={selectedOrder.counterparty} />
              <Info label={selectedOrder.kind === "服务订单" ? "服务" : "商品"} value={selectedOrder.products} />
              {selectedOrder.kind === "采购订单" && <Info label="数量" value={String(selectedOrder.quantity && selectedOrder.quantity > 0 ? selectedOrder.quantity : "—")} />}
              <Info label="金额" value={money(selectedOrder.amount)} />
              {(selectedOrder.kind === "销售订单" || selectedOrder.kind === "服务订单") && <Info label="实收金额" value={money((selectedOrder.raw as SalesOrder | ServiceOrder).receivedAmount ?? 0)} />}
              {(selectedOrder.kind === "销售订单" || selectedOrder.kind === "服务订单") && <Info label="收款账户/公司" value={collectionAccountText(data, (selectedOrder.raw as SalesOrder | ServiceOrder).collectionAccount)} />}
              {selectedOrder.kind === "采购订单" && <Info label="货款状态" value={(selectedOrder.raw as PurchaseOrder).paymentStatus ?? DEFAULT_ORDER_PAYMENT_STATUS} />}
              {selectedOrder.kind === "采购订单" && <Info label="已付金额" value={money(purchaseOrderPaidAmount(selectedOrder.raw as PurchaseOrder, data.transactions))} />}
              {selectedOrder.kind === "采购订单" && <Info label="付款银行" value={collectionAccountText(data, (selectedOrder.raw as PurchaseOrder).collectionAccount)} />}
              {selectedOrder.kind === "采购订单" && <Info label="合同状态" value={(selectedOrder.raw as PurchaseOrder).contractStatus ?? DEFAULT_CONTRACT_STATUS} />}
              {selectedOrder.kind === "采购订单" && <Info label="对账状态" value={(selectedOrder.raw as PurchaseOrder).reconcileStatus ?? DEFAULT_RECONCILE_STATUS} />}
              <Info label="状态" value={selectedOrder.status} />
              {(() => {
                const invoiceKind = selectedOrder.kind === "销售订单" ? "sales" : selectedOrder.kind === "采购订单" ? "purchase" : "service";
                const overview = orderInvoiceOverview(data, selectedOrder.id, invoiceKind, selectedOrder.amount);
                return (
                  <>
                    <Info label={selectedOrder.kind === "采购订单" ? "收票" : "开票"} value={`${overview.statusLabel}${overview.linked ? ` · ${overview.invoices.length} 张 · ${money(overview.invoiced)}` : ""}`} />
                    {overview.invoices.map((invoice) => {
                      const linkedAmount = invoiceKind === "service"
                        ? invoiceAmountForServiceOrder(data, invoice, selectedOrder.id)
                        : invoiceKind === "purchase"
                          ? invoiceAmountForOrder(invoice, selectedOrder.id, "purchase")
                          : invoiceAmountForOrder(invoice, selectedOrder.id, "sales");
                      return (
                        <Info
                          key={invoice.id}
                          label={invoice.invoiceNo || "发票"}
                          value={`${invoice.status} ${money(linkedAmount)}${invoice.invoiceDate || invoice.date ? ` · ${invoice.invoiceDate || invoice.date}` : ""}`}
                        />
                      );
                    })}
                  </>
                );
              })()}
              <Info label={selectedOrder.timeLabel} value={selectedOrder.timeValue} />
              <Info label={selectedOrder.kind === "服务订单" ? "创建时间" : "下单时间"} value={formatDateTime(selectedOrder.raw.createdAt)} />
              <Info label="更新时间" value={formatDateTime("updatedAt" in selectedOrder.raw ? selectedOrder.raw.updatedAt : undefined)} />
              <Info label="备注" value={selectedOrder.note ?? "无"} />
              {selectedOrder.kind === "销售订单" && can("profit.view") && (() => {
                const profit = salesOrderProfit(data, selectedOrder.raw as SalesOrder);
                return (
                  <>
                    <Info label="订单销售额" value={money(profit.salesAmount)} />
                    <Info label="分摊采购成本" value={money(profit.costAmount)} />
                    <Info label="订单毛利" value={`${money(profit.profit)} · ${grossMarginText(profit.margin)}`} />
                  </>
                );
              })()}
            </div>
            {selectedOrder.kind === "销售订单" && (can("salesOrder.manage") || can("project.edit")) && (
              <div className="sales-composer-fields order-purchaser-fields">
                <span className="sales-composer-field sales-composer-field-full">采购人</span>
                <PurchaserQuickPaste onFill={(parsed) => setPurchaserDraft({ ...purchaserDraft, ...parsed })} />
                <label className="sales-composer-field">
                  <span>公司名称</span>
                  <input value={purchaserDraft.purchaserCompany} onChange={(event) => setPurchaserDraft({ ...purchaserDraft, purchaserCompany: event.target.value })} aria-label="采购人公司名称" />
                </label>
                <label className="sales-composer-field">
                  <span>地址（收货地址）</span>
                  <input value={purchaserDraft.purchaserAddress} onChange={(event) => setPurchaserDraft({ ...purchaserDraft, purchaserAddress: event.target.value })} aria-label="采购人收货地址" />
                </label>
                <label className="sales-composer-field">
                  <span>姓名</span>
                  <input value={purchaserDraft.purchaserName} onChange={(event) => setPurchaserDraft({ ...purchaserDraft, purchaserName: event.target.value })} aria-label="采购人姓名" />
                </label>
                <label className="sales-composer-field">
                  <span>电话</span>
                  <input value={purchaserDraft.purchaserPhone} onChange={(event) => setPurchaserDraft({ ...purchaserDraft, purchaserPhone: event.target.value })} aria-label="采购人电话" />
                </label>
                <div className="sales-composer-field">
                  <span> </span>
                  <button className="ghost" type="button" onClick={() => void saveSelectedPurchaser()}>保存采购人</button>
                </div>
              </div>
            )}
            {selectedOrder.kind === "销售订单" && !(can("salesOrder.manage") || can("project.edit")) && (
              <div className="info-grid">
                <Info label="采购人公司" value={(selectedOrder.raw as SalesOrder).purchaserCompany || "未录入"} />
                <Info label="收货地址" value={(selectedOrder.raw as SalesOrder).purchaserAddress || "未录入"} />
                <Info label="采购人姓名" value={(selectedOrder.raw as SalesOrder).purchaserName || "未录入"} />
                <Info label="采购人电话" value={(selectedOrder.raw as SalesOrder).purchaserPhone || "未录入"} />
              </div>
            )}
            {selectedOrder.kind === "服务订单" && can("invoice.manage") && (
              <div className="invoice-link-bar" style={{ marginTop: 12 }}>
                <SearchableSelect
                  value={orderInvoiceIds[selectedOrder.id] ?? ""}
                  options={invoiceLinkSelectOptions(data, {
                    kind: "service",
                    projectId: selectedOrder.raw.projectId,
                    orderId: selectedOrder.id,
                  })}
                  onChange={(invoiceId) => setOrderInvoiceIds({ ...orderInvoiceIds, [selectedOrder.id]: invoiceId })}
                  placeholder="搜索发票号、买卖方或金额"
                  ariaLabel="搜索并选择已有发票关联到服务订单"
                />
                <button
                  type="button"
                  className="ghost"
                  onClick={() => void linkInvoiceToServiceOrder(orderInvoiceIds[selectedOrder.id] ?? "", selectedOrder.raw as ServiceOrder)}
                >
                  关联发票
                </button>
              </div>
            )}
            {selectedOrder.kind === "服务订单" && (() => {
              const overview = orderInvoiceOverview(data, selectedOrder.id, "service", selectedOrder.amount);
              if (!overview.linked || !can("invoice.manage")) return null;
              return (
                <div className="linked-invoice-list" style={{ marginTop: 8 }}>
                  {overview.invoices.map((invoice) => (
                    <div key={invoice.id} className="linked-invoice-card">
                      <div className="linked-invoice-card-head">
                        <strong>{invoice.invoiceNo || "未录入发票号"}</strong>
                        <em>{invoice.status} · 本单 {money(invoiceAmountForServiceOrder(data, invoice, selectedOrder.id))}</em>
                        <button
                          type="button"
                          className="linked-invoice-unlink"
                          title="取消关联"
                          aria-label={`取消关联发票 ${invoice.invoiceNo || "未录入"}`}
                          onClick={() => void unlinkServiceInvoiceRecord({
                            data,
                            commit,
                            invoice,
                            projectId: selectedOrder.raw.projectId,
                            serviceOrderId: selectedOrder.id,
                            label: selectedOrder.orderNo,
                          })}
                        >
                          ×
                        </button>
                      </div>
                    </div>
                  ))}
                </div>
              );
            })()}
            <OrderTransactionList
              data={data}
              transactions={transactionsForOrder(data.transactions, selectedOrder.id, selectedOrder.kind, selectedOrder.orderNo)}
            />
            <div className="modal-actions">
              {(selectedOrder.kind === "销售订单" || selectedOrder.kind === "服务订单") && (selectedOrder.raw as SalesOrder | ServiceOrder).voucherFileId && <button className="ghost" onClick={() => openBusinessDocument((selectedOrder.raw as SalesOrder | ServiceOrder).voucherFileId)}><FileText size={16} />{selectedOrder.status === "退款" ? "查看打款凭证" : "查看收款凭证"}</button>}
              {selectedOrder.kind === "采购订单" && (selectedOrder.raw as PurchaseOrder).voucherFileId && <button className="ghost" onClick={() => openBusinessDocument((selectedOrder.raw as PurchaseOrder).voucherFileId)}><FileText size={16} />查看付款凭证</button>}
              {(selectedOrder.kind === "销售订单" || selectedOrder.kind === "服务订单") && canBackfillCollection(can, selectedOrder.kind === "服务订单" ? "service" : "sales") && missingCollectionAmount((selectedOrder.raw as SalesOrder | ServiceOrder).receivedAmount, collectionTxTotalForOrder(data.transactions, selectedOrder.id, selectedOrder.kind === "服务订单" ? "service" : "sales")) > 0 && (
                <button className="ghost" onClick={() => void backfillSelectedOrder()}><Banknote size={16} />补录缺失流水</button>
              )}
              {selectedOrder.kind === "采购订单" && canRegisterPurchasePayment(can) && ((selectedOrder.raw as PurchaseOrder).paymentStatus ?? DEFAULT_ORDER_PAYMENT_STATUS) !== "已付款" && (
                <button className="ghost" onClick={() => void paySelectedPurchaseOrder()}><Banknote size={16} />登记付款</button>
              )}
              {selectedOrderProject && can("project.view") && <button className="ghost" onClick={() => onOpenProject(selectedOrderProject.id)}>查看关联项目</button>}
              <button className="ghost" onClick={() => setSelectedOrder(null)}>关闭</button>
            </div>
          </div>
        </div>
      )}
      {tab === "销售订单" && (
        <SalesOrderComposerModals
          data={data}
          commit={commit}
          open={salesComposerOpen}
          allowSelectProject={!appendSalesOrder}
          initialProject={appendSalesOrder
            ? data.projects.find((item) => item.id === appendSalesOrder.projectId)
            : focusProject}
          targetOrder={appendSalesOrder ?? undefined}
          onClose={() => {
            setSalesComposerOpen(false);
            setAppendSalesOrder(null);
          }}
          onSubmitted={() => {
            setSalesComposerOpen(false);
            setAppendSalesOrder(null);
            ordersPage.reload();
          }}
        />
      )}
      {tab === "销售订单" && salesOrderPanel && (() => {
        const panelOrder = data.salesOrders.find((item) => item.id === salesOrderPanel.orderId);
        if (!panelOrder) return null;
        const panelProject = data.projects.find((item) => item.id === panelOrder.projectId);
        const customer = data.organizations.find((org) => org.id === panelOrder.customerOrgId);
        const ownCompany = data.organizations.find((org) => org.id === panelOrder.ownCompanyOrgId);
        if (salesOrderPanel.kind === "invoice") {
          return (
            <div className="modal-backdrop" role="presentation">
              <div className="modal order-invoice-modal" role="dialog" aria-modal="true" aria-label="销售订单发票管理">
                <div className="modal-head">
                  <div>
                    <h2>发票管理</h2>
                    <p>{panelOrder.orderNo} · 关联已有发票、手工添加或 OCR 识别后关联到本单</p>
                  </div>
                  <button className="icon-button" onClick={() => setSalesOrderPanel(null)} aria-label="关闭发票管理"><X size={18} /></button>
                </div>
                <OrderInvoiceAssociationPanel
                  linkedInvoices={orderLinkedInvoices(data, panelOrder.id, "sales")}
                  invoiceSelectOptions={invoiceLinkSelectOptions(data, { kind: "sales", projectId: panelOrder.projectId, orderId: panelOrder.id })}
                  selectedInvoiceId={orderInvoiceIds[panelOrder.id] ?? ""}
                  canManage={can("invoice.manage")}
                  invoices={data.invoices}
                  organizations={data.organizations}
                  defaultBuyer={{ id: customer?.id, name: customer?.name, taxNo: customer?.unifiedCreditCode }}
                  defaultSeller={{ id: ownCompany?.id, name: ownCompany?.name, taxNo: ownCompany?.unifiedCreditCode }}
                  existingHint={`到本销售订单 ${panelOrder.orderNo}（销项）`}
                  ocrNewHint={`识别完成，保存时将新增销项发票并关联 ${panelOrder.orderNo}。`}
                  expectedInvoiceType="销项"
                  orderId={panelOrder.id}
                  orderType="sales"
                  orderSummary={orderInvoicePickSummary(data, panelOrder.id, "sales")}
                  orderNoById={buildOrderNoById(data)}
                  onSelectInvoice={(invoiceId) => setOrderInvoiceIds({ ...orderInvoiceIds, [panelOrder.id]: invoiceId })}
                  onLink={(lineIndexes, lineQuantities) => void linkInvoiceToOrderRecord({ data, commit, invoiceId: orderInvoiceIds[panelOrder.id], order: panelOrder, type: "sales", lineIndexes, lineQuantities }).then((ok) => { if (ok) setOrderInvoiceIds({ ...orderInvoiceIds, [panelOrder.id]: "" }); })}
                  onUnlink={(invoice) => void unlinkInvoiceFromOrderRecord({ data, commit, invoice, order: panelOrder, type: "sales" })}
                  onLinkExisting={async (invoice, lineIndexes, lineQuantities) => linkInvoiceToOrderRecord({ data, commit, invoiceId: invoice.id, order: panelOrder, type: "sales", lineIndexes, lineQuantities })}
                  onCreateNew={(payload) => panelProject ? createLinkedInvoiceRecord({
                    data,
                    commit,
                    can,
                    project: panelProject,
                    payload,
                    options: {
                      type: "销项",
                      salesOrderId: panelOrder.id,
                      defaultProductName: salesOrderLinkedItems(data, panelOrder.id)[0]?.productName ?? panelProject.name,
                      logDetail: `销售订单销项发票关联：${panelOrder.orderNo}`,
                    },
                    customer,
                    ownCompany,
                  }) : Promise.resolve(false)}
                />
                <div className="modal-actions">
                  <button className="ghost" type="button" onClick={() => setSalesOrderPanel(null)}>关闭</button>
                </div>
              </div>
            </div>
          );
        }
        if (salesOrderPanel.kind === "transactions") {
          return (
            <div className="modal-backdrop" role="presentation">
              <div className="modal order-tx-modal" role="dialog" aria-modal="true" aria-label="销售订单流水">
                <div className="modal-head">
                  <div>
                    <h2>查看流水</h2>
                    <p>{panelOrder.orderNo} · 已收 {money(panelOrder.receivedAmount ?? 0)} / 应收 {money(panelOrder.receivableAmount ?? panelOrder.amount)}</p>
                  </div>
                  <button className="icon-button" onClick={() => setSalesOrderPanel(null)} aria-label="关闭流水"><X size={18} /></button>
                </div>
                <OrderTransactionList
                  data={data}
                  transactions={transactionsForOrder(data.transactions, panelOrder.id, "销售订单", panelOrder.orderNo)}
                />
                <div className="modal-actions">
                  {canBackfillCollection(can, "sales") && missingCollectionAmount(panelOrder.receivedAmount, collectionTxTotalForOrder(data.transactions, panelOrder.id, "sales")) > 0 && (
                    <button className="ghost" type="button" onClick={() => void backfillMissingCollectionTx({
                      data,
                      commit,
                      requestPayment,
                      kind: "sales",
                      order: panelOrder,
                      operator: "当前用户",
                    })}><Banknote size={16} />补录流水</button>
                  )}
                  <button className="ghost" type="button" onClick={() => setSalesOrderPanel(null)}>关闭</button>
                </div>
              </div>
            </div>
          );
        }
        return (
          <div className="modal-backdrop" role="presentation">
            <div className="modal order-tx-modal" role="dialog" aria-modal="true" aria-label="关联采购订单">
              <div className="modal-head">
                <div>
                  <h2>关联采购订单</h2>
                  <p>{panelOrder.orderNo} · 可手动关联本项目的多张采购订单，毛利按订单计算</p>
                </div>
                <button className="icon-button" onClick={() => setSalesOrderPanel(null)} aria-label="关闭采购订单"><X size={18} /></button>
              </div>
              <SalesOrderPurchaseLinker
                data={data}
                order={panelOrder}
                canManage={(can("salesOrder.manage") || can("project.edit")) && panelProject?.status !== "已完成"}
                canViewProfit={can("profit.view")}
                onSave={async (purchaseOrderIds) => {
                  await commit(
                    applySalesOrderPurchaseLinks(data, panelOrder.id, purchaseOrderIds),
                    {
                      action: "关联销售订单采购",
                      targetType: "项目",
                      targetName: panelProject?.name ?? panelOrder.orderNo,
                      operator: "当前用户",
                      detail: `${panelOrder.orderNo} 关联采购 ${purchaseOrderIds.length} 笔`,
                    },
                  );
                }}
              />
              <div className="modal-actions">
                {panelProject && can("project.view") && (
                  <button className="ghost" type="button" onClick={() => onOpenProject(panelProject.id)}>查看项目采购</button>
                )}
                <button className="ghost" type="button" onClick={() => setSalesOrderPanel(null)}>关闭</button>
              </div>
            </div>
          </div>
        );
      })()}
      {tab === "采购订单" && purchaseOrderPanel && (() => {
        const panelOrder = data.purchaseOrders.find((item) => item.id === purchaseOrderPanel.orderId);
        if (!panelOrder) return null;
        const panelProject = data.projects.find((item) => item.id === panelOrder.projectId);
        const supplier = data.organizations.find((org) => org.id === panelOrder.supplierOrgId);
        const ownCompany = data.organizations.find((org) => org.id === (panelOrder.ownCompanyOrgId || panelProject?.ownCompanyOrgId));
        const canEditFulfillment = can("purchase.manage") || can("purchaseOrder.manage");
        if (purchaseOrderPanel.kind === "fulfillment") {
          return (
            <div className="modal-backdrop" role="presentation">
              <div className="modal order-fulfillment-modal" role="dialog" aria-modal="true" aria-label="采购订单履约详情">
                <div className="modal-head">
                  <div>
                    <h2>履约详情</h2>
                    <p>{panelOrder.orderNo} · 执行 {panelOrder.status} · 货款 {panelOrder.paymentStatus ?? DEFAULT_ORDER_PAYMENT_STATUS}</p>
                  </div>
                  <button className="icon-button" onClick={() => setPurchaseOrderPanel(null)} aria-label="关闭履约详情"><X size={18} /></button>
                </div>
                <div className="fulfillment-grid">
                  <label>
                    <span>执行状态</span>
                    <select
                      value={panelOrder.status}
                      disabled={!canEditFulfillment}
                      onChange={(event) => {
                        const status = event.target.value as PurchaseOrder["status"];
                        if (!canTransition(panelOrder.status, status, getAllowedPurchaseOrderStatuses(panelOrder, purchaseOrderStatuses))) {
                          window.alert(`采购订单状态不能从“${panelOrder.status}”变更为“${status}”。`);
                          return;
                        }
                        void updateListPurchaseOrderFields(panelOrder, { status }, "订单列表修改采购订单状态");
                      }}
                    >
                      {getAllowedPurchaseOrderStatuses(panelOrder, purchaseOrderStatuses).map((status) => <option key={status}>{status}</option>)}
                    </select>
                  </label>
                  <label>
                    <span>物流状态</span>
                    <select
                      value={panelOrder.logisticsStatus ?? DEFAULT_LOGISTICS_STATUS}
                      disabled={!canEditFulfillment}
                      onChange={(event) => void updateListPurchaseOrderFields(panelOrder, { logisticsStatus: event.target.value as LogisticsStatus })}
                    >
                      {logisticsStatusOptions.map((status) => <option key={status}>{status}</option>)}
                    </select>
                  </label>
                  {(panelOrder.logisticsStatus ?? DEFAULT_LOGISTICS_STATUS) === "已发货" && (
                    <label>
                      <span>物流单号</span>
                      <input
                        defaultValue={panelOrder.logisticsNo ?? ""}
                        key={`list-logistics-no-${panelOrder.id}-${panelOrder.updatedAt}`}
                        disabled={!canEditFulfillment}
                        placeholder="请输入物流单号"
                        onBlur={(event) => {
                          if ((panelOrder.logisticsNo ?? "") !== event.target.value.trim()) {
                            void updateListPurchaseOrderFields(panelOrder, { logisticsNo: event.target.value.trim() || undefined });
                          }
                        }}
                      />
                    </label>
                  )}
                  <label>
                    <span>验收状态</span>
                    <select
                      value={panelOrder.acceptanceStatus ?? DEFAULT_ACCEPTANCE_STATUS}
                      disabled={!canEditFulfillment}
                      onChange={(event) => void updateListPurchaseOrderFields(panelOrder, { acceptanceStatus: event.target.value as AcceptanceStatus })}
                    >
                      {acceptanceStatusOptions.map((status) => <option key={status}>{status}</option>)}
                    </select>
                  </label>
                  <label>
                    <span>交付状态</span>
                    <select
                      value={panelOrder.deliveryStatus ?? DEFAULT_DELIVERY_STATUS}
                      disabled={!canEditFulfillment}
                      onChange={(event) => void updateListPurchaseOrderFields(panelOrder, { deliveryStatus: event.target.value as DeliveryStatus })}
                    >
                      {deliveryStatusOptions.map((status) => <option key={status}>{status}</option>)}
                    </select>
                  </label>
                  <label>
                    <span>合同状态</span>
                    <select
                      value={panelOrder.contractStatus ?? DEFAULT_CONTRACT_STATUS}
                      disabled={!canEditFulfillment}
                      onChange={(event) => void updateListPurchaseOrderContractStatus(panelOrder, event.target.value as ContractStatus)}
                    >
                      {contractStatusOptions.map((status) => <option key={status}>{status}</option>)}
                    </select>
                  </label>
                  {((panelOrder.contractStatus ?? DEFAULT_CONTRACT_STATUS) === "已签" || panelOrder.contractFileId) && (
                    <label>
                      <span>合同文件</span>
                      <ContractFileActions
                        fileId={panelOrder.contractFileId}
                        canReplace={canEditFulfillment}
                        onView={() => setContractViewerFileId(panelOrder.contractFileId!)}
                        onReplace={() => { setPoContractUploadOrderId(panelOrder.id); setPoContractFile(null); }}
                      />
                    </label>
                  )}
                  <label>
                    <span>对账状态</span>
                    <select
                      value={panelOrder.reconcileStatus ?? DEFAULT_RECONCILE_STATUS}
                      disabled={!canEditFulfillment}
                      onChange={(event) => {
                        const next = event.target.value as ReconcileStatus;
                        if (next === (panelOrder.reconcileStatus ?? DEFAULT_RECONCILE_STATUS)) return;
                        void updateListPurchaseOrderFields(panelOrder, { reconcileStatus: next }, "订单列表修改采购对账状态");
                      }}
                    >
                      {reconcileStatusOptions.map((status) => <option key={status}>{status}</option>)}
                    </select>
                  </label>
                </div>
                <div className="modal-actions">
                  <button className="ghost" type="button" onClick={() => setPurchaseOrderPanel(null)}>关闭</button>
                </div>
              </div>
            </div>
          );
        }
        if (purchaseOrderPanel.kind === "invoice") {
          return (
            <div className="modal-backdrop" role="presentation">
              <div className="modal order-invoice-modal" role="dialog" aria-modal="true" aria-label="采购订单发票管理">
                <div className="modal-head">
                  <div>
                    <h2>发票管理</h2>
                    <p>{panelOrder.orderNo} · 关联已有发票、手工添加或 OCR 识别后关联到本单</p>
                  </div>
                  <button className="icon-button" onClick={() => setPurchaseOrderPanel(null)} aria-label="关闭发票管理"><X size={18} /></button>
                </div>
                <OrderInvoiceAssociationPanel
                  linkedInvoices={orderLinkedInvoices(data, panelOrder.id, "purchase")}
                  invoiceSelectOptions={invoiceLinkSelectOptions(data, { kind: "purchase", projectId: panelOrder.projectId, orderId: panelOrder.id })}
                  selectedInvoiceId={orderInvoiceIds[panelOrder.id] ?? ""}
                  canManage={can("invoice.manage")}
                  invoices={data.invoices}
                  organizations={data.organizations}
                  defaultBuyer={{ id: ownCompany?.id, name: ownCompany?.name, taxNo: ownCompany?.unifiedCreditCode }}
                  defaultSeller={{ id: supplier?.id, name: supplier?.name, taxNo: supplier?.unifiedCreditCode }}
                  existingHint={`到本采购订单 ${panelOrder.orderNo}（进项）`}
                  ocrNewHint={`识别完成，保存时将新增进项发票并关联 ${panelOrder.orderNo}。`}
                  expectedInvoiceType="进项"
                  orderId={panelOrder.id}
                  orderType="purchase"
                  orderSummary={orderInvoicePickSummary(data, panelOrder.id, "purchase")}
                  orderNoById={buildOrderNoById(data)}
                  onSelectInvoice={(invoiceId) => setOrderInvoiceIds({ ...orderInvoiceIds, [panelOrder.id]: invoiceId })}
                  onLink={(lineIndexes, lineQuantities) => void linkInvoiceToOrderRecord({ data, commit, invoiceId: orderInvoiceIds[panelOrder.id], order: panelOrder, type: "purchase", lineIndexes, lineQuantities }).then((ok) => { if (ok) setOrderInvoiceIds({ ...orderInvoiceIds, [panelOrder.id]: "" }); })}
                  onUnlink={(invoice) => void unlinkInvoiceFromOrderRecord({ data, commit, invoice, order: panelOrder, type: "purchase" })}
                  onLinkExisting={async (invoice, lineIndexes, lineQuantities) => linkInvoiceToOrderRecord({ data, commit, invoiceId: invoice.id, order: panelOrder, type: "purchase", lineIndexes, lineQuantities })}
                  onCreateNew={(payload) => panelProject ? createLinkedInvoiceRecord({
                    data,
                    commit,
                    can,
                    project: panelProject,
                    payload,
                    options: {
                      type: "进项",
                      purchaseOrderId: panelOrder.id,
                      defaultProductName: data.projectItems.find((item) => item.purchaseOrderId === panelOrder.id)?.productName ?? panelProject.name,
                      logDetail: `采购订单进项发票关联：${panelOrder.orderNo}`,
                    },
                    customer: supplier,
                    ownCompany,
                  }) : Promise.resolve(false)}
                />
                <div className="modal-actions">
                  <button className="ghost" type="button" onClick={() => setPurchaseOrderPanel(null)}>关闭</button>
                </div>
              </div>
            </div>
          );
        }
        return (
          <div className="modal-backdrop" role="presentation">
            <div className="modal order-tx-modal" role="dialog" aria-modal="true" aria-label="采购订单流水">
              <div className="modal-head">
                <div>
                  <h2>查看流水</h2>
                  <p>{panelOrder.orderNo} · 已付 {money(purchaseOrderPaidAmount(panelOrder, data.transactions))} / 应付 {money(purchaseOrderDisplayAmount(data, panelOrder))}</p>
                </div>
                <button className="icon-button" onClick={() => setPurchaseOrderPanel(null)} aria-label="关闭流水"><X size={18} /></button>
              </div>
              <OrderTransactionList
                data={data}
                transactions={transactionsForOrder(data.transactions, panelOrder.id, "采购订单", panelOrder.orderNo)}
              />
              <div className="modal-actions">
                {canRegisterPurchasePayment(can) && (panelOrder.paymentStatus ?? DEFAULT_ORDER_PAYMENT_STATUS) !== "已付款" && (
                  <button
                    className="ghost"
                    type="button"
                    onClick={() => void registerPurchasePayment({
                      data,
                      commit,
                      requestPayment,
                      order: panelOrder,
                      payable: purchaseOrderDisplayAmount(data, panelOrder),
                      targetStatus: (panelOrder.paymentStatus ?? DEFAULT_ORDER_PAYMENT_STATUS) === "待付款" ? "部分付款" : "已付款",
                      operator: "当前用户",
                    })}
                  >
                    <Banknote size={16} />登记付款
                  </button>
                )}
                <button className="ghost" type="button" onClick={() => setPurchaseOrderPanel(null)}>关闭</button>
              </div>
            </div>
          </div>
        );
      })()}
      {tab === "采购订单" && poContractUploadOrderId && (() => {
        const uploadOrder = data.purchaseOrders.find((item) => item.id === poContractUploadOrderId);
        if (!uploadOrder) return null;
        return (
          <div className="modal-backdrop is-nested" role="presentation">
            <div className="modal" role="dialog" aria-modal="true" aria-label="上传采购合同">
              <div className="modal-head">
                <div>
                  <h2>{uploadOrder.contractFileId ? "替换采购合同" : "上传采购合同"}</h2>
                  <p>{uploadOrder.orderNo} · 仅支持 PDF</p>
                </div>
                <button className="icon-button" onClick={() => { setPoContractUploadOrderId(""); setPoContractFile(null); }} aria-label="关闭上传合同"><X size={18} /></button>
              </div>
              <div className="form-grid">
                <FilePicker
                  accept=".pdf,application/pdf"
                  fileName={poContractFile?.name}
                  placeholder="请选择单个 PDF 合同文件"
                  buttonLabel="选择合同"
                  ariaLabel="选择采购合同文件"
                  onFile={(file) => setPoContractFile(file ?? null)}
                />
              </div>
              <div className="modal-actions">
                <button className="ghost" type="button" onClick={() => { setPoContractUploadOrderId(""); setPoContractFile(null); }}>取消</button>
                <button className="primary" type="button" onClick={() => void saveListPoSignedContract()}>
                  <FileText size={16} />{uploadOrder.contractFileId ? "上传并替换" : "上传并标记已签"}
                </button>
              </div>
            </div>
          </div>
        );
      })()}
      {tab === "采购订单" && contractViewerFileId && (
        <div className="modal-backdrop is-nested" role="presentation">
          <div className="modal contract-viewer-modal" role="dialog" aria-modal="true" aria-label="查看合同">
            <div className="modal-head">
              <div>
                <h2>合同预览</h2>
                <p>{data.purchaseOrders.find((order) => order.contractFileId === contractViewerFileId)?.contractFileName || "PDF 合同"}</p>
              </div>
              <div className="contract-viewer-actions">
                <button className="ghost" type="button" onClick={() => openBusinessDocument(contractViewerFileId)}>新窗口打开</button>
                <button className="icon-button" onClick={() => setContractViewerFileId("")} aria-label="关闭合同预览"><X size={18} /></button>
              </div>
            </div>
            <iframe src={businessDocumentUrl(contractViewerFileId)} title="合同内容" />
          </div>
        </div>
      )}
      {paymentDialog}
    </div>
  );
}

function Entities({
  data,
  commit,
  applyData,
  onNotice,
  can,
  operatorName,
}: {
  data: AppData;
  commit: (data: AppData, log?: Omit<OperationLog, "id" | "createdAt">) => Promise<void>;
  applyData: (data: AppData) => void;
  onNotice: (notice: { type: "success" | "error"; message: string }) => void;
  can: CanAccess;
  operatorName: string;
}) {
  const [name, setName] = useState("");
  const [creditCode, setCreditCode] = useState("");
  const [legalPerson, setLegalPerson] = useState("");
  const [phone, setPhone] = useState("");
  const [email, setEmail] = useState("");
  const [entityType, setEntityType] = useState<EntityType | "">("");
  const [roles, setRoles] = useState<OrganizationRole[]>([]);
  const [taxpayerType, setTaxpayerType] = useState<TaxpayerType | "">("");
  const [roleFilter, setRoleFilter] = useState<OrganizationRole | "全部">("全部");
  const [entitySearch, setEntitySearch] = useState("");
  const [mergeOrgId, setMergeOrgId] = useState("");
  const [showEntityModal, setShowEntityModal] = useState(false);
  const [licenseFileName, setLicenseFileName] = useState("");
  const [licenseFile, setLicenseFile] = useState<File | null>(null);
  const [licenseOcrStatus, setLicenseOcrStatus] = useState("");
  const [showLicenseDocument, setShowLicenseDocument] = useState(false);
  const [address, setAddress] = useState("");
  const [selectedOrgId, setSelectedOrgId] = useState("");
  const [logOrgId, setLogOrgId] = useState("");
  const [showTemporaryContract, setShowTemporaryContract] = useState(false);
  const entityTypeOptions = optionValues(data, "entity_type", entityTypes) as EntityType[];
  const orgRoleOptions = optionValues(data, "organization_role", orgRoles) as OrganizationRole[];

  const filteredPage = useServerPagedList<Organization>({
    collection: "organizations",
    search: entitySearch,
    filters: { role: roleFilter === "全部" ? undefined : roleFilter },
    pageSize: 10,
    refreshKey: data.organizations,
  });

  function resetEntityForm() {
    setName("");
    setCreditCode("");
    setLegalPerson("");
    setPhone("");
    setEmail("");
    setEntityType("");
    setRoles([]);
    setTaxpayerType("");
    setMergeOrgId("");
    setLicenseFileName("");
    setLicenseFile(null);
    setLicenseOcrStatus("");
    setShowLicenseDocument(false);
    setAddress("");
  }

  function openEntityModal(organization?: Organization) {
    resetEntityForm();
    setSelectedOrgId("");
    setShowEntityModal(true);
    if (!organization) return;
    const current = data.organizations.find((org) => org.id === organization.id) ?? organization;
    setMergeOrgId(current.id);
    setName(current.name);
    setCreditCode(current.unifiedCreditCode ?? "");
    setLegalPerson(current.legalPerson ?? "");
    setPhone(current.phone ?? "");
    setEmail(current.email ?? "");
    setEntityType(current.entityType);
    setRoles(current.roles);
    setTaxpayerType(current.taxpayerType ?? "");
    setAddress(current.address ?? "");
    setLicenseFileName(current.licenseFileName ?? "");
  }

  function selectLicenseFile(file: File | undefined) {
    setLicenseFile(file ?? null);
    setLicenseFileName(file?.name ?? "");
    setLicenseOcrStatus("");
    setShowLicenseDocument(false);
  }

  async function fillFromLicenseOcr() {
    if (!licenseFile) {
      setLicenseOcrStatus("请先选择营业执照图片或 PDF。");
      return;
    }
    setLicenseOcrStatus("正在识别营业执照...");
    try {
      const formData = new FormData();
      formData.append("file", await prepareOcrUpload(licenseFile));
      const response = await fetch(ocrServiceUrl("/api/ocr/business-license"), {
        method: "POST",
        body: formData,
      });
      if (!response.ok) {
        const errorText = await response.text();
        throw new Error(errorText || "营业执照识别失败");
      }
      const result = await response.json();
      if (result.status !== "recognized" || !result.data) {
        setLicenseOcrStatus(result.message || "暂未识别到营业执照字段。");
        return;
      }
      const parsed = result.data as {
        unified_credit_code?: string;
        name?: string;
        entity_type?: string;
        legal_person?: string;
        address?: string;
      };
      setName(parsed.name ?? "");
      setCreditCode(parsed.unified_credit_code ?? "");
      setLegalPerson(parsed.legal_person ?? "");
      setAddress(parsed.address ?? "");
      setEntityType(entityTypeOptions.includes(parsed.entity_type as EntityType) ? parsed.entity_type as EntityType : "");
      setRoles([]);
      const existing = data.organizations.find((org) => org.unifiedCreditCode === parsed.unified_credit_code);
      setMergeOrgId(existing?.id ?? "");
      setLicenseOcrStatus(result.message || "营业执照识别完成。");
    } catch (error) {
      setLicenseOcrStatus(error instanceof Error ? error.message : "营业执照识别失败");
    }
  }

  function selectMergeTarget(orgId: string) {
    const organization = data.organizations.find((org) => org.id === orgId);
    setMergeOrgId(orgId);
    if (!organization) return;
    setName(organization.name);
    setCreditCode(organization.unifiedCreditCode ?? "");
    setLegalPerson(organization.legalPerson ?? "");
    setPhone(organization.phone ?? "");
    setEmail(organization.email ?? "");
    setEntityType(organization.entityType);
    setAddress(organization.address ?? "");
  }

  async function addOrganization() {
    if (!name.trim()) {
      window.alert("请输入单位名称。");
      return;
    }
    const normalizedCreditCode = creditCode.trim();
    if (!normalizedCreditCode) {
      window.alert("请填写统一社会信用代码。");
      return;
    }
    if (!entityType) {
      window.alert("请选择实体类型。");
      return;
    }
    if (!taxpayerType) {
      window.alert("请选择纳税人类型。");
      return;
    }
    if (roles.length === 0) {
      window.alert("请至少选择一个业务身份。");
      return;
    }
    const duplicate = data.organizations.find((org) => org.unifiedCreditCode === normalizedCreditCode);
    const mergeTarget = duplicate;
    if (mergeTarget) {
      const savedLicense = licenseFile ? await uploadBusinessDocument(licenseFile, "business_license", mergeTarget.id) : null;
      const updated = data.organizations.map((org) =>
        org.id === mergeTarget.id
          ? {
              ...org,
              name: name || org.name,
                unifiedCreditCode: normalizedCreditCode,
                legalPerson: legalPerson || org.legalPerson,
                phone: phone || org.phone,
                email: email || org.email,
                address: address || org.address,
                roles,
                taxpayerType,
                taxpayerTypeHistory: org.taxpayerType === taxpayerType ? org.taxpayerTypeHistory : [
                  ...(org.taxpayerTypeHistory ?? []).map((item) => item.endedAt ? item : { ...item, endedAt: new Date().toISOString() }),
                  { type: taxpayerType, effectiveAt: todayDate(), changedAt: new Date().toISOString() },
                ],
                updatedAt: new Date().toISOString(),
                licenseFileId: savedLicense?.id ?? org.licenseFileId,
                licenseFileName: savedLicense?.fileName ?? org.licenseFileName,
              }
          : org,
      );
      await commit(
        { ...data, organizations: updated },
        { action: "更新企业/单位", targetType: "实体", targetName: mergeTarget.name, operator: "当前用户", detail: `身份：${roles.join("、")}` },
      );
      resetEntityForm();
      setShowEntityModal(false);
      return;
    }
    const organizationId = createId("org");
    const savedLicense = licenseFile ? await uploadBusinessDocument(licenseFile, "business_license", organizationId) : null;
    const organization: Organization = {
      id: organizationId,
      name,
      entityType,
      roles,
      taxpayerType,
      taxpayerTypeHistory: [{ type: taxpayerType, effectiveAt: todayDate(), changedAt: new Date().toISOString() }],
      unifiedCreditCode: normalizedCreditCode,
      legalPerson: legalPerson || undefined,
      phone: phone || undefined,
      email: email || undefined,
      address: address || undefined,
      status: "正常",
      createdAt: today(),
      updatedAt: new Date().toISOString(),
      licenseFileId: savedLicense?.id,
      licenseFileName: savedLicense?.fileName,
    };
    await commit(
      { ...data, organizations: [organization, ...data.organizations] },
      { action: "新增企业/单位", targetType: "实体", targetName: organization.name, operator: "当前用户", detail: `身份：${roles.join("、")}` },
    );
    resetEntityForm();
    setShowEntityModal(false);
  }

  async function deleteOrganization(org: Organization) {
    if (!window.confirm(`确定删除「${org.name}」吗？`)) return;
    const references = organizationReferenceCounts(data, org.id);
    const referenced = formatOrganizationReferences(references);
    if (referenced) {
      window.alert(`该企业/单位仍被业务数据引用，无法删除：${referenced}`);
      return;
    }
    try {
      await deleteCollectionItem("organizations", org.id);
      const savedLog = await createCollectionItem<OperationLog>("operationLogs", {
        id: createId("log"),
        createdAt: today(),
        action: "删除企业/单位",
        targetType: "实体",
        targetName: org.name,
        operator: operatorName,
        detail: `统一社会信用代码：${org.unifiedCreditCode || "未录入"}`,
      });
      applyData({
        ...data,
        organizations: data.organizations.filter((item) => item.id !== org.id),
        operationLogs: [savedLog, ...data.operationLogs],
      });
      filteredPage.reload();
      onNotice({ type: "success", message: "删除企业/单位成功" });
      if (selectedOrgId === org.id) setSelectedOrgId("");
      if (logOrgId === org.id) setLogOrgId("");
    } catch (error) {
      onNotice({ type: "error", message: error instanceof Error ? error.message : "删除失败，请稍后重试" });
    }
  }

  const selectedOrganization = data.organizations.find((org) => org.id === selectedOrgId);
  const selectedOrgProjects = selectedOrganization
    ? data.projects.filter((project) =>
        project.customerOrgId === selectedOrganization.id
        || project.usageUnitOrgId === selectedOrganization.id
        || project.ownCompanyOrgId === selectedOrganization.id,
      )
    : [];
  const selectedOrgInvoices = selectedOrganization
    ? data.invoices.filter((invoice) =>
        invoice.buyerOrgId === selectedOrganization.id
        || invoice.sellerOrgId === selectedOrganization.id
        || invoice.counterpartyOrgId === selectedOrganization.id,
      )
    : [];
  const selectedOrgAccounts = selectedOrganization
    ? data.platformAccounts.filter((account) => account.customerOrgId === selectedOrganization.id)
    : [];

  return (
    <div className="stack">
      <div className="panel">
        <div className="panel-title action-title">
          <div>
            <h2>客户基础信息管理</h2>
            <p>集中维护客户主体、业务身份、纳税人类型及基础资料；列表展示关联服务项目与商品项目数量。</p>
          </div>
          <div className="panel-title-buttons">
            {can("project.edit") && (
              <button className="ghost" type="button" onClick={() => setShowTemporaryContract(true)}>
                <FileText size={16} />生成临时合同
              </button>
            )}
            {can("entity.create") && <button className="primary" onClick={() => openEntityModal()}><UserPlus size={16} />添加客户</button>}
          </div>
        </div>
        <div className="segmented">
          {["全部", ...orgRoleOptions].map((item) => (
            <button key={item} className={roleFilter === item ? "active" : ""} onClick={() => setRoleFilter(item as OrganizationRole | "全部")}>{item}</button>
          ))}
        </div>
        <SearchField
          value={entitySearch}
          onChange={setEntitySearch}
          placeholder="搜索公司、信用代码、联系人、电话"
        />
        <div className="table entity-list-table">
          <div className="table-row entity-table head">
            <span>公司/实体</span><span>身份</span><span>类型/纳税人类型</span><span>统一社会信用代码</span><span>服务项目</span><span>商品项目</span><span>联系人</span><span>修改时间</span><span>操作</span>
          </div>
          {filteredPage.items.map((org) => {
            const serviceProjectCount = data.projects.filter((project) => project.type === "服务项目" && project.customerOrgId === org.id).length;
            const productProjectCount = data.projects.filter((project) => project.type === "商品项目" && project.customerOrgId === org.id).length;
            return (
            <div className="table-row entity-table" key={org.id}>
              <span className="entity-name-cell">
                <CopyableLine text={org.name} label="公司名称" onOpen={() => setSelectedOrgId(org.id)}>
                  <strong>{org.name}</strong>
                </CopyableLine>
                <em>{org.address || org.city || "暂无地址"}</em>
              </span>
              <span><span className="entity-role-list">{org.roles.map((item) => <em key={item}>{item}</em>)}</span></span>
              <span>{org.entityType}<em>{org.taxpayerType || "未设置"}</em></span>
              <span>
                <CopyableLine
                  text={org.unifiedCreditCode}
                  label="统一社会信用代码"
                  className={org.licenseFileId ? "entity-credit-code has-file" : "entity-credit-code no-file"}
                  onOpen={org.licenseFileId ? () => openBusinessDocument(org.licenseFileId) : undefined}
                >
                  {org.licenseFileId ? (
                    <>
                      <FileText size={14} />
                      <span>{org.unifiedCreditCode || "未录入"}</span>
                    </>
                  ) : (org.unifiedCreditCode || "未录入")}
                </CopyableLine>
              </span>
              <span>{serviceProjectCount}</span>
              <span>{productProjectCount}</span>
              <span className="entity-contact-cell">
                <CopyableLine text={org.legalPerson} label="联系人">
                  {org.legalPerson || "未录入"}
                </CopyableLine>
                <CopyableLine text={org.phone} label="电话" className="is-secondary">
                  <em>{org.phone || "暂无电话"}</em>
                </CopyableLine>
                <CopyableLine text={org.email} label="邮箱" className="is-secondary">
                  <em>{org.email || "暂无邮箱"}</em>
                </CopyableLine>
              </span>
              <span>{formatDateTimeValue(org.updatedAt ?? org.createdAt)}<em>创建 {formatDateTimeValue(org.createdAt)}</em></span>
              <span className="entity-row-actions">
                <button className="copy-link" onClick={() => setLogOrgId(org.id)}>日志</button>
                {can("entity.create") && <button className="copy-link" onClick={() => openEntityModal(org)}>编辑</button>}
                {can("entity.create") && <button className="copy-link danger-action" onClick={() => void deleteOrganization(org)}>删除</button>}
              </span>
            </div>
            );
          })}
          {filteredPage.items.length === 0 && <div className="table-empty">暂无符合条件的客户信息</div>}
        </div>
        <Pagination {...filteredPage} onPageChange={filteredPage.setPage} />
      </div>
      {showEntityModal && (
        <div className="modal-backdrop" role="presentation">
          <div className={`modal entity-license-modal${showLicenseDocument && licenseFile ? " is-comparing" : ""}`} role="dialog" aria-modal="true" aria-label="添加客户信息">
            {showLicenseDocument && licenseFile && <LicenseDocumentView file={licenseFile} onClose={() => setShowLicenseDocument(false)} />}
            <div className="entity-license-form-pane">
            <div className="modal-head">
              <div>
                <h2>维护企业/单位</h2>
                <p>可上传营业执照 OCR 回填，也可以手动录入；统一社会信用代码必填，重复时更新已有资料。</p>
              </div>
              <button className="icon-button" onClick={() => setShowEntityModal(false)} aria-label="关闭">×</button>
            </div>
            <div className="upload-strip">
              <FilePicker
                accept="image/*,.pdf,application/pdf"
                fileName={licenseFileName}
                placeholder="未选择营业执照文件"
                buttonLabel="选择执照"
                ariaLabel="选择营业执照文件"
                onFile={(file) => selectLicenseFile(file)}
              />
              {licenseFile && <button className="license-preview-trigger" type="button" onClick={() => setShowLicenseDocument(true)}><FileText size={15} />查看原件</button>}
              {can("entity.create") && <button className="ghost" onClick={fillFromLicenseOcr}><FileScan size={16} />OCR 识别并填充</button>}
            </div>
            {licenseOcrStatus && <div className="copy-tip">{licenseOcrStatus}</div>}
            <div className="form-grid entity-form">
              <input value={name} onChange={(event) => setName(event.target.value)} placeholder="单位名称" />
              <input value={creditCode} onChange={(event) => setCreditCode(event.target.value)} placeholder="统一社会信用代码（必填）" />
              <input value={legalPerson} onChange={(event) => setLegalPerson(event.target.value)} placeholder="法人/负责人" />
              <input value={phone} onChange={(event) => setPhone(event.target.value)} placeholder="联系电话" />
              <input type="email" value={email} onChange={(event) => setEmail(event.target.value)} placeholder="联系邮箱" />
              <input value={address} onChange={(event) => setAddress(event.target.value)} placeholder="注册地址/经营地址" />
              <select value={entityType} onChange={(event) => setEntityType(event.target.value as EntityType)}>
                <option value="">请选择实体类型</option>
                {entityTypeOptions.map((type) => <option key={type}>{type}</option>)}
              </select>
              <select value={taxpayerType} onChange={(event) => setTaxpayerType(event.target.value as TaxpayerType)}>
                <option value="">请选择纳税人类型</option>
                {taxpayerTypes.map((item) => <option key={item}>{item}</option>)}
              </select>
              <div className="role-checkboxes span-2">
                {orgRoleOptions.map((item) => <label key={item}><input type="checkbox" checked={roles.includes(item)} onChange={() => setRoles((current) => current.includes(item) ? current.filter((value) => value !== item) : [...current, item])} />{item}</label>)}
              </div>
            </div>
            <div className="modal-actions">
              <button className="ghost" onClick={() => setShowEntityModal(false)}>取消</button>
              {can("entity.create") && <button className="primary" onClick={addOrganization}><UserPlus size={16} />保存企业/单位</button>}
            </div>
            </div>
          </div>
        </div>
      )}
      {selectedOrganization && (
        <div className="modal-backdrop" role="presentation">
          <div className="modal" role="dialog" aria-modal="true" aria-label="实体详情">
            <div className="modal-head">
              <div>
                <h2>实体详情</h2>
                <p>{selectedOrganization.name}</p>
              </div>
              <button className="icon-button" onClick={() => setSelectedOrgId("")} aria-label="关闭">×</button>
            </div>
            <div className="info-grid">
              <Info label="实体类型" value={selectedOrganization.entityType} />
              <Info label="身份" value={selectedOrganization.roles.join("、")} />
              <Info label="统一社会信用代码" value={selectedOrganization.unifiedCreditCode || "未录入"} />
              <Info label="法人/负责人" value={selectedOrganization.legalPerson || "未录入"} />
              <Info label="电话" value={selectedOrganization.phone || "未录入"} />
              <Info label="邮箱" value={selectedOrganization.email || "未录入"} />
              <Info label="地址" value={selectedOrganization.address || "未录入"} />
              <Info label="营业执照" value={selectedOrganization.licenseFileName || "未保存原件"} />
              <Info label="状态" value={selectedOrganization.status} />
              <Info label="关联项目" value={`${selectedOrgProjects.length} 个`} />
              <Info label="关联发票" value={`${selectedOrgInvoices.length} 张`} />
              <Info label="平台账号" value={`${selectedOrgAccounts.length} 个`} />
            </div>
            <h3>关联项目</h3>
            <div className="table">
              <div className="table-row head"><span>项目</span><span>类型</span><span>状态</span><span>金额</span></div>
              {selectedOrgProjects.length > 0
                ? selectedOrgProjects.map((project) => (
                    <div className="table-row" key={project.id}>
                      <span>{project.name}</span>
                      <span>{project.type}</span>
                      <span>{project.status}</span>
                      <span>{money(project.totalAmount)}</span>
                    </div>
                  ))
                : <div className="table-row"><span>暂无关联项目</span><span></span><span></span><span></span></div>}
            </div>
            <div className="modal-actions">
              {can("entity.create") && <button className="ghost" onClick={() => openEntityModal(selectedOrganization)}><UserPlus size={16} />合并/编辑身份</button>}
              <button className="ghost" onClick={() => setSelectedOrgId("")}>关闭</button>
            </div>
          </div>
        </div>
      )}
      {logOrgId && (() => {
        const organization = data.organizations.find((org) => org.id === logOrgId);
        const logs = organization ? organizationRelatedLogs(data, organization) : [];
        return <RelatedLogsModal title={`${organization?.name ?? "企业"} · 企业日志`} logs={logs} onClose={() => setLogOrgId("")} />;
      })()}
      {showTemporaryContract && (
        <TemporaryContractDialog
          data={data}
          formatName="entity-temp-contract-format"
          onClose={() => setShowTemporaryContract(false)}
        />
      )}
    </div>
  );
}

function Products({ data, commit, can }: { data: AppData; commit: (data: AppData, log?: Omit<OperationLog, "id" | "createdAt">) => Promise<void>; can: CanAccess }) {
  const emptyProductForm = {
    code: "",
    name: "",
    category: "空调",
    frameworkPrice: "",
    quotePrice: "",
    passThroughPrice: "",
    costPrice: "",
    orderInfo: "",
    platformIds: [] as string[],
  };
  const [form, setForm] = useState(emptyProductForm);
  const [productStatus, setProductStatus] = useState("");
  const [productTab, setProductTab] = useState<Product["kind"]>("实体商品");
  const [productNameSearch, setProductNameSearch] = useState("");
  const [creatingProductKind, setCreatingProductKind] = useState<Product["kind"] | null>(null);
  const [editingProductId, setEditingProductId] = useState("");
  const [productImportFile, setProductImportFile] = useState<File | null>(null);
  const [productImportFileName, setProductImportFileName] = useState("");
  const [importSupplierOrgId, setImportSupplierOrgId] = useState(data.organizations.find((org) => isSupplierOrganization(org))?.id ?? "");
  const [priceProductId, setPriceProductId] = useState("");
  const [priceDraft, setPriceDraft] = useState({ supplierOrgId: "", purchasePrice: "", effectiveDate: new Date().toISOString().slice(0, 10), note: "" });
  const suppliers = data.organizations.filter((org) => isSupplierOrganization(org));
  const priceProduct = data.products.find((product) => product.id === priceProductId);
  const editingProduct = data.products.find((product) => product.id === editingProductId);
  const productModalKind = editingProduct?.kind ?? creatingProductKind;
  const visibleProductsPage = useServerPagedList<Product>({
    collection: "products",
    search: productNameSearch,
    filters: { kind: productTab },
    pageSize: 10,
    refreshKey: data.products,
  });
  const canViewChannelPrices = can("product.manage") || can("purchase.manage") || can("profit.view");
  const priceProductBindings = priceProduct
    ? data.supplierPrices
      .filter((price) => price.productId === priceProduct.id)
      .sort((a, b) => (b.effectiveDate || "").localeCompare(a.effectiveDate || ""))
    : [];

  function openProductModal(kind: Product["kind"]) {
    setEditingProductId("");
    setCreatingProductKind(kind);
    setForm({
      ...emptyProductForm,
      category: kind === "实体商品" ? "空调" : "平台服务",
    });
    setProductStatus("");
  }

  function openEditProductModal(product: Product) {
    setCreatingProductKind(null);
    setEditingProductId(product.id);
    setForm({
      code: product.code,
      name: product.name,
      category: product.category,
      frameworkPrice: product.frameworkPrice != null ? String(product.frameworkPrice) : "",
      quotePrice: String(product.quotePrice ?? ""),
      passThroughPrice: product.passThroughPrice != null ? String(product.passThroughPrice) : "",
      costPrice: String(product.costPrice ?? ""),
      orderInfo: product.orderInfo ?? "",
      platformIds: product.platformIds ?? [],
    });
    setProductStatus("");
  }

  function closeProductModal() {
    setCreatingProductKind(null);
    setEditingProductId("");
  }

  function openSupplierBindModal(product: Product) {
    setPriceProductId(product.id);
    setPriceDraft({
      supplierOrgId: suppliers[0]?.id ?? "",
      purchasePrice: product.costPrice ? String(product.costPrice) : "",
      effectiveDate: new Date().toISOString().slice(0, 10),
      note: "",
    });
  }

  function selectProductImportFile(file: File | undefined) {
    setProductImportFile(file ?? null);
    setProductImportFileName(file?.name ?? "");
    setProductStatus("");
  }

  function cellText(row: unknown[], index: number) {
    const value = row[index];
    return value == null ? "" : String(value).trim();
  }

  function cellNumber(row: unknown[], index: number) {
    const text = cellText(row, index).replace(/[￥¥,\s]/g, "");
    const value = Number(text);
    return Number.isFinite(value) ? value : 0;
  }

  async function importProductsFromFile() {
    if (!productImportFile) {
      setProductStatus("请先选择商品和价格管理 Excel 文件。");
      return;
    }
    const buffer = await productImportFile.arrayBuffer();
    const workbook = XLSX.read(buffer, { type: "array" });
    const worksheet = workbook.Sheets[workbook.SheetNames[0]];
    if (!worksheet) {
      setProductStatus("未读取到有效工作表。");
      return;
    }
    const rows = XLSX.utils.sheet_to_json<unknown[]>(worksheet, { header: 1, defval: "" });
    let nextProducts = [...data.products];
    let nextSupplierPrices = [...data.supplierPrices];
    let createdCount = 0;
    let updatedCount = 0;
    let priceCount = 0;
    const todayText = new Date().toISOString().slice(0, 10);

    for (const row of rows.slice(1)) {
      const code = cellText(row, 0);
      const name = cellText(row, 1);
      if (!code || !name) continue;
      const kind: Product["kind"] = name.includes("入驻") || cellText(row, 2).includes("服务") ? "虚拟服务" : "实体商品";
      const productPatch: Omit<Product, "id"> = {
        code,
        name,
        kind,
        category: kind === "虚拟服务" ? "平台入驻" : (cellText(row, 2) || "空调"),
        capacity: cellText(row, 3) || undefined,
        energyLevel: cellText(row, 4) || undefined,
        shape: cellText(row, 5) || cellText(row, 2) || undefined,
        frameworkPrice: cellNumber(row, 6) || undefined,
        quotePrice: cellNumber(row, 7),
        passThroughPrice: cellNumber(row, 9) || undefined,
        costPrice: cellNumber(row, 10),
        platformCode: cellText(row, 12) || undefined,
        orderInfo: cellText(row, 13) || undefined,
        area: cellText(row, 15) || undefined,
        description: [cellText(row, 16), cellText(row, 20)].filter(Boolean).join("；") || undefined,
      };
      const existing = nextProducts.find((product) => product.code === code);
      const productId = existing?.id ?? createId("prd");
      if (existing) {
        nextProducts = nextProducts.map((product) => (product.id === existing.id ? { ...product, ...productPatch } : product));
        updatedCount += 1;
      } else {
        nextProducts = [{ id: productId, ...productPatch }, ...nextProducts];
        createdCount += 1;
      }

      if (kind === "实体商品" && importSupplierOrgId && productPatch.costPrice > 0) {
        const hasSamePrice = nextSupplierPrices.some((price) =>
          price.productId === productId
          && price.supplierOrgId === importSupplierOrgId
          && price.purchasePrice === productPatch.costPrice
          && price.effectiveDate === todayText,
        );
        if (!hasSamePrice) {
          nextSupplierPrices = [{
            id: createId("sp"),
            productId,
            supplierOrgId: importSupplierOrgId,
            purchasePrice: productPatch.costPrice,
            effectiveDate: todayText,
            note: `Excel导入：${productImportFile.name}`,
          }, ...nextSupplierPrices];
          priceCount += 1;
        }
      }
    }

    if (createdCount + updatedCount === 0) {
      setProductStatus("未导入商品，请确认第一张表为价格体系且包含商品编号、商品名称。");
      return;
    }

    await commit(
      { ...data, products: nextProducts, supplierPrices: nextSupplierPrices },
      { action: "导入商品价格", targetType: "商品", targetName: productImportFile.name, operator: "当前用户", detail: `新增 ${createdCount} 个，更新 ${updatedCount} 个，新增渠道价 ${priceCount} 条` },
    );
    setProductStatus(`导入完成：新增 ${createdCount} 个商品，更新 ${updatedCount} 个商品，新增 ${priceCount} 条渠道价。`);
    setProductImportFile(null);
    setProductImportFileName("");
  }

  async function saveProduct() {
    if (!productModalKind) return;
    const name = form.name.trim();
    const code = form.code.trim() || (editingProduct ? editingProduct.code : `AUTO-${new Date().toISOString().replace(/\D/g, "").slice(0, 14)}`);
    if (!name) {
      setProductStatus("请先填写商品名称。");
      return;
    }
    const exists = data.products.some((product) => product.code === code && product.id !== editingProductId);
    if (exists) {
      setProductStatus(`商品编码 ${code} 已存在，请更换编码。`);
      return;
    }
    const isService = productModalKind === "虚拟服务";
    const quotePrice = Number(form.quotePrice) || 0;
    const passThroughPrice = isService
      ? undefined
      : (form.passThroughPrice !== "" ? Number(form.passThroughPrice) : Math.round(quotePrice * 1.1 * 100) / 100);
    const nowIso = new Date().toISOString();
    const productPatch: Omit<Product, "id"> = {
      code,
      name,
      kind: productModalKind,
      category: form.category,
      frameworkPrice: isService ? undefined : (form.frameworkPrice !== "" ? Number(form.frameworkPrice) : undefined),
      quotePrice,
      passThroughPrice,
      costPrice: isService ? 0 : Number(form.costPrice) || 0,
      orderInfo: form.orderInfo || undefined,
      platformIds: isService ? form.platformIds : undefined,
      capacity: editingProduct?.capacity,
      energyLevel: editingProduct?.energyLevel,
      shape: editingProduct?.shape,
      platformCode: editingProduct?.platformCode,
      area: editingProduct?.area,
      description: editingProduct?.description,
      createdAt: editingProduct?.createdAt ?? nowIso,
      updatedAt: nowIso,
      source: editingProduct?.source,
      sourceProjectId: editingProduct?.sourceProjectId,
    };
    try {
      if (editingProduct) {
        await commit(
          {
            ...data,
            products: data.products.map((product) => product.id === editingProduct.id ? { ...product, ...productPatch } : product),
          },
          { action: "编辑商品", targetType: "商品", targetName: productPatch.name, operator: "当前用户", detail: `商品编码：${productPatch.code}` },
        );
        setProductStatus(`已更新商品：${productPatch.name}`);
      } else {
        const product: Product = { id: createId("prd"), ...productPatch };
        await commit(
          { ...data, products: [product, ...data.products] },
          { action: "新建商品", targetType: "商品", targetName: product.name, operator: "当前用户", detail: `商品编码：${product.code}` },
        );
        setProductStatus(`已新建商品：${product.name}`);
      }
      setForm(emptyProductForm);
      closeProductModal();
    } catch (error) {
      setProductStatus(error instanceof Error ? error.message : "商品保存失败，请稍后重试。");
    }
  }

  async function deleteProduct(product: Product) {
    await commit(
      {
        ...data,
        products: data.products.filter((item) => item.id !== product.id),
        supplierPrices: data.supplierPrices.filter((price) => price.productId !== product.id),
        projectItems: data.projectItems.filter((item) => item.productId !== product.id),
      },
      { action: "删除商品", targetType: "商品", targetName: product.name, operator: "当前用户", detail: "开发环境删除商品档案、渠道价格和项目明细引用" },
    );
  }

  async function deleteChannelPrice(price: SupplierPrice, product: Product) {
    await commit(
      { ...data, supplierPrices: data.supplierPrices.filter((item) => item.id !== price.id) },
      { action: "删除渠道价格", targetType: "商品", targetName: product.name, operator: "当前用户", detail: `删除渠道价格：${money(price.purchasePrice)}` },
    );
  }

  async function addChannelPrice() {
    if (!priceProduct || !priceDraft.supplierOrgId || !Number(priceDraft.purchasePrice)) {
      setProductStatus("请选择供应商并填写有效进货价。");
      return;
    }
    const newPrice: SupplierPrice = {
      id: createId("sp"),
      productId: priceProduct.id,
      supplierOrgId: priceDraft.supplierOrgId,
      purchasePrice: Number(priceDraft.purchasePrice),
      effectiveDate: priceDraft.effectiveDate,
      note: priceDraft.note || "绑定供应商",
    };
    await commit(
      { ...data, supplierPrices: [newPrice, ...data.supplierPrices] },
      { action: "绑定供应商", targetType: "商品", targetName: priceProduct.name, operator: "当前用户", detail: `${money(newPrice.purchasePrice)}，生效日期：${newPrice.effectiveDate}` },
    );
    setProductStatus(`已绑定供应商：${priceProduct.name} / ${money(newPrice.purchasePrice)}`);
    setPriceDraft({
      supplierOrgId: priceDraft.supplierOrgId,
      purchasePrice: "",
      effectiveDate: new Date().toISOString().slice(0, 10),
      note: "",
    });
  }

  return (
    <div className="stack">
      <div className="panel">
        <div className="panel-title action-title">
          <div>
            <h2>商品与价格管理</h2>
            <p>商品档案和渠道价格分开管理；同一渠道价格可保留多条波动记录。</p>
          </div>
          {can("product.manage") && (
            <div className="product-create-actions">
              <button className="primary" onClick={() => openProductModal("实体商品")}><Package size={16} />新建实体商品</button>
              <button className="primary" onClick={() => openProductModal("虚拟服务")}><ShieldCheck size={16} />新建服务类商品</button>
            </div>
          )}
        </div>
        {productStatus && <div className="copy-tip">{productStatus}</div>}
        <div className="platform-account-toolbar">
          <div className="segmented">
            {(["实体商品", "虚拟服务"] as const).map((item) => (
              <button
                key={item}
                className={productTab === item ? "active" : ""}
                onClick={() => {
                  setProductTab(item);
                  setProductNameSearch("");
                }}
              >
                {item === "实体商品" ? "产品类" : "服务类"}
              </button>
            ))}
          </div>
          <SearchField
            value={productNameSearch}
            onChange={setProductNameSearch}
            placeholder={productTab === "实体商品" ? "按商品名称搜索" : "按服务名称搜索"}
            ariaLabel={productTab === "实体商品" ? "按商品名称搜索" : "按服务名称搜索"}
          />
        </div>
        <div className="product-list">
          {visibleProductsPage.items.map((product) => {
            const productPrices = data.supplierPrices
              .filter((price) => price.productId === product.id)
              .sort((a, b) => (b.effectiveDate || "").localeCompare(a.effectiveDate || ""));
            const marketPriceText = product.frameworkPrice != null ? money(product.frameworkPrice) : "未录入";
            const salesPriceText = money(product.quotePrice);
            const copyProductPrices = () => {
              const payload = `${product.name}\n平台价 ${marketPriceText}\n供货价 ${salesPriceText}`;
              void writeClipboardText(payload)
                .then(() => {
                  setProductStatus(`已复制：${product.name}`);
                  window.setTimeout(() => setProductStatus(""), 1600);
                })
                .catch(() => {
                  setProductStatus("复制失败，请检查浏览器剪贴板权限");
                  window.setTimeout(() => setProductStatus(""), 1600);
                });
            };
            const copyOrderInfo = () => {
              const lines = [
                product.orderInfo?.trim() ? `下单信息：${product.orderInfo.trim()}` : "",
                product.platformCode?.trim() ? `平台编码：${product.platformCode.trim()}` : "",
                product.description?.trim() ? `备注：${product.description.trim()}` : "",
              ].filter(Boolean);
              if (lines.length === 0) {
                setProductStatus("该商品暂无下单信息/链接/备注");
                window.setTimeout(() => setProductStatus(""), 1600);
                return;
              }
              void writeClipboardText(lines.join("\n"))
                .then(() => {
                  setProductStatus(`已复制下单信息：${product.name}`);
                  window.setTimeout(() => setProductStatus(""), 1600);
                })
                .catch(() => {
                  setProductStatus("复制失败，请检查浏览器剪贴板权限");
                  window.setTimeout(() => setProductStatus(""), 1600);
                });
            };
            return (
              <article className="product-card expanded" key={product.id}>
                <div className="product-card-main">
                  <h3 className="product-card-title">
                    <span className="product-card-name">{product.name}</span>
                    <button type="button" className="quick-copy-btn product-card-icon-btn" title="复制名称与价格" aria-label="复制名称与价格" onClick={copyProductPrices}>
                      <Copy size={13} strokeWidth={2.2} />
                    </button>
                    <button type="button" className="quick-copy-btn product-card-icon-btn" title="复制下单信息/链接/备注" aria-label="复制下单信息" onClick={copyOrderInfo}>
                      <Link2 size={13} strokeWidth={2.2} />
                    </button>
                  </h3>
                  <div className="supplier-prices product-price-summary">
                    {product.kind === "实体商品" ? (
                      <>
                        <span>平台价 {marketPriceText}</span>
                        <span>供货价 {salesPriceText}</span>
                        <span>过单价 {product.passThroughPrice != null ? money(product.passThroughPrice) : "未录入"}</span>
                        {(can("product.manage") || can("profit.view")) && <span>成本价 {money(product.costPrice)}</span>}
                      </>
                    ) : (
                      <>
                        <span>服务价 {salesPriceText}</span>
                        {(can("product.manage") || can("profit.view")) && <span>成本价 {money(product.costPrice)}</span>}
                      </>
                    )}
                  </div>
                </div>
                <div className="card-actions">
                  {can("product.manage") && <button className="copy-link" onClick={() => openEditProductModal(product)}>编辑</button>}
                  {product.kind === "实体商品" && can("product.manage") && <button className="copy-link" onClick={() => openSupplierBindModal(product)}>绑定供应商</button>}
                  {can("product.manage") && <button className="copy-link danger-action" onClick={() => void deleteProduct(product)}>删除</button>}
                </div>
                {product.kind === "实体商品" && canViewChannelPrices && productPrices.length > 0 && (
                  <div className="channel-price-panel">
                    <div className="channel-price-head">
                      <strong>已绑定供应商</strong>
                    </div>
                    <div className="price-history">
                      {productPrices.map((price) => {
                        const supplier = data.organizations.find((org) => org.id === price.supplierOrgId);
                        return (
                          <span key={price.id}>
                            {supplier?.name} · {money(price.purchasePrice)} · {price.effectiveDate || "无日期"} · {price.note || "当前价"}
                            {can("product.manage") && <button className="copy-link danger-action" onClick={() => void deleteChannelPrice(price, product)}>删除</button>}
                          </span>
                        );
                      })}
                    </div>
                  </div>
                )}
              </article>
            );
          })}
        </div>
        <Pagination {...visibleProductsPage} onPageChange={visibleProductsPage.setPage} />
      </div>
      {productModalKind && (
        <div className="modal-backdrop" role="presentation">
          <div className="modal product-create-modal" role="dialog" aria-modal="true" aria-label={editingProduct ? "编辑商品" : productModalKind === "实体商品" ? "新建实体商品" : "新建服务类商品"}>
            <div className="modal-head">
              <div>
                <h2>{editingProduct ? `编辑${productModalKind === "实体商品" ? "实体商品" : "服务类商品"}` : productModalKind === "实体商品" ? "新建实体商品" : "新建服务类商品"}</h2>
                <p>{productModalKind === "实体商品" ? "维护商品名称与价格；供应商请在列表中单独绑定。" : "维护服务档案、服务价格及适用平台。"}</p>
              </div>
              <button className="icon-button" onClick={closeProductModal} aria-label="关闭">×</button>
            </div>
            <div className="product-form product-modal-form">
              <input value={form.code} onChange={(event) => setForm({ ...form, code: event.target.value })} placeholder="商品编码（不填则自动生成）" />
              <input value={form.name} onChange={(event) => setForm({ ...form, name: event.target.value })} placeholder={productModalKind === "实体商品" ? "商品名称" : "服务名称"} />
              <select value={form.category} onChange={(event) => setForm({ ...form, category: event.target.value })}>
                {(productModalKind === "实体商品"
                  ? ["空调", "空气净化器", "净水器", "文具", "其他"]
                  : ["平台服务", "框架服务", "其他服务"]
                ).map((item) => <option key={item}>{item}</option>)}
              </select>
              {productModalKind === "实体商品" ? (
                <>
                  <input type="number" value={form.frameworkPrice} onChange={(event) => setForm({ ...form, frameworkPrice: event.target.value })} placeholder="平台价" />
                  <input type="number" value={form.quotePrice} onChange={(event) => setForm({ ...form, quotePrice: event.target.value, passThroughPrice: form.passThroughPrice || (event.target.value ? String(Math.round(Number(event.target.value) * 1.1 * 100) / 100) : "") })} placeholder="供货价" />
                  <input type="number" value={form.passThroughPrice} onChange={(event) => setForm({ ...form, passThroughPrice: event.target.value })} placeholder="过单价（默认供货价 +10%）" />
                  <input type="number" value={form.costPrice} onChange={(event) => setForm({ ...form, costPrice: event.target.value })} placeholder="成本价" />
                </>
              ) : (
                <>
                  <input type="number" min="0" value={form.quotePrice} onChange={(event) => setForm({ ...form, quotePrice: event.target.value })} placeholder="服务价格" />
                  <div className="role-checkboxes product-platform-options">
                    {optionValues(data, "platform", ["泉E采", "青慧采", "齐鲁云采", "政采云", "公采云", "国铁", "其他"]).map((platform) => (
                      <label key={platform}>
                        <input type="checkbox" checked={form.platformIds.includes(platform)} onChange={(event) => setForm({ ...form, platformIds: event.target.checked ? [...form.platformIds, platform] : form.platformIds.filter((item) => item !== platform) })} />
                        {platform}
                      </label>
                    ))}
                  </div>
                </>
              )}
              <textarea value={form.orderInfo} onChange={(event) => setForm({ ...form, orderInfo: event.target.value })} placeholder="下单信息/链接/备注" />
            </div>
            <div className="modal-actions">
              <button className="ghost" onClick={closeProductModal}>取消</button>
              <button className="primary" onClick={() => void saveProduct()}><Package size={16} />{editingProduct ? "保存修改" : `保存${productModalKind === "实体商品" ? "实体商品" : "服务类商品"}`}</button>
            </div>
          </div>
        </div>
      )}
      {priceProduct && (
        <div className="modal-backdrop" role="presentation">
          <div className="modal product-bind-supplier-modal" role="dialog" aria-modal="true" aria-label="绑定供应商">
            <div className="modal-head">
              <div>
                <h2>绑定供应商</h2>
                <p>{priceProduct.name}</p>
              </div>
              <button className="icon-button" onClick={() => setPriceProductId("")} aria-label="关闭">×</button>
            </div>
            <div className="channel-price-panel">
              <div className="channel-price-head"><strong>当前绑定关系</strong></div>
              <div className="price-history">
                {priceProductBindings.length === 0 && <span>暂无绑定供应商</span>}
                {priceProductBindings.map((price) => {
                  const supplier = data.organizations.find((org) => org.id === price.supplierOrgId);
                  return (
                    <span key={price.id}>
                      {supplier?.name || "未知供应商"} · 进货价 {money(price.purchasePrice)} · {price.effectiveDate || "无日期"} · {price.note || "当前价"}
                      {can("product.manage") && <button className="copy-link danger-action" onClick={() => void deleteChannelPrice(price, priceProduct)}>删除</button>}
                    </span>
                  );
                })}
              </div>
            </div>
            <div className="form-grid">
              <select value={priceDraft.supplierOrgId} onChange={(event) => setPriceDraft({ ...priceDraft, supplierOrgId: event.target.value })}>
                <option value="">选择供应商</option>
                {suppliers.map((supplier) => <option value={supplier.id} key={supplier.id}>{supplier.name}</option>)}
              </select>
              <input value={priceDraft.purchasePrice} onChange={(event) => setPriceDraft({ ...priceDraft, purchasePrice: event.target.value })} placeholder="绑定进货价" />
              <DateTimeField value={priceDraft.effectiveDate} onChange={(effectiveDate) => setPriceDraft({ ...priceDraft, effectiveDate })} ariaLabel="生效日期" placeholder="生效日期" />
              <input value={priceDraft.note} onChange={(event) => setPriceDraft({ ...priceDraft, note: event.target.value })} placeholder="备注/版本" />
            </div>
            <div className="modal-actions">
              <button className="ghost" onClick={() => setPriceProductId("")}>关闭</button>
              <button className="primary" onClick={() => void addChannelPrice()}>保存绑定</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

function PlatformAccounts({
  data,
  applyData,
  onNotice,
  can,
  operatorName,
}: {
  data: AppData;
  applyData: (data: AppData) => void;
  onNotice: (notice: { type: "success" | "error"; message: string }) => void;
  can: CanAccess;
  operatorName: string;
}) {
  const customers = data.organizations.filter((org) => isCustomerOrganization(org));
  const [platformFilter, setPlatformFilter] = useState<PlatformAccount["platform"] | "全部">("全部");
  const [customerSearch, setCustomerSearch] = useState("");
  const [expandedAccountId, setExpandedAccountId] = useState("");
  const [copyTip, setCopyTip] = useState("");
  const [showAccountModal, setShowAccountModal] = useState(false);
  const [editingAccountId, setEditingAccountId] = useState("");
  const [editingCustomerName, setEditingCustomerName] = useState("");
  const [savingAccount, setSavingAccount] = useState(false);
  const [form, setForm] = useState({
    projectId: "",
    customerOrgId: "",
    platform: "泉E采" as PlatformAccount["platform"],
    accountName: "",
    accountPasswordMasked: "",
    merchantId: "",
    shopId: "",
    shopName: "",
    cloudAccount: "",
    domain: "",
    icpRecordNo: "",
    currentStatus: "已付款待办理",
    salesOwner: "当前用户",
    serviceYears: "1",
    note: "",
  });
  const rowsPage = useServerPagedList<PlatformAccount>({
    collection: "platformAccounts",
    search: customerSearch,
    filters: { platform: platformFilter === "全部" ? undefined : platformFilter },
    pageSize: 10,
    refreshKey: data.platformAccounts,
  });
  const platformOptions = optionValues(data, "platform", ["泉E采", "青慧采", "齐鲁云采", "政采云", "公采云", "国铁", "其他"]) as PlatformAccount["platform"][];
  const platformCustomerOptions = sortByCreatedDesc(customers).map((customer) => ({
    value: customer.id,
    label: customer.name,
    detail: [customer.unifiedCreditCode, customer.legalPerson, customer.phone].filter(Boolean).join(" / "),
  }));

  async function copyText(text: string | undefined, label: string, account?: PlatformAccount, field?: PlatformSensitiveField) {
    if (account && field) {
      try {
        text = await fetchPlatformSensitiveValue(account.id, field);
      } catch {
        setCopyTip(`${label}读取失败，请重新登录后重试`);
        return;
      }
    }
    if (!text) {
      setCopyTip(`${label}未录入`);
      return;
    }
    try {
      await writeClipboardText(text);
      void auditSensitiveAccess({ targetName: account?.accountName || account?.platform, fieldLabel: label, platform: account?.platform, source: "平台账号管理" });
      setCopyTip(`已复制${label}`);
    } catch {
      setCopyTip(`${label}复制失败，请检查浏览器剪贴板权限`);
    }
  }

  async function copyPassword(text: string | undefined, label: string, account?: PlatformAccount, field?: PlatformSensitiveField) {
    if (account && field) {
      try {
        text = await fetchPlatformSensitiveValue(account.id, field);
      } catch {
        setCopyTip(`${label}读取失败，请重新登录后重试`);
        return;
      }
    }
    if (!text) {
      setCopyTip(`${label}未录入`);
      return;
    }
    try {
      await writeClipboardText(text);
      void auditSensitiveAccess({ targetName: account?.accountName || account?.platform, fieldLabel: label, platform: account?.platform, source: "平台账号管理" });
      setCopyTip(`已复制${label}`);
    } catch {
      setCopyTip(`${label}复制失败，请检查浏览器剪贴板权限`);
    }
  }

  function masked(value?: string) {
    if (!value) return "未录入";
    if (value.length <= 4) return "****";
    return `${value.slice(0, 2)}***${value.slice(-2)}`;
  }

  async function addAccount() {
    if (savingAccount) return;
    if (!form.customerOrgId || !form.platform || !form.accountName.trim() || !form.accountPasswordMasked) {
      setCopyTip("请完整填写客户、平台、账号和密码。");
      return;
    }
    const customer = data.organizations.find((org) => org.id === form.customerOrgId);
    const existingAccount = (editingAccountId
      ? data.platformAccounts.find((item) => item.id === editingAccountId) ?? rowsPage.items.find((item) => item.id === editingAccountId)
      : undefined);
    const now = new Date().toISOString();
    const account: PlatformAccount = {
      ...existingAccount,
      id: editingAccountId || createId("pa"),
      createdAt: existingAccount?.createdAt ?? existingAccount?.updatedAt ?? now,
      updatedAt: now,
      projectId: form.projectId || existingAccount?.projectId,
      customerOrgId: form.customerOrgId,
      platform: form.platform,
      accountName: form.accountName.trim() || undefined,
      accountPasswordMasked: form.accountPasswordMasked || undefined,
      merchantId: form.merchantId.trim() || undefined,
      shopId: form.shopId.trim() || undefined,
      shopName: form.shopName.trim() || undefined,
      cloudAccount: form.cloudAccount || existingAccount?.cloudAccount,
      domain: form.domain || existingAccount?.domain,
      icpRecordNo: form.icpRecordNo || existingAccount?.icpRecordNo,
      licenseDisplayStatus: existingAccount?.licenseDisplayStatus ?? "未处理",
      publicSecurityStatus: existingAccount?.publicSecurityStatus ?? "未处理",
      backendTemplateStatus: existingAccount?.backendTemplateStatus ?? "未录入",
      caStatus: existingAccount?.caStatus ?? "未办理",
      serviceYears: Number(form.serviceYears) || existingAccount?.serviceYears || 1,
      salesOwner: form.salesOwner || existingAccount?.salesOwner,
      currentStatus: form.currentStatus || existingAccount?.currentStatus || "已付款待办理",
      note: form.note || existingAccount?.note,
    };
    const log = platformAccountLog(existingAccount, account, customer?.name || editingCustomerName);
    setSavingAccount(true);
    try {
      const saved = editingAccountId
        ? await patchCollectionItem<PlatformAccount>("platformAccounts", editingAccountId, account)
        : await createCollectionItem<PlatformAccount>("platformAccounts", account);
      const savedLog = await createCollectionItem<OperationLog>("operationLogs", {
        id: createId("log"),
        createdAt: today(),
        action: log.action,
        targetType: "系统",
        targetName: log.targetName,
        operator: operatorName,
        detail: log.detail,
      });
      const nextAccounts = data.platformAccounts.some((item) => item.id === saved.id)
        ? data.platformAccounts.map((item) => (item.id === saved.id ? { ...item, ...saved } : item))
        : [saved, ...data.platformAccounts];
      applyData({
        ...data,
        platformAccounts: nextAccounts,
        operationLogs: [savedLog, ...data.operationLogs],
      });
      onNotice({ type: "success", message: `${log.action}成功` });
      setForm({ ...form, accountName: "", accountPasswordMasked: "", merchantId: "", shopId: "", shopName: "", cloudAccount: "", domain: "", icpRecordNo: "", note: "" });
      setEditingAccountId("");
      setEditingCustomerName("");
      setShowAccountModal(false);
    } catch (error) {
      const message = error instanceof Error ? error.message : "保存失败，请稍后重试";
      setCopyTip(message);
      onNotice({ type: "error", message });
    } finally {
      setSavingAccount(false);
    }
  }

  function openNewAccountModal() {
    setEditingAccountId("");
    setEditingCustomerName("");
    setForm({
      projectId: "",
      customerOrgId: "",
      platform: "泉E采",
      accountName: "",
      accountPasswordMasked: "",
      merchantId: "",
      shopId: "",
      shopName: "",
      cloudAccount: "",
      domain: "",
      icpRecordNo: "",
      currentStatus: "已付款待办理",
      salesOwner: "当前用户",
      serviceYears: "1",
      note: "",
    });
    setShowAccountModal(true);
  }

  function editAccount(account: PlatformAccount, customerName = "") {
    setEditingAccountId(account.id);
    setEditingCustomerName(customerName);
    setForm({
      projectId: account.projectId ?? "",
      customerOrgId: account.customerOrgId,
      platform: account.platform,
      accountName: account.accountName ?? "",
      accountPasswordMasked: account.accountPasswordMasked ?? "",
      merchantId: account.merchantId ?? "",
      shopId: account.shopId ?? "",
      shopName: account.shopName ?? "",
      cloudAccount: account.cloudAccount ?? "",
      domain: account.domain ?? "",
      icpRecordNo: account.icpRecordNo ?? "",
      currentStatus: account.currentStatus,
      salesOwner: account.salesOwner ?? "当前用户",
      serviceYears: String(account.serviceYears ?? 1),
      note: account.note ?? "",
    });
    setShowAccountModal(true);
  }

  async function deleteAccount(account: PlatformAccount) {
    const customer = data.organizations.find((org) => org.id === account.customerOrgId);
    try {
      await deleteCollectionItem("platformAccounts", account.id);
      const savedLog = await createCollectionItem<OperationLog>("operationLogs", {
        id: createId("log"),
        createdAt: today(),
        action: "删除平台账号",
        targetType: "系统",
        targetName: customer?.name ?? account.platform,
        operator: operatorName,
        detail: `删除 ${account.platform} 账号记录`,
      });
      applyData({
        ...data,
        platformAccounts: data.platformAccounts.filter((item) => item.id !== account.id),
        operationLogs: [savedLog, ...data.operationLogs],
      });
      onNotice({ type: "success", message: "删除平台账号成功" });
    } catch (error) {
      onNotice({ type: "error", message: error instanceof Error ? error.message : "删除失败，请稍后重试" });
    }
  }

  return (
    <div className="stack">
      <div className="panel">
        <div className="panel-title action-title">
          <div>
            <h2>平台账号台账</h2>
            <p>维护客户入驻平台账号、域名备案、亮照、公安备案、后台模板和 CA 办理进度。</p>
          </div>
          {can("platformAccount.manage") && (
            <button className="primary" onClick={openNewAccountModal}><FileScan size={16} />新增平台账号</button>
          )}
        </div>
        {copyTip && <div className="copy-tip">{copyTip}</div>}
        {rowsPage.error && <div className="form-error">{rowsPage.error}</div>}
        <div className="platform-account-toolbar">
          <div className="segmented">
            {(["全部", ...platformOptions] as Array<PlatformAccount["platform"] | "全部">).map((item) => (
              <button key={item} className={platformFilter === item ? "active" : ""} onClick={() => setPlatformFilter(item)}>{item}</button>
            ))}
          </div>
          <SearchField
            value={customerSearch}
            onChange={setCustomerSearch}
            placeholder="按客户名称搜索"
            ariaLabel="按客户名称搜索平台账号"
          />
        </div>
        <div className="table platform-account-list">
          <div className="table-row platform-table head"><span>客户</span><span>平台</span><span>账号</span><span>密码</span><span>商家ID</span><span>店铺ID</span><span>店铺名称</span><span>创建/更新</span><span>操作</span></div>
          {rowsPage.items.map((account) => {
            const customer = data.organizations.find((org) => org.id === account.customerOrgId);
            const customerName = customer?.name ?? "";
            const expanded = expandedAccountId === account.id;
            const customerAddress = [customer?.city, customer?.district, customer?.address].filter(Boolean).join("");
            return (
              <div className={`platform-account-block${expanded ? " is-expanded" : ""}`} key={account.id}>
                <div className="table-row platform-table">
                  <span className="platform-customer-cell">
                    {customerName ? (
                      <CopyableLine
                        text={customerName}
                        label="客户名称"
                        onOpen={() => setExpandedAccountId(expanded ? "" : account.id)}
                      >
                        <span className="platform-customer-name">
                          <ChevronDown size={14} className={`platform-expand-icon${expanded ? " is-open" : ""}`} aria-hidden />
                          <strong>{customerName}</strong>
                        </span>
                      </CopyableLine>
                    ) : "未知客户"}
                  </span>
                  <span>{account.platform}</span>
                  <span>
                    <button className="copy-link" onClick={() => void copyText(account.accountName, "平台账号", account, "accountName")}>{masked(account.accountName)}</button>
                  </span>
                  <span>
                    <button className="copy-secret" onClick={() => void copyPassword(account.accountPasswordMasked, "平台密码", account, "accountPasswordMasked")}>{masked(account.accountPasswordMasked)}</button>
                  </span>
                  <span>
                    {account.merchantId ? (
                      <CopyableLine text={account.merchantId} label="商家ID">
                        {account.merchantId}
                      </CopyableLine>
                    ) : "未录入"}
                  </span>
                  <span>
                    {account.shopId ? (
                      <CopyableLine text={account.shopId} label="店铺ID">
                        {account.shopId}
                      </CopyableLine>
                    ) : "未录入"}
                  </span>
                  <span>
                    {account.shopName ? (
                      <CopyableLine text={account.shopName} label="店铺名称">
                        {account.shopName}
                      </CopyableLine>
                    ) : "未录入"}
                  </span>
                  <span>{formatDateTimeValue(account.createdAt)}<em>更新 {formatDateTimeValue(account.updatedAt)}</em></span>
                  <span className="option-actions">{can("platformAccount.manage") && <>
                    <button className="copy-link" onClick={() => editAccount(account, customerName)}>编辑</button>
                    <button className="copy-link danger-action" onClick={() => void deleteAccount(account)}>删除</button>
                  </>}</span>
                </div>
                {expanded && (
                  <div className="platform-customer-detail" aria-label={`${customerName || "客户"}详细信息`}>
                    {customer ? (
                      <div className="platform-customer-detail-grid">
                        <div className="platform-customer-field">
                          <span>统一社会信用代码</span>
                          {customer.unifiedCreditCode ? (
                            <CopyableLine text={customer.unifiedCreditCode} label="统一社会信用代码">
                              <strong>{customer.unifiedCreditCode}</strong>
                            </CopyableLine>
                          ) : <strong>未录入</strong>}
                        </div>
                        <div className="platform-customer-field">
                          <span>联系电话</span>
                          {customer.phone ? (
                            <CopyableLine text={customer.phone} label="联系电话">
                              <strong>{customer.phone}</strong>
                            </CopyableLine>
                          ) : <strong>未录入</strong>}
                        </div>
                        <div className="platform-customer-field">
                          <span>法人姓名</span>
                          {customer.legalPerson ? (
                            <CopyableLine text={customer.legalPerson} label="法人姓名">
                              <strong>{customer.legalPerson}</strong>
                            </CopyableLine>
                          ) : <strong>未录入</strong>}
                        </div>
                        <div className="platform-customer-field">
                          <span>邮箱</span>
                          {customer.email ? (
                            <CopyableLine text={customer.email} label="邮箱">
                              <strong>{customer.email}</strong>
                            </CopyableLine>
                          ) : <strong>未录入</strong>}
                        </div>
                        <div className="platform-customer-field span-2">
                          <span>地址</span>
                          {customerAddress ? (
                            <CopyableLine text={customerAddress} label="地址">
                              <strong>{customerAddress}</strong>
                            </CopyableLine>
                          ) : <strong>未录入</strong>}
                        </div>
                        <div className="platform-customer-field">
                          <span>实体类型</span>
                          <strong>{customer.entityType || "未录入"}</strong>
                        </div>
                        <div className="platform-customer-field">
                          <span>纳税人类型</span>
                          <strong>{customer.taxpayerType || "未设置"}</strong>
                        </div>
                      </div>
                    ) : (
                      <p className="platform-customer-detail-empty">未找到关联客户资料</p>
                    )}
                  </div>
                )}
              </div>
            );
          })}
        </div>
        <Pagination {...rowsPage} onPageChange={rowsPage.setPage} />
      </div>
      {showAccountModal && (
        <div className="modal-backdrop" role="presentation">
          <div className="modal platform-account-modal" role="dialog" aria-modal="true" aria-label={editingAccountId ? "编辑平台账号" : "新增平台账号"}>
            <div className="modal-head">
              <div><h2>{editingAccountId ? "编辑平台账号" : "新增平台账号"}</h2><p>选择企业/单位和平台后录入账号密码。</p></div>
              <button className="icon-button" onClick={() => setShowAccountModal(false)} aria-label="关闭">×</button>
            </div>
            <div className="form-grid platform-account-form">
              <label className="field span-12"><span>企业/单位</span>
                <SearchableSelect value={form.customerOrgId} options={platformCustomerOptions} onChange={(value) => setForm({ ...form, customerOrgId: value })} placeholder="输入名称、信用代码或联系人搜索" ariaLabel="搜索并选择企业或单位" />
              </label>
              <label className="field span-12"><span>平台</span><select value={form.platform} onChange={(event) => setForm({ ...form, platform: event.target.value as PlatformAccount["platform"] })}>
                {platformOptions.map((item) => <option key={item}>{item}</option>)}
              </select></label>
              <label className="field span-12"><span>账号</span><input value={form.accountName} onChange={(event) => setForm({ ...form, accountName: event.target.value })} placeholder="请输入账号" /></label>
              <label className="field span-12"><span>密码</span><input type="text" value={form.accountPasswordMasked} onChange={(event) => setForm({ ...form, accountPasswordMasked: event.target.value })} placeholder="请输入密码" autoComplete="off" /></label>
              <label className="field span-12"><span>商家ID（可选）</span><input value={form.merchantId} onChange={(event) => setForm({ ...form, merchantId: event.target.value })} placeholder="请输入商家ID" /></label>
              <label className="field span-12"><span>店铺ID（可选）</span><input value={form.shopId} onChange={(event) => setForm({ ...form, shopId: event.target.value })} placeholder="请输入店铺ID" /></label>
              <label className="field span-12"><span>店铺名称（可选）</span><input value={form.shopName} onChange={(event) => setForm({ ...form, shopName: event.target.value })} placeholder="请输入店铺名称" /></label>
            </div>
            <div className="modal-actions">
              <button className="ghost" onClick={() => setShowAccountModal(false)} disabled={savingAccount}>取消</button>
              <button className="primary" disabled={savingAccount} onClick={() => void addAccount()}><FileScan size={16} />{savingAccount ? "保存中..." : editingAccountId ? "保存修改" : "保存账号"}</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

function TrademarkCertificates({
  data,
  applyData,
  onNotice,
  can,
  operatorName,
}: {
  data: AppData;
  applyData: (data: AppData) => void;
  onNotice: (notice: { type: "success" | "error"; message: string }) => void;
  can: CanAccess;
  operatorName: string;
}) {
  type AttachmentDraft = {
    key: string;
    fileId?: string;
    fileName: string;
    file?: File;
  };
  const emptyForm = {
    registrationNo: "",
    registrant: "",
    registrantAddress: "",
    internationalClass: "",
    approvedGoods: "",
    registrationDate: "",
    validUntil: "",
    trademarkName: "",
    note: "",
  };
  const [search, setSearch] = useState("");
  const [showModal, setShowModal] = useState(false);
  const [editingId, setEditingId] = useState("");
  const [saving, setSaving] = useState(false);
  const [form, setForm] = useState(emptyForm);
  const [originalFile, setOriginalFile] = useState<File | null>(null);
  const [originalFileName, setOriginalFileName] = useState("");
  const [existingFileId, setExistingFileId] = useState("");
  const [showOriginalPreview, setShowOriginalPreview] = useState(false);
  const [ocrStatus, setOcrStatus] = useState("");
  const [attachments, setAttachments] = useState<AttachmentDraft[]>([]);
  const [attachmentListFor, setAttachmentListFor] = useState<TrademarkCertificate | null>(null);
  const rowsPage = useServerPagedList<TrademarkCertificate>({
    collection: "trademarkCertificates",
    search,
    pageSize: 10,
    refreshKey: data.trademarkCertificates,
  });
  const canManage = can("trademarkCertificate.manage");
  const canViewOriginal = can("trademarkCertificate.view");
  const comparingOriginal = Boolean(originalFile && showOriginalPreview);

  function resetModal() {
    setEditingId("");
    setForm(emptyForm);
    setOriginalFile(null);
    setOriginalFileName("");
    setExistingFileId("");
    setShowOriginalPreview(false);
    setOcrStatus("");
    setAttachments([]);
  }

  function openCreate() {
    resetModal();
    setShowModal(true);
  }

  function openEdit(item: TrademarkCertificate) {
    setEditingId(item.id);
    setForm({
      registrationNo: item.registrationNo || "",
      registrant: item.registrant || "",
      registrantAddress: item.registrantAddress || "",
      internationalClass: item.internationalClass || "",
      approvedGoods: item.approvedGoods || "",
      registrationDate: item.registrationDate || "",
      validUntil: item.validUntil || "",
      trademarkName: item.trademarkName || "",
      note: item.note || "",
    });
    setOriginalFile(null);
    setOriginalFileName(item.fileName || "");
    setExistingFileId(item.fileId || "");
    setShowOriginalPreview(false);
    setOcrStatus("");
    setAttachments(
      (item.attachments || []).map((itemAttachment) => ({
        key: itemAttachment.id || itemAttachment.fileId,
        fileId: itemAttachment.fileId,
        fileName: itemAttachment.fileName,
      })),
    );
    setShowModal(true);
  }

  function selectOriginalFile(file: File | undefined) {
    setOriginalFile(file ?? null);
    setOriginalFileName(file?.name ?? (existingFileId ? originalFileName : ""));
    setShowOriginalPreview(Boolean(file));
    setOcrStatus("");
  }

  function addAttachmentFile(file: File | undefined) {
    if (!file) return;
    setAttachments((current) => [
      ...current,
      { key: createId("tma"), fileName: file.name, file },
    ]);
  }

  async function removeAttachment(draft: AttachmentDraft) {
    if (draft.fileId && canManage) {
      try {
        await deleteBusinessDocument(draft.fileId);
      } catch (error) {
        onNotice({ type: "error", message: error instanceof Error ? error.message : "删除附件失败" });
        return;
      }
    }
    setAttachments((current) => current.filter((item) => item.key !== draft.key));
  }

  async function fillFromOcr() {
    if (!originalFile) {
      setOcrStatus("请先选择商标注册证图片或 PDF。");
      return;
    }
    setOcrStatus("正在识别商标注册证...");
    try {
      const formData = new FormData();
      formData.append("file", await prepareOcrUpload(originalFile));
      const response = await fetch(ocrServiceUrl("/api/ocr/trademark"), {
        method: "POST",
        body: formData,
      });
      if (!response.ok) {
        const errorText = await response.text();
        throw new Error(errorText || "商标注册证识别失败");
      }
      const result = await response.json();
      if (result.status !== "recognized" || !result.data) {
        setOcrStatus(result.message || "暂未识别到商标注册证字段。");
        return;
      }
      const parsed = result.data as {
        registration_no?: string;
        registrant?: string;
        registrant_address?: string;
        international_class?: string;
        approved_goods?: string;
        registration_date?: string;
        valid_until?: string;
        trademark_name?: string;
      };
      setForm((current) => ({
        ...current,
        registrationNo: parsed.registration_no || current.registrationNo,
        registrant: parsed.registrant || current.registrant,
        registrantAddress: parsed.registrant_address || current.registrantAddress,
        internationalClass: parsed.international_class || current.internationalClass,
        approvedGoods: parsed.approved_goods || current.approvedGoods,
        registrationDate: parsed.registration_date || current.registrationDate,
        validUntil: parsed.valid_until || current.validUntil,
        trademarkName: parsed.trademark_name || current.trademarkName,
      }));
      const missingName = !(parsed.trademark_name || "").trim();
      setOcrStatus(
        missingName
          ? `${result.message || "商标注册证识别完成。"}商标名称未识别到，请手动录入。`
          : (result.message || "商标注册证识别完成。"),
      );
    } catch (error) {
      setOcrStatus(error instanceof Error ? error.message : "商标注册证识别失败");
    }
  }

  async function saveCertificate() {
    if (saving) return;
    const registrationNo = form.registrationNo.trim().replace(/\s+/g, "").toUpperCase();
    const registrant = form.registrant.trim();
    if (!registrationNo) {
      window.alert("请填写商标注册号。");
      return;
    }
    if (!registrant) {
      window.alert("请填写注册人。");
      return;
    }
    const duplicate = data.trademarkCertificates.find(
      (item) => item.id !== editingId && item.registrationNo.replace(/\s+/g, "").toUpperCase() === registrationNo,
    );
    if (duplicate) {
      window.alert(`商标注册号「${registrationNo}」已存在，请勿重复添加。`);
      return;
    }
    const now = new Date().toISOString();
    const existing = editingId
      ? data.trademarkCertificates.find((item) => item.id === editingId) ?? rowsPage.items.find((item) => item.id === editingId)
      : undefined;
    const certificateId = editingId || createId("tm");
    setSaving(true);
    try {
      let fileId = existing?.fileId;
      let fileName = existing?.fileName;
      if (originalFile) {
        const savedFile = await uploadBusinessDocument(originalFile, "trademark_certificate", certificateId);
        fileId = savedFile.id;
        fileName = savedFile.fileName;
      }
      const savedAttachments: TrademarkAttachment[] = [];
      for (const draft of attachments) {
        if (draft.fileId && !draft.file) {
          savedAttachments.push({
            id: draft.key,
            fileId: draft.fileId,
            fileName: draft.fileName,
            uploadedAt: existing?.attachments?.find((item) => item.fileId === draft.fileId)?.uploadedAt || now,
          });
          continue;
        }
        if (!draft.file) continue;
        const uploaded = await uploadBusinessDocument(draft.file, "trademark_attachment", certificateId);
        savedAttachments.push({
          id: draft.key,
          fileId: uploaded.id,
          fileName: uploaded.fileName,
          uploadedAt: now,
        });
      }
      const payload: TrademarkCertificate = {
        ...existing,
        id: certificateId,
        registrationNo,
        registrant,
        registrantAddress: form.registrantAddress.trim(),
        internationalClass: form.internationalClass.trim(),
        approvedGoods: form.approvedGoods.trim() || undefined,
        registrationDate: form.registrationDate.trim(),
        validUntil: form.validUntil.trim(),
        trademarkName: form.trademarkName.trim() || undefined,
        note: form.note.trim() || undefined,
        fileId,
        fileName,
        attachments: savedAttachments,
        createdAt: existing?.createdAt ?? now,
        updatedAt: now,
      };
      const saved = editingId
        ? await patchCollectionItem<TrademarkCertificate>("trademarkCertificates", editingId, payload)
        : await createCollectionItem<TrademarkCertificate>("trademarkCertificates", payload);
      const action = editingId ? "编辑商标注册证" : "新增商标注册证";
      const savedLog = await createCollectionItem<OperationLog>("operationLogs", {
        id: createId("log"),
        createdAt: today(),
        action,
        targetType: "系统",
        targetName: saved.registrant || saved.registrationNo,
        operator: operatorName,
        detail: `注册号 ${saved.registrationNo}${saved.internationalClass ? ` / 国际分类 ${saved.internationalClass}` : ""}${savedAttachments.length ? ` / 附件 ${savedAttachments.length} 个` : ""}`,
      });
      const nextItems = data.trademarkCertificates.some((item) => item.id === saved.id)
        ? data.trademarkCertificates.map((item) => (item.id === saved.id ? { ...item, ...saved } : item))
        : [saved, ...data.trademarkCertificates];
      applyData({
        ...data,
        trademarkCertificates: nextItems,
        operationLogs: [savedLog, ...data.operationLogs],
      });
      onNotice({ type: "success", message: `${action}成功` });
      setShowModal(false);
      resetModal();
      void rowsPage.reload();
    } catch (error) {
      const message = error instanceof Error ? error.message : "保存失败，请稍后重试";
      setOcrStatus(message);
      onNotice({ type: "error", message });
    } finally {
      setSaving(false);
    }
  }

  async function deleteCertificate(item: TrademarkCertificate) {
    if (!window.confirm(`确定删除商标注册证「${item.registrationNo} / ${item.registrant}」吗？`)) return;
    try {
      await deleteCollectionItem("trademarkCertificates", item.id);
      const savedLog = await createCollectionItem<OperationLog>("operationLogs", {
        id: createId("log"),
        createdAt: today(),
        action: "删除商标注册证",
        targetType: "系统",
        targetName: item.registrant || item.registrationNo,
        operator: operatorName,
        detail: `删除注册号 ${item.registrationNo}`,
      });
      applyData({
        ...data,
        trademarkCertificates: data.trademarkCertificates.filter((row) => row.id !== item.id),
        operationLogs: [savedLog, ...data.operationLogs],
      });
      onNotice({ type: "success", message: "删除商标注册证成功" });
      void rowsPage.reload();
    } catch (error) {
      onNotice({ type: "error", message: error instanceof Error ? error.message : "删除失败，请稍后重试" });
    }
  }

  function validityText(item: TrademarkCertificate) {
    if (item.registrationDate && item.validUntil) return `${item.registrationDate} ~ ${item.validUntil}`;
    return item.registrationDate || item.validUntil || "未录入";
  }

  const attachmentListItems = attachmentListFor?.attachments || [];

  return (
    <div className="stack">
      <div className="panel">
        <div className="panel-title action-title">
          <div>
            <h2>商标管理</h2>
            <p>维护商标注册证资料，支持上传原件 OCR 回填、判重、附件与原件查看。</p>
          </div>
          {canManage && (
            <button className="primary" onClick={openCreate}><Stamp size={16} />新增商标注册证</button>
          )}
        </div>
        {rowsPage.error && <div className="form-error">{rowsPage.error}</div>}
        <div className="platform-account-toolbar">
          <SearchField
            value={search}
            onChange={setSearch}
            placeholder="搜索商标名称、注册人、注册号、地址、分类号"
            ariaLabel="搜索商标注册证"
          />
        </div>
        <div className="table">
          <div className="table-row trademark-table head">
            <span>基本信息</span>
            <span>注册人 / 地址</span>
            <span>有效期起止</span>
            <span>服务项目</span>
            <span>操作</span>
          </div>
          {rowsPage.items.map((item) => {
            const attachmentCount = item.attachments?.length || 0;
            return (
              <div className="table-row trademark-table" key={item.id}>
                <span className="trademark-main-cell">
                  <CopyableLine text={item.trademarkName || ""} label="商品名称">
                    <strong>{item.trademarkName || "未录入"}</strong>
                  </CopyableLine>
                  <CopyableLine text={item.registrationNo} label="商标注册号" className="is-secondary">
                    <em>注册号 {item.registrationNo || "未录入"}</em>
                  </CopyableLine>
                  <em>国际分类 {item.internationalClass || "未录入"}</em>
                </span>
                <span className="trademark-main-cell">
                  <CopyableLine text={item.registrant} label="注册人">
                    <strong>{item.registrant || "未录入"}</strong>
                  </CopyableLine>
                  <CopyableLine text={item.registrantAddress} label="注册人地址" className="is-secondary">
                    <em>{item.registrantAddress || "暂无地址"}</em>
                  </CopyableLine>
                </span>
                <span>{validityText(item)}</span>
                <span className="trademark-goods-cell">{item.approvedGoods || "未录入"}</span>
                <span className="option-actions">
                  {canManage && <button className="copy-link" type="button" onClick={() => openEdit(item)}>编辑</button>}
                  {canManage && <button className="copy-link danger-action" type="button" onClick={() => void deleteCertificate(item)}>删除</button>}
                  {canViewOriginal && item.fileId && (
                    <button className="copy-link" type="button" onClick={() => openBusinessDocument(item.fileId)}>查看原件</button>
                  )}
                  {canViewOriginal && (
                    <button
                      className="copy-link"
                      type="button"
                      onClick={() => setAttachmentListFor(item)}
                      disabled={attachmentCount === 0}
                      title={attachmentCount === 0 ? "暂无附件" : `查看 ${attachmentCount} 个附件`}
                    >
                      附件{attachmentCount > 0 ? `(${attachmentCount})` : ""}
                    </button>
                  )}
                </span>
              </div>
            );
          })}
          {rowsPage.items.length === 0 && <div className="table-empty">暂无商标注册证</div>}
        </div>
        <Pagination {...rowsPage} onPageChange={rowsPage.setPage} />
      </div>
      {showModal && (
        <div className="modal-backdrop" role="presentation">
          <div
            className={`modal trademark-modal${comparingOriginal ? " is-comparing" : ""}`}
            role="dialog"
            aria-modal="true"
            aria-label={editingId ? "编辑商标注册证" : "新增商标注册证"}
          >
            <div className="trademark-form-pane">
              <div className="trademark-form-scroll">
              <div className="modal-head">
                <div>
                  <h2>{editingId ? "编辑商标注册证" : "新增商标注册证"}</h2>
                  <p>可上传图片或 PDF 原件识别填充，并可附带转让等相关附件。</p>
                </div>
                <button className="icon-button" onClick={() => { setShowModal(false); resetModal(); }} aria-label="关闭">×</button>
              </div>
              <div className="upload-strip">
                <FilePicker
                  accept="image/*,.pdf,application/pdf"
                  fileName={originalFileName}
                  placeholder="未选择商标注册证原件"
                  buttonLabel="选择原件"
                  ariaLabel="选择商标注册证原件"
                  onFile={(file) => selectOriginalFile(file)}
                />
                {originalFile && !showOriginalPreview && (
                  <button className="license-preview-trigger" type="button" onClick={() => setShowOriginalPreview(true)}>
                    <FileText size={15} />查看原件
                  </button>
                )}
                {canManage && <button className="ghost" type="button" onClick={() => void fillFromOcr()}><FileScan size={16} />OCR 识别并填充</button>}
                {canViewOriginal && existingFileId && !originalFile && (
                  <button className="ghost" type="button" onClick={() => openBusinessDocument(existingFileId)}><FileText size={16} />查看已存原件</button>
                )}
              </div>
              {ocrStatus && <div className="copy-tip">{ocrStatus}</div>}
              <div className="form-grid trademark-form">
                <label className="field span-6"><span>商标注册号</span><input value={form.registrationNo} onChange={(event) => setForm({ ...form, registrationNo: event.target.value })} placeholder="商标注册号" /></label>
                <label className="field span-6"><span>国际分类号</span><input value={form.internationalClass} onChange={(event) => setForm({ ...form, internationalClass: event.target.value })} placeholder="如 21" /></label>
                <label className="field span-12">
                  <span>商标名称（商品名称）</span>
                  <input
                    value={form.trademarkName}
                    onChange={(event) => setForm({ ...form, trademarkName: event.target.value })}
                    placeholder="如识别失败请手动录入，例：鲁奇亚 Luqiya"
                  />
                </label>
                <label className="field span-12"><span>注册人</span><input value={form.registrant} onChange={(event) => setForm({ ...form, registrant: event.target.value })} placeholder="注册人名称" /></label>
                <label className="field span-12"><span>注册人地址</span><input value={form.registrantAddress} onChange={(event) => setForm({ ...form, registrantAddress: event.target.value })} placeholder="注册人地址" /></label>
                <label className="field span-6">
                  <span>有效期起（注册日期）</span>
                  <DateTimeField
                    mode="date"
                    format="iso"
                    value={form.registrationDate}
                    onChange={(value) => setForm({ ...form, registrationDate: value })}
                    placeholder="yyyy-mm-dd"
                    ariaLabel="有效期起"
                  />
                </label>
                <label className="field span-6">
                  <span>有效期至</span>
                  <DateTimeField
                    mode="date"
                    format="iso"
                    value={form.validUntil}
                    onChange={(value) => setForm({ ...form, validUntil: value })}
                    placeholder="yyyy-mm-dd"
                    ariaLabel="有效期至"
                  />
                </label>
                <label className="field span-12"><span>核定使用商品/服务项目</span><textarea value={form.approvedGoods} onChange={(event) => setForm({ ...form, approvedGoods: event.target.value })} placeholder="核定使用商品/服务项目" rows={3} /></label>
                <label className="field span-12"><span>备注</span><input value={form.note} onChange={(event) => setForm({ ...form, note: event.target.value })} placeholder="备注" /></label>
              </div>
              <div className="trademark-attachment-panel">
                <div className="trademark-attachment-head">
                  <div>
                    <strong>相关附件</strong>
                    <span>可上传转让证明、协议等 PDF / 图片附件</span>
                  </div>
                  {canManage && (
                    <FilePicker
                      accept="image/*,.pdf,application/pdf"
                      placeholder="未选择附件"
                      buttonLabel="添加附件"
                      ariaLabel="添加商标相关附件"
                      onFile={(file) => addAttachmentFile(file)}
                    />
                  )}
                </div>
                {attachments.length === 0 ? (
                  <div className="trademark-attachment-empty">暂无附件</div>
                ) : (
                  <ul className="trademark-attachment-list">
                    {attachments.map((draft) => (
                      <li key={draft.key}>
                        <button
                          type="button"
                          className="copy-link"
                          disabled={!draft.fileId || !canViewOriginal}
                          onClick={() => openBusinessDocument(draft.fileId)}
                          title={draft.fileId ? "查看附件" : "保存后可查看"}
                        >
                          <FileText size={14} />
                          {draft.fileName}
                          {!draft.fileId && <em>（待保存）</em>}
                        </button>
                        {canManage && (
                          <button type="button" className="copy-link danger-action" onClick={() => void removeAttachment(draft)}>移除</button>
                        )}
                      </li>
                    ))}
                  </ul>
                )}
              </div>
              </div>
              <div className="modal-actions">
                <button className="ghost" type="button" onClick={() => { setShowModal(false); resetModal(); }} disabled={saving}>取消</button>
                {canManage && <button className="primary" type="button" disabled={saving} onClick={() => void saveCertificate()}><Stamp size={16} />{saving ? "保存中..." : editingId ? "保存修改" : "保存"}</button>}
              </div>
            </div>
            {comparingOriginal && originalFile && (
              <LicenseDocumentView
                file={originalFile}
                onClose={() => setShowOriginalPreview(false)}
                hint="可与左侧表单对照核对"
              />
            )}
          </div>
        </div>
      )}
      {attachmentListFor && (
        <div className="modal-backdrop" role="presentation" onClick={() => setAttachmentListFor(null)}>
          <div
            className="modal trademark-attachment-modal"
            role="dialog"
            aria-modal="true"
            aria-label="商标注册证附件"
            onClick={(event) => event.stopPropagation()}
          >
            <div className="modal-head">
              <div>
                <h2>附件列表</h2>
                <p>{attachmentListFor.registrationNo} / {attachmentListFor.registrant}</p>
              </div>
              <button className="icon-button" type="button" onClick={() => setAttachmentListFor(null)} aria-label="关闭">×</button>
            </div>
            {attachmentListItems.length === 0 ? (
              <div className="trademark-attachment-empty">暂无附件</div>
            ) : (
              <ul className="trademark-attachment-list is-modal">
                {attachmentListItems.map((item) => (
                  <li key={item.id || item.fileId}>
                    <button
                      type="button"
                      className="copy-link"
                      onClick={() => openBusinessDocument(item.fileId)}
                    >
                      <FileText size={14} />
                      {item.fileName || "未命名附件"}
                    </button>
                  </li>
                ))}
              </ul>
            )}
            <div className="modal-actions">
              <button className="ghost" type="button" onClick={() => setAttachmentListFor(null)}>关闭</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

function WebsiteLeads({
  data,
  applyData,
  onNotice,
  currentUser,
}: {
  data: AppData;
  applyData: (data: AppData) => void;
  onNotice: (notice: { type: "success" | "error"; message: string }) => void;
  currentUser: User;
}) {
  const platformOptions = optionValues(data, "platform", ["泉E采", "齐鲁云采", "青慧采", "政采云", "公采云", "国铁", "其他"]) as WebsiteLead["platform"][];
  const leadStatusOptions = (() => {
    const values = optionValues(data, "website_lead_status", ["未跟进", "已跟进", "已成交", "放弃"]);
    const seen = new Set(values);
    const merged = [...values];
    for (const status of ["未跟进", "已跟进", "已成交", "放弃"]) {
      if (!seen.has(status)) merged.push(status);
    }
    return [...merged.filter((item) => item !== "放弃"), "放弃"] as WebsiteLead["status"][];
  })();
  const [form, setForm] = useState({
    companyName: "",
    phone: "",
    contactName: "",
    platform: "泉E采" as WebsiteLead["platform"],
    remark: "",
  });
  const [statusFilter, setStatusFilter] = useState<"全部" | WebsiteLead["status"]>("全部");
  const [keyword, setKeyword] = useState("");
  const [memoLead, setMemoLead] = useState<WebsiteLead | null>(null);
  const [memoDraft, setMemoDraft] = useState("");
  const leadsPage = useServerPagedList<WebsiteLead>({
    collection: "websiteLeads",
    search: keyword,
    filters: { status: statusFilter === "全部" ? undefined : statusFilter },
    pageSize: 10,
    refreshKey: data.websiteLeads,
  });
  const memoLeadFresh = memoLead
    ? (data.websiteLeads.find((item) => item.id === memoLead.id) ?? leadsPage.items.find((item) => item.id === memoLead.id) ?? memoLead)
    : null;
  const memoItems = sortByCreatedDesc(memoLeadFresh?.memos ?? []);

  function upsertLead(next: WebsiteLead) {
    return data.websiteLeads.some((item) => item.id === next.id)
      ? data.websiteLeads.map((item) => (item.id === next.id ? next : item))
      : [next, ...data.websiteLeads];
  }

  async function persistLead(next: WebsiteLead, log: Omit<OperationLog, "id" | "createdAt">) {
    const exists = data.websiteLeads.some((item) => item.id === next.id)
      || leadsPage.items.some((item) => item.id === next.id);
    const saved = exists
      ? await patchCollectionItem<WebsiteLead>("websiteLeads", next.id, next)
      : await createCollectionItem<WebsiteLead>("websiteLeads", next);
    const savedLog = await createCollectionItem<OperationLog>("operationLogs", {
      id: createId("log"),
      createdAt: today(),
      action: log.action,
      targetType: log.targetType,
      targetName: log.targetName,
      operator: log.operator === "当前用户" ? currentUser.name : log.operator,
      detail: log.detail,
    });
    const merged = { ...next, ...saved };
    applyData({
      ...data,
      websiteLeads: upsertLead(merged),
      operationLogs: [savedLog, ...data.operationLogs],
    });
    onNotice({ type: "success", message: `${log.action}成功` });
    return merged;
  }

  async function addLead() {
    if (!form.companyName.trim() || !form.phone.trim()) return;
    const lead: WebsiteLead = {
      id: createId("lead"),
      companyName: form.companyName.trim(),
      phone: form.phone.trim(),
      contactName: form.contactName.trim(),
      platform: form.platform,
      remark: form.remark.trim() || undefined,
      status: "未跟进",
      createdAt: today(),
      lastOperatorName: currentUser.name,
      memos: [],
    };
    try {
      await persistLead(lead, { action: "新增官网留言", targetType: "系统", targetName: lead.companyName, operator: "当前用户", detail: `${lead.platform} / ${lead.phone}` });
      setForm({ companyName: "", phone: "", contactName: "", platform: "泉E采", remark: "" });
    } catch (error) {
      if (error instanceof AuthExpiredError) return;
      onNotice({ type: "error", message: error instanceof Error ? error.message : "保存失败，请稍后重试" });
    }
  }

  async function updateLeadStatus(lead: WebsiteLead, status: WebsiteLead["status"]) {
    const next: WebsiteLead = {
      ...lead,
      status,
      handledAt: status === "未跟进" ? "" : today(),
      lastOperatorName: currentUser.name,
    };
    try {
      const saved = await persistLead(next, { action: "修改官网留言状态", targetType: "系统", targetName: lead.companyName, operator: "当前用户", detail: `${lead.status} -> ${status}` });
      if (memoLead?.id === lead.id) setMemoLead(saved);
    } catch (error) {
      if (error instanceof AuthExpiredError) return;
      onNotice({ type: "error", message: error instanceof Error ? error.message : "保存失败，请稍后重试" });
    }
  }

  async function addLeadMemo() {
    if (!memoLeadFresh || !memoDraft.trim()) return;
    const memo: WebsiteLeadMemo = {
      id: createId("lmemo"),
      content: memoDraft.trim(),
      createdBy: currentUser.name,
      createdAt: today(),
    };
    const next: WebsiteLead = {
      ...memoLeadFresh,
      memos: [memo, ...(memoLeadFresh.memos ?? [])],
      lastOperatorName: currentUser.name,
    };
    try {
      const saved = await persistLead(next, { action: "新增商机备忘", targetType: "系统", targetName: next.companyName, operator: "当前用户", detail: memo.content.slice(0, 80) });
      setMemoLead(saved);
      setMemoDraft("");
    } catch (error) {
      if (error instanceof AuthExpiredError) return;
      onNotice({ type: "error", message: error instanceof Error ? error.message : "保存失败，请稍后重试" });
    }
  }

  return (
    <div className="stack">
      <div className="panel">
        <PanelTitle title="新增商机" subtitle="保存公司官网留言或其它渠道线索；默认状态为未跟进。" />
        <div className="lead-form">
          <input value={form.companyName} onChange={(event) => setForm({ ...form, companyName: event.target.value })} placeholder="公司名称" />
          <input value={form.phone} onChange={(event) => setForm({ ...form, phone: event.target.value })} placeholder="手机号" />
          <input value={form.contactName} onChange={(event) => setForm({ ...form, contactName: event.target.value })} placeholder="联系人" />
          <select value={form.platform} onChange={(event) => setForm({ ...form, platform: event.target.value as WebsiteLead["platform"] })}>
            {platformOptions.map((platform) => <option key={platform}>{platform}</option>)}
          </select>
          <textarea value={form.remark} onChange={(event) => setForm({ ...form, remark: event.target.value })} placeholder="备注" />
          <button className="primary" onClick={addLead}><MessageSquare size={16} />保存商机</button>
        </div>
      </div>
      <div className="panel">
        <div className="panel-title action-title">
          <div>
            <h2>商机管理</h2>
            <p>按跟进状态筛选商机，处理完成后修改状态；列表展示备忘，公司名后可复制公司、联系人和手机号。</p>
          </div>
          <SearchField
            value={keyword}
            onChange={setKeyword}
            placeholder="搜索公司、手机号、联系人、平台"
          />
        </div>
        <div className="segmented">
          {(["全部", ...leadStatusOptions] as Array<WebsiteLead["status"] | "全部">).map((item) => (
            <button key={item} className={statusFilter === item ? "active" : ""} onClick={() => setStatusFilter(item)}>{item}</button>
          ))}
        </div>
        <div className="table">
          <div className="table-row lead-table head"><span>公司/联系人</span><span>手机号</span><span>平台</span><span>备注</span><span>备忘</span><span>状态</span><span>时间</span><span>操作</span></div>
          {leadsPage.items.map((lead) => {
            const memoText = sortByCreatedDesc(lead.memos ?? []).map((memo) => memo.content.trim()).filter(Boolean).join("\n");
            const copyText = [lead.companyName, lead.contactName, lead.phone].filter(Boolean).join("\n");
            return (
            <div className="table-row lead-table" key={lead.id}>
              <span>
                <CopyableLine text={copyText} label="公司、联系人和手机号">
                  {lead.companyName}
                </CopyableLine>
                <em>{lead.contactName || "未录入联系人"}</em>
              </span>
              <span>
                <CopyableLine text={lead.phone} label="手机号">
                  {lead.phone}
                </CopyableLine>
              </span>
              <span>{lead.platform}</span>
              <span>{lead.remark || "无"}</span>
              <span className="lead-memo-cell">{memoText || "无"}</span>
              <span>
                <select value={lead.status} onChange={(event) => void updateLeadStatus(lead, event.target.value as WebsiteLead["status"])}>
                  {leadStatusOptions.map((status) => <option key={status}>{status}</option>)}
                </select>
                {lead.lastOperatorName ? <em>{lead.lastOperatorName}</em> : null}
              </span>
              <span>{formatDateTimeMinute(lead.createdAt)}<em>{lead.handledAt ? `跟进于 ${formatDateTimeMinute(lead.handledAt)}` : "待跟进"}</em></span>
              <span className="option-actions">
                <button className="copy-link" onClick={() => { setMemoLead(lead); setMemoDraft(""); }}>备忘</button>
              </span>
            </div>
            );
          })}
          {leadsPage.total === 0 && <div className="table-row lead-table"><span>暂无商机</span><span></span><span></span><span></span><span></span><span></span><span></span><span></span></div>}
        </div>
        <Pagination {...leadsPage} onPageChange={leadsPage.setPage} />
      </div>
      {memoLeadFresh && (
        <div className="modal-backdrop" role="presentation">
          <div className="modal" role="dialog" aria-modal="true" aria-label="商机备忘">
            <div className="modal-head">
              <div>
                <h2>商机备忘</h2>
                <p>{memoLeadFresh.companyName} / {memoLeadFresh.phone}</p>
              </div>
              <button className="icon-button" onClick={() => setMemoLead(null)} aria-label="关闭备忘">×</button>
            </div>
            <div className="project-memo-form">
              <label className="project-memo-field">
                <span>添加备忘</span>
                <textarea value={memoDraft} onChange={(event) => setMemoDraft(event.target.value)} placeholder="输入备忘内容" />
              </label>
              <button className="primary" type="button" disabled={!memoDraft.trim()} onClick={() => void addLeadMemo()}>保存备忘</button>
            </div>
            <div className="table">
              <div className="table-row lead-memo-table head"><span>操作人</span><span>备忘内容</span><span>添加时间</span></div>
              {memoItems.map((memo) => (
                <div className="table-row lead-memo-table" key={memo.id}>
                  <span>{memo.createdBy}</span>
                  <span>{memo.content}</span>
                  <span>{formatDateTimeMinute(memo.createdAt)}</span>
                </div>
              ))}
              {memoItems.length === 0 && <div className="table-row lead-memo-table"><span>暂无备忘</span><span></span><span></span></div>}
            </div>
            <div className="modal-actions">
              <button className="ghost" onClick={() => setMemoLead(null)}>关闭</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

function Reminders({ data, commit, currentUser }: { data: AppData; commit: (data: AppData, log?: Omit<OperationLog, "id" | "createdAt">) => Promise<void>; currentUser: User }) {
  const [tab, setTab] = useState<"all" | "mine">("all");
  const [statusFilter, setStatusFilter] = useState<"全部" | ProjectReminder["status"]>("全部");
  const [keyword, setKeyword] = useState("");
  const remindersPage = useServerPagedList<ProjectReminder>({
    collection: "projectReminders",
    search: keyword,
    filters: {
      status: statusFilter === "全部" ? undefined : statusFilter,
      createdByUserId: tab === "mine" ? currentUser.id : undefined,
    },
    pageSize: 10,
    refreshKey: data.projectReminders,
  });

  return (
    <div className="stack">
      <div className="panel">
        <PanelTitle title="创建每日任务" subtitle="选择项目和工作内容，默认状态为进行中。" />
        <ReminderForm data={data} commit={commit} currentUser={currentUser} />
      </div>
      <div className="panel">
        <div className="panel-title action-title">
          <div>
            <h2>每日任务列表</h2>
            <p>所有同事都可以查看、创建和处理任务。</p>
          </div>
          <SearchField
            value={keyword}
            onChange={setKeyword}
            placeholder="搜索项目、工作内容、创建人"
          />
        </div>
        <div className="segmented">
          <button className={tab === "all" ? "active" : ""} onClick={() => setTab("all")}>所有任务</button>
          <button className={tab === "mine" ? "active" : ""} onClick={() => setTab("mine")}>我的任务</button>
          {(["全部", "进行中", "已完成"] as const).map((item) => (
            <button key={item} className={statusFilter === item ? "active" : ""} onClick={() => setStatusFilter(item)}>{item}</button>
          ))}
        </div>
        <ReminderList data={data} commit={commit} reminders={remindersPage.items} />
        <Pagination {...remindersPage} onPageChange={remindersPage.setPage} />
      </div>
    </div>
  );
}

function InvoiceReadonlyDetail({ data, invoice }: { data: AppData; invoice: Invoice }) {
  const projects = invoiceRelatedProjects(data, invoice);
  const orders = invoiceOrderEntries(data, invoice);
  const directOrders = orders.filter((order) => order.direct);
  const visibleOrders = directOrders.length > 0 ? directOrders : orders;
  return (
    <>
      <div className="info-grid">
        <div className="info invoice-related-info">
          <span>关联项目</span>
          {projects.length > 0 ? (
            <ul className="invoice-related-list">
              {projects.map((project) => (
                <li key={project.id}>
                  <CopyableLine text={project.name} label="项目名称">{project.name}</CopyableLine>
                  {project.projectNo ? <em>{project.projectNo}</em> : null}
                </li>
              ))}
            </ul>
          ) : <strong>未关联</strong>}
        </div>
        <div className="info invoice-related-info">
          <span>关联订单</span>
          {visibleOrders.length > 0 ? (
            <ul className="invoice-related-list">
              {visibleOrders.map((order) => (
                <li key={order.id}>
                  <CopyableLine text={order.orderNo} label="订单号">{`${order.kind} ${order.orderNo}`}</CopyableLine>
                  <em>{[order.party, money(order.amount), order.direct ? "" : "项目内订单"].filter(Boolean).join(" · ")}</em>
                </li>
              ))}
            </ul>
          ) : <strong>未关联</strong>}
        </div>
        <Info label="买方名称" value={invoice.buyerName || "未录入"} />
        <Info label="买方税号" value={invoice.buyerTaxNo || "未录入"} />
        <Info label="卖方名称" value={invoice.sellerName || "未录入"} />
        <Info label="卖方税号" value={invoice.sellerTaxNo || "未录入"} />
        <Info label="不含税金额" value={money(invoice.amountWithoutTax ?? 0)} />
        <Info label="税额" value={money(invoice.taxAmount ?? 0)} />
        <Info label="价税合计" value={money(invoice.amount)} />
        <Info label="状态" value={invoice.status} />
        <Info label="发票原件" value={invoice.fileName || "未保存"} />
      </div>
      <div className="invoice-items">
        {(invoice.lineItems ?? []).length > 0
          ? invoice.lineItems?.map((item, index) => {
              const linkedOrder = invoiceLineLinkedOrder(data, invoice, item);
              return (
                <span key={`${item.productId || item.productName}-${index}`}>
                  {item.productName}
                  <em>{item.specification || "无规格"} / {item.quantity ?? "-"}{item.unit || ""} / 不含税 {money(item.amount ?? 0)} / 税额 {money(item.taxAmount ?? 0)} / 价税合计 {money(invoiceLineGrossAmount(item))}</em>
                  <em>{linkedOrder ? `已关联 ${linkedOrder.orderNo}` : "未关联订单"}</em>
                </span>
              );
            })
          : <span>暂无商品明细</span>}
      </div>
    </>
  );
}

function ProjectReadonlyDetail({ data, project }: { data: AppData; project: Project }) {
  const purchaseTotal = projectPurchaseAmount(data, project.id);
  const orderTotal = project.type === "服务项目"
    ? data.serviceOrders.filter((order) => order.projectId === project.id && order.status !== "取消" && order.status !== "退款").reduce((sum, order) => sum + (Number(order.receivableAmount ?? order.amount) || 0), 0)
    : data.salesOrders.filter((order) => order.projectId === project.id && order.status !== "取消" && order.status !== "退款").reduce((sum, order) => sum + (Number(order.receivableAmount ?? order.amount) || 0), 0);
  return (
    <div className="info-grid">
      <Info label="项目名称" value={project.name} />
      <Info label="项目编号" value={project.projectNo} />
      <Info label="类型" value={project.type} />
      <Info label="状态" value={project.status} />
      <Info label="客户" value={orgNameById(data, project.customerOrgId) || "未录入"} />
      <Info label="本公司" value={orgNameById(data, project.ownCompanyOrgId) || "未录入"} />
      <Info label="项目金额" value={money(project.totalAmount)} />
      <Info label="订单合计" value={money(orderTotal)} />
      <Info label="项目成本" value={money(purchaseTotal)} />
      <Info label="采购合计" value={money(purchaseTotal)} />
    </div>
  );
}

function Invoices({ data, commit, can }: { data: AppData; commit: (data: AppData, log?: Omit<OperationLog, "id" | "createdAt">) => Promise<void>; can: CanAccess }) {
  const invoiceStatusOptions = optionValues(data, "invoice_status", ["草稿", "待确认", "已确认", "作废"]) as Invoice["status"][];
  const invoiceProjects = sortByCreatedDesc(data.projects);
  const firstProject = invoiceProjects[0];
  const invoiceProjectOptions = invoiceProjects.map((project) => ({
    value: project.id,
    label: project.name,
    detail: `${project.projectNo} / ${project.sourcePlatform || "无平台"} / ${formatDateTimeValue(project.createdAt)}`,
  }));
  const [projectId, setProjectId] = useState(firstProject?.id ?? "");
  const [linkedProjectIds, setLinkedProjectIds] = useState<string[]>(firstProject ? [firstProject.id] : []);
  const [linkedSalesOrderIds, setLinkedSalesOrderIds] = useState<string[]>([]);
  const [linkedPurchaseOrderIds, setLinkedPurchaseOrderIds] = useState<string[]>([]);
  const [type, setType] = useState<Invoice["type"]>("销项");
  const [invoiceNo, setInvoiceNo] = useState("");
  const [invoiceDate, setInvoiceDate] = useState(new Date().toISOString().slice(0, 10));
  const [buyerOrgId, setBuyerOrgId] = useState(firstProject?.customerOrgId ?? "");
  const [sellerOrgId, setSellerOrgId] = useState(firstProject?.ownCompanyOrgId ?? data.organizations.find((org) => isOwnCompanyOrganization(org))?.id ?? "");
  const [amountWithoutTax, setAmountWithoutTax] = useState("");
  const [taxAmount, setTaxAmount] = useState("");
  const [status, setStatus] = useState<Invoice["status"]>("待确认");
  const [showInvoiceModal, setShowInvoiceModal] = useState(false);
  const [invoiceFileName, setInvoiceFileName] = useState("");
  const [invoiceFile, setInvoiceFile] = useState<File | null>(null);
  const [invoiceOcrStatus, setInvoiceOcrStatus] = useState("");
  const [buyerNameInput, setBuyerNameInput] = useState("");
  const [buyerTaxNoInput, setBuyerTaxNoInput] = useState("");
  const [sellerNameInput, setSellerNameInput] = useState("");
  const [sellerTaxNoInput, setSellerTaxNoInput] = useState("");
  const [invoiceLineItems, setInvoiceLineItems] = useState<InvoiceLineItem[]>([]);
  const [selectedInvoiceId, setSelectedInvoiceId] = useState("");
  const [editingInvoiceStatusId, setEditingInvoiceStatusId] = useState("");
  const [invoiceSearch, setInvoiceSearch] = useState("");

  function resetInvoiceForm() {
    setProjectId(firstProject?.id ?? "");
    setLinkedProjectIds(firstProject ? [firstProject.id] : []);
    setLinkedSalesOrderIds([]);
    setLinkedPurchaseOrderIds([]);
    setType("销项");
    setInvoiceNo("");
    setInvoiceDate(new Date().toISOString().slice(0, 10));
    setBuyerOrgId(firstProject?.customerOrgId ?? "");
    setSellerOrgId(firstProject?.ownCompanyOrgId ?? data.organizations.find((org) => isOwnCompanyOrganization(org))?.id ?? "");
    setAmountWithoutTax("");
    setTaxAmount("");
    setStatus("待确认");
    setInvoiceFileName("");
    setInvoiceFile(null);
    setInvoiceOcrStatus("");
    setBuyerNameInput("");
    setBuyerTaxNoInput("");
    setSellerNameInput("");
    setSellerTaxNoInput("");
    setInvoiceLineItems([]);
  }

  function openInvoiceModal() {
    resetInvoiceForm();
    setShowInvoiceModal(true);
  }

  function applyProject(projectIdValue: string, invoiceType = type) {
    const project = data.projects.find((item) => item.id === projectIdValue);
    setProjectId(projectIdValue);
    setLinkedProjectIds(projectIdValue ? [projectIdValue] : []);
    setLinkedSalesOrderIds([]);
    setLinkedPurchaseOrderIds([]);
    if (!project) return;
    if (invoiceType === "销项") {
      selectBuyerOrg(project.customerOrgId);
      selectSellerOrg(project.ownCompanyOrgId ?? data.organizations.find((org) => isOwnCompanyOrganization(org))?.id ?? "");
    } else {
      selectBuyerOrg(project.ownCompanyOrgId ?? data.organizations.find((org) => isOwnCompanyOrganization(org))?.id ?? "");
      const item = data.projectItems.find((projectItem) => projectItem.projectId === project.id);
      const latestPrice = item ? data.supplierPrices.find((price) => price.productId === item.productId) : undefined;
      selectSellerOrg(latestPrice?.supplierOrgId ?? data.organizations.find((org) => isSupplierOrganization(org))?.id ?? "");
    }
  }

  function changeType(nextType: Invoice["type"]) {
    setType(nextType);
    applyProject(projectId, nextType);
  }

  function selectBuyerOrg(orgId: string) {
    setBuyerOrgId(orgId);
    const org = data.organizations.find((item) => item.id === orgId);
    if (!org) return;
    setBuyerNameInput(org.name);
    setBuyerTaxNoInput(org.unifiedCreditCode ?? "");
  }

  function selectSellerOrg(orgId: string) {
    setSellerOrgId(orgId);
    const org = data.organizations.find((item) => item.id === orgId);
    if (!org) return;
    setSellerNameInput(org.name);
    setSellerTaxNoInput(org.unifiedCreditCode ?? "");
  }

  function selectInvoiceFile(file: File | undefined) {
    setInvoiceFile(file ?? null);
    setInvoiceFileName(file?.name ?? "");
    setInvoiceOcrStatus("");
  }

  async function fillFromInvoiceOcr() {
    if (!invoiceFile) {
      setInvoiceOcrStatus("请先选择发票 PDF 文件。");
      return;
    }
    setInvoiceOcrStatus("正在识别 PDF 发票...");
    try {
      const formData = new FormData();
      formData.append("file", invoiceFile);
      const response = await fetch(ocrServiceUrl("/api/ocr/invoice"), {
        method: "POST",
        body: formData,
      });
      if (!response.ok) {
        const errorText = await response.text();
        throw new Error(errorText || "发票识别失败");
      }
      const result = await response.json();
      if (result.status !== "recognized" || !result.data) {
        setInvoiceOcrStatus(result.message || "该 PDF 暂未识别到文本层，需要图片 OCR。");
        return;
      }
      const parsed = result.data as {
        invoice_no?: string;
        invoice_date?: string;
        buyer_name?: string;
        buyer_tax_no?: string;
        seller_name?: string;
        seller_tax_no?: string;
        amount_without_tax?: number;
        tax_amount?: number;
        line_items?: Array<{
          product_name?: string;
          specification?: string;
          unit?: string;
          quantity?: number;
          unit_price?: number;
          amount?: number;
          tax_rate?: string;
          tax_amount?: number;
          raw?: string;
        }>;
      };
      if (parsed.invoice_no) setInvoiceNo(parsed.invoice_no);
      if (parsed.invoice_date) setInvoiceDate(parsed.invoice_date);
      if (parsed.amount_without_tax != null) setAmountWithoutTax(String(parsed.amount_without_tax));
      if (parsed.tax_amount != null) setTaxAmount(String(parsed.tax_amount));
      const applyOcrParty = (
        parsedName: string | undefined,
        parsedTax: string | undefined,
        selectOrg: (orgId: string) => void,
        setOrgId: (orgId: string) => void,
        setName: (value: string) => void,
        setTax: (value: string) => void,
      ) => {
        const name = parsedName?.trim() ?? "";
        const tax = parsedTax?.trim() ?? "";
        if (!name && !tax) return;
        const matched = findOrganizationByInvoiceParty(data.organizations, tax, name);
        if (matched) {
          selectOrg(matched.id);
          return;
        }
        setOrgId("");
        setName(name);
        setTax(tax);
      };
      applyOcrParty(parsed.buyer_name, parsed.buyer_tax_no, selectBuyerOrg, setBuyerOrgId, setBuyerNameInput, setBuyerTaxNoInput);
      applyOcrParty(parsed.seller_name, parsed.seller_tax_no, selectSellerOrg, setSellerOrgId, setSellerNameInput, setSellerTaxNoInput);
      setInvoiceLineItems((parsed.line_items ?? []).map((item) => ({
        productName: item.product_name ?? "",
        specification: item.specification,
        unit: item.unit,
        quantity: item.quantity,
        unitPrice: item.unit_price,
        amount: item.amount,
        taxRate: item.tax_rate,
        taxAmount: item.tax_amount,
        raw: item.raw,
      })).filter((item) => item.productName));

      const selectedProject = data.projects.find((project) => project.id === projectId);
      const projectOwnName = selectedProject?.ownCompanyOrgId
        ? data.organizations.find((org) => org.id === selectedProject.ownCompanyOrgId)?.name
        : undefined;
      const ownCompanyNames = projectOwnName
        ? [projectOwnName]
        : data.organizations.filter((org) => isOwnCompanyOrganization(org)).map((org) => org.name).filter(Boolean);
      const detectedType = detectInvoiceTypeFromParties(parsed.buyer_name, parsed.seller_name, ownCompanyNames);
      if (detectedType) setType(detectedType);

      setStatus("待确认");
      const itemCount = (parsed.line_items ?? []).length;
      const itemHint = itemCount > 0 ? `已识别 ${itemCount} 个商品明细` : "未识别到商品明细，可手工核对";
      const typeHint = detectedType
        ? `；已按己方主体自动选为「${detectedType}」（己方≈${detectedType === "销项" ? "销方" : "购方"}）`
        : "；进项/销项未能自动判断，仍为当前选择";
      const baseMessage = typeof result.message === "string" && /[\u4e00-\u9fff]/.test(result.message)
        ? result.message
        : "发票识别完成";
      setInvoiceOcrStatus(`${baseMessage}${itemCount ? "" : `（${itemHint}）`}${typeHint}`);
    } catch (error) {
      setInvoiceOcrStatus(error instanceof Error ? error.message : "发票识别失败");
    }
  }

  async function addInvoice() {
    const withoutTax = Number(amountWithoutTax);
    const tax = Number(taxAmount);
    if (!invoiceFile) {
      setInvoiceOcrStatus("请先选择并上传发票原件。");
      return;
    }
    if (!invoiceNo.trim() || Number.isNaN(withoutTax) || Number.isNaN(tax)) return;
    const invoiceAmount = roundMoney(withoutTax + tax);
    if (data.invoices.some((invoice) => invoice.invoiceNo && invoice.invoiceNo === invoiceNo.trim())) {
      window.alert(`发票号码 ${invoiceNo.trim()} 已存在，不能重复保存。`);
      return;
    }

    let nextOrganizations = [...data.organizations];
    let nextProducts = [...data.products];

    function ensureOrganization(
      selectedOrgId: string,
      name: string,
      taxNo: string,
      role: OrganizationRole,
      defaultType: EntityType,
    ) {
      const selected = nextOrganizations.find((org) => org.id === selectedOrgId);
      const matched = nextOrganizations.find((org) => taxNo && org.unifiedCreditCode === taxNo)
        ?? nextOrganizations.find((org) => name && org.name === name)
        ?? (selected && (!taxNo || !selected.unifiedCreditCode || selected.unifiedCreditCode === taxNo) ? selected : undefined);
      if (matched) {
        nextOrganizations = nextOrganizations.map((org) =>
          org.id === matched.id
            ? {
                ...org,
                name: name || org.name,
                unifiedCreditCode: taxNo || org.unifiedCreditCode,
                roles: Array.from(new Set([...org.roles, role])) as OrganizationRole[],
              }
            : org,
        );
        return { ...matched, name: name || matched.name, unifiedCreditCode: taxNo || matched.unifiedCreditCode, roles: Array.from(new Set([...matched.roles, role])) as OrganizationRole[] };
      }
      const organization: Organization = {
        id: createId("org"),
        name,
        entityType: defaultType,
        roles: [role],
        unifiedCreditCode: taxNo || undefined,
        status: "正常",
        createdAt: today(),
      };
      nextOrganizations = [organization, ...nextOrganizations];
      return organization;
    }

    function ensureProduct(line: InvoiceLineItem) {
      const matched = nextProducts.find((product) =>
        product.name === line.productName && (!line.specification || product.capacity === line.specification || product.description?.includes(line.specification)),
      );
      if (matched) return matched;
      const product: Product = {
        id: createId("prd"),
        code: `INV-${invoiceNo}-${nextProducts.length + 1}`,
        name: line.productName,
        kind: "实体商品",
        category: line.productName.includes("空调") ? "空调" : "发票导入",
        capacity: line.specification,
        quotePrice: line.unitPrice ?? 0,
        costPrice: 0,
        description: line.raw,
      };
      nextProducts = [product, ...nextProducts];
      return product;
    }

    const buyerName = buyerNameInput.trim() || data.organizations.find((org) => org.id === buyerOrgId)?.name || "";
    const sellerName = sellerNameInput.trim() || data.organizations.find((org) => org.id === sellerOrgId)?.name || "";
    if (!buyerName || !sellerName) return;

    const buyer = ensureOrganization(buyerOrgId, buyerName, buyerTaxNoInput.trim(), "客户", "企业");
    const seller = ensureOrganization(sellerOrgId, sellerName, sellerTaxNoInput.trim(), "本方主体", "企业");
    const project = data.projects.find((item) => item.id === projectId);
    const savedLineItems = invoiceLineItems.map((line) => {
      const product = ensureProduct(line);
      if (invoiceLineItems.length <= 1) {
        return {
          ...line,
          productId: product.id,
          salesOrderId: type === "销项" ? linkedSalesOrderIds[0] : undefined,
          purchaseOrderId: type === "进项" ? linkedPurchaseOrderIds[0] : undefined,
        };
      }
      return { ...line, productId: product.id };
    });
    const nextSalesOrderIds = Array.from(new Set(savedLineItems.map((item) => item.salesOrderId).filter((id): id is string => Boolean(id))));
    const nextPurchaseOrderIds = Array.from(new Set(savedLineItems.map((item) => item.purchaseOrderId).filter((id): id is string => Boolean(id))));
    const finalSalesOrderIds = nextSalesOrderIds.length > 0 ? nextSalesOrderIds : linkedSalesOrderIds;
    const finalPurchaseOrderIds = nextPurchaseOrderIds.length > 0 ? nextPurchaseOrderIds : linkedPurchaseOrderIds;
    const invoiceId = createId("inv");
    try {
      const savedFile = await uploadBusinessDocument(invoiceFile, "invoice", invoiceId);
      const invoice: Invoice = {
        id: invoiceId,
        createdAt: new Date().toISOString(),
        projectId: linkedProjectIds[0] || projectId || undefined,
        projectIds: linkedProjectIds,
        salesOrderIds: finalSalesOrderIds,
        purchaseOrderIds: finalPurchaseOrderIds,
        type,
        counterpartyOrgId: type === "销项" ? buyer.id : seller.id,
        invoiceNo,
        invoiceDate,
        buyerOrgId: buyer.id,
        buyerName: buyer.name,
        buyerTaxNo: buyer.unifiedCreditCode,
        sellerOrgId: seller.id,
        sellerName: seller.name,
        sellerTaxNo: seller.unifiedCreditCode,
        amountWithoutTax: withoutTax,
        taxAmount: tax,
        amount: invoiceAmount,
        status,
        date: invoiceDate,
        lineItems: savedLineItems,
        fileId: savedFile.id,
        fileName: savedFile.fileName,
      };
      const reconciledInvoice = reconcileInvoiceProjectIds(data, invoice);
      const nextInvoices = [reconciledInvoice, ...data.invoices];
      await commit(
        {
          ...data,
          organizations: nextOrganizations,
          products: nextProducts,
          invoices: nextInvoices,
          projects: data.projects.map((item) => item.type === "服务项目" && linkedProjectIds.includes(item.id) ? { ...item, invoiceStatus: "已开全部" } : item),
        },
          { action: "新增发票", targetType: "发票", targetName: invoice.invoiceNo ?? project?.name ?? "未关联项目发票", operator: "当前用户", detail: `${type}发票关联项目 ${linkedProjectIds.length} 个，销售订单 ${finalSalesOrderIds.length} 个，采购订单 ${finalPurchaseOrderIds.length} 个` },
      );
      resetInvoiceForm();
      setShowInvoiceModal(false);
    } catch (error) {
      const message = error instanceof Error ? error.message : "保存发票失败";
      setInvoiceOcrStatus(message);
    }
  }

  async function deleteInvoice(invoice: Invoice) {
    if (isConfirmedInvoice(invoice)) {
      window.alert("已确认的发票不可删除。");
      return;
    }
    await commit(
      { ...data, invoices: data.invoices.filter((item) => item.id !== invoice.id) },
      { action: "删除发票", targetType: "发票", targetName: invoice.invoiceNo || "未录入发票号", operator: "当前用户", detail: "开发环境允许删除发票记录" },
    );
    if (selectedInvoiceId === invoice.id) setSelectedInvoiceId("");
  }

  async function updateInvoiceStatus(invoice: Invoice, nextStatus: Invoice["status"]) {
    if (!canTransition(invoice.status, nextStatus, getAllowedInvoiceStatuses(invoice, invoiceStatusOptions))) {
      window.alert(`发票状态不能从“${invoice.status}”变更为“${nextStatus}”。`);
      setEditingInvoiceStatusId("");
      return;
    }
    await commit(
      { ...data, invoices: data.invoices.map((item) => item.id === invoice.id ? { ...item, status: nextStatus } : item) },
      { action: "修改发票状态", targetType: "发票", targetName: invoice.invoiceNo || "未录入发票号", operator: "当前用户", detail: `${invoice.status} -> ${nextStatus}` },
    );
    setEditingInvoiceStatusId("");
  }

  const selectedInvoice = data.invoices.find((invoice) => invoice.id === selectedInvoiceId);
  const invoicesPage = useServerPagedList<Invoice>({
    collection: "invoices",
    search: invoiceSearch,
    pageSize: 10,
    refreshKey: data.invoices,
  });
  const availableSalesOrders = data.salesOrders.filter((order) => linkedProjectIds.length === 0 || linkedProjectIds.includes(order.projectId));
  const availablePurchaseOrders = data.purchaseOrders.filter((order) => linkedProjectIds.length === 0 || linkedProjectIds.includes(order.projectId));

  function invoiceProjectText(invoice: Invoice) {
    const projectIds = invoice.projectIds ?? (invoice.projectId ? [invoice.projectId] : []);
    const names = projectIds.map((id) => data.projects.find((project) => project.id === id)?.name).filter(Boolean);
    return names.length ? names.join(" / ") : "";
  }

  function salesOrderOptionLabel(order: SalesOrder) {
    const customer = data.organizations.find((org) => org.id === order.customerOrgId)?.name;
    return [order.orderNo, customer, money(order.amount)].filter(Boolean).join("｜");
  }

  function purchaseOrderOptionLabel(order: PurchaseOrder) {
    const supplier = data.organizations.find((org) => org.id === order.supplierOrgId)?.name;
    return [order.orderNo, supplier, money(order.amount)].filter(Boolean).join("｜");
  }

  return (
    <div className="stack">
      <div className="panel">
        <div className="panel-title action-title">
          <div>
            <h2>发票管理</h2>
            <p>列表优先展示关联的销售、采购或服务订单；只挂了项目时，会带出该项目下的具体订单。</p>
          </div>
          {can("invoice.manage") && <button className="primary" onClick={openInvoiceModal}><FileText size={16} />添加发票</button>}
        </div>
        <SearchField
          value={invoiceSearch}
          onChange={setInvoiceSearch}
          placeholder="搜索发票号、订单号、买方、卖方、税号或项目"
        />
        <div className="table">
          <div className="table-row invoice-table head"><span>发票号码/日期</span><span>订单</span><span>买方</span><span>卖方</span><span>不含税</span><span>税额</span><span>价税合计</span><span>状态</span><span>操作</span></div>
          {invoicesPage.items.map((invoice) => {
            const projectText = invoiceProjectText(invoice);
            const orders = invoiceOrderEntries(data, invoice);
            const shownOrders = orders.slice(0, 4);
            const hiddenOrderCount = orders.length - shownOrders.length;
            const inferred = shownOrders.length > 0 && shownOrders.every((order) => !order.direct);
            return (
              <div className="table-row invoice-table" key={invoice.id}>
                <span>
                  <CopyableLine text={invoice.invoiceNo || ""} label="发票号" onOpen={() => setSelectedInvoiceId(invoice.id)}>
                    {invoice.invoiceNo || "未录入"}
                  </CopyableLine>
                  <em>{invoice.invoiceDate || invoice.date || "未录入日期"}</em>
                </span>
                <span className="invoice-order-cell">
                  {shownOrders.length === 0 ? "未关联订单" : shownOrders.map((order) => (
                    <CopyableLine key={order.id} text={order.orderNo} label="订单号">
                      <strong>{order.kind} {order.orderNo}</strong>
                    </CopyableLine>
                  ))}
                  {hiddenOrderCount > 0 && <em>另 {hiddenOrderCount} 笔</em>}
                  {projectText ? <em>{projectText}</em> : null}
                  {inferred && <em>未直接关联，以上为项目内订单</em>}
                </span>
                <span>
                  <CopyableLine text={invoice.buyerName || ""} label="买方">
                    {invoice.buyerName || "未录入"}
                  </CopyableLine>
                  <em>{invoice.buyerTaxNo || "无税号"}</em>
                </span>
                <span>
                  <CopyableLine text={invoice.sellerName || ""} label="卖方">
                    {invoice.sellerName || "未录入"}
                  </CopyableLine>
                  <em>{invoice.sellerTaxNo || "无税号"}</em>
                </span>
                <span>{money(invoice.amountWithoutTax ?? 0)}</span>
                <span>{money(invoice.taxAmount ?? 0)}</span>
                <span>{money(invoice.amount)}</span>
                <span className="editable-status" onDoubleClick={() => can("invoice.manage") && getAllowedInvoiceStatuses(invoice, invoiceStatusOptions).length > 1 && setEditingInvoiceStatusId(invoice.id)}>
                  {editingInvoiceStatusId === invoice.id ? (
                    <select value={invoice.status} autoFocus onBlur={() => setEditingInvoiceStatusId("")} onChange={(event) => void updateInvoiceStatus(invoice, event.target.value as Invoice["status"])}>
                      {getAllowedInvoiceStatuses(invoice, invoiceStatusOptions).map((item) => <option key={item}>{item}</option>)}
                    </select>
                  ) : invoice.status}
                </span>
                <span>
                  {invoice.fileId && <button className="copy-link" onClick={() => openBusinessDocument(invoice.fileId)}>查看原件</button>}
                  <button className="copy-link" onClick={() => setSelectedInvoiceId(invoice.id)}>详情</button>
                  {can("invoice.manage") && !isConfirmedInvoice(invoice) && <button className="copy-link danger-action" onClick={() => void deleteInvoice(invoice)}>删除</button>}
                </span>
              </div>
            );
          })}
        </div>
        <Pagination {...invoicesPage} onPageChange={invoicesPage.setPage} />
      </div>
      {showInvoiceModal && (
        <div className="modal-backdrop" role="presentation">
          <div className="modal" role="dialog" aria-modal="true" aria-label="添加发票">
            <div className="modal-head">
              <div>
                <h2>添加发票</h2>
                <p>上传发票文件后 OCR 回填发票号码、日期和金额，再确认项目、买方、卖方后保存。</p>
              </div>
              <button className="icon-button" onClick={() => setShowInvoiceModal(false)} aria-label="关闭">×</button>
            </div>
            <div className="upload-strip">
              <FilePicker
                accept=".pdf,application/pdf"
                fileName={invoiceFileName}
                placeholder="未选择发票文件"
                buttonLabel="选择发票"
                ariaLabel="选择发票文件"
                onFile={(file) => selectInvoiceFile(file)}
              />
              {can("invoice.manage") && <button className="ghost" onClick={fillFromInvoiceOcr}><FileScan size={16} />OCR 识别并填充</button>}
            </div>
            {invoiceOcrStatus && <div className="copy-tip">{invoiceOcrStatus}</div>}
            <div className="form-grid invoice-form">
              <label className="field span-4">
                <span>关联项目</span>
                <SearchableSelect value={projectId} options={[{ value: "", label: "暂不关联项目" }, ...invoiceProjectOptions]} onChange={(value) => applyProject(value)} placeholder="输入项目、编号或平台搜索" ariaLabel="搜索并选择关联项目" />
              </label>
              <label className="field span-2">
                <span>进项/销项</span>
                <select value={type} onChange={(event) => changeType(event.target.value as Invoice["type"])} aria-label="进项/销项">
                  <option>销项</option>
                  <option>进项</option>
                </select>
              </label>
              {invoiceLineItems.length <= 1 ? (
                <>
                  <label className="field span-3">
                    <span>关联销售订单（可多选）</span>
                    <select multiple value={linkedSalesOrderIds} onChange={(event) => setLinkedSalesOrderIds(Array.from(event.currentTarget.selectedOptions, (option) => option.value))}>
                      {availableSalesOrders.map((order) => <option key={order.id} value={order.id}>{salesOrderOptionLabel(order)}</option>)}
                    </select>
                  </label>
                  <label className="field span-3">
                    <span>关联采购订单（可多选）</span>
                    <select multiple value={linkedPurchaseOrderIds} onChange={(event) => setLinkedPurchaseOrderIds(Array.from(event.currentTarget.selectedOptions, (option) => option.value))}>
                      {availablePurchaseOrders.map((order) => <option key={order.id} value={order.id}>{purchaseOrderOptionLabel(order)}</option>)}
                    </select>
                  </label>
                </>
              ) : (
                <p className="span-6 copy-tip">该发票含 {invoiceLineItems.length} 个商品，请在下方明细中为每个商品选择对应订单。各订单关联金额按所选商品价税合计校验。</p>
              )}
              <input className="span-3" value={invoiceNo} onChange={(event) => setInvoiceNo(event.target.value)} placeholder="发票号码" />
              <DateTimeField className="span-3" value={invoiceDate} onChange={setInvoiceDate} ariaLabel="发票日期" placeholder="发票日期" />
              <select className="span-6" value={buyerOrgId} onChange={(event) => selectBuyerOrg(event.target.value)}>
                <option value="">买方未入库，保存时自动创建客户</option>
                {data.organizations.map((org) => <option key={org.id} value={org.id}>{org.name}</option>)}
              </select>
              <select className="span-6" value={sellerOrgId} onChange={(event) => selectSellerOrg(event.target.value)}>
                <option value="">卖方未入库，保存时自动创建本方主体</option>
                {data.organizations.map((org) => <option key={org.id} value={org.id}>{org.name}</option>)}
              </select>
              <input className="span-4" value={buyerNameInput} onChange={(event) => setBuyerNameInput(event.target.value)} placeholder="买方名称" />
              <input className="span-2" value={buyerTaxNoInput} onChange={(event) => setBuyerTaxNoInput(event.target.value)} placeholder="买方统一社会信用代码" />
              <input className="span-4" value={sellerNameInput} onChange={(event) => setSellerNameInput(event.target.value)} placeholder="卖方名称" />
              <input className="span-2" value={sellerTaxNoInput} onChange={(event) => setSellerTaxNoInput(event.target.value)} placeholder="卖方统一社会信用代码" />
              <input className="span-2" type="number" value={amountWithoutTax} onChange={(event) => setAmountWithoutTax(event.target.value)} placeholder="不含税金额" />
              <input className="span-2" type="number" value={taxAmount} onChange={(event) => setTaxAmount(event.target.value)} placeholder="税额" />
              <select className="span-2" value={status} onChange={(event) => setStatus(event.target.value as Invoice["status"])}>
                {invoiceStatusOptions.map((item) => <option key={item}>{item}</option>)}
              </select>
            </div>
            {invoiceLineItems.length > 0 && (
              <div className="invoice-items">
                {invoiceLineItems.map((item, index) => (
                  <span key={`${item.productName}-${index}`}>
                    {item.productName}
                    <em>{item.specification || "无规格"} / {item.quantity ?? "-"}{item.unit || ""} / 不含税 {money(item.amount ?? 0)} / 价税合计 {money(invoiceLineGrossAmount(item))}</em>
                    {invoiceLineItems.length > 1 && (
                      <select
                        aria-label={`商品 ${item.productName} 关联订单`}
                        value={type === "销项" ? (item.salesOrderId ?? "") : (item.purchaseOrderId ?? "")}
                        onChange={(event) => {
                          const orderId = event.target.value || undefined;
                          setInvoiceLineItems((current) => current.map((line, lineIndex) => (
                            lineIndex === index
                              ? {
                                  ...line,
                                  salesOrderId: type === "销项" ? orderId : undefined,
                                  purchaseOrderId: type === "进项" ? orderId : undefined,
                                }
                              : line
                          )));
                        }}
                      >
                        <option value="">暂不关联订单</option>
                        {(type === "销项" ? availableSalesOrders : availablePurchaseOrders).map((order) => (
                          <option key={order.id} value={order.id}>{type === "销项" ? salesOrderOptionLabel(order as SalesOrder) : purchaseOrderOptionLabel(order as PurchaseOrder)}（剩余 {money(Math.max(roundMoney(orderInvoiceCap(data, order, type === "销项" ? "sales" : "purchase") - orderInvoicedAmount(data, order.id, type === "销项" ? "sales" : "purchase")), 0))}）</option>
                        ))}
                      </select>
                    )}
                  </span>
                ))}
              </div>
            )}
            <div className="modal-actions">
              <button className="ghost" onClick={() => setShowInvoiceModal(false)}>取消</button>
              {can("invoice.manage") && <button className="primary" onClick={addInvoice}><FileText size={16} />保存发票</button>}
            </div>
          </div>
        </div>
      )}
      {selectedInvoice && (
        <div className="modal-backdrop" role="presentation">
          <div className="modal" role="dialog" aria-modal="true" aria-label="发票详情">
            <div className="modal-head">
              <div>
                <h2>发票详情</h2>
                <p>{selectedInvoice.invoiceNo || "未录入发票号"} / {selectedInvoice.invoiceDate || selectedInvoice.date || "未录入日期"}</p>
              </div>
              <button className="icon-button" onClick={() => setSelectedInvoiceId("")} aria-label="关闭">×</button>
            </div>
            <InvoiceReadonlyDetail data={data} invoice={selectedInvoice} />
            <div className="modal-actions">
              {selectedInvoice.fileId && <button className="ghost" onClick={() => openBusinessDocument(selectedInvoice.fileId)}><FileText size={16} />查看原件</button>}
              {can("invoice.manage") && !isConfirmedInvoice(selectedInvoice) && <button className="ghost danger-action" onClick={() => void deleteInvoice(selectedInvoice)}><Trash2 size={16} />删除发票</button>}
              <button className="ghost" onClick={() => setSelectedInvoiceId("")}>关闭</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

function financeStatementExportName(kind: string, dateFrom: string, dateTo: string) {
  const parts = ["财务清单"];
  if (kind && kind !== "全部") parts.push(kind);
  if (dateFrom && dateTo) parts.push(`${dateFrom}至${dateTo}`);
  else if (dateFrom) parts.push(`${dateFrom}起`);
  else if (dateTo) parts.push(`截止${dateTo}`);
  parts.push(formatLocalDate(new Date()));
  return `${parts.join("-")}.xlsx`;
}

function downloadFinanceStatementWorkbook(rows: FinanceStatementRow[], filename: string) {
  const sheetRows = rows.map((row) => ({
    客户: row.customerName,
    客户类型: row.serviceCustomerKind || "",
    主体: row.companyName,
    收款银行: row.bankName || "",
    账户: row.accountNumber || (row.accountText === "未录入" ? "" : row.accountText.replace(/\n/g, " / ")),
    业务员: row.salesperson,
    金额: row.amount,
    流水类型: row.txType || "",
    交易时间: formatDateTimeValue(row.occurredAt),
    类型: row.businessKind,
  }));
  const sheet = XLSX.utils.json_to_sheet(sheetRows);
  sheet["!cols"] = [
    { wch: 22 },
    { wch: 12 },
    { wch: 22 },
    { wch: 16 },
    { wch: 22 },
    { wch: 12 },
    { wch: 12 },
    { wch: 10 },
    { wch: 20 },
    { wch: 8 },
  ];
  const workbook = XLSX.utils.book_new();
  XLSX.utils.book_append_sheet(workbook, sheet, "财务清单");
  XLSX.writeFile(workbook, filename);
}

function FinanceStatements({
  data,
  onNotice,
}: {
  data: AppData;
  onNotice: (notice: { type: "success" | "error"; message: string }) => void;
}) {
  const [businessKind, setBusinessKind] = useState<"全部" | "服务" | "商品" | "采购">("全部");
  const [customerOrgId, setCustomerOrgId] = useState("");
  const [ownCompanyOrgId, setOwnCompanyOrgId] = useState("");
  const [salesperson, setSalesperson] = useState("");
  const [collectionAccountId, setCollectionAccountId] = useState("");
  const [dateFrom, setDateFrom] = useState("");
  const [dateTo, setDateTo] = useState("");
  const [exporting, setExporting] = useState(false);
  const kindTabs: Array<"全部" | "服务" | "商品" | "采购"> = ["全部", "服务", "商品", "采购"];
  const customerOptions = useMemo(
    () => data.organizations
      .filter((org) => !isOwnCompanyOrganization(org))
      .map((org) => ({ value: org.id, label: org.name })),
    [data.organizations],
  );
  const companyOptions = useMemo(
    () => data.organizations
      .filter((org) => isOwnCompanyOrganization(org))
      .map((org) => ({ value: org.id, label: org.name })),
    [data.organizations],
  );
  const salespersonOptions = useMemo(() => {
    const options: SearchableSelectOption[] = data.users
      .filter((user) => user.status === "启用")
      .map((user) => ({ value: user.id, label: user.name }));
    const seen = new Set(options.map((item) => item.label));
    for (const project of data.projects) {
      const owner = project.owner?.trim();
      if (!owner || seen.has(owner)) continue;
      seen.add(owner);
      options.push({ value: `name:${owner}`, label: owner });
    }
    return options;
  }, [data.users, data.projects]);
  const bankOptions = useMemo(
    () => (data.optionGroups.find((group) => group.key === "collection_account")?.items ?? [])
      .filter((item) => item.enabled !== false && (item.accountNumber || item.bankName))
      .map((item) => ({
        value: item.id,
        label: collectionAccountOptionLabel(data, item),
      })),
    [data.optionGroups, data.organizations],
  );
  const listFilters = useMemo(() => ({
    businessKind: businessKind === "全部" ? undefined : businessKind,
    customerOrgId,
    ownCompanyOrgId,
    salesperson,
    collectionAccountId,
    dateFrom,
    dateTo,
  }), [businessKind, customerOrgId, ownCompanyOrgId, salesperson, collectionAccountId, dateFrom, dateTo]);
  const list = useServerPagedList<FinanceStatementRow>({
    collection: "financeStatements",
    pageSize: 20,
    filters: listFilters,
    refreshKey: data.transactions.length,
  });

  async function exportCurrentFilters() {
    if (exporting) return;
    setExporting(true);
    try {
      const result = await queryCollection<FinanceStatementRow>("financeStatements", {
        paged: false,
        filters: listFilters,
      });
      if (result.items.length === 0) {
        onNotice({ type: "error", message: "当前筛选没有可导出的对账记录" });
        return;
      }
      downloadFinanceStatementWorkbook(result.items, financeStatementExportName(businessKind, dateFrom, dateTo));
      onNotice({ type: "success", message: `已导出 ${result.items.length} 条财务清单` });
    } catch (error) {
      if (error instanceof AuthExpiredError) return;
      onNotice({ type: "error", message: error instanceof Error ? error.message : "导出失败" });
    } finally {
      setExporting(false);
    }
  }

  return (
    <div className="stack">
      <div className="panel">
        <div className="panel-title action-title">
          <div>
            <h2>财务清单</h2>
            <p>按交易时间倒序，供财务对账核对客户、主体、收款账户、业务员与金额。导出使用当前筛选条件。</p>
          </div>
          <div className="panel-title-buttons">
            <button
              className="ghost"
              type="button"
              disabled={exporting || (list.total === 0 && !list.loading)}
              onClick={() => void exportCurrentFilters()}
            >
              <Download size={16} />{exporting ? "导出中..." : "导出"}
            </button>
          </div>
        </div>
        <div className="segmented" role="tablist" aria-label="业务类型">
          {kindTabs.map((item) => (
            <button
              key={item}
              type="button"
              className={businessKind === item ? "active" : ""}
              onClick={() => setBusinessKind(item)}
            >
              {item}
            </button>
          ))}
        </div>
        <form className="finance-statement-filters" onSubmit={(event) => event.preventDefault()}>
          <div className="orders-filter-field">
            <span>客户</span>
            <SearchableSelect
              value={customerOrgId}
              options={customerOptions}
              onChange={setCustomerOrgId}
              placeholder="全部客户"
              ariaLabel="客户"
            />
          </div>
          <div className="orders-filter-field">
            <span>主体</span>
            <SearchableSelect
              value={ownCompanyOrgId}
              options={companyOptions}
              onChange={setOwnCompanyOrgId}
              placeholder="全部主体"
              ariaLabel="主体"
            />
          </div>
          <div className="orders-filter-field">
            <span>业务员</span>
            <SearchableSelect
              value={salesperson}
              options={salespersonOptions}
              onChange={setSalesperson}
              placeholder="全部业务员"
              ariaLabel="业务员"
            />
          </div>
          <div className="orders-filter-field">
            <span>银行</span>
            <SearchableSelect
              value={collectionAccountId}
              options={bankOptions}
              onChange={setCollectionAccountId}
              placeholder="全部银行账号"
              ariaLabel="银行账号"
            />
          </div>
          <div className="orders-filter-field finance-statement-dates">
            <span>交易时间</span>
            <div className="cashflow-custom-range">
              <DateTimeField mode="date" value={dateFrom} onChange={setDateFrom} ariaLabel="开始日期" />
              <span>至</span>
              <DateTimeField mode="date" value={dateTo} onChange={setDateTo} ariaLabel="结束日期" />
            </div>
          </div>
        </form>
        {list.error && <div className="form-error">{list.error}</div>}
        {list.items.length === 0 && !list.loading ? (
          <div className="table-empty">没有符合条件的对账记录，可调整类型或筛选条件。</div>
        ) : (
          <div className="table">
            <div className="table-row finance-statement-table head">
              <span>客户</span>
              <span>主体</span>
              <span>收款银行/账户</span>
              <span>业务员</span>
              <span>金额</span>
              <span>交易时间</span>
              <span>类型</span>
            </div>
            {list.items.map((row) => (
              <div className="table-row finance-statement-table" key={row.id}>
                <span>
                  <CopyableLine text={row.customerName} label="客户">{row.customerName}</CopyableLine>
                  {row.serviceCustomerKind ? <em>{row.serviceCustomerKind}</em> : null}
                </span>
                <span>
                  <CopyableLine text={row.companyName} label="主体">{row.companyName}</CopyableLine>
                </span>
                <span className="collection-account-cell">
                  <CopyableLine text={row.accountText} label="收款银行/账户">{row.accountText}</CopyableLine>
                </span>
                <span>
                  <CopyableLine text={row.salesperson} label="业务员">{row.salesperson}</CopyableLine>
                </span>
                <span>
                  {money(row.amount)}
                  {row.txType ? <em>{row.txType}</em> : null}
                </span>
                <span>{formatDateTimeValue(row.occurredAt)}</span>
                <span>{row.businessKind}</span>
              </div>
            ))}
          </div>
        )}
        <Pagination {...list} onPageChange={list.setPage} />
      </div>
    </div>
  );
}

function Transactions({
  data,
  commit,
  applyData,
  onNotice,
  can,
  operatorName,
  onOpenProject,
}: {
  data: AppData;
  commit: (data: AppData, log?: Omit<OperationLog, "id" | "createdAt">) => Promise<void>;
  applyData: (data: AppData) => void;
  onNotice: (notice: { type: "success" | "error"; message: string }) => void;
  can: CanAccess;
  operatorName: string;
  onOpenProject: (id: string) => void;
}) {
  const [sortMode, setSortMode] = useState<"created" | "occurred">("created");
  const [search, setSearch] = useState("");
  const [selectedTransactionId, setSelectedTransactionId] = useState("");
  const [accountDraft, setAccountDraft] = useState("");
  const [savingAccount, setSavingAccount] = useState(false);
  const [validation, setValidation] = useState<FinanceValidationResult | null>(null);
  const [validationError, setValidationError] = useState("");
  const [isValidating, setIsValidating] = useState(false);
  const [previewInvoiceId, setPreviewInvoiceId] = useState("");
  const [previewProjectId, setPreviewProjectId] = useState("");
  const { requestPayment, paymentDialog } = usePaymentDialog(data);

  async function deleteTransaction(tx: Transaction) {
    const project = data.projects.find((item) => item.id === tx.projectId);
    await commit(
      { ...data, transactions: data.transactions.filter((item) => item.id !== tx.id) },
      { action: "删除交易流水", targetType: "流水", targetName: project?.name ?? tx.id, operator: "当前用户", detail: `开发环境删除 ${tx.type} ${money(tx.amount)}` },
    );
  }

  async function updateTransactionAccount(tx: Transaction) {
    if (!accountDraft) {
      window.alert("请选择收款账号。");
      return;
    }
    if (accountDraft === (findCollectionAccountItem(data, tx.account)?.id ?? tx.account)) return;
    setSavingAccount(true);
    try {
      const savedTx = await patchCollectionItem<Transaction>("transactions", tx.id, { account: accountDraft });
      let salesOrders = data.salesOrders;
      let serviceOrders = data.serviceOrders;
      if (tx.salesOrderId) {
        const savedOrder = await patchCollectionItem<SalesOrder>("salesOrders", tx.salesOrderId, { collectionAccount: accountDraft });
        salesOrders = data.salesOrders.map((order) => order.id === tx.salesOrderId ? { ...order, ...savedOrder } : order);
      }
      if (tx.serviceOrderId) {
        const savedOrder = await patchCollectionItem<ServiceOrder>("serviceOrders", tx.serviceOrderId, { collectionAccount: accountDraft });
        serviceOrders = data.serviceOrders.map((order) => order.id === tx.serviceOrderId ? { ...order, ...savedOrder } : order);
      }
      const project = data.projects.find((item) => item.id === tx.projectId);
      const log: OperationLog = {
        id: createId("log"),
        createdAt: today(),
        action: "修改收款账号",
        targetType: "流水",
        targetName: project?.name ?? tx.id,
        operator: operatorName,
        detail: `${collectionAccountText(data, tx.account)} -> ${collectionAccountText(data, accountDraft)}`,
      };
      const savedLog = await createCollectionItem<OperationLog>("operationLogs", log);
      applyData({
        ...data,
        transactions: data.transactions.map((item) => item.id === tx.id ? { ...item, ...savedTx, projectId: savedTx.projectId || item.projectId } : item),
        salesOrders,
        serviceOrders,
        operationLogs: [savedLog, ...data.operationLogs],
      });
      onNotice({ type: "success", message: "修改收款账号成功" });
    } catch (error) {
      onNotice({ type: "error", message: error instanceof Error ? error.message : "修改收款账号失败" });
    } finally {
      setSavingAccount(false);
    }
  }

  async function runFinanceValidation() {
    try {
      setIsValidating(true);
      setValidationError("");
      const result = await fetchFinanceValidation();
      const issues = visibleFinanceIssues(result.issues);
      setValidation({
        ...result,
        issues,
        summary: {
          ...result.summary,
          errors: issues.filter((item) => item.level === "error").length,
          warnings: issues.filter((item) => item.level === "warning").length,
        },
      });
    } catch (error) {
      setValidationError(error instanceof Error ? error.message : "财务一致性校验失败");
    } finally {
      setIsValidating(false);
    }
  }

  function issueOrderKind(issue: FinanceValidationIssue): "sales" | "service" | null {
    if (issue.targetType === "服务订单") return "service";
    if (issue.targetType === "销售订单") return "sales";
    return null;
  }

  function findIssueOrder(issue: FinanceValidationIssue) {
    const kind = issueOrderKind(issue);
    if (!kind) return null;
    const order = kind === "service"
      ? (data.serviceOrders.find((item) => item.id === issue.targetId) ?? data.serviceOrders.find((item) => item.orderNo === issue.targetName))
      : (data.salesOrders.find((item) => item.id === issue.targetId) ?? data.salesOrders.find((item) => item.orderNo === issue.targetName));
    return order ? { kind, order } : null;
  }

  function canBackfillIssue(issue: FinanceValidationIssue) {
    const found = findIssueOrder(issue);
    if (!found || !canBackfillCollection(can, found.kind)) return false;
    if (issue.code !== "received_transaction_mismatch" && issue.code !== "order_amount_transaction_mismatch") return false;
    if ((issue.diff ?? 0) <= 0.01) return false;
    return missingCollectionAmount(found.order.receivedAmount, collectionTxTotalForOrder(data.transactions, found.order.id, found.kind)) > 0;
  }

  async function backfillFromIssue(issue: FinanceValidationIssue) {
    const found = findIssueOrder(issue);
    if (!found || !canBackfillCollection(can, found.kind)) return;
    const ok = await backfillMissingCollectionTx({
      data,
      commit,
      requestPayment,
      kind: found.kind,
      order: found.order,
      operator: operatorName,
    });
    if (!ok) return;
    onNotice({ type: "success", message: `已为 ${found.order.orderNo} 补录收款流水` });
    setValidation((current) => {
      if (!current) return current;
      const remaining = current.issues.filter((item) => !(
        item.targetId === issue.targetId
        && item.targetType === issue.targetType
        && (item.code === "received_transaction_mismatch" || item.code === "order_amount_transaction_mismatch")
      ));
      return {
        ...current,
        issues: remaining,
        summary: {
          ...current.summary,
          errors: remaining.filter((item) => item.level === "error").length,
          warnings: remaining.filter((item) => item.level === "warning").length,
        },
      };
    });
    await runFinanceValidation();
  }

  function openIssueProject(details: FinanceValidationDetails, issue: FinanceValidationIssue) {
    const projectId = details.projectId
      || (issue.targetType === "项目" ? issue.targetId : undefined)
      || data.projects.find((project) => project.projectNo === details.projectNo || project.name === details.projectName)?.id;
    if (projectId) setPreviewProjectId(projectId);
  }

  function openIssueInvoice(issue: FinanceValidationIssue) {
    if (issue.targetType === "发票" && issue.targetId) {
      setPreviewInvoiceId(issue.targetId);
      return;
    }
    const invoice = data.invoices.find((item) => item.invoiceNo === issue.targetName);
    if (invoice) setPreviewInvoiceId(invoice.id);
  }

  async function ignoreFinanceIssue(issue: FinanceValidationIssue) {
    if (!window.confirm("忽略后下次校验不再显示该提醒，确定忽略？")) return;
    try {
      const response = await fetch(backendApiUrl("/api/validation/finance/ignore/"), {
        method: "POST",
        credentials: "include",
        headers: { "Content-Type": "application/json", Accept: "application/json" },
        body: JSON.stringify({
          code: issue.code,
          targetType: issue.targetType,
          targetId: issue.targetId,
          targetName: issue.targetName,
          message: issue.message,
        }),
      });
      throwIfAuthExpired(response);
      if (!response.ok) throw new Error("忽略失败");
      setValidation((current) => {
        if (!current) return current;
        const remaining = current.issues.filter((item) => financeIssueIgnoreKey(item) !== financeIssueIgnoreKey(issue));
        return {
          ...current,
          issues: remaining,
          summary: {
            ...current.summary,
            errors: remaining.filter((item) => item.level === "error").length,
            warnings: remaining.filter((item) => item.level === "warning").length,
          },
        };
      });
      onNotice({ type: "success", message: "已忽略该提醒" });
    } catch (error) {
      onNotice({ type: "error", message: error instanceof Error ? error.message : "忽略失败" });
    }
  }

  const totals = data.transactions.reduce(
    (acc, tx) => {
      if (tx.type === "收款" || tx.type === "后返") acc.income += tx.amount;
      if (tx.type === "付款" || tx.type === "垫付" || tx.type === "退款") acc.outcome += tx.amount;
      return acc;
    },
    { income: 0, outcome: 0 },
  );
  const transactionsPage = useServerPagedList<Transaction>({
    collection: "transactions",
    search,
    filters: { sort: sortMode === "occurred" ? "occurred" : undefined },
    pageSize: 10,
    refreshKey: `${sortMode}:${data.transactions.length}:${data.transactions[0]?.id ?? ""}`,
  });
  const selectedTransaction = data.transactions.find((transaction) => transaction.id === selectedTransactionId);
  const previewInvoice = data.invoices.find((invoice) => invoice.id === previewInvoiceId);
  const previewProject = data.projects.find((project) => project.id === previewProjectId);

  return (
    <div className="stack">
      <div className="metric-grid compact-metrics">
        <Metric label="收入流水" value={money(totals.income)} icon={Banknote} />
        <Metric label="支出/垫付/退款" value={money(totals.outcome)} icon={WalletCards} />
        <Metric label="流水条数" value={data.transactions.length.toString()} icon={ClipboardList} />
      </div>
      <div className="panel">
        <div className="panel-title action-title">
          <div>
            <h2>财务一致性校验</h2>
            <p>核对收款流水与订单金额（应收），并检查实收、发票和项目汇总。项目成本与采购合计均按未取消采购订单金额统计。不拿商品报价/明细价替代订单金额。</p>
          </div>
          <button className="ghost" onClick={() => void runFinanceValidation()} disabled={isValidating}>
            <RefreshCw size={16} />{isValidating ? "校验中..." : "运行校验"}
          </button>
        </div>
        {validationError && <div className="form-error">{validationError}</div>}
        {validation && (
          <div className="validation-panel">
            <div className="metric-grid compact-metrics">
              <Metric label="错误" value={String(validation.summary.errors)} icon={AlertTriangle} />
              <Metric label="提醒" value={String(validation.summary.warnings)} icon={ClipboardList} />
              <Metric label="校验时间" value={new Date(validation.summary.checkedAt).toLocaleString("zh-CN", { hour12: false })} icon={History} />
            </div>
            <div className="log-list">
              {validation.issues.length === 0 ? (
                <div className="empty-state">未发现财务一致性问题</div>
              ) : validation.issues.map((issue, index) => {
                const details = mergeFinanceIssueDetails(issue, data);
                const title = details.orderNo || issue.targetName || issue.targetId || "未命名";
                const rows = financeIssueDetailRows(issue, details);
                const titleOpen = issue.targetType === "发票"
                  ? () => openIssueInvoice(issue)
                  : issue.targetType === "项目"
                    ? () => openIssueProject(details, issue)
                    : undefined;
                return (
                  <article className="log-card validation-issue-card" key={`${issue.code}-${issue.targetId}-${index}`}>
                    <div>
                      <span className="tag">{issue.level === "error" ? "错误" : "提醒"}</span>
                      <strong>{issue.message}</strong>
                      <p>
                        {issue.targetType} ·{" "}
                        <CopyableLine text={title} label={issue.targetType} onOpen={titleOpen}>{title}</CopyableLine>
                      </p>
                      {rows.length > 0 && (
                        <dl className="validation-issue-details">
                          {rows.map((row) => (
                            <div key={row.label}>
                              <dt>{row.label}</dt>
                              <dd>
                                {row.copy || row.open ? (
                                  <CopyableLine
                                    text={row.value}
                                    label={row.label}
                                    onOpen={
                                      row.open === "project"
                                        ? () => openIssueProject(details, issue)
                                        : row.open === "invoice"
                                          ? () => openIssueInvoice(issue)
                                          : undefined
                                    }
                                  >
                                    {row.value}
                                  </CopyableLine>
                                ) : row.value}
                              </dd>
                            </div>
                          ))}
                        </dl>
                      )}
                    </div>
                    <div className="validation-issue-meta">
                      {typeof issue.diff === "number" && <p>差额：{money(issue.diff)}</p>}
                      {canBackfillIssue(issue) && (
                        <button type="button" className="ghost" onClick={() => void backfillFromIssue(issue)} disabled={isValidating}>
                          <Banknote size={16} />补录流水
                        </button>
                      )}
                      {canIgnoreFinanceIssue(issue) && can("finance.view") && (
                        <button type="button" className="ghost" onClick={() => void ignoreFinanceIssue(issue)} disabled={isValidating}>
                          忽略
                        </button>
                      )}
                    </div>
                  </article>
                );
              })}
            </div>
          </div>
        )}
      </div>
      <div className="panel">
        <div className="panel-title action-title">
          <div>
            <h2>交易流水台账</h2>
            <p>默认按创建时间倒序，可切换为按交易时间倒序。</p>
          </div>
        </div>
        <div className="tx-toolbar">
          <SearchField
            value={search}
            onChange={setSearch}
            placeholder="搜索项目、收款账号、交易单号、备注"
          />
          <select className="toolbar-select" value={sortMode} onChange={(event) => setSortMode(event.target.value as "created" | "occurred")}>
            <option value="created">按创建时间倒序</option>
            <option value="occurred">按交易时间倒序</option>
          </select>
        </div>
        <div className="table">
          <div className="table-row tx-table head"><span>项目</span><span>类型</span><span>金额</span><span>收款账户/公司</span><span>状态</span><span>创建/交易时间</span><span>备注</span><span>操作</span></div>
          {transactionsPage.items.map((tx) => {
            return <div className="table-row tx-table" key={tx.id}><span>{transactionProjectName(data, tx)}</span><span>{tx.type}</span><span>{money(tx.amount)}</span><span className="collection-account-cell">{collectionAccountText(data, tx.account)}</span><span>{tx.status}</span><span>{formatDateTimeValue(tx.createdAt)}<em>交易 {formatDateTimeValue(tx.occurredAt || tx.date)}</em></span><span>{tx.remark || "无"}</span><span><button className="copy-link" onClick={() => { setSelectedTransactionId(tx.id); setAccountDraft(findCollectionAccountItem(data, tx.account)?.id ?? ""); }}>详情</button>{can("finance.manage") && <button className="copy-link danger-action" onClick={() => void deleteTransaction(tx)}>删除</button>}</span></div>;
          })}
        </div>
        <Pagination {...transactionsPage} onPageChange={transactionsPage.setPage} />
      </div>
      {selectedTransaction && (
        <div className="modal-backdrop" role="presentation">
          <div className="modal" role="dialog" aria-modal="true" aria-label="流水详情">
            <div className="modal-head">
              <div><h2>流水详情</h2><p>{selectedTransaction.transactionNo || selectedTransaction.id}</p></div>
              <button className="icon-button" onClick={() => setSelectedTransactionId("")} aria-label="关闭流水详情"><X size={18} /></button>
            </div>
            <div className="info-grid">
              <Info label="项目" value={transactionProjectName(data, selectedTransaction) || "未关联项目"} />
              <Info label="类型" value={selectedTransaction.type} />
              <Info label="金额" value={money(selectedTransaction.amount)} />
              {can("finance.manage") ? (
                <div className="info" style={{ gridColumn: "span 2" }}>
                  <span>收款账户/公司</span>
                  <CollectionAccountSelect data={data} value={accountDraft} onChange={setAccountDraft} />
                </div>
              ) : (
                <Info label="收款账户/公司" value={collectionAccountText(data, selectedTransaction.account)} />
              )}
              <Info label="交易时间" value={formatDateTimeValue(selectedTransaction.occurredAt || selectedTransaction.date)} />
              <Info label="创建时间" value={formatDateTimeValue(selectedTransaction.createdAt)} />
              <Info label="交易单号" value={selectedTransaction.transactionNo || "未录入"} />
              <Info label={selectedTransaction.type === "退款" ? "打款凭证" : "收款凭证"} value={selectedTransaction.voucherName || "未上传"} />
            </div>
            <div className="modal-actions">
              {selectedTransaction.voucherFileId && <button className="ghost" onClick={() => openBusinessDocument(selectedTransaction.voucherFileId)}><FileText size={16} />{selectedTransaction.type === "退款" ? "查看打款凭证" : "查看收款凭证"}</button>}
              {can("finance.manage") && <button className="primary" disabled={savingAccount} onClick={() => void updateTransactionAccount(selectedTransaction)}>{savingAccount ? "保存中..." : "保存收款账号"}</button>}
              <button className="ghost" onClick={() => setSelectedTransactionId("")}>关闭</button>
            </div>
          </div>
        </div>
      )}
      {previewInvoice && (
        <div className="modal-backdrop" role="presentation">
          <div className="modal" role="dialog" aria-modal="true" aria-label="发票详情">
            <div className="modal-head">
              <div>
                <h2>发票详情</h2>
                <p>{previewInvoice.invoiceNo || "未录入发票号"} / {previewInvoice.invoiceDate || previewInvoice.date || "未录入日期"}</p>
              </div>
              <button className="icon-button" onClick={() => setPreviewInvoiceId("")} aria-label="关闭">×</button>
            </div>
            <InvoiceReadonlyDetail data={data} invoice={previewInvoice} />
            <div className="modal-actions">
              {previewInvoice.fileId && <button className="ghost" onClick={() => openBusinessDocument(previewInvoice.fileId)}><FileText size={16} />查看原件</button>}
              <button className="ghost" onClick={() => setPreviewInvoiceId("")}>关闭</button>
            </div>
          </div>
        </div>
      )}
      {previewProject && (
        <div className="modal-backdrop" role="presentation">
          <div className="modal" role="dialog" aria-modal="true" aria-label="项目详情">
            <div className="modal-head">
              <div>
                <h2>项目详情</h2>
                <p>{previewProject.projectNo} / {previewProject.name}</p>
              </div>
              <button className="icon-button" onClick={() => setPreviewProjectId("")} aria-label="关闭">×</button>
            </div>
            <ProjectReadonlyDetail data={data} project={previewProject} />
            <div className="modal-actions">
              {can("project.view") && (
                <button className="ghost" onClick={() => { setPreviewProjectId(""); onOpenProject(previewProject.id); }}>查看完整项目</button>
              )}
              <button className="ghost" onClick={() => setPreviewProjectId("")}>关闭</button>
            </div>
          </div>
        </div>
      )}
      {paymentDialog}
    </div>
  );
}

function RelatedLogsModal({ title, logs, onClose }: { title: string; logs: OperationLog[]; onClose: () => void }) {
  return (
    <div className="modal-backdrop" role="presentation">
      <div className="modal related-logs-modal" role="dialog" aria-modal="true" aria-label={title}>
        <div className="modal-head">
          <div><h2>{title}</h2><p>仅显示与当前记录相关的操作日志，共 {logs.length} 条。</p></div>
          <button className="icon-button" onClick={onClose} aria-label="关闭日志"><X size={18} /></button>
        </div>
        <div className="log-list related-log-list">
          {logs.length > 0 ? logs.map((log) => (
            <article className="log-card" key={log.id}>
              <div><span className="tag">{log.targetType}</span><strong>{log.action}</strong><p>{log.targetName}</p></div>
              <div><span>{log.operator}</span><em>{formatDateTimeValue(log.createdAt)}</em></div>
              <p>{log.detail || "无详情"}</p>
            </article>
          )) : <div className="empty-state">暂无相关日志</div>}
        </div>
        <div className="modal-actions"><button className="ghost" onClick={onClose}>关闭</button></div>
      </div>
    </div>
  );
}

function OperationLogs({ data, commit, can }: { data: AppData; commit: (data: AppData, log?: Omit<OperationLog, "id" | "createdAt">) => Promise<void>; can: CanAccess }) {
  const logsPage = useServerPagedList<OperationLog>({
    collection: "operationLogs",
    pageSize: 10,
    refreshKey: data.operationLogs.length,
  });

  async function deleteLog(log: OperationLog) {
    await commit(
      { ...data, operationLogs: data.operationLogs.filter((item) => item.id !== log.id) },
      { action: "删除操作日志", targetType: "系统", targetName: log.action, operator: "当前用户", detail: "开发环境允许清理日志记录" },
    );
  }

  return (
    <div className="panel">
      <PanelTitle title="系统操作日志" subtitle="记录关键业务操作；当前开发环境允许删除，正式发布后恢复只读。" />
      <div className="log-list">
        {logsPage.items.map((log) => (
          <article className="log-card" key={log.id}>
            <div>
              <span className="tag">{log.targetType}</span>
              <strong>{log.action}</strong>
              <p>{log.targetName}</p>
            </div>
            <div>
              <span>{log.operator}</span>
              <em>{new Date(log.createdAt).toLocaleString("zh-CN")}</em>
            </div>
            <p>{log.detail || "无详情"}</p>
            {can("user.manage") && <button className="copy-link danger-action" onClick={() => void deleteLog(log)}>删除</button>}
          </article>
        ))}
      </div>
      <Pagination {...logsPage} onPageChange={logsPage.setPage} />
    </div>
  );
}

function OptionSettings({ data, commit, mode = "options" }: { data: AppData; commit: (data: AppData, log?: Omit<OperationLog, "id" | "createdAt">) => Promise<void>; mode?: "accounts" | "options" }) {
  const regularOptionGroups = data.optionGroups.filter((group) => group.key !== "collection_account" && group.key !== "finance_validation_ignores");
  const [selectedGroupKey, setSelectedGroupKey] = useState(regularOptionGroups[0]?.key ?? "");
  const [newLabel, setNewLabel] = useState("");
  const [editingAccountId, setEditingAccountId] = useState("");
  const [accountForm, setAccountForm] = useState({ ownCompanyOrgId: "", bankName: "", accountNumber: "" });
  const selectedGroup = regularOptionGroups.find((group) => group.key === selectedGroupKey) ?? regularOptionGroups[0];
  const collectionAccountGroup = data.optionGroups.find((group) => group.key === "collection_account");
  const ownCompanies = data.organizations.filter((org) => isOwnCompanyOrganization(org));

  function updateOptionGroups(groups: OptionGroup[], action: string, targetName: string, detail: string) {
    return commit(
      { ...data, optionGroups: groups },
      { action, targetType: "系统", targetName, operator: "当前用户", detail },
    );
  }

  async function addOption() {
    if (!selectedGroup || !newLabel.trim()) return;
    const value = newLabel.trim();
    const exists = selectedGroup.items.some((item) => item.value === value || item.label === value);
    if (exists) return;
    const nextGroups = data.optionGroups.map((group) => group.key === selectedGroup.key
      ? {
          ...group,
          items: [
            ...group.items,
            {
              id: createId("opt"),
              label: value,
              value,
              enabled: true,
              sortOrder: group.items.length + 1,
            },
          ],
        }
      : group);
    await updateOptionGroups(nextGroups, "新增选项", selectedGroup.name, value);
    setNewLabel("");
  }

  async function toggleOption(group: OptionGroup, itemId: string) {
    const item = group.items.find((option) => option.id === itemId);
    const nextGroups = data.optionGroups.map((optionGroup) => optionGroup.key === group.key
      ? { ...optionGroup, items: optionGroup.items.map((option) => option.id === itemId ? { ...option, enabled: !option.enabled } : option) }
      : optionGroup);
    await updateOptionGroups(nextGroups, "修改选项状态", group.name, `${item?.label ?? itemId}：${item?.enabled ? "停用" : "启用"}`);
  }

  async function editOption(group: OptionGroup, itemId: string) {
    const item = group.items.find((option) => option.id === itemId);
    if (!item) return;
    const label = window.prompt("修改选项名称", item.label)?.trim();
    if (!label || label === item.label) return;
    const nextGroups = data.optionGroups.map((optionGroup) => optionGroup.key === group.key
      ? { ...optionGroup, items: optionGroup.items.map((option) => option.id === itemId ? { ...option, label, value: label } : option) }
      : optionGroup);
    await updateOptionGroups(nextGroups, "编辑选项", group.name, `${item.label} -> ${label}`);
  }

  async function deleteOption(group: OptionGroup, itemId: string) {
    const item = group.items.find((option) => option.id === itemId);
    if (!item || !window.confirm(`确定删除选项：${group.name} / ${item.label}？`)) return;
    const nextGroups = data.optionGroups.map((optionGroup) => optionGroup.key === group.key
      ? { ...optionGroup, items: optionGroup.items.filter((option) => option.id !== itemId) }
      : optionGroup);
    await updateOptionGroups(nextGroups, "删除选项", group.name, item.label);
  }

  function editCollectionAccount(itemId: string) {
    const item = collectionAccountGroup?.items.find((option) => option.id === itemId);
    if (!item) return;
    setEditingAccountId(item.id);
    setAccountForm({
      ownCompanyOrgId: item.ownCompanyOrgId ?? "",
      bankName: item.bankName ?? "",
      accountNumber: item.accountNumber ?? item.value,
    });
  }

  async function saveCollectionAccount() {
    if (!accountForm.ownCompanyOrgId || !accountForm.bankName.trim() || !accountForm.accountNumber.trim()) {
      window.alert("请选择自有主体，并填写所属银行和账号。");
      return;
    }
    const bankName = accountForm.bankName.trim();
    const accountNumber = accountForm.accountNumber.trim();
    const item = {
      id: editingAccountId || createId("opt-account"),
      label: `${bankName} ${accountNumber}`,
      value: accountNumber,
      enabled: true,
      sortOrder: editingAccountId
        ? collectionAccountGroup?.items.find((option) => option.id === editingAccountId)?.sortOrder ?? 1
        : (collectionAccountGroup?.items.length ?? 0) + 1,
      ownCompanyOrgId: accountForm.ownCompanyOrgId,
      bankName,
      accountNumber,
    };
    const nextGroup: OptionGroup = collectionAccountGroup
      ? {
          ...collectionAccountGroup,
          items: editingAccountId
            ? collectionAccountGroup.items.map((option) => option.id === editingAccountId ? item : option)
            : [...collectionAccountGroup.items, item],
        }
      : {
          id: "optgrp-collection_account",
          key: "collection_account",
          name: "收款账号",
          description: "维护订单收款时可选择的银行卡收款账号。",
          usages: ["系统设置：收款账号管理", "订单收款：收款账号"],
          items: [item],
        };
    const nextGroups = collectionAccountGroup
      ? data.optionGroups.map((group) => group.key === nextGroup.key ? nextGroup : group)
      : [...data.optionGroups, nextGroup];
    await updateOptionGroups(nextGroups, editingAccountId ? "编辑收款账号" : "新增收款账号", bankName, accountNumber);
    setEditingAccountId("");
    setAccountForm({ ownCompanyOrgId: "", bankName: "", accountNumber: "" });
  }

  return (
    <div className="stack">
      {mode === "accounts" && (
      <div className="panel">
        <div className="panel-title action-title">
          <div>
            <h2>收款账号管理</h2>
            <p>维护银行卡收款时可选择的自有主体、所属银行和账号。</p>
          </div>
        </div>
        <div className="collection-account-form">
          <select value={accountForm.ownCompanyOrgId} onChange={(event) => setAccountForm({ ...accountForm, ownCompanyOrgId: event.target.value })}>
            <option value="">请选择自有主体</option>
            {ownCompanies.map((org) => <option key={org.id} value={org.id}>{org.name}</option>)}
          </select>
          <input value={accountForm.bankName} onChange={(event) => setAccountForm({ ...accountForm, bankName: event.target.value })} placeholder="所属银行" />
          <input value={accountForm.accountNumber} onChange={(event) => setAccountForm({ ...accountForm, accountNumber: event.target.value })} placeholder="账号" />
          <button className="primary" onClick={() => void saveCollectionAccount()}>{editingAccountId ? "保存修改" : "添加收款账号"}</button>
          {editingAccountId && <button className="ghost" onClick={() => {
            setEditingAccountId("");
            setAccountForm({ ownCompanyOrgId: "", bankName: "", accountNumber: "" });
          }}>取消编辑</button>}
        </div>
        <div className="table">
          <div className="table-row collection-account-table head"><span>自有主体</span><span>所属银行</span><span>账号</span><span>状态</span><span>操作</span></div>
          {[...(collectionAccountGroup?.items ?? [])].sort((a, b) => a.sortOrder - b.sortOrder).map((item) => (
            <div className="table-row collection-account-table" key={item.id}>
              <span>{ownCompanies.find((org) => org.id === item.ownCompanyOrgId)?.name || "未设置"}</span>
              <span>{item.bankName || "未设置"}</span>
              <span>{item.accountNumber || item.value}</span>
              <span>{item.enabled ? "启用" : "停用"}</span>
              <span className="option-actions">
                <button className="copy-link" onClick={() => editCollectionAccount(item.id)}>编辑</button>
                {collectionAccountGroup && <button className="copy-link" onClick={() => void toggleOption(collectionAccountGroup, item.id)}>{item.enabled ? "停用" : "启用"}</button>}
              </span>
            </div>
          ))}
        </div>
      </div>
      )}
      {mode === "options" && (
      <div className="split settings-split">
      <div className="panel list-panel">
        <PanelTitle title="选项分类" subtitle="每个分类都标明会影响哪些页面和下拉框。" />
        <div className="option-group-list">
          {regularOptionGroups.map((group) => (
            <button key={group.key} className={`row-card option-group-card ${selectedGroup?.key === group.key ? "selected" : ""}`} onClick={() => setSelectedGroupKey(group.key)}>
              <span>{group.name}</span>
              <strong>{group.items.filter((item) => item.enabled).length} 个启用</strong>
              <em>{group.key}</em>
            </button>
          ))}
        </div>
      </div>
      <div className="panel">
        {selectedGroup ? (
          <>
            <div className="panel-title action-title">
              <div>
                <h2>{selectedGroup.name}</h2>
                <p>{selectedGroup.description || "维护该分类下拉选项；停用后不再出现在对应下拉框。"}</p>
              </div>
            </div>
            <div className="usage-list">
              {selectedGroup.usages.map((usage) => <span key={usage}>{usage}</span>)}
            </div>
            <div className="option-add-row">
              <input value={newLabel} onChange={(event) => setNewLabel(event.target.value)} placeholder="新增选项名称" />
              <button className="primary" onClick={() => void addOption()}><BadgeCheck size={16} />新增选项</button>
            </div>
            <div className="table">
              <div className="table-row option-table head"><span>显示名称</span><span>保存值</span><span>排序</span><span>状态</span><span>操作</span></div>
              {[...selectedGroup.items].sort((a, b) => a.sortOrder - b.sortOrder).map((item) => (
                <div className="table-row option-table" key={item.id}>
                  <span>{item.label}</span>
                  <span>{item.value}</span>
                  <span>{item.sortOrder}</span>
                  <span>{item.enabled ? "启用" : "停用"}</span>
                  <span className="option-actions">
                    <button className="copy-link" onClick={() => void editOption(selectedGroup, item.id)}>编辑</button>
                    <button className="copy-link" onClick={() => void toggleOption(selectedGroup, item.id)}>{item.enabled ? "停用" : "启用"}</button>
                  </span>
                </div>
              ))}
            </div>
          </>
        ) : (
          <div className="empty-state">暂无选项分类。</div>
        )}
      </div>
      </div>
      )}
    </div>
  );
}

function AccessControl({ data, commit }: { data: AppData; commit: (data: AppData, log?: Omit<OperationLog, "id" | "createdAt">) => Promise<void> }) {
  const [name, setName] = useState("");
  const [phone, setPhone] = useState("");
  const [password, setPassword] = useState("123456");
  const [roleId, setRoleId] = useState(data.roles[0]?.id ?? "");
  const [editingUser, setEditingUser] = useState<User | null>(null);
  const [editForm, setEditForm] = useState({
    name: "",
    phone: "",
    password: "",
    roleIds: [] as string[],
    status: "启用" as User["status"],
  });
  const [editingRole, setEditingRole] = useState<Role | null>(null);
  const [showCreateRole, setShowCreateRole] = useState(false);
  const [roleForm, setRoleForm] = useState({
    name: "",
    description: "",
    permissions: [] as PermissionKey[],
  });
  const [savingAction, setSavingAction] = useState<"user" | "role" | "create-role" | "add-user" | "">("");

  useEffect(() => {
    if (!data.roles.some((role) => role.id === roleId)) {
      setRoleId(data.roles[0]?.id ?? "");
    }
  }, [data.roles, roleId]);

  async function addUser() {
    if (savingAction) return;
    if (!name.trim()) {
      window.alert("请输入用户姓名。");
      return;
    }
    if (!roleId) {
      window.alert("请先创建或选择用户角色。");
      return;
    }
    const user: User = {
      id: createId("user"),
      name,
      phone: phone || undefined,
      password: password || "123456",
      roleIds: [roleId],
      status: "启用",
      createdAt: today(),
    };
    try {
      setSavingAction("add-user");
      await commit(
        { ...data, users: [user, ...data.users] },
        { action: "新增用户", targetType: "用户", targetName: user.name, operator: "当前用户", detail: `角色：${data.roles.find((role) => role.id === roleId)?.name}` },
      );
      setName("");
      setPhone("");
      setPassword("123456");
    } catch {
      // 全局提交提示负责展示错误，保留表单内容便于修正后重试。
    } finally {
      setSavingAction("");
    }
  }

  async function toggleUser(userId: string) {
    const target = data.users.find((user) => user.id === userId);
    if (!target) return;
    const nextStatus = target.status === "启用" ? "停用" : "启用";
    await commit(
      {
        ...data,
        users: data.users.map((user) => (user.id === userId ? { ...user, status: nextStatus } : user)),
      },
      { action: `${nextStatus}用户`, targetType: "用户", targetName: target.name, operator: "当前用户" },
    );
  }

  async function deleteUser(user: User) {
    await commit(
      { ...data, users: data.users.filter((item) => item.id !== user.id) },
      { action: "删除用户", targetType: "用户", targetName: user.name, operator: "当前用户", detail: "开发环境允许删除用户测试数据" },
    );
  }

  function openEditUser(user: User) {
    setEditingUser(user);
    setEditForm({
      name: user.name,
      phone: user.phone ?? "",
      // 留空表示不改密码（接口会剥离 password，勿把旧值回填）。
      password: "",
      roleIds: user.roleIds,
      status: user.status,
    });
  }

  function toggleEditRole(roleId: string) {
    setEditForm((current) => ({
      ...current,
      roleIds: current.roleIds.includes(roleId)
        ? current.roleIds.filter((id) => id !== roleId)
        : [...current.roleIds, roleId],
    }));
  }

  async function saveEditUser() {
    if (!editingUser || !editForm.name.trim() || editForm.roleIds.length === 0 || savingAction) return;
    const nextUser: User = {
      ...editingUser,
      name: editForm.name.trim(),
      phone: editForm.phone.trim() || undefined,
      password: editForm.password || undefined,
      roleIds: editForm.roleIds,
      status: editForm.status,
    };
    try {
      setSavingAction("user");
      await commit(
        { ...data, users: data.users.map((user) => (user.id === editingUser.id ? nextUser : user)) },
        { action: "编辑用户", targetType: "用户", targetName: nextUser.name, operator: "当前用户", detail: `角色：${roleNames(nextUser)}；状态：${nextUser.status}` },
      );
      setEditingUser(null);
    } catch {
      // 保存失败时保持弹窗打开。
    } finally {
      setSavingAction("");
    }
  }

  function openCreateRole() {
    setEditingRole(null);
    setRoleForm({ name: "", description: "", permissions: [] });
    setShowCreateRole(true);
  }

  function openEditRole(role: Role) {
    setShowCreateRole(false);
    setEditingRole(role);
    setRoleForm({
      name: role.name,
      description: role.description,
      permissions: [...role.permissions],
    });
  }

  async function saveEditRole() {
    if (!editingRole || !roleForm.name.trim() || roleForm.permissions.length === 0 || savingAction) return;
    const nextRole: Role = {
      ...editingRole,
      name: roleForm.name.trim(),
      description: roleForm.description.trim(),
      permissions: roleForm.permissions,
    };
    try {
      setSavingAction("role");
      await commit(
        { ...data, roles: data.roles.map((role) => (role.id === editingRole.id ? nextRole : role)) },
        { action: "编辑角色", targetType: "权限", targetName: nextRole.name, operator: "当前用户", detail: `${editingRole.name} -> ${nextRole.name}；${nextRole.permissions.length} 个权限点` },
      );
      setEditingRole(null);
      setRoleForm({ name: "", description: "", permissions: [] });
    } catch {
      // 保存失败时保持弹窗打开。
    } finally {
      setSavingAction("");
    }
  }

  function toggleRolePermission(permission: PermissionKey) {
    setRoleForm((current) => ({
      ...current,
      permissions: current.permissions.includes(permission)
        ? current.permissions.filter((item) => item !== permission)
        : [...current.permissions, permission],
    }));
  }

  async function addRole() {
    if (!roleForm.name.trim() || roleForm.permissions.length === 0 || savingAction) return;
    const role: Role = {
      id: createId("role"),
      name: roleForm.name.trim(),
      description: roleForm.description.trim() || "自定义角色",
      permissions: roleForm.permissions,
    };
    try {
      setSavingAction("create-role");
      await commit(
        { ...data, roles: [...data.roles, role] },
        { action: "新增角色", targetType: "权限", targetName: role.name, operator: "当前用户", detail: `${role.permissions.length} 个权限点` },
      );
      setShowCreateRole(false);
      setRoleForm({ name: "", description: "", permissions: [] });
    } catch {
      // 保存失败时保持弹窗打开。
    } finally {
      setSavingAction("");
    }
  }

  function roleNames(user: User) {
    return user.roleIds.map((id) => data.roles.find((role) => role.id === id)?.name).filter(Boolean).join("、");
  }
  const usersPage = useServerPagedList<User>({
    collection: "users",
    pageSize: 10,
    refreshKey: data.users,
  });
  const rolesPage = useServerPagedList<Role>({
    collection: "roles",
    pageSize: 10,
    refreshKey: data.roles,
  });

  return (
    <div className="stack">
      <div className="two-col access-layout">
        <div className="panel">
          <PanelTitle title="用户管理" subtitle="验证用户、角色和启停规则；当前开发环境允许删除。" />
          <div className="user-form">
            <input value={name} onChange={(event) => setName(event.target.value)} placeholder="姓名" />
            <input value={phone} onChange={(event) => setPhone(event.target.value)} placeholder="手机号" />
            <input value={password} onChange={(event) => setPassword(event.target.value)} placeholder="初始密码" />
            <select value={roleId} onChange={(event) => setRoleId(event.target.value)}>
              {data.roles.map((role) => <option value={role.id} key={role.id}>{role.name}</option>)}
            </select>
            <button className="primary" disabled={!!savingAction} onClick={() => void addUser()}><UserPlus size={16} />{savingAction === "add-user" ? "保存中..." : "新增用户"}</button>
          </div>
          <div className="user-list">
            {usersPage.items.map((user) => (
              <article className="user-card" key={user.id}>
                <div>
                  <CopyableLine text={user.name} label="用户姓名">
                    <strong>{user.name}</strong>
                  </CopyableLine>
                  <span>{user.phone || "暂无手机号"} · {roleNames(user)}</span>
                </div>
                <em className={user.status === "启用" ? "status-on" : "status-off"}>{user.status}</em>
                <button className="ghost" onClick={() => openEditUser(user)}>编辑</button>
                <button className="ghost" onClick={() => toggleUser(user.id)}>{user.status === "启用" ? "停用" : "启用"}</button>
                <button className="ghost danger-action" onClick={() => void deleteUser(user)}><Trash2 size={15} />删除</button>
              </article>
            ))}
          </div>
          <Pagination {...usersPage} onPageChange={usersPage.setPage} />
        </div>
        <div className="panel">
          <div className="panel-title action-title">
            <div>
              <h2>角色说明</h2>
              <p>小团队可一人多角色，系统按角色叠加权限。</p>
            </div>
            <button className="primary" onClick={openCreateRole}><UserPlus size={16} />新增角色</button>
          </div>
          <div className="role-list">
            {rolesPage.items.map((role) => (
              <article className="role-card" key={role.id}>
                <div>
                  <CopyableLine text={role.name} label="角色名称">
                    <strong>{role.name}</strong>
                  </CopyableLine>
                  <p>{role.description}</p>
                  <span>{role.permissions.length} 个权限点</span>
                </div>
                <button className="ghost" onClick={() => openEditRole(role)}>编辑</button>
              </article>
            ))}
          </div>
          <Pagination {...rolesPage} onPageChange={rolesPage.setPage} />
        </div>
      </div>
      <div className="panel">
        <PanelTitle title="权限矩阵" subtitle="权限点由系统功能定义，通过角色勾选分配；已包含平台账号查看/管理。" />
        <div className="permission-table">
          <div className="permission-row permission-head">
            <span>权限点</span>
            {data.roles.map((role) => <strong key={role.id}>{role.name}</strong>)}
          </div>
          {permissionGroups.map((group) => (
            <div className="permission-group" key={group.title}>
              <div className="permission-section">{group.title}</div>
              {group.keys.map((key) => (
                <div className="permission-row" key={key}>
                  <span>{permissionLabels[key]}</span>
                  {data.roles.map((role) => (
                    <b key={role.id} className={role.permissions.includes(key) ? "allowed" : "denied"}>
                      {role.permissions.includes(key) ? "允许" : "无"}
                    </b>
                  ))}
                </div>
              ))}
            </div>
          ))}
        </div>
      </div>
      {editingUser && (
        <div className="modal-backdrop" role="presentation">
          <div className="modal user-edit-modal" role="dialog" aria-modal="true" aria-label="编辑用户">
            <div className="modal-head">
              <div>
                <h2>编辑用户</h2>
                <p>修改用户基础信息、登录密码、状态和角色权限。</p>
              </div>
              <button className="icon-button" onClick={() => setEditingUser(null)} aria-label="关闭编辑用户"><X size={18} /></button>
            </div>
            <div className="user-edit-form">
              <input value={editForm.name} onChange={(event) => setEditForm({ ...editForm, name: event.target.value })} placeholder="姓名" />
              <input value={editForm.phone} onChange={(event) => setEditForm({ ...editForm, phone: event.target.value })} placeholder="手机号" />
              <input
                type="password"
                value={editForm.password}
                onChange={(event) => setEditForm({ ...editForm, password: event.target.value })}
                placeholder="重置密码（留空则不改）"
                autoComplete="new-password"
              />
              <select value={editForm.status} onChange={(event) => setEditForm({ ...editForm, status: event.target.value as User["status"] })}>
                <option>启用</option>
                <option>停用</option>
              </select>
              <div className="role-check-list">
                {data.roles.map((role) => (
                  <label key={role.id}>
                    <input type="checkbox" checked={editForm.roleIds.includes(role.id)} onChange={() => toggleEditRole(role.id)} />
                    <span>{role.name}</span>
                  </label>
                ))}
              </div>
            </div>
            <div className="modal-actions">
              <button className="ghost" onClick={() => setEditingUser(null)}>取消</button>
              <button className="primary" disabled={!!savingAction || !editForm.name.trim() || editForm.roleIds.length === 0} onClick={() => void saveEditUser()}>{savingAction === "user" ? "保存中..." : "保存修改"}</button>
            </div>
          </div>
        </div>
      )}
      {editingRole && (
        <div className="modal-backdrop" role="presentation">
          <div className="modal role-create-modal" role="dialog" aria-modal="true" aria-label="编辑角色">
            <div className="modal-head">
              <div>
                <h2>编辑角色</h2>
                <p>可修改角色名称、说明和权限点；保存后立即对已分配该角色的用户生效。</p>
              </div>
              <button className="icon-button" onClick={() => setEditingRole(null)} aria-label="关闭编辑角色"><X size={18} /></button>
            </div>
            <div className="role-edit-form">
              <input value={roleForm.name} onChange={(event) => setRoleForm({ ...roleForm, name: event.target.value })} placeholder="角色名称" />
              <textarea value={roleForm.description} onChange={(event) => setRoleForm({ ...roleForm, description: event.target.value })} placeholder="角色说明" />
              <div className="role-permission-list">
                {permissionGroups.map((group) => (
                  <div className="permission-check-group" key={group.title}>
                    <strong>{group.title}</strong>
                    {group.keys.map((key) => (
                      <label key={key}>
                        <input type="checkbox" checked={roleForm.permissions.includes(key)} onChange={() => toggleRolePermission(key)} />
                        <span>{permissionLabels[key]}</span>
                      </label>
                    ))}
                  </div>
                ))}
              </div>
            </div>
            <div className="modal-actions">
              <button className="ghost" onClick={() => setEditingRole(null)}>取消</button>
              <button className="primary" disabled={!!savingAction || !roleForm.name.trim() || roleForm.permissions.length === 0} onClick={() => void saveEditRole()}>{savingAction === "role" ? "保存中..." : "保存修改"}</button>
            </div>
          </div>
        </div>
      )}
      {showCreateRole && (
        <div className="modal-backdrop" role="presentation">
          <div className="modal role-create-modal" role="dialog" aria-modal="true" aria-label="新增角色">
            <div className="modal-head">
              <div>
                <h2>新增角色</h2>
                <p>创建后可在新增用户和编辑用户时分配该角色。</p>
              </div>
              <button className="icon-button" onClick={() => setShowCreateRole(false)} aria-label="关闭新增角色"><X size={18} /></button>
            </div>
            <div className="role-edit-form">
              <input value={roleForm.name} onChange={(event) => setRoleForm({ ...roleForm, name: event.target.value })} placeholder="角色名称" />
              <textarea value={roleForm.description} onChange={(event) => setRoleForm({ ...roleForm, description: event.target.value })} placeholder="角色说明" />
              <div className="role-permission-list">
                {permissionGroups.map((group) => (
                  <div className="permission-check-group" key={group.title}>
                    <strong>{group.title}</strong>
                    {group.keys.map((key) => (
                      <label key={key}>
                        <input type="checkbox" checked={roleForm.permissions.includes(key)} onChange={() => toggleRolePermission(key)} />
                        <span>{permissionLabels[key]}</span>
                      </label>
                    ))}
                  </div>
                ))}
              </div>
            </div>
            <div className="modal-actions">
              <button className="ghost" onClick={() => setShowCreateRole(false)}>取消</button>
              <button className="primary" disabled={!!savingAction || !roleForm.name.trim() || roleForm.permissions.length === 0} onClick={() => void addRole()}>{savingAction === "create-role" ? "保存中..." : "保存角色"}</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

export function SearchableSelect({
  value,
  options,
  onChange,
  placeholder,
  ariaLabel,
}: {
  value: string;
  options: SearchableSelectOption[];
  onChange: (value: string) => void;
  placeholder: string;
  ariaLabel: string;
}) {
  const [query, setQuery] = useState("");
  const [open, setOpen] = useState(false);
  const selected = options.find((option) => option.value === value);
  const normalizedQuery = query.trim().toLowerCase();
  const filteredOptions = normalizedQuery
    ? options.filter((option) => displayOption(option).toLowerCase().includes(normalizedQuery))
    : options;
  const inputValue = open ? query : selected ? selected.label : "";

  function displayOption(option: SearchableSelectOption) {
    return option.detail ? `${option.label}｜${option.detail}` : option.label;
  }

  function selectOption(option: SearchableSelectOption) {
    onChange(option.value);
    setQuery("");
    setOpen(false);
  }

  function clearValue(event: { preventDefault: () => void; stopPropagation: () => void }) {
    event.preventDefault();
    event.stopPropagation();
    onChange("");
    setQuery("");
    setOpen(true);
  }

  const showClear = Boolean(value) || Boolean(query);

  return (
    <div className={`searchable-select${showClear ? " has-clear" : ""}`}>
      <input
        value={inputValue}
        onChange={(event) => {
          setQuery(event.target.value);
          setOpen(true);
        }}
        onFocus={() => {
          setQuery("");
          setOpen(true);
        }}
        onClick={() => {
          setQuery("");
          setOpen(true);
        }}
        onBlur={() => window.setTimeout(() => setOpen(false), 120)}
        onKeyDown={(event) => {
          if (event.key === "Escape") {
            setQuery("");
            setOpen(false);
          }
          if (event.key === "Enter" && filteredOptions[0]) {
            event.preventDefault();
            selectOption(filteredOptions[0]);
          }
        }}
        placeholder={placeholder}
        aria-label={ariaLabel}
        role="combobox"
        aria-expanded={open}
      />
      {showClear ? (
        <button
          type="button"
          className="search-clear searchable-select-clear"
          aria-label={`清空${ariaLabel}`}
          onMouseDown={clearValue}
        >
          <X size={14} />
        </button>
      ) : null}
      <span className="searchable-select-arrow" aria-hidden="true">▾</span>
      {open && (
        <div className="searchable-select-menu">
          {filteredOptions.length > 0 ? filteredOptions.map((option) => (
            <button
              type="button"
              key={option.value}
              className={option.value === value ? "selected" : ""}
              onMouseDown={(event) => {
                event.preventDefault();
                selectOption(option);
              }}
            >
              <span>{option.label}</span>
              {option.detail && <em>{option.detail}</em>}
            </button>
          )) : <div className="searchable-select-empty">无匹配数据</div>}
        </div>
      )}
    </div>
  );
}

function Info({ label, value }: { label: string; value?: string | number }) {
  return (
    <div className="info">
      <span>{label}</span>
      <strong>{value || "未录入"}</strong>
    </div>
  );
}
