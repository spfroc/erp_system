import { openDB } from "idb";
import { backendApiUrl } from "./apiConfig";
import {
  DEFAULT_ACCEPTANCE_STATUS,
  DEFAULT_DELIVERY_STATUS,
  DEFAULT_INSTALLATION_STATUS,
  DEFAULT_LOGISTICS_STATUS,
  DEFAULT_ORDER_PAYMENT_STATUS,
  DEFAULT_RECONCILE_STATUS,
  mapLegacyAcceptanceStatus,
  mapLegacyContractStatus,
  mapLegacyDeliveryStatus,
  mapLegacyInvoiceDisplayStatus,
  mapLegacyLogisticsStatus,
  mapLegacyPaymentStatus,
  mapLegacyProductProjectStatus,
  productProjectBlocker,
  aggregateFulfillmentFromPurchaseOrders,
  reconcileInvoiceProjectIds,
} from "./productProjectFlow";
import { seedData } from "./seed";
import type { AppData, OptionGroup, PurchaseOrder, WebsiteLead } from "./types";
import { formatShopCategories, type ServiceContractDraft, type ServiceContractFileFormat } from "./serviceContract";

const DB_NAME = "yicai-erp-prototype";
const STORE = "app";
const KEY = "data";
const API_PATH = "/api/app-data/";
/** 普通写入只提交变更行；全量同步仍可能较大，生产保存不再依赖短超时。 */
const API_TIMEOUT_MS = 60_000;

async function getDatabase() {
  return openDB(DB_NAME, 1, {
    upgrade(db) {
      db.createObjectStore(STORE);
    },
  });
}

function apiUrl(path: string) {
  return backendApiUrl(path);
}

export function migrateData(current: Partial<AppData>): AppData {
  const migrated = {
    ...seedData,
    ...current,
    organizations: current.organizations ?? seedData.organizations,
    users: (current.users ?? seedData.users).map((user) => ({ ...user, password: user.password || undefined })),
    roles: current.roles ?? seedData.roles,
    operationLogs: current.operationLogs ?? seedData.operationLogs,
    platformAccounts: current.platformAccounts ?? seedData.platformAccounts,
    websiteLeads: current.websiteLeads ?? seedData.websiteLeads,
    projectReminders: current.projectReminders ?? seedData.projectReminders,
    projectMemos: current.projectMemos ?? seedData.projectMemos,
    optionGroups: current.optionGroups ?? seedData.optionGroups,
    salesOrders: current.salesOrders ?? seedData.salesOrders ?? [],
    purchaseOrders: current.purchaseOrders ?? seedData.purchaseOrders ?? [],
    serviceOrders: current.serviceOrders ?? seedData.serviceOrders ?? [],
    trademarkCertificates: current.trademarkCertificates ?? seedData.trademarkCertificates ?? [],
  } as AppData;
  migrated.organizations = migrated.organizations.map((organization) => ({
    ...organization,
    roles: organization.roles.map((role) => (Object.assign({} as Record<string, string>, {
      客户: "终端采购人",
      供应商: "上游供应商",
      平台入驻客户: "平台入驻商",
      本方主体: "自有主体",
      使用单位: "使用单位",
    })[role] ?? role)) as AppData["organizations"][number]["roles"],
  }));
  migrated.roles = migrated.roles.map((role) => ({
    ...role,
    permissions: Array.from(new Set(role.permissions ?? [])),
  }));
  migrated.salesOrders = migrated.salesOrders.map((order) => {
    const legacyStatus = order.status as string;
    const status = legacyStatus === "已完成" || legacyStatus === "待发货" || legacyStatus === "部分发货"
      ? "已付款"
      : legacyStatus === "已取消"
        ? "取消"
        : legacyStatus === "退款"
          ? "退款"
          : legacyStatus === "取消"
            ? "取消"
            : legacyStatus === "已付款"
              ? "已付款"
              : "待付款";
    return {
      ...order,
      receivableAmount: order.receivableAmount ?? order.amount,
      receivedAmount: order.receivedAmount ?? (status === "已付款" ? order.amount : 0),
      status,
      paidAt: status === "已付款" ? (order.paidAt ?? order.updatedAt ?? order.createdAt) : order.paidAt,
      refundedAt: status === "退款" ? (order.refundedAt ?? order.updatedAt ?? order.createdAt) : order.refundedAt,
      cancelledAt: status === "取消" ? (order.cancelledAt ?? order.updatedAt ?? order.createdAt) : order.cancelledAt,
    };
  });
  migrated.serviceOrders = migrated.serviceOrders.map((order) => {
    const legacyStatus = order.status as string;
    const status = legacyStatus === "部分付款" || legacyStatus === "已付款" || legacyStatus === "退款" || legacyStatus === "取消" ? legacyStatus : "待付款";
    return {
      ...order,
      receivableAmount: order.receivableAmount ?? order.amount,
      receivedAmount: order.receivedAmount ?? (status === "已付款" ? order.amount : 0),
      status,
      paidAt: status === "已付款" ? (order.paidAt ?? order.updatedAt ?? order.createdAt) : order.paidAt,
      refundedAt: status === "退款" ? (order.refundedAt ?? order.updatedAt ?? order.createdAt) : order.refundedAt,
      cancelledAt: status === "取消" ? (order.cancelledAt ?? order.updatedAt ?? order.createdAt) : order.cancelledAt,
    };
  });
  const configuredServiceStatuses = migrated.optionGroups
    .find((group) => group.key === "service_project_status")
    ?.items.filter((item) => item.enabled)
    .map((item) => item.value) ?? [];

  const ensureOptionGroup = (key: string) => {
    const seedGroup = seedData.optionGroups.find((group) => group.key === key);
    if (!seedGroup) return;
    const existing = migrated.optionGroups.find((group) => group.key === key);
    if (!existing) {
      migrated.optionGroups = [...migrated.optionGroups, seedGroup];
      return;
    }
    if (key === "project_status" || key === "logistics_status" || key === "acceptance_status" || key === "delivery_status" || key === "contract_status" || key === "reconcile_status" || key === "website_lead_status") {
      migrated.optionGroups = migrated.optionGroups.map((group) => {
        if (group.key !== key) return group;
        return {
          ...group,
          name: seedGroup.name,
          description: seedGroup.description,
          usages: seedGroup.usages,
          items: seedGroup.items.map((seedItem, index) => {
            const matched = group.items.find((item) => item.value === seedItem.value);
            return matched
              ? { ...matched, label: seedItem.label, value: seedItem.value, enabled: true, sortOrder: index + 1 }
              : { ...seedItem, sortOrder: index + 1 };
          }),
        };
      });
    }
  };
  ["project_status", "logistics_status", "acceptance_status", "delivery_status", "installation_status", "contract_status", "reconcile_status", "purchase_payment_status", "website_lead_status"].forEach(ensureOptionGroup);

  migrated.projects = migrated.projects.map((project) => {
    const seedProject = seedData.projects.find((item) => item.id === project.id);
    const type = ((project.type as string) === "平台入驻服务" || (project.type as string) === "服务项目" ? "服务项目" : "商品项目") as AppData["projects"][number]["type"];
    // 线上历史选项仍可能使用“到期 / 结束 / 终止合作”。这些都是有效的
    // 终态，不能在每次加载迁移时回退为“入驻中”。
    const serviceStatusValues = new Set([
      ...configuredServiceStatuses,
      "入驻中",
      "服务中",
      "服务交付完成",
      "服务到期结束",
      "服务完成",
      "服务到期",
      "项目终止",
      "到期",
      "结束",
      "终止合作",
    ]);
    const status = type === "服务项目"
      ? (!serviceStatusValues.has(project.status) ? "入驻中" : project.status)
      : mapLegacyProductProjectStatus(project.status, migrated, project.id);
    const nextProject = {
      ...project,
      type,
      status,
      ownCompanyOrgId: project.ownCompanyOrgId ?? seedProject?.ownCompanyOrgId ?? "org-7",
      platformOrderNo: project.platformOrderNo ?? seedProject?.platformOrderNo,
      serviceProductId: project.serviceProductId ?? seedProject?.serviceProductId,
      serviceProductName: project.serviceProductName ?? seedProject?.serviceProductName,
      serviceType: project.serviceType ?? seedProject?.serviceType ?? (type === "服务项目" ? "周期" : undefined),
      serviceStartDate: project.serviceStartDate ?? seedProject?.serviceStartDate ?? (type === "服务项目" ? (project.updatedAt ?? new Date().toISOString()).slice(0, 10) : undefined),
      serviceEndDate: project.serviceEndDate ?? seedProject?.serviceEndDate,
      servicePeriodUnit: project.servicePeriodUnit ?? seedProject?.servicePeriodUnit,
      servicePeriodValue: project.servicePeriodValue ?? seedProject?.servicePeriodValue,
      serviceGiftMonths: project.serviceGiftMonths ?? seedProject?.serviceGiftMonths ?? 0,
      serviceSalesUserId: project.serviceSalesUserId ?? seedProject?.serviceSalesUserId,
      serviceSalesName: project.serviceSalesName ?? seedProject?.serviceSalesName ?? project.owner,
      serviceOperatorUserId: project.serviceOperatorUserId ?? seedProject?.serviceOperatorUserId,
      serviceOperatorName: project.serviceOperatorName ?? seedProject?.serviceOperatorName,
      serviceRemark: project.serviceRemark ?? seedProject?.serviceRemark,
      contractStatus: mapLegacyContractStatus(project.contractStatus),
      paymentStatus: mapLegacyPaymentStatus(project.paymentStatus as string),
      invoiceStatus: mapLegacyInvoiceDisplayStatus(project.invoiceStatus as string),
      reconcileStatus: project.reconcileStatus ?? DEFAULT_RECONCILE_STATUS,
      logisticsStatus: type === "商品项目" ? mapLegacyLogisticsStatus(project.logisticsStatus as string) : undefined,
      acceptanceStatus: type === "商品项目" ? mapLegacyAcceptanceStatus(project.acceptanceStatus as string) : undefined,
      deliveryStatus: type === "商品项目"
        ? mapLegacyDeliveryStatus((project.deliveryStatus ?? project.installationStatus) as string)
        : undefined,
      acceptanceRemark: project.acceptanceRemark ?? "",
      deliveryRemark: project.deliveryRemark ?? project.installationRemark ?? "",
      createdAt: project.createdAt ?? seedProject?.createdAt ?? project.updatedAt ?? new Date().toISOString(),
    };
    return {
      ...nextProject,
      currentBlocker: type === "商品项目"
        ? productProjectBlocker(migrated, nextProject)
        : (project.currentBlocker ?? seedProject?.currentBlocker),
    };
  });
  if (migrated.serviceOrders.length === 0) {
    migrated.serviceOrders = migrated.projects
      .filter((project) => project.type === "服务项目")
      .map((project, index) => {
        const legacyOrder = migrated.salesOrders.find((order) => order.projectId === project.id);
        return {
          id: `svc-${project.id}`,
          orderNo: `SV-${project.projectNo || String(index + 1).padStart(3, "0")}-01`,
          projectId: project.id,
          serviceId: project.serviceProductId ?? migrated.projectItems.find((item) => item.projectId === project.id)?.productId ?? "prd-3",
          customerOrgId: project.customerOrgId,
          amount: legacyOrder?.amount ?? project.totalAmount,
          status: (project.paymentStatus as string) === "已付款" || (project.paymentStatus as string) === "已收" ? "已付款" : "待付款",
          paymentMethod: "银行转账",
          salesUserId: project.serviceSalesUserId,
          salesName: project.serviceSalesName ?? project.owner,
          createdAt: legacyOrder?.createdAt ?? project.createdAt ?? project.updatedAt ?? new Date().toISOString(),
          updatedAt: legacyOrder?.createdAt ?? project.updatedAt ?? new Date().toISOString(),
          paidAt: (project.paymentStatus as string) === "已付款" || (project.paymentStatus as string) === "已收" ? legacyOrder?.createdAt ?? project.updatedAt : undefined,
          note: legacyOrder?.note ?? "由旧服务项目自动生成",
        };
      });
  }
  if (migrated.salesOrders.length === 0) {
    migrated.salesOrders = migrated.projects.map((project, index) => ({
      id: `so-${project.id}`,
      projectId: project.id,
      orderNo: `SO-${project.projectNo || String(index + 1).padStart(3, "0")}`,
      platform: project.sourcePlatform,
      platformOrderNo: project.platformOrderNo,
      customerOrgId: project.customerOrgId,
      ownCompanyOrgId: project.ownCompanyOrgId,
      amount: project.totalAmount,
      status: project.status === "已完成" ? "已付款" : "待付款",
      createdAt: project.updatedAt ?? new Date().toISOString(),
      note: "由旧项目数据自动生成",
    }));
  }
  const resolvePurchaseUnitCost = (
    productId: string,
    quantityCostPrice: number | undefined,
    supplierOrgId?: string,
  ) => {
    if (quantityCostPrice && quantityCostPrice > 0) return quantityCostPrice;
    const supplierPrice = supplierOrgId
      ? migrated.supplierPrices
          .filter((price) => price.productId === productId && price.supplierOrgId === supplierOrgId)
          .sort((a, b) => (b.effectiveDate || "").localeCompare(a.effectiveDate || ""))[0]
      : migrated.supplierPrices
          .filter((price) => price.productId === productId)
          .sort((a, b) => (b.effectiveDate || "").localeCompare(a.effectiveDate || ""))[0];
    if (supplierPrice?.purchasePrice) return supplierPrice.purchasePrice;
    return migrated.products.find((product) => product.id === productId)?.costPrice ?? 0;
  };

  if (migrated.purchaseOrders.length === 0) {
    migrated.purchaseOrders = migrated.projects
      .filter((project) => project.type === "商品项目")
      .flatMap((project, index) => {
        const items = migrated.projectItems.filter((projectItem) => projectItem.projectId === project.id);
        const item = items[0];
        const supplierPrice = item
          ? migrated.supplierPrices
              .filter((price) => price.productId === item.productId)
              .sort((a, b) => (b.effectiveDate || "").localeCompare(a.effectiveDate || ""))[0]
          : undefined;
        if (!supplierPrice && items.length === 0) return [];
        const supplierOrgId = supplierPrice?.supplierOrgId ?? item?.supplierOrgId;
        if (!supplierOrgId) return [];
        const amount = items.reduce((sum, projectItem) => {
          const unitCost = resolvePurchaseUnitCost(projectItem.productId, projectItem.costPrice, supplierOrgId);
          return sum + projectItem.quantity * unitCost;
        }, 0);
        return [{
          id: `po-${project.id}`,
          projectId: project.id,
          orderNo: `PO-${project.projectNo || String(index + 1).padStart(3, "0")}`,
          supplierOrgId,
          ownCompanyOrgId: project.ownCompanyOrgId,
          amount: amount || project.totalCost || 0,
          status: project.purchaseStatus === "已完成" ? "已完成" : "待下单",
          createdAt: project.updatedAt ?? new Date().toISOString(),
          note: "由旧项目数据自动生成",
        }];
      });
  }
  migrated.projectItems = migrated.projectItems.map((item) => {
    const salesOrder = migrated.salesOrders.find((order) => order.projectId === item.projectId);
    const purchaseOrder = migrated.purchaseOrders.find((order) => order.projectId === item.projectId);
    const supplierOrgId = item.supplierOrgId ?? purchaseOrder?.supplierOrgId;
    const supplierPrice = supplierOrgId
      ? migrated.supplierPrices
          .filter((price) => price.productId === item.productId && price.supplierOrgId === supplierOrgId)
          .sort((a, b) => (b.effectiveDate || "").localeCompare(a.effectiveDate || ""))[0]
      : undefined;
    const costPrice = resolvePurchaseUnitCost(item.productId, item.costPrice, supplierOrgId);
    // 销售/采购明细分别回填关联，避免销售行误挂采购单、采购行误挂销售单。
    let nextSalesOrderId = item.salesOrderId;
    let nextPurchaseOrderId = item.purchaseOrderId;
    const looksLikeSales = Number(item.actualPrice) > 0;
    const looksLikePurchase = Number(item.actualPrice) === 0 && (Number(item.costPrice) > 0 || Number(costPrice) > 0);
    if (!nextSalesOrderId && !nextPurchaseOrderId) {
      if (looksLikeSales) nextSalesOrderId = salesOrder?.id;
      else nextPurchaseOrderId = purchaseOrder?.id;
    } else {
      if (!nextSalesOrderId && looksLikeSales) nextSalesOrderId = salesOrder?.id;
      if (!nextPurchaseOrderId && looksLikePurchase && !looksLikeSales) nextPurchaseOrderId = purchaseOrder?.id;
    }
    return {
      ...item,
      salesOrderId: nextSalesOrderId,
      purchaseOrderId: nextPurchaseOrderId,
      supplierOrgId,
      supplierPriceId: item.supplierPriceId ?? supplierPrice?.id,
      costPrice,
    };
  });
  // 修复历史脏数据：销售明细误挂采购单、采购明细误挂销售单。
  // 旧项目一行同时挂销售+采购时，拆成销售行（保留 sourcePurchaseOrderId）和采购行。
  const existingItemIds = new Set(migrated.projectItems.map((item) => item.id));
  const purchaseClones: typeof migrated.projectItems = [];
  migrated.projectItems = migrated.projectItems.map((item) => {
    if (!(item.salesOrderId && item.purchaseOrderId)) return item;
    if (Number(item.actualPrice) > 0) {
      const hasPurchaseOnlySibling = migrated.projectItems.some(
        (other) => other.id !== item.id && other.purchaseOrderId === item.purchaseOrderId && !other.salesOrderId,
      );
      if (!hasPurchaseOnlySibling) {
        const cloneId = `pi-po-${item.id}`;
        if (!existingItemIds.has(cloneId)) {
          purchaseClones.push({
            ...item,
            id: cloneId,
            salesOrderId: undefined,
            sourcePurchaseOrderId: undefined,
            actualPrice: 0,
          });
          existingItemIds.add(cloneId);
        }
      }
      return {
        ...item,
        sourcePurchaseOrderId: item.sourcePurchaseOrderId || item.purchaseOrderId,
        purchaseOrderId: undefined,
      };
    }
    if (Number(item.costPrice) > 0) {
      return { ...item, salesOrderId: undefined };
    }
    return item;
  });
  if (purchaseClones.length) {
    migrated.projectItems = [...migrated.projectItems, ...purchaseClones];
  }
  const isPurchaseLineItem = (item: { salesOrderId?: string; actualPrice?: number; costPrice?: number }) => {
    if (!item.salesOrderId) return true;
    return Number(item.actualPrice) === 0 && Number(item.costPrice) > 0;
  };
  migrated.purchaseOrders = migrated.purchaseOrders.map((order) => {
    let items = migrated.projectItems.filter(
      (item) => item.purchaseOrderId === order.id && isPurchaseLineItem(item),
    );
    if (items.length === 0) {
      items = migrated.projectItems.filter((item) => item.purchaseOrderId === order.id);
    }
    if (items.length === 0) {
      const projectPurchaseOrders = migrated.purchaseOrders.filter((item) => item.projectId === order.projectId);
      if (projectPurchaseOrders.length === 1) {
        items = migrated.projectItems.filter(
          (item) => item.projectId === order.projectId && isPurchaseLineItem(item),
        );
      }
    }
    const computedAmount = items.reduce((sum, item) => {
      const unitCost = resolvePurchaseUnitCost(item.productId, item.costPrice, order.supplierOrgId || item.supplierOrgId);
      return sum + item.quantity * unitCost;
    }, 0);
    const project = migrated.projects.find((item) => item.id === order.projectId);
    const projectPurchaseCount = migrated.purchaseOrders.filter((item) => item.projectId === order.projectId).length;
    const copyProjectFulfillment = project?.type === "商品项目" && projectPurchaseCount === 1;
    const next: PurchaseOrder = {
      ...order,
      amount: (!order.amount || order.amount <= 0) && computedAmount > 0 ? computedAmount : order.amount,
      paymentStatus: order.paymentStatus
        ?? (order.status === "已完成" ? "已付款" : DEFAULT_ORDER_PAYMENT_STATUS),
      reconcileStatus: order.reconcileStatus ?? DEFAULT_RECONCILE_STATUS,
      contractStatus: mapLegacyContractStatus(order.contractStatus ?? "待签"),
      logisticsStatus: order.logisticsStatus
        ?? (copyProjectFulfillment ? mapLegacyLogisticsStatus(project?.logisticsStatus as string) : DEFAULT_LOGISTICS_STATUS),
      acceptanceStatus: order.acceptanceStatus
        ?? (copyProjectFulfillment ? mapLegacyAcceptanceStatus(project?.acceptanceStatus as string) : DEFAULT_ACCEPTANCE_STATUS),
      deliveryStatus: order.deliveryStatus
        ?? (copyProjectFulfillment
          ? mapLegacyDeliveryStatus((project?.deliveryStatus ?? project?.installationStatus) as string)
          : DEFAULT_DELIVERY_STATUS),
      logisticsNo: order.logisticsNo,
      contractFileId: order.contractFileId,
      contractFileName: order.contractFileName,
    };
    return next;
  });
  migrated.projects = migrated.projects.map((project) => {
    if (project.type !== "商品项目") return project;
    const totalCost = Math.round(
      migrated.purchaseOrders
        .filter((order) => order.projectId === project.id && order.status !== "已取消")
        .reduce((sum, order) => sum + (Number(order.amount) || 0), 0) * 100,
    ) / 100;
    const fulfillment = aggregateFulfillmentFromPurchaseOrders(
      migrated.purchaseOrders.filter((order) => order.projectId === project.id),
    );
    return {
      ...project,
      totalCost,
      logisticsStatus: fulfillment.logisticsStatus,
      acceptanceStatus: fulfillment.acceptanceStatus,
      deliveryStatus: fulfillment.deliveryStatus,
      currentBlocker: productProjectBlocker(migrated, {
        ...project,
        logisticsStatus: fulfillment.logisticsStatus,
        acceptanceStatus: fulfillment.acceptanceStatus,
        deliveryStatus: fulfillment.deliveryStatus,
      }),
    };
  });
  migrated.salesOrders = migrated.salesOrders.map((order) => {
    const fulfillment = aggregateFulfillmentFromPurchaseOrders(
      migrated.purchaseOrders.filter((item) => item.projectId === order.projectId),
    );
    return {
      ...order,
      logisticsStatus: fulfillment.logisticsStatus,
      acceptanceStatus: fulfillment.acceptanceStatus,
      deliveryStatus: fulfillment.deliveryStatus,
    };
  });
  migrated.invoices = migrated.invoices.map((invoice) => {
    const seedInvoice = seedData.invoices.find((item) => item.id === invoice.id);
    let merged = { ...seedInvoice, ...invoice };
    merged.projectIds = merged.projectIds ?? (merged.projectId ? [merged.projectId] : []);
    if (!merged.projectId && merged.projectIds.length > 0) merged.projectId = merged.projectIds[0];
    merged.salesOrderIds = merged.salesOrderIds ?? [];
    merged.purchaseOrderIds = merged.purchaseOrderIds ?? [];
    if (merged.invoiceNo === "26372000002896402906") {
      merged = {
        ...merged,
        buyerName: "郓城金木商贸销售有限公司",
        buyerTaxNo: "91371725MA3WE8QPXA",
        sellerName: "山东壹知产数字科技有限公司",
        sellerTaxNo: "91370103MA3T1BXA6N",
        amountWithoutTax: 12831.86,
        taxAmount: 1668.14,
        amount: 14500,
      };
    }
    return reconcileInvoiceProjectIds(migrated, merged);
  });
  migrated.websiteLeads = migrated.websiteLeads.map((lead) => {
    const raw = String(lead.status || "");
    const status = (raw === "未处理" ? "未跟进" : raw === "已处理" ? "已跟进" : raw || "未跟进") as WebsiteLead["status"];
    return { ...lead, status, memos: lead.memos ?? [] };
  });
  return migrated;
}

async function loadLocalData(): Promise<AppData | null> {
  const db = await getDatabase();
  const current = await db.get(STORE, KEY);
  return current ? migrateData(current as Partial<AppData>) : null;
}

async function clearLocalData(): Promise<void> {
  const db = await getDatabase();
  await db.delete(STORE, KEY);
}

async function fetchWithTimeout(input: RequestInfo | URL, init: RequestInit = {}, timeoutMs = API_TIMEOUT_MS) {
  const controller = new AbortController();
  const timeout = window.setTimeout(() => controller.abort(), timeoutMs);
  try {
    const response = await fetch(input, { credentials: "include", ...init, signal: controller.signal });
    if (response.status === 401 && !isAuthLoginRequest(input)) {
      notifyAuthExpired();
      throw new AuthExpiredError();
    }
    return response;
  } catch (error) {
    if (error instanceof AuthExpiredError) throw error;
    if (error instanceof DOMException && error.name === "AbortError") {
      throw new Error("请求超时，请稍后重试");
    }
    throw error;
  } finally {
    window.clearTimeout(timeout);
  }
}

export const AUTH_EXPIRED_EVENT = "erp-auth-expired";

export class AuthExpiredError extends Error {
  constructor() {
    super("登录已过期，请重新登录");
    this.name = "AuthExpiredError";
  }
}

function isAuthLoginRequest(input: RequestInfo | URL) {
  return String(input).includes("/api/auth/login/");
}

function notifyAuthExpired() {
  window.dispatchEvent(new Event(AUTH_EXPIRED_EVENT));
}

function purchaseOrderRepairFingerprint(data: Partial<AppData> | AppData) {
  return JSON.stringify({
    purchaseOrders: (data.purchaseOrders ?? []).map((order) => [order.id, Number(order.amount) || 0]),
    projectItems: (data.projectItems ?? []).map((item) => [item.id, item.purchaseOrderId ?? "", Number(item.costPrice) || 0]),
  });
}

async function fetchServerData(): Promise<{ raw: Partial<AppData> | null; data: AppData | null }> {
  const response = await fetchWithTimeout(apiUrl(API_PATH), { headers: { Accept: "application/json" } });
  if (!response.ok) throw new Error("服务端数据读取失败");
  const payload = await response.json() as { data: Partial<AppData> | null };
  return {
    raw: payload.data,
    data: payload.data ? migrateData(payload.data) : null,
  };
}

export type CollectionDeleteIds = Partial<Record<keyof AppData, string[]>>;

async function saveServerData(
  data: Partial<AppData>,
  partial = false,
  deleteIds?: CollectionDeleteIds,
): Promise<AppData | null> {
  const body: { data: Partial<AppData>; partial: boolean; deleteIds?: CollectionDeleteIds } = { data, partial };
  if (partial && deleteIds && Object.keys(deleteIds).length) {
    body.deleteIds = deleteIds;
  }
  const response = await fetchWithTimeout(apiUrl(API_PATH), {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!response.ok) {
    if (response.status === 401) throw new Error("登录已过期，请重新登录");
    if (response.status === 403) throw new Error("当前账号没有执行此操作的权限");
    let detail = "";
    try {
      const payload = await response.json() as { detail?: string };
      detail = payload.detail ?? "";
    } catch {
      // 非 JSON 错误响应使用统一提示。
    }
    throw new Error(detail ? `服务端数据保存失败：${detail}` : "服务端数据保存失败，请稍后重试");
  }
  const payload = await response.json() as { data?: Partial<AppData> | null; partial?: boolean };
  if (!payload.data) {
    if (partial) return null;
    throw new Error("服务端数据保存失败");
  }
  return migrateData(payload.data);
}

function dataRecordCount(data: AppData): number {
  return [
    data.users,
    data.roles,
    data.organizations,
    data.products,
    data.supplierPrices,
    data.projects,
    data.projectItems,
    data.salesOrders,
    data.purchaseOrders,
    data.serviceOrders,
    data.onboardingRecords,
    data.platformAccounts,
    data.websiteLeads,
    data.projectReminders,
    data.projectMemos,
    data.optionGroups,
    data.invoices,
    data.transactions,
    data.operationLogs,
    data.ocrJobs,
    data.trademarkCertificates,
  ].reduce((total, collection) => total + collection.length, 0);
}

export async function loadData(): Promise<AppData> {
  const localData = await loadLocalData();
  let serverRaw: Partial<AppData> | null = null;
  let serverData: AppData | null;

  try {
    const fetched = await fetchServerData();
    serverRaw = fetched.raw;
    serverData = fetched.data;
  } catch (error) {
    console.error("Server database is unavailable.", error);
    throw new Error("服务端数据库不可用，请先启动后端服务。", { cause: error });
  }

  if (serverData) {
    if (localData && dataRecordCount(localData) > dataRecordCount(serverData)) {
      await saveServerData(localData);
      await clearLocalData();
      return localData;
    }
    await clearLocalData();
    // 只回写采购订单/明细修复，避免每次打开页面都 PUT 整包 app-data 把页面卡住。
    if (serverRaw && purchaseOrderRepairFingerprint(serverRaw) !== purchaseOrderRepairFingerprint(serverData)) {
      try {
        await saveServerData({
          purchaseOrders: serverData.purchaseOrders,
          projectItems: serverData.projectItems,
        }, true);
      } catch (error) {
        console.error("Failed to persist purchase order repairs.", error);
      }
    }
    return serverData;
  }

  const initialData = localData ?? seedData;
  try {
    await saveServerData(initialData);
  } catch (error) {
    console.error("Server data initialization failed.", error);
    throw new Error("服务端数据库初始化失败。", { cause: error });
  }
  await clearLocalData();
  return initialData;
}

export function diffPartialAppData(previous: AppData, next: AppData): {
  upserts: Partial<AppData>;
  deleteIds: CollectionDeleteIds;
} {
  const upserts: Partial<AppData> = {};
  const deleteIds: CollectionDeleteIds = {};
  (Object.keys(next) as Array<keyof AppData>).forEach((key) => {
    if (next[key] === previous[key]) return;
    const prevItems = previous[key];
    const nextItems = next[key];
    if (!Array.isArray(prevItems) || !Array.isArray(nextItems)) return;
    const prevById = new Map(prevItems.map((item) => [item.id, item]));
    const nextIdSet = new Set(nextItems.map((item) => item.id));
    const changed = nextItems.filter((item) => prevById.get(item.id) !== item);
    const removed = prevItems.filter((item) => !nextIdSet.has(item.id)).map((item) => item.id);
    if (changed.length) {
      (upserts as Record<string, unknown[]>)[key] = changed;
    }
    if (removed.length) deleteIds[key] = removed;
  });
  return { upserts, deleteIds };
}

export async function saveData(
  data: Partial<AppData>,
  partial = false,
  deleteIds?: CollectionDeleteIds,
): Promise<AppData | null> {
  const saved = await saveServerData(data, partial, deleteIds);
  await clearLocalData();
  return saved;
}

export async function resetData(): Promise<AppData> {
  await saveServerData(seedData);
  await clearLocalData();
  return seedData;
}

export type CollectionListQuery = {
  page?: number;
  pageSize?: number;
  search?: string;
  filters?: Record<string, string | number | boolean | undefined | null>;
  includeDeleted?: boolean;
  paged?: boolean;
};

export type CollectionListResult<T> = {
  items: T[];
  total: number;
  page: number;
  pageSize: number;
};

export async function queryCollection<T = Record<string, unknown>>(
  collection: string,
  query: CollectionListQuery = {},
): Promise<CollectionListResult<T>> {
  const params = new URLSearchParams();
  const paged = query.paged !== false;
  if (paged) {
    params.set("paged", "1");
    params.set("page", String(Math.max(1, query.page ?? 1)));
    params.set("page_size", String(Math.min(100, Math.max(1, query.pageSize ?? 20))));
  }
  if (query.search?.trim()) params.set("search", query.search.trim());
  if (query.includeDeleted) params.set("includeDeleted", "1");
  if (query.filters) {
    for (const [key, value] of Object.entries(query.filters)) {
      if (value === undefined || value === null || value === "") continue;
      params.set(key, String(value));
    }
  }
  const response = await fetchWithTimeout(apiUrl(`/api/collections/${encodeURIComponent(collection)}/?${params.toString()}`), {
    headers: { Accept: "application/json" },
  });
  if (!response.ok) {
    if (response.status === 401) throw new Error("登录已过期，请重新登录");
    if (response.status === 403) throw new Error("当前账号没有执行此操作的权限");
    throw new Error("列表数据加载失败");
  }
  const payload = await response.json() as {
    items?: T[];
    total?: number;
    page?: number;
    page_size?: number;
    data?: T[];
  };
  if (Array.isArray(payload.items)) {
    return {
      items: payload.items,
      total: Number(payload.total ?? payload.items.length),
      page: Number(payload.page ?? query.page ?? 1),
      pageSize: Number(payload.page_size ?? query.pageSize ?? 20),
    };
  }
  const data = Array.isArray(payload.data) ? payload.data : [];
  return {
    items: data,
    total: data.length,
    page: 1,
    pageSize: data.length || (query.pageSize ?? 20),
  };
}

export async function createCollectionItem<T>(collection: string, record: T): Promise<T> {
  const response = await fetchWithTimeout(apiUrl(`/api/collections/${encodeURIComponent(collection)}/`), {
    method: "POST",
    headers: { "Content-Type": "application/json", Accept: "application/json" },
    body: JSON.stringify({ data: record }),
  });
  if (!response.ok) {
    if (response.status === 401) throw new Error("登录已过期，请重新登录");
    if (response.status === 403) throw new Error("当前账号没有执行此操作的权限");
    let detail = "";
    try {
      const payload = await response.json() as { detail?: string };
      detail = (payload.detail ?? "").trim();
    } catch {
      // ignore non-json
    }
    throw new Error(detail || "保存失败，请稍后重试");
  }
  const payload = await response.json() as { data: T };
  return payload.data;
}

export async function patchCollectionItem<T>(
  collection: string,
  recordId: string,
  patch: Partial<T>,
): Promise<T> {
  const response = await fetchWithTimeout(apiUrl(`/api/collections/${encodeURIComponent(collection)}/${encodeURIComponent(recordId)}/`), {
    method: "PATCH",
    headers: { "Content-Type": "application/json", Accept: "application/json" },
    body: JSON.stringify({ data: patch }),
  });
  if (!response.ok) {
    if (response.status === 401) throw new Error("登录已过期，请重新登录");
    if (response.status === 403) throw new Error("当前账号没有执行此操作的权限");
    let detail = "";
    try {
      const payload = await response.json() as { detail?: string };
      detail = (payload.detail ?? "").trim();
    } catch {
      // ignore non-json
    }
    throw new Error(detail || "保存失败，请稍后重试");
  }
  const payload = await response.json() as { data: T };
  return payload.data;
}

export async function deleteCollectionItem(collection: string, recordId: string): Promise<void> {
  const response = await fetchWithTimeout(apiUrl(`/api/collections/${encodeURIComponent(collection)}/${encodeURIComponent(recordId)}/`), {
    method: "DELETE",
    headers: { Accept: "application/json" },
  });
  if (!response.ok) {
    if (response.status === 401) throw new Error("登录已过期，请重新登录");
    if (response.status === 403) throw new Error("当前账号没有执行此操作的权限");
    let detail = "";
    try {
      const payload = await response.json() as { detail?: string };
      detail = (payload.detail ?? "").trim();
    } catch {
      // 非 JSON 错误使用统一提示。
    }
    if (response.status === 409) throw new Error(detail || "当前数据仍被引用，无法删除");
    throw new Error(detail || "删除失败，请稍后重试");
  }
}

export async function downloadServiceContract(projectId: string, draft: ServiceContractDraft, format: ServiceContractFileFormat = "word") {
  const response = await fetchWithTimeout(apiUrl(`/api/projects/${encodeURIComponent(projectId)}/generate-contract/`), {
    method: "POST",
    headers: { "Content-Type": "application/json", Accept: "application/octet-stream" },
    body: JSON.stringify({ ...contractDownloadPayload(draft), format }),
  }, 90_000);
  await saveContractDownload(response, draft, format);
}

export async function downloadStandaloneServiceContract(platform: string, draft: ServiceContractDraft, format: ServiceContractFileFormat = "word") {
  const response = await fetchWithTimeout(apiUrl("/api/contracts/generate/"), {
    method: "POST",
    headers: { "Content-Type": "application/json", Accept: "application/octet-stream" },
    body: JSON.stringify({ ...contractDownloadPayload(draft), platform, format }),
  }, 90_000);
  await saveContractDownload(response, draft, format);
}

function contractDownloadPayload(draft: ServiceContractDraft) {
  return {
    ...draft,
    shopCategory: formatShopCategories(draft.shopCategories),
    partyASigner: "",
    partyBSigner: "",
  };
}

async function saveContractDownload(response: Response, draft: ServiceContractDraft, format: ServiceContractFileFormat = "word") {
  if (!response.ok) {
    if (response.status === 403) throw new Error("当前账号没有执行此操作的权限");
    let detail = "";
    try {
      const payload = await response.json() as { detail?: string };
      detail = (payload.detail ?? "").trim();
    } catch {
      // 非 JSON 错误使用统一提示。
    }
    throw new Error(detail || "生成合同失败，请稍后重试");
  }
  const blob = await response.blob();
  const ext = format === "pdf" ? "pdf" : "docx";
  const fallback = `${draft.partyAName || draft.shopName || "服务合同"}-服务合同.${ext}`;
  const filename = filenameFromDisposition(response.headers.get("Content-Disposition"), fallback);
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  link.remove();
  window.setTimeout(() => URL.revokeObjectURL(url), 1000);
}

function filenameFromDisposition(header: string | null, fallback: string) {
  if (!header) return fallback;
  const utf = header.match(/filename\*=UTF-8''([^;]+)/i);
  if (utf?.[1]) {
    try {
      return decodeURIComponent(utf[1]);
    } catch {
      return fallback;
    }
  }
  const ascii = header.match(/filename="?([^";]+)"?/i);
  return ascii?.[1] || fallback;
}

export function createId(prefix: string) {
  if (typeof crypto !== "undefined" && typeof crypto.randomUUID === "function") {
    return `${prefix}-${crypto.randomUUID().slice(0, 8)}`;
  }

  if (typeof crypto !== "undefined" && typeof crypto.getRandomValues === "function") {
    const values = new Uint32Array(2);
    crypto.getRandomValues(values);
    return `${prefix}-${Array.from(values, (value) => value.toString(16).padStart(8, "0")).join("").slice(0, 8)}`;
  }

  return `${prefix}-${Date.now().toString(36)}${Math.random().toString(36).slice(2, 6)}`;
}
