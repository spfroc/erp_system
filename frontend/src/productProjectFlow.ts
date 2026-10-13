import type {
  AcceptanceStatus,
  AppData,
  ContractStatus,
  DeliveryStatus,
  Invoice,
  InvoiceDisplayStatus,
  InvoiceLineItem,
  LogisticsStatus,
  OrderPaymentStatus,
  Product,
  Project,
  ProjectItem,
  ProjectStatus,
  PurchaseOrder,
  ReconcileStatus,
  SalesOrder,
} from "./types";

export const PRODUCT_PROJECT_STATUSES: ProjectStatus[] = ["初始化", "进行中", "已完成", "终止"];

export const DEFAULT_LOGISTICS_STATUS: LogisticsStatus = "待发货";
export const DEFAULT_ACCEPTANCE_STATUS: AcceptanceStatus = "待验收";
export const DEFAULT_DELIVERY_STATUS: DeliveryStatus = "待交付";
export const DEFAULT_RECONCILE_STATUS: ReconcileStatus = "待对账";
export const DEFAULT_CONTRACT_STATUS: ContractStatus = "待签";
export const DEFAULT_ORDER_PAYMENT_STATUS: OrderPaymentStatus = "待付款";
export const DEFAULT_INVOICE_DISPLAY_STATUS: InvoiceDisplayStatus = "待开";

export function isCatalogProduct(product: Pick<Product, "source">) {
  return product.source !== "project";
}

export function isProjectScopedProduct(product: Pick<Product, "source" | "sourceProjectId">, projectId?: string) {
  if (product.source !== "project") return false;
  return !projectId || product.sourceProjectId === projectId;
}

export function buildProjectScopedProduct(params: {
  id: string;
  projectId: string;
  projectNo: string;
  name: string;
  platformPrice: number;
  createdAt: string;
}): Product {
  const name = params.name.trim();
  return {
    id: params.id,
    code: `PJ-${params.projectNo}-${params.id.replace(/^prd-/, "")}`,
    name,
    kind: "实体商品",
    category: "项目商品",
    frameworkPrice: params.platformPrice,
    quotePrice: params.platformPrice,
    costPrice: 0,
    source: "project",
    sourceProjectId: params.projectId,
    createdAt: params.createdAt,
    updatedAt: params.createdAt,
  };
}

/** @deprecated 兼容旧引用 */
export const DEFAULT_INSTALLATION_STATUS = DEFAULT_DELIVERY_STATUS;

const LEGACY_PRODUCT_STATUSES = new Set<string>([
  "已付款待办理",
  "待签/待收款",
  "待采购/平台操作",
  "履约中",
  "待开票/待结算",
  "异常",
]);

export function isPurchaseLineItem(item: { salesOrderId?: string; actualPrice?: number; costPrice?: number }) {
  if (!item.salesOrderId) return true;
  return Number(item.actualPrice) === 0 && Number(item.costPrice) > 0;
}

/** 销售订单明细：有销售单号且不是纯采购行。旧数据可能同时挂了采购单号。 */
export function salesOrderLineItems<T extends { salesOrderId?: string; actualPrice?: number; costPrice?: number }>(
  items: T[],
  orderId: string,
) {
  return items.filter((item) => item.salesOrderId === orderId && !isPurchaseLineItem(item));
}

export function hasProductSalesOrder(data: Pick<AppData, "salesOrders">, projectId: string) {
  return data.salesOrders.some((order) => order.projectId === projectId);
}

export function hasProductPurchaseOrder(data: Pick<AppData, "purchaseOrders">, projectId: string) {
  return data.purchaseOrders.some((order) => order.projectId === projectId);
}

export function activePurchaseOrders(data: Pick<AppData, "purchaseOrders">, projectId: string) {
  return data.purchaseOrders.filter((order) => order.projectId === projectId && order.status !== "已取消");
}

export function mapLegacyLogisticsStatus(value?: string): LogisticsStatus {
  if (value === "已签收" || value === "已到货") return "已签收";
  if (value === "已发货" || value === "运输中" || value === "部分发货") return "已发货";
  return "待发货";
}

export function mapLegacyAcceptanceStatus(value?: string): AcceptanceStatus {
  if (value === "已验收") return "已验收";
  if (value === "验收中" || value === "部分验收") return "验收中";
  return "待验收";
}

export function mapLegacyDeliveryStatus(value?: string): DeliveryStatus {
  if (value === "已交付" || value === "已安装") return "已交付";
  if (value === "部分交付") return "部分交付";
  if (value === "交付中" || value === "安装中") return "交付中";
  return "待交付";
}

export function mapLegacyPaymentStatus(value?: string): OrderPaymentStatus {
  if (value === "已付款" || value === "已收" || value === "垫付已清") return "已付款";
  if (value === "部分付款" || value === "部分收" || value === "垫付未清") return "部分付款";
  if (value === "退款") return "退款";
  if (value === "取消") return "取消";
  return "待付款";
}

export function mapLegacyInvoiceDisplayStatus(value?: string): InvoiceDisplayStatus {
  if (value === "已开全部" || value === "已开" || value === "已开票") return "已开全部";
  if (value === "已开部分" || value === "部分开") return "已开部分";
  if (value === "无需") return "无需";
  return "待开";
}

export function mapLegacyContractStatus(value?: string): ContractStatus {
  if (value === "无需" || value === "待签" || value === "已签" || value === "已发送") return value;
  return "待签";
}

export type FulfillmentAggregate = {
  logisticsStatus: LogisticsStatus;
  acceptanceStatus: AcceptanceStatus;
  deliveryStatus: DeliveryStatus;
};

/** 多渠道采购履约汇总：全员终态才升终态，否则取保守进展态。 */
export function aggregateFulfillmentFromPurchaseOrders(orders: PurchaseOrder[]): FulfillmentAggregate {
  const active = orders.filter((order) => order.status !== "已取消");
  if (active.length === 0) {
    return {
      logisticsStatus: DEFAULT_LOGISTICS_STATUS,
      acceptanceStatus: DEFAULT_ACCEPTANCE_STATUS,
      deliveryStatus: DEFAULT_DELIVERY_STATUS,
    };
  }

  const logistics = active.map((order) => order.logisticsStatus ?? DEFAULT_LOGISTICS_STATUS);
  const acceptance = active.map((order) => order.acceptanceStatus ?? DEFAULT_ACCEPTANCE_STATUS);
  const delivery = active.map((order) => order.deliveryStatus ?? DEFAULT_DELIVERY_STATUS);

  let logisticsStatus: LogisticsStatus = DEFAULT_LOGISTICS_STATUS;
  if (logistics.every((item) => item === "已签收")) logisticsStatus = "已签收";
  else if (logistics.some((item) => item === "已发货" || item === "已签收")) logisticsStatus = "已发货";

  let acceptanceStatus: AcceptanceStatus = DEFAULT_ACCEPTANCE_STATUS;
  if (acceptance.every((item) => item === "已验收")) acceptanceStatus = "已验收";
  else if (acceptance.some((item) => item === "验收中" || item === "已验收")) acceptanceStatus = "验收中";

  let deliveryStatus: DeliveryStatus = DEFAULT_DELIVERY_STATUS;
  if (delivery.every((item) => item === "已交付")) deliveryStatus = "已交付";
  else if (delivery.some((item) => item === "已交付") && delivery.some((item) => item !== "已交付")) deliveryStatus = "部分交付";
  else if (delivery.some((item) => item === "交付中" || item === "部分交付")) {
    deliveryStatus = delivery.some((item) => item === "部分交付") ? "部分交付" : "交付中";
  }

  return { logisticsStatus, acceptanceStatus, deliveryStatus };
}

export function deriveInvoiceStatus(linkedInvoices: Invoice[], orderAmount: number): InvoiceDisplayStatus {
  const active = linkedInvoices.filter((invoice) => invoice.status !== "作废");
  if (active.length === 0 || orderAmount <= 0) return "待开";
  const invoiced = active.reduce((sum, invoice) => sum + (Number(invoice.amount) || 0), 0);
  if (invoiced <= 0) return "待开";
  if (invoiced + 0.009 >= orderAmount) return "已开全部";
  return "已开部分";
}

export function invoiceLineGrossAmount(item: { amount?: number; taxAmount?: number }) {
  return Math.round(((Number(item.amount) || 0) + (Number(item.taxAmount) || 0)) * 100) / 100;
}

function moneyCents(value: number) {
  return Math.round((Number(value) + Number.EPSILON) * 100);
}

export function invoiceLineAssignedOrderId(
  line: { salesOrderId?: string; purchaseOrderId?: string },
  orderType: "sales" | "purchase",
) {
  return orderType === "purchase" ? line.purchaseOrderId : line.salesOrderId;
}

/** 默认勾选：发票行价税合计与订单行「数量×单价」一对一相等；已关联任意订单的行不预选。 */
export function defaultInvoiceLinePickIndexes(
  lines: Array<{ amount?: number; taxAmount?: number; salesOrderId?: string; purchaseOrderId?: string }>,
  orderItems: Array<{ lineAmount: number }>,
  orderId?: string,
  orderType?: "sales" | "purchase",
) {
  const remaining = orderItems.map((item) => moneyCents(item.lineAmount));
  const indexes: number[] = [];
  lines.forEach((line, index) => {
    const assignedId = orderType ? invoiceLineAssignedOrderId(line, orderType) : (line.salesOrderId || line.purchaseOrderId);
    if (orderId && assignedId) return;
    const matchAt = remaining.indexOf(moneyCents(invoiceLineGrossAmount(line)));
    if (matchAt < 0) return;
    remaining.splice(matchAt, 1);
    indexes.push(index);
  });
  return indexes;
}

export function allocatedInvoiceLineGross(
  item: { quantity?: number; amount?: number; taxAmount?: number },
  quantity?: number,
) {
  const originalQty = Number(item.quantity) || 0;
  const gross = invoiceLineGrossAmount(item);
  if (!quantity || !originalQty || quantity >= originalQty) return gross;
  return Math.round((gross * (quantity / originalQty) + Number.EPSILON) * 100) / 100;
}

function roundMoneyValue(value: number) {
  return Math.round((Number(value) + Number.EPSILON) * 100) / 100;
}

export function scaleInvoiceLine(item: InvoiceLineItem, quantity: number): InvoiceLineItem {
  const originalQty = Number(item.quantity) || 0;
  if (originalQty <= 0 || quantity === originalQty) return { ...item, quantity };
  const ratio = quantity / originalQty;
  const linkedGross = allocatedInvoiceLineGross(item, quantity);
  const linkedAmount = item.amount == null ? item.amount : roundMoneyValue(Number(item.amount) * ratio);
  const linkedTax = item.taxAmount == null && item.amount == null
    ? item.taxAmount
    : roundMoneyValue(linkedGross - (Number(linkedAmount) || 0));
  return {
    ...item,
    quantity,
    amount: linkedAmount,
    taxAmount: linkedTax,
  };
}

export function splitInvoiceLine(item: InvoiceLineItem, quantity: number): [InvoiceLineItem, InvoiceLineItem] {
  const originalQty = Number(item.quantity) || 0;
  const linkedQty = originalQty > 0 ? Math.min(quantity, originalQty) : quantity;
  const linked = scaleInvoiceLine(item, linkedQty);
  const restQty = originalQty - (Number(linked.quantity) || 0);
  const restAmount = item.amount == null ? item.amount : roundMoneyValue(Number(item.amount) - (Number(linked.amount) || 0));
  const restGross = roundMoneyValue(invoiceLineGrossAmount(item) - invoiceLineGrossAmount(linked));
  const restTax = item.taxAmount == null && item.amount == null
    ? item.taxAmount
    : roundMoneyValue(restGross - (Number(restAmount) || 0));
  return [
    linked,
    {
      ...item,
      quantity: restQty,
      amount: restAmount,
      taxAmount: restTax,
    },
  ];
}

export function applyInvoiceLineAllocations(
  invoice: Invoice,
  type: "sales" | "purchase",
  allocations: Array<{ index: number; quantity?: number }>,
  orderId: string,
): Invoice {
  const selected = new Map(allocations.map((item) => [item.index, item.quantity]));
  const nextLines: InvoiceLineItem[] = [];
  (invoice.lineItems ?? []).forEach((item, index) => {
    const existingId = invoiceLineAssignedOrderId(item, type);
    if (existingId && existingId !== orderId) {
      nextLines.push(item);
      return;
    }
    if (!selected.has(index)) {
      nextLines.push(item);
      return;
    }
    if (!orderId) {
      nextLines.push(type === "sales" ? { ...item, salesOrderId: undefined } : { ...item, purchaseOrderId: undefined });
      return;
    }
    const originalQty = Number(item.quantity) || 0;
    const requested = Number(selected.get(index));
    const linkedQty = originalQty > 0 && Number.isFinite(requested) && requested > 0
      ? Math.min(requested, originalQty)
      : originalQty;
    const assigned = type === "sales"
      ? { ...item, salesOrderId: orderId, purchaseOrderId: undefined }
      : { ...item, purchaseOrderId: orderId, salesOrderId: undefined };
    if (originalQty > 0 && linkedQty < originalQty) {
      const [linked, rest] = splitInvoiceLine(item, linkedQty);
      nextLines.push(type === "sales"
        ? { ...linked, salesOrderId: orderId, purchaseOrderId: undefined }
        : { ...linked, purchaseOrderId: orderId, salesOrderId: undefined });
      nextLines.push({
        ...rest,
        salesOrderId: type === "sales" ? undefined : item.salesOrderId,
        purchaseOrderId: type === "purchase" ? undefined : item.purchaseOrderId,
      });
      return;
    }
    nextLines.push(assigned);
  });
  return {
    ...invoice,
    lineItems: nextLines,
    salesOrderIds: Array.from(new Set(nextLines.map((item) => item.salesOrderId).filter((id): id is string => Boolean(id)))),
    purchaseOrderIds: Array.from(new Set(nextLines.map((item) => item.purchaseOrderId).filter((id): id is string => Boolean(id)))),
  };
}

export function invoiceAmountForOrder(
  invoice: Pick<Invoice, "amount" | "salesOrderIds" | "purchaseOrderIds" | "lineItems">,
  orderId: string,
  type: "sales" | "purchase",
) {
  const lines = invoice.lineItems ?? [];
  const allocated = lines.filter((item) => (
    type === "sales" ? item.salesOrderId === orderId : item.purchaseOrderId === orderId
  ));
  if (allocated.length > 0) {
    if (allocated.length === lines.length) return Number(invoice.amount) || 0;
    return Math.round(allocated.reduce((sum, item) => sum + invoiceLineGrossAmount(item), 0) * 100) / 100;
  }
  const ids = type === "sales" ? invoice.salesOrderIds : invoice.purchaseOrderIds;
  if ((ids ?? []).includes(orderId)) return Number(invoice.amount) || 0;
  return 0;
}

export function invoiceLinkedToOrder(
  invoice: Pick<Invoice, "salesOrderIds" | "purchaseOrderIds" | "lineItems">,
  orderId: string,
  type: "sales" | "purchase",
) {
  if (type === "sales") {
    return (invoice.salesOrderIds ?? []).includes(orderId)
      || (invoice.lineItems ?? []).some((item) => item.salesOrderId === orderId);
  }
  return (invoice.purchaseOrderIds ?? []).includes(orderId)
    || (invoice.lineItems ?? []).some((item) => item.purchaseOrderId === orderId);
}

function invoiceAssignedOrderIds(invoice: Pick<Invoice, "salesOrderIds" | "purchaseOrderIds" | "lineItems">) {
  const sales = new Set([
    ...(invoice.salesOrderIds ?? []),
    ...(invoice.lineItems ?? []).map((item) => item.salesOrderId).filter((id): id is string => Boolean(id)),
  ]);
  const purchase = new Set([
    ...(invoice.purchaseOrderIds ?? []),
    ...(invoice.lineItems ?? []).map((item) => item.purchaseOrderId).filter((id): id is string => Boolean(id)),
  ]);
  return { sales, purchase };
}

export function invoiceHasProductOrderLinks(invoice: Pick<Invoice, "salesOrderIds" | "purchaseOrderIds" | "lineItems">) {
  const { sales, purchase } = invoiceAssignedOrderIds(invoice);
  return sales.size > 0 || purchase.size > 0;
}

export function invoiceDirectProjectIds(invoice: Pick<Invoice, "projectId" | "projectIds">) {
  return Array.from(new Set([
    ...(invoice.projectIds ?? []),
    ...(invoice.projectId ? [invoice.projectId] : []),
  ]));
}

function invoiceProjectsOfType(
  data: Pick<AppData, "projects">,
  invoice: Pick<Invoice, "projectId" | "projectIds">,
  type: Project["type"],
) {
  return invoiceDirectProjectIds(invoice).filter((id) => data.projects.find((project) => project.id === id)?.type === type);
}

export function invoiceHasServiceProjectLink(
  data: Pick<AppData, "projects">,
  invoice: Pick<Invoice, "projectId" | "projectIds" | "serviceAllocations">,
) {
  if (normalizeServiceAllocations(invoice.serviceAllocations).length > 0) return true;
  return invoiceProjectsOfType(data, invoice, "服务项目").length > 0;
}

export function normalizeServiceAllocations(
  allocations: Array<{ projectId?: string; serviceOrderId?: string; amount?: number }> | undefined,
): NonNullable<Invoice["serviceAllocations"]> {
  return (allocations ?? [])
    .map((item) => ({
      projectId: String(item.projectId ?? "").trim(),
      serviceOrderId: item.serviceOrderId ? String(item.serviceOrderId).trim() || undefined : undefined,
      amount: Math.round((Number(item.amount) || 0) * 100) / 100,
    }))
    .filter((item) => item.projectId && item.amount > 0.009);
}

/** 已占用额度：服务拆分金额、销/采明细/订单，或旧版服务 projectIds 整票。 */
export function invoiceAllocatedAmount(
  data: Pick<AppData, "projects">,
  invoice: Pick<Invoice, "amount" | "projectId" | "projectIds" | "salesOrderIds" | "purchaseOrderIds" | "lineItems" | "serviceAllocations">,
) {
  const serviceAllocs = normalizeServiceAllocations(invoice.serviceAllocations);
  if (serviceAllocs.length > 0) {
    return Math.round(serviceAllocs.reduce((sum, item) => sum + item.amount, 0) * 100) / 100;
  }
  const lines = invoice.lineItems ?? [];
  if (lines.length > 0) {
    const assigned = lines.filter((item) => item.salesOrderId || item.purchaseOrderId);
    if (assigned.length > 0) {
      return Math.round(assigned.reduce((sum, item) => sum + invoiceLineGrossAmount(item), 0) * 100) / 100;
    }
  }
  if (invoiceHasProductOrderLinks(invoice)) return Number(invoice.amount) || 0;
  if (invoiceHasServiceProjectLink(data, invoice)) return Number(invoice.amount) || 0;
  return 0;
}

export function invoiceRemainingAmount(
  data: Pick<AppData, "projects">,
  invoice: Pick<Invoice, "amount" | "projectId" | "projectIds" | "salesOrderIds" | "purchaseOrderIds" | "lineItems" | "serviceAllocations">,
) {
  const allocated = invoiceAllocatedAmount(data, invoice);
  return Math.round(Math.max((Number(invoice.amount) || 0) - allocated, 0) * 100) / 100;
}

/** 某服务订单在该发票上分到的金额（含仅挂项目、无 serviceOrderId 的拆分；旧数据整票归属）。 */
export function invoiceAmountForServiceOrder(
  data: Partial<Pick<AppData, "serviceOrders">>,
  invoice: Pick<Invoice, "amount" | "projectId" | "projectIds" | "salesOrderIds" | "purchaseOrderIds" | "lineItems" | "serviceAllocations">,
  serviceOrderId: string,
) {
  if (invoiceHasProductOrderLinks(invoice)) return 0;
  const order = data.serviceOrders?.find((item) => item.id === serviceOrderId);
  if (!order) return 0;
  const allocs = normalizeServiceAllocations(invoice.serviceAllocations);
  if (allocs.length > 0) {
    const byOrder = allocs.filter((item) => item.serviceOrderId === serviceOrderId);
    if (byOrder.length > 0) {
      return Math.round(byOrder.reduce((sum, item) => sum + item.amount, 0) * 100) / 100;
    }
    const projectLevel = allocs.filter((item) => item.projectId === order.projectId && !item.serviceOrderId);
    if (projectLevel.length === 0) return 0;
    const siblings = (data.serviceOrders ?? []).filter(
      (item) => item.projectId === order.projectId && item.status !== "取消",
    );
    if (siblings.length > 1) return 0;
    return Math.round(projectLevel.reduce((sum, item) => sum + item.amount, 0) * 100) / 100;
  }
  if (invoiceDirectProjectIds(invoice).includes(order.projectId)) return Number(invoice.amount) || 0;
  return 0;
}

export function serviceOrderInvoicedAmount(
  data: Pick<AppData, "invoices" | "serviceOrders">,
  serviceOrderId: string,
) {
  return Math.round(
    invoicesForOrder(data, serviceOrderId, "service").reduce(
      (sum, invoice) => sum + invoiceAmountForServiceOrder(data, invoice, serviceOrderId),
      0,
    ) * 100,
  ) / 100;
}

/** 按服务订单是否盖满应收，推导服务项目开票状态。 */
export function deriveServiceProjectInvoiceStatus(
  data: Pick<AppData, "invoices" | "serviceOrders" | "projects" | "salesOrders" | "purchaseOrders">,
  projectId: string,
): InvoiceDisplayStatus {
  const orders = (data.serviceOrders ?? []).filter(
    (order) => order.projectId === projectId && order.status !== "取消",
  );
  if (orders.length === 0) {
    const linked = data.invoices.filter((invoice) => (
      invoice.status !== "作废"
      && !invoiceHasProductOrderLinks(invoice)
      && invoiceBelongsToProject(data, invoice, projectId)
    ));
    return linked.length > 0 ? "已开全部" : "待开";
  }
  let anyLinked = false;
  let allFull = true;
  for (const order of orders) {
    const orderAmount = Number(order.receivableAmount ?? order.amount) || 0;
    const invoiced = serviceOrderInvoicedAmount(data, order.id);
    if (invoiced > 0.009) anyLinked = true;
    if (orderAmount > 0 && invoiced + 0.009 < orderAmount) allFull = false;
  }
  if (!anyLinked) return "待开";
  return allFull ? "已开全部" : "已开部分";
}

export function applyServiceInvoiceAllocation(
  data: Pick<AppData, "projects" | "salesOrders" | "purchaseOrders">,
  invoice: Invoice,
  allocation: { projectId: string; serviceOrderId?: string; amount: number },
): Invoice {
  const next: Invoice = {
    ...invoice,
    serviceAllocations: normalizeServiceAllocations([
      ...(invoice.serviceAllocations ?? []),
      allocation,
    ]),
  };
  return reconcileInvoiceProjectIds(data, next, allocation.projectId);
}

/** 取消服务项目/订单与发票的金额分摊；无分摊时清掉旧版 projectId 直挂。 */
export function removeServiceInvoiceAllocation(
  data: Pick<AppData, "projects" | "salesOrders" | "purchaseOrders">,
  invoice: Invoice,
  target: { projectId: string; serviceOrderId?: string },
): Invoice {
  const allocs = normalizeServiceAllocations(invoice.serviceAllocations);
  let nextAllocs = allocs;
  if (allocs.length > 0) {
    nextAllocs = allocs.filter((item) => {
      if (target.serviceOrderId) {
        return !(item.serviceOrderId === target.serviceOrderId
          || (!item.serviceOrderId && item.projectId === target.projectId));
      }
      return item.projectId !== target.projectId;
    });
  }
  const next: Invoice = {
    ...invoice,
    serviceAllocations: nextAllocs.length > 0 ? nextAllocs : undefined,
    projectId: undefined,
    projectIds: undefined,
  };
  if (allocs.length === 0) {
    // 旧数据：仅 projectId/projectIds 整票挂接，去掉本项目即可
    const ids = invoiceDirectProjectIds(invoice).filter((id) => id !== target.projectId);
    next.projectId = ids[0];
    next.projectIds = ids.length > 0 ? ids : undefined;
    return reconcileInvoiceProjectIds(data, next);
  }
  return reconcileInvoiceProjectIds(data, next);
}

export function invoiceFullyMatchesItems(
  invoice: Pick<Invoice, "amount" | "lineItems">,
  items: Array<{ lineAmount: number }>,
) {
  const lines = invoice.lineItems ?? [];
  if (lines.length === 0) {
    const total = Math.round(items.reduce((sum, item) => sum + (Number(item.lineAmount) || 0), 0) * 100) / 100;
    return items.length > 0 && moneyCents(total) === moneyCents(Number(invoice.amount) || 0);
  }
  if (items.length !== lines.length) return false;
  return defaultInvoiceLinePickIndexes(lines, items).length === lines.length;
}

function projectInvoiceMatchItems(
  data: Pick<AppData, "projectItems" | "serviceOrders" | "salesOrders" | "purchaseOrders">,
  project: Pick<Project, "id" | "type">,
  invoiceType: Invoice["type"],
) {
  if (project.type === "服务项目") {
    return (data.serviceOrders ?? [])
      .filter((order) => order.projectId === project.id && order.status !== "取消")
      .map((order) => ({ lineAmount: Number(order.receivableAmount ?? order.amount) || 0 }));
  }
  if (invoiceType === "进项") {
    return data.projectItems
      .filter((item) => item.projectId === project.id && item.purchaseOrderId && isPurchaseLineItem(item))
      .map((item) => ({
        lineAmount: Math.round(((Number(item.quantity) || 0) * (Number(item.costPrice) || 0)) * 100) / 100,
      }));
  }
  return data.projectItems
    .filter((item) => item.projectId === project.id && item.salesOrderId && !isPurchaseLineItem(item))
    .map((item) => ({
      lineAmount: Math.round(((Number(item.quantity) || 0) * (Number(item.actualPrice) || 0)) * 100) / 100,
    }));
}

export function invoiceCompletelyMatchingProjectId(
  data: Pick<AppData, "projects" | "projectItems" | "serviceOrders" | "salesOrders" | "purchaseOrders">,
  invoice: Pick<Invoice, "type" | "amount" | "projectId" | "projectIds" | "salesOrderIds" | "purchaseOrderIds" | "lineItems">,
) {
  const { sales, purchase } = invoiceAssignedOrderIds(invoice);
  const candidateIds = new Set([
    ...invoiceDirectProjectIds(invoice),
    ...data.salesOrders.filter((order) => sales.has(order.id)).map((order) => order.projectId),
    ...data.purchaseOrders.filter((order) => purchase.has(order.id)).map((order) => order.projectId),
  ]);
  for (const projectId of candidateIds) {
    const project = data.projects.find((item) => item.id === projectId);
    if (!project) continue;
    if (invoiceFullyMatchesItems(invoice, projectInvoiceMatchItems(data, project, invoice.type))) return projectId;
  }
  return undefined;
}

export type InvoiceLinkTarget =
  | { kind: "sales" | "purchase"; projectId: string; orderId?: string }
  | { kind: "service"; projectId: string; orderId?: string };

/** 销售/服务关联销项，采购关联进项，避免选错票种。 */
export function invoiceTypeForLinkTarget(target: InvoiceLinkTarget): Invoice["type"] {
  return target.kind === "purchase" ? "进项" : "销项";
}

/**
 * 不可再关联的原因。额度用尽、已与完全匹配项目锁定、商品/服务互斥时返回中文说明。
 * 仍允许把剩余明细挂到同一锁定项目下的其他订单。
 */
export function invoiceLinkBlockReason(
  data: Pick<AppData, "projects" | "projectItems" | "serviceOrders" | "salesOrders" | "purchaseOrders">,
  invoice: Invoice,
  target: InvoiceLinkTarget,
) {
  if (invoice.status === "作废") return "作废发票不能关联。";
  const expectedType = invoiceTypeForLinkTarget(target);
  if (invoice.type !== expectedType) {
    return target.kind === "purchase"
      ? "采购订单只能关联进项发票。"
      : target.kind === "service"
        ? "服务项目只能关联销项发票。"
        : "销售订单只能关联销项发票。";
  }
  const remaining = invoiceRemainingAmount(data, invoice);
  const matchedProjectId = invoiceCompletelyMatchingProjectId(data, invoice);
  const productLinked = invoiceHasProductOrderLinks(invoice);
  const serviceLinked = invoiceHasServiceProjectLink(data, invoice);

  if (target.kind === "service") {
    if (productLinked) return "该发票已关联商品订单，不能再关联服务项目。";
    if (matchedProjectId && matchedProjectId !== target.projectId) {
      return "该发票已与完全匹配的项目锁定，不能再关联其他项目。";
    }
    if (remaining <= 0.009) return "该发票额度已全部关联，不能再关联其他项目。";
    return null;
  }

  if (serviceLinked && !productLinked) return "该发票已关联服务项目，不能再关联商品订单。";
  if (target.orderId && invoiceLinkedToOrder(invoice, target.orderId, target.kind) && remaining <= 0.009) {
    return "该发票已经关联到这个订单。";
  }
  if (matchedProjectId && matchedProjectId !== target.projectId) {
    return "该发票已与完全匹配的项目锁定，不能再关联其他项目。";
  }
  if (remaining <= 0.009) return "该发票额度已全部关联，不能再关联其他订单。";
  return null;
}

export function invoicesEligibleToLink(
  data: Pick<AppData, "projects" | "projectItems" | "serviceOrders" | "salesOrders" | "purchaseOrders" | "invoices">,
  target: InvoiceLinkTarget,
) {
  return data.invoices.filter((invoice) => invoice.status !== "作废" && !invoiceLinkBlockReason(data, invoice, target));
}

/** 按真实销/采订单回写项目，去掉商品/服务串项残留。 */
export function reconcileInvoiceProjectIds<T extends Pick<Invoice, "projectId" | "projectIds" | "salesOrderIds" | "purchaseOrderIds" | "lineItems" | "serviceAllocations">>(
  data: Pick<AppData, "projects" | "salesOrders" | "purchaseOrders">,
  invoice: T,
  extraProjectId?: string,
): T {
  const { sales, purchase } = invoiceAssignedOrderIds(invoice);
  const fromOrders = Array.from(new Set([
    ...data.salesOrders.filter((order) => sales.has(order.id)).map((order) => order.projectId),
    ...data.purchaseOrders.filter((order) => purchase.has(order.id)).map((order) => order.projectId),
  ]));
  if (fromOrders.length > 0) {
    const projectIds = extraProjectId && !fromOrders.includes(extraProjectId)
      ? (data.projects.find((project) => project.id === extraProjectId)?.type === "商品项目"
        ? Array.from(new Set([...fromOrders, extraProjectId]))
        : fromOrders)
      : fromOrders;
    return { ...invoice, projectId: projectIds[0], projectIds };
  }
  const fromAllocations = normalizeServiceAllocations(
    (invoice as Pick<Invoice, "serviceAllocations">).serviceAllocations,
  ).map((item) => item.projectId);
  const existing = Array.from(new Set([
    ...invoiceDirectProjectIds(invoice),
    ...fromAllocations,
    ...(extraProjectId ? [extraProjectId] : []),
  ]));
  const serviceIds = existing.filter((id) => data.projects.find((project) => project.id === id)?.type === "服务项目");
  if (serviceIds.length > 0) {
    return { ...invoice, projectId: serviceIds[0], projectIds: serviceIds };
  }
  return { ...invoice, projectId: existing[0], projectIds: existing };
}

/** 项目归属判断：projectId/projectIds，或经本项目销/采订单关联。用于状态同步等宽口径场景。 */
export function invoiceBelongsToProject(
  data: Pick<AppData, "salesOrders" | "purchaseOrders">,
  invoice: Pick<Invoice, "projectId" | "projectIds" | "salesOrderIds" | "purchaseOrderIds" | "lineItems">,
  projectId: string,
) {
  const directIds = Array.from(new Set([
    ...(invoice.projectIds ?? []),
    ...(invoice.projectId ? [invoice.projectId] : []),
  ]));
  if (directIds.includes(projectId)) return true;

  const salesOrderIds = new Set(
    data.salesOrders.filter((order) => order.projectId === projectId).map((order) => order.id),
  );
  if ((invoice.salesOrderIds ?? []).some((id) => salesOrderIds.has(id))) return true;
  if ((invoice.lineItems ?? []).some((item) => item.salesOrderId && salesOrderIds.has(item.salesOrderId))) return true;

  const purchaseOrderIds = new Set(
    data.purchaseOrders.filter((order) => order.projectId === projectId).map((order) => order.id),
  );
  if ((invoice.purchaseOrderIds ?? []).some((id) => purchaseOrderIds.has(id))) return true;
  return (invoice.lineItems ?? []).some((item) => item.purchaseOrderId && purchaseOrderIds.has(item.purchaseOrderId));
}

function orderHasActiveInvoice(
  data: Pick<AppData, "invoices">,
  orderId: string,
  type: "sales" | "purchase",
) {
  return invoicesForOrder(data, orderId, type).length > 0;
}

export function invoicesForOrder(
  data: Pick<AppData, "invoices"> & Partial<Pick<AppData, "serviceOrders">>,
  orderId: string,
  kind: "sales" | "purchase" | "service",
): Invoice[] {
  const active = data.invoices.filter((invoice) => invoice.status !== "作废");
  if (kind === "purchase") {
    return active.filter((invoice) => invoiceLinkedToOrder(invoice, orderId, "purchase"));
  }
  if (kind === "sales") {
    return active.filter((invoice) => invoiceLinkedToOrder(invoice, orderId, "sales"));
  }
  const service = data.serviceOrders?.find((order) => order.id === orderId);
  if (!service) return [];
  const siblingCount = (data.serviceOrders ?? []).filter(
    (order) => order.projectId === service.projectId && order.status !== "取消",
  ).length;
  return active.filter((invoice) => {
    if (invoice.type !== "销项" || invoiceHasProductOrderLinks(invoice)) return false;
    const allocs = normalizeServiceAllocations(invoice.serviceAllocations);
    if (allocs.length > 0) {
      if (allocs.some((item) => item.serviceOrderId === orderId)) return true;
      if (siblingCount > 1) return false;
      return allocs.some((item) => item.projectId === service.projectId && !item.serviceOrderId);
    }
    return invoice.projectId === service.projectId
      || (invoice.projectIds ?? []).includes(service.projectId);
  });
}

export function orderInvoiceOverview(
  data: Pick<AppData, "invoices"> & Partial<Pick<AppData, "serviceOrders">>,
  orderId: string,
  kind: "sales" | "purchase" | "service",
  orderAmount: number,
) {
  const invoices = invoicesForOrder(data, orderId, kind);
  const invoiced = Math.round(invoices.reduce((sum, invoice) => {
    if (kind === "purchase") return sum + invoiceAmountForOrder(invoice, orderId, "purchase");
    if (kind === "sales") return sum + invoiceAmountForOrder(invoice, orderId, "sales");
    return sum + invoiceAmountForServiceOrder(data, invoice, orderId);
  }, 0) * 100) / 100;
  const unpaidLabel = kind === "purchase" ? "未收票" : "未开票";
  const fullLabel = kind === "purchase" ? "已收全部" : "已开全部";
  const partLabel = kind === "purchase" ? "已收部分" : "已开部分";
  let statusLabel = unpaidLabel;
  if (invoices.length > 0) {
    statusLabel = orderAmount > 0 && invoiced + 0.009 >= orderAmount ? fullLabel : partLabel;
  }
  return { invoices, invoiced, statusLabel, linked: invoices.length > 0 };
}

function isContractCounted(status?: ContractStatus, fileId?: string) {
  return status === "已签" || status === "已发送" || Boolean(fileId);
}

/**
 * 项目详情「发票」页签与销/采订单关联面板对齐：
 * 仅汇总挂到本项目销售/采购订单的非作废发票（去重），不含仅挂 projectId 的孤儿发票。
 */
export function projectLinkedInvoices(data: AppData, projectId: string) {
  const salesOrderIds = new Set(
    data.salesOrders.filter((order) => order.projectId === projectId).map((order) => order.id),
  );
  const purchaseOrderIds = new Set(
    data.purchaseOrders.filter((order) => order.projectId === projectId).map((order) => order.id),
  );
  return data.invoices.filter((invoice) => {
    if (invoice.status === "作废") return false;
    const bySales = (invoice.salesOrderIds ?? []).some((id) => salesOrderIds.has(id))
      || (invoice.lineItems ?? []).some((item) => item.salesOrderId && salesOrderIds.has(item.salesOrderId));
    const byPurchase = (invoice.purchaseOrderIds ?? []).some((id) => purchaseOrderIds.has(id))
      || (invoice.lineItems ?? []).some((item) => item.purchaseOrderId && purchaseOrderIds.has(item.purchaseOrderId));
    return bySales || byPurchase;
  });
}

/** 项目详情发票列表：服务项目认 projectId/projectIds，商品项目仍按销/采订单挂载。 */
export function projectVisibleInvoices(data: AppData, project: Pick<Project, "id" | "type">) {
  if (project.type === "服务项目") {
    return data.invoices.filter((invoice) => (
      invoice.status !== "作废"
      && !invoiceHasProductOrderLinks(invoice)
      && invoiceBelongsToProject(data, invoice, project.id)
    ));
  }
  return projectLinkedInvoices(data, project.id);
}

/** 商品项目列表「订单/合同/发票/对账」两行汇总。 */
export function productProjectOrderStatusLines(data: AppData, project: Project) {
  const salesOrders = data.salesOrders.filter((order) => order.projectId === project.id);
  const purchaseOrders = data.purchaseOrders.filter((order) => order.projectId === project.id);
  const salesN = salesOrders.length;
  const purchaseN = purchaseOrders.length;

  const salesContract = isContractCounted(project.contractStatus, project.contractFileId) ? salesN : 0;
  const purchaseContract = purchaseOrders.filter((order) =>
    isContractCounted(order.contractStatus, order.contractFileId),
  ).length;

  const salesInvoiced = salesOrders.filter((order) => orderHasActiveInvoice(data, order.id, "sales")).length;
  const purchaseInvoiced = purchaseOrders.filter((order) => orderHasActiveInvoice(data, order.id, "purchase")).length;

  const salesReconciled = (project.reconcileStatus ?? DEFAULT_RECONCILE_STATUS) === "已对账" ? salesN : 0;
  const purchaseReconciled = purchaseOrders.filter(
    (order) => (order.reconcileStatus ?? DEFAULT_RECONCILE_STATUS) === "已对账",
  ).length;

  return {
    salesLine: `销售 ${salesN} · 合同${salesContract}/${salesN} · 发票${salesInvoiced}/${salesN} · 对账 ${salesReconciled}/${salesN}`,
    purchaseLine: `采购 ${purchaseN} · 合同${purchaseContract}/${purchaseN} · 发票${purchaseInvoiced}/${purchaseN} · 对账 ${purchaseReconciled}/${purchaseN}`,
  };
}

export function productProjectBlocker(data: Pick<AppData, "salesOrders" | "purchaseOrders">, project: Project) {
  if (project.type !== "商品项目") return project.currentBlocker;
  if (project.status === "已完成") return "无阻塞";
  if (project.status === "终止") return "项目已终止";
  const hasSales = hasProductSalesOrder(data, project.id);
  const hasPurchase = hasProductPurchaseOrder(data, project.id);
  if (!hasSales && !hasPurchase) return "待添加商品与渠道采购";
  if (!hasSales) return "待添加商品（销售订单）";
  if (!hasPurchase) return "待添加渠道采购";
  if (project.status === "进行中") {
    const fulfillment = aggregateFulfillmentFromPurchaseOrders(activePurchaseOrders(data, project.id));
    const pending: string[] = [];
    if (fulfillment.logisticsStatus !== "已签收") pending.push("物流");
    if (fulfillment.acceptanceStatus !== "已验收") pending.push("验收");
    if (fulfillment.deliveryStatus !== "已交付") pending.push("交付");
    if (pending.length) return `履约推进中：${pending.join("/")}`;
    return "待订单结清后完成项目";
  }
  return project.currentBlocker ?? "待推进";
}

function salesOrderSettled(order: SalesOrder) {
  return order.status === "已付款" || order.status === "退款" || order.status === "取消";
}

function purchaseOrderSettled(order: PurchaseOrder) {
  return order.status === "已完成" || order.status === "已取消" || order.paymentStatus === "已付款" || order.paymentStatus === "退款" || order.paymentStatus === "取消";
}

export function productProjectCompletionIssues(
  project: Project,
  data: Pick<AppData, "salesOrders" | "purchaseOrders">,
) {
  if (project.type !== "商品项目") return [] as string[];
  const issues: string[] = [];
  const salesOrders = data.salesOrders.filter((order) => order.projectId === project.id);
  const purchaseOrders = activePurchaseOrders(data, project.id);
  if (salesOrders.length === 0) issues.push("缺少销售订单");
  if (purchaseOrders.length === 0) issues.push("缺少采购订单");
  if (salesOrders.some((order) => !salesOrderSettled(order))) issues.push("存在未结清销售订单");
  if (purchaseOrders.some((order) => !purchaseOrderSettled(order) && order.status !== "已完成")) {
    issues.push("存在未完成采购订单");
  }
  const fulfillment = aggregateFulfillmentFromPurchaseOrders(purchaseOrders);
  if (fulfillment.logisticsStatus !== "已签收") issues.push("物流未全部签收");
  if (fulfillment.acceptanceStatus !== "已验收") issues.push("验收未完成");
  if (fulfillment.deliveryStatus !== "已交付") issues.push("交付未完成");
  return issues;
}

export function canAutoCompleteProductProject(
  project: Project,
  data: Pick<AppData, "salesOrders" | "purchaseOrders">,
) {
  return productProjectCompletionIssues(project, data).length === 0;
}

export function canAppendSalesOrderItems(order: Pick<SalesOrder, "status">) {
  return order.status === "待付款";
}

export function salesOrderLinkedPurchaseOrders(
  data: Pick<AppData, "purchaseOrders" | "projectItems">,
  order: Pick<SalesOrder, "id" | "purchaseOrderIds">,
) {
  const ids = new Set(order.purchaseOrderIds ?? []);
  data.projectItems.forEach((item) => {
    if (item.salesOrderId === order.id && item.sourcePurchaseOrderId) ids.add(item.sourcePurchaseOrderId);
  });
  return data.purchaseOrders.filter((po) => ids.has(po.id) && po.status !== "已取消");
}

/** 已被未取消、未退款销售订单关联的采购订单，不再作为关联备选项。 */
export function purchaseOrderIdsTakenBySalesOrders(
  data: Pick<AppData, "salesOrders" | "purchaseOrders" | "projectItems">,
) {
  const ids = new Set<string>();
  for (const order of data.salesOrders) {
    if (!salesOrderCountsTowardProfit(order)) continue;
    for (const purchaseOrder of salesOrderLinkedPurchaseOrders(data, order)) ids.add(purchaseOrder.id);
  }
  return ids;
}

function roundCents(value: number) {
  return Math.round((Number(value) || 0) * 100) / 100;
}

function salesOrderCountsTowardProfit(order: Pick<SalesOrder, "status">) {
  return order.status !== "取消" && order.status !== "退款";
}

/** 仍参与成本分摊的销售订单。已取消、已退款的单子不再分摊采购成本。 */
export function salesOrdersLinkingPurchase(
  data: Pick<AppData, "salesOrders" | "purchaseOrders" | "projectItems">,
  purchaseOrderId: string,
) {
  return data.salesOrders
    .filter((order) => salesOrderCountsTowardProfit(order) && salesOrderLinkedPurchaseOrders(data, order).some((po) => po.id === purchaseOrderId))
    .sort((a, b) => a.id.localeCompare(b.id));
}

/** 一张采购订单被多张销售订单关联时，按销售金额比例分摊，尾差记在最后一张。 */
export function allocatedPurchaseCosts(
  data: Pick<AppData, "salesOrders" | "purchaseOrders" | "projectItems">,
  purchaseOrder: Pick<PurchaseOrder, "id" | "amount">,
) {
  const amount = roundCents(purchaseOrder.amount);
  const linked = salesOrdersLinkingPurchase(data, purchaseOrder.id);
  const shares = new Map<string, number>();
  if (linked.length === 0) return shares;
  if (linked.length === 1) {
    shares.set(linked[0].id, amount);
    return shares;
  }
  const weights = linked.map((order) => Math.max(0, roundCents(order.amount)));
  const total = roundCents(weights.reduce((sum, value) => sum + value, 0));
  let used = 0;
  linked.forEach((order, index) => {
    if (index === linked.length - 1) {
      shares.set(order.id, roundCents(amount - used));
      return;
    }
    const share = total > 0
      ? roundCents(amount * weights[index] / total)
      : roundCents(amount / linked.length);
    shares.set(order.id, share);
    used = roundCents(used + share);
  });
  return shares;
}

export function salesOrderProfit(
  data: Pick<AppData, "salesOrders" | "purchaseOrders" | "projectItems">,
  order: Pick<SalesOrder, "id" | "amount" | "status" | "purchaseOrderIds">,
) {
  const purchaseOrders = salesOrderLinkedPurchaseOrders(data, order);
  if (!salesOrderCountsTowardProfit(order)) {
    return { salesAmount: 0, costAmount: 0, profit: 0, margin: null as number | null, purchaseOrders };
  }
  const salesAmount = roundCents(order.amount);
  const costAmount = roundCents(purchaseOrders.reduce((sum, purchaseOrder) => {
    return sum + (allocatedPurchaseCosts(data, purchaseOrder).get(order.id) ?? 0);
  }, 0));
  const profit = roundCents(salesAmount - costAmount);
  return {
    salesAmount,
    costAmount,
    profit,
    margin: salesAmount > 0 ? profit / salesAmount : null,
    purchaseOrders,
  };
}

/** 手工设置销售订单关联的采购订单，并清掉已取消关联的商品行渠道指向。 */
export function applySalesOrderPurchaseLinks(data: AppData, salesOrderId: string, purchaseOrderIds: string[]) {
  const nextIds = [...new Set(purchaseOrderIds.filter(Boolean))];
  const allowed = new Set(nextIds);
  const now = new Date().toISOString();
  return {
    ...data,
    salesOrders: data.salesOrders.map((order) => order.id === salesOrderId
      ? { ...order, purchaseOrderIds: nextIds, updatedAt: now }
      : order),
    projectItems: data.projectItems.map((item) => {
      if (item.salesOrderId !== salesOrderId || !item.sourcePurchaseOrderId || allowed.has(item.sourcePurchaseOrderId)) return item;
      return { ...item, sourcePurchaseOrderId: undefined };
    }),
  };
}

function isShippedOrSignedLogistics(status?: LogisticsStatus) {
  const value = status ?? DEFAULT_LOGISTICS_STATUS;
  return value === "已发货" || value === "已签收";
}

/** 关联渠道采购已发货或已签收后，销售单商品不可再改。 */
export function isSalesOrderLogisticsLocked(
  data: Pick<AppData, "purchaseOrders" | "projectItems">,
  order: Pick<SalesOrder, "id" | "purchaseOrderIds">,
) {
  return salesOrderLinkedPurchaseOrders(data, order).some((po) => isShippedOrSignedLogistics(po.logisticsStatus));
}

export function canEditSalesOrderItems(
  data: Pick<AppData, "purchaseOrders" | "projectItems">,
  order: Pick<SalesOrder, "id" | "status" | "purchaseOrderIds">,
) {
  return canAppendSalesOrderItems(order) && !isSalesOrderLogisticsLocked(data, order);
}

export function salesOrderItemsEditBlockReason(
  data: Pick<AppData, "purchaseOrders" | "projectItems">,
  order: Pick<SalesOrder, "id" | "status" | "purchaseOrderIds">,
) {
  if (!canAppendSalesOrderItems(order)) {
    return "仅「待付款」的销售订单可修改商品，其他状态请新建销售订单。";
  }
  if (isSalesOrderLogisticsLocked(data, order)) {
    return "关联采购订单已发货或已签收，不可移除、追加或修改数量。";
  }
  return null;
}

export function canAppendPurchaseOrderItems(order: Pick<PurchaseOrder, "status">) {
  return order.status === "待下单" || order.status === "草稿";
}

export function formatProductProjectNameDate(value?: string) {
  const source = value ? new Date(`${String(value).slice(0, 10)}T00:00:00`) : new Date();
  const date = Number.isNaN(source.getTime()) ? new Date() : source;
  return `${date.getFullYear()}年${String(date.getMonth() + 1).padStart(2, "0")}月${String(date.getDate()).padStart(2, "0")}日`;
}

export function buildProductProjectName(input: {
  customerName?: string;
  usageUnitName?: string;
  platform?: string;
  remark?: string;
  projectAt?: string;
}) {
  return [
    input.customerName,
    input.usageUnitName,
    input.platform,
    input.remark?.trim(),
    input.projectAt ? formatProductProjectNameDate(input.projectAt) : "",
  ].filter((part): part is string => Boolean(part)).join(" - ");
}

export function salesOrderItemsAmount(items: Array<{ quantity?: number; actualPrice?: number }>) {
  return Math.round(items.reduce((sum, item) => {
    return sum + (Number(item.quantity) || 0) * (Number(item.actualPrice) || 0);
  }, 0) * 100) / 100;
}

export function syncSalesOrderAmountsFromItems(data: AppData, projectId: string): AppData {
  let ordersChanged = false;
  const salesOrders = data.salesOrders.map((order) => {
    if (order.projectId !== projectId) return order;
    if (order.status === "取消" || order.status === "退款") return order;
    const amount = salesOrderItemsAmount(salesOrderLineItems(data.projectItems, order.id));
    if (Math.abs((order.amount || 0) - amount) < 0.01 && Math.abs((order.receivableAmount ?? order.amount ?? 0) - amount) < 0.01) {
      return order;
    }
    ordersChanged = true;
    return { ...order, amount, receivableAmount: amount };
  });
  const next = ordersChanged ? { ...data, salesOrders } : data;
  const project = next.projects.find((item) => item.id === projectId);
  if (!project || project.type !== "商品项目") return next;
  const totalAmount = Math.round(next.salesOrders
    .filter((order) => order.projectId === projectId && order.status !== "取消" && order.status !== "退款")
    .reduce((sum, order) => sum + (order.receivableAmount ?? order.amount), 0) * 100) / 100;
  if (Math.abs((project.totalAmount || 0) - totalAmount) < 0.01) return next;
  return {
    ...next,
    projects: next.projects.map((item) => item.id === projectId ? { ...item, totalAmount } : item),
  };
}

/** 按已有单号取下一个 `PREFIX + 两位序号`，避免按数量编号在删单后撞号。 */
export function nextPrefixedOrderNo(existingNos: string[], prefix: string) {
  const escaped = prefix.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  const pattern = new RegExp(`^${escaped}(\\d+)$`);
  let max = 0;
  for (const orderNo of existingNos) {
    const match = orderNo.match(pattern);
    if (!match) continue;
    const value = Number(match[1]);
    if (Number.isFinite(value)) max = Math.max(max, value);
  }
  return `${prefix}${String(max + 1).padStart(2, "0")}`;
}

export function mapLegacyProductProjectStatus(
  status: ProjectStatus | string,
  data: Pick<AppData, "salesOrders" | "purchaseOrders">,
  projectId: string,
): ProjectStatus {
  if (status === "已完成" || status === "初始化" || status === "进行中" || status === "终止") {
    return status;
  }
  if (status === "异常") return "终止";
  if (LEGACY_PRODUCT_STATUSES.has(status)) {
    return hasProductSalesOrder(data, projectId) && hasProductPurchaseOrder(data, projectId)
      ? "进行中"
      : "初始化";
  }
  return "初始化";
}

export type ProductProjectSyncResult = {
  project: Project;
  changed: boolean;
  autoDetail?: string;
};

export function syncProductProjectStatus(
  project: Project,
  data: Pick<AppData, "salesOrders" | "purchaseOrders" | "invoices">,
): ProductProjectSyncResult {
  if (project.type !== "商品项目") {
    return { project, changed: false };
  }

  const purchaseOrders = activePurchaseOrders(data, project.id);
  const fulfillment = aggregateFulfillmentFromPurchaseOrders(purchaseOrders);
  const projectInvoices = data.invoices.filter((invoice) =>
    invoice.status !== "作废" && invoiceBelongsToProject(data, invoice, project.id),
  );
  const salesAmount = data.salesOrders
    .filter((order) => order.projectId === project.id && order.status !== "取消")
    .reduce((sum, order) => sum + (order.receivableAmount ?? order.amount), 0);

  let next: Project = {
    ...project,
    logisticsStatus: fulfillment.logisticsStatus,
    acceptanceStatus: fulfillment.acceptanceStatus,
    deliveryStatus: fulfillment.deliveryStatus,
    reconcileStatus: project.reconcileStatus ?? DEFAULT_RECONCILE_STATUS,
    paymentStatus: mapLegacyPaymentStatus(project.paymentStatus),
    invoiceStatus: project.invoiceStatus === "无需"
      ? "无需"
      : deriveInvoiceStatus(projectInvoices, salesAmount || project.totalAmount || 0),
    contractStatus: mapLegacyContractStatus(project.contractStatus),
  };

  if (next.status === "已完成" || next.status === "终止") {
    const blocker = productProjectBlocker(data, next);
    if (blocker !== next.currentBlocker
      || next.logisticsStatus !== project.logisticsStatus
      || next.acceptanceStatus !== project.acceptanceStatus
      || next.deliveryStatus !== project.deliveryStatus
      || next.invoiceStatus !== project.invoiceStatus) {
      return { project: { ...next, currentBlocker: blocker }, changed: true };
    }
    return { project: next, changed: next !== project };
  }

  let autoDetail: string | undefined;
  const hasSales = hasProductSalesOrder(data, next.id);
  const hasPurchase = hasProductPurchaseOrder(data, next.id);

  if (next.status === "初始化" && hasSales && hasPurchase) {
    next = { ...next, status: "进行中" };
    autoDetail = "系统自动：已添加商品与渠道采购，项目进入进行中";
  }

  const blocker = productProjectBlocker(data, next);
  next = { ...next, currentBlocker: blocker };

  const changed = next.status !== project.status
    || next.currentBlocker !== project.currentBlocker
    || next.logisticsStatus !== project.logisticsStatus
    || next.acceptanceStatus !== project.acceptanceStatus
    || next.deliveryStatus !== project.deliveryStatus
    || next.invoiceStatus !== project.invoiceStatus
    || next.reconcileStatus !== project.reconcileStatus;

  return { project: next, changed, autoDetail };
}

/** 单笔采购：物流/验收/交付是否均为完成态（已签收/已验收/已交付） */
export function isPurchaseFulfillmentComplete(
  order: Pick<PurchaseOrder, "logisticsStatus" | "acceptanceStatus" | "deliveryStatus">,
) {
  return (order.logisticsStatus ?? DEFAULT_LOGISTICS_STATUS) === "已签收"
    && (order.acceptanceStatus ?? DEFAULT_ACCEPTANCE_STATUS) === "已验收"
    && (order.deliveryStatus ?? DEFAULT_DELIVERY_STATUS) === "已交付";
}

/** 履约三态均完成时，将采购执行状态标为「已完成」（不改已取消） */
export function withAutoCompletedPurchaseOrderStatus(order: PurchaseOrder): PurchaseOrder {
  if (order.status === "已取消" || order.status === "已完成") return order;
  if (!isPurchaseFulfillmentComplete(order)) return order;
  return { ...order, status: "已完成" };
}

/** 按履约终态自动推进本项目下采购订单执行状态 */
export function syncPurchaseOrdersStatusFromFulfillment(
  data: AppData,
  projectId: string,
): { data: AppData; autoDetail?: string } {
  const completedNos: string[] = [];
  const purchaseOrders = data.purchaseOrders.map((order) => {
    if (order.projectId !== projectId) return order;
    const next = withAutoCompletedPurchaseOrderStatus(order);
    if (next.status === order.status) return order;
    completedNos.push(order.orderNo);
    return next;
  });
  if (completedNos.length === 0) return { data };
  return {
    data: { ...data, purchaseOrders },
    autoDetail: `系统自动：采购订单 ${completedNos.join("、")} 物流/验收/交付均已完成，执行状态标记为已完成`,
  };
}

/** 将项目履约汇总写回销售订单派生字段 */
export function syncSalesOrdersFulfillment(
  data: AppData,
  projectId: string,
): AppData {
  const fulfillment = aggregateFulfillmentFromPurchaseOrders(activePurchaseOrders(data, projectId));
  let changed = false;
  const salesOrders = data.salesOrders.map((order) => {
    if (order.projectId !== projectId) return order;
    if (
      order.logisticsStatus === fulfillment.logisticsStatus
      && order.acceptanceStatus === fulfillment.acceptanceStatus
      && order.deliveryStatus === fulfillment.deliveryStatus
    ) {
      return order;
    }
    changed = true;
    return {
      ...order,
      logisticsStatus: fulfillment.logisticsStatus,
      acceptanceStatus: fulfillment.acceptanceStatus,
      deliveryStatus: fulfillment.deliveryStatus,
    };
  });
  return changed ? { ...data, salesOrders } : data;
}

export function applyProductProjectSync(
  data: AppData,
  projectId: string,
): { data: AppData; autoDetail?: string; project?: Project } {
  const current = data.projects.find((item) => item.id === projectId);
  if (!current || current.type !== "商品项目") return { data };
  const amountsSynced = syncSalesOrderAmountsFromItems(data, projectId);
  const purchaseSynced = syncPurchaseOrdersStatusFromFulfillment(amountsSynced, projectId);
  const withSales = syncSalesOrdersFulfillment(purchaseSynced.data, projectId);
  const currentAfterAmounts = withSales.projects.find((item) => item.id === projectId) ?? current;
  const liveCost = Math.round(
    withSales.purchaseOrders
      .filter((order) => order.projectId === projectId && order.status !== "已取消")
      .reduce((sum, order) => sum + (Number(order.amount) || 0), 0) * 100,
  ) / 100;
  const result = syncProductProjectStatus(currentAfterAmounts, withSales);
  const project = { ...result.project, totalCost: liveCost };
  const autoDetail = [purchaseSynced.autoDetail, result.autoDetail].filter(Boolean).join("；") || undefined;
  const costChanged = liveCost !== (Number(current.totalCost) || 0);
  if (!result.changed && withSales === data && !purchaseSynced.autoDetail && amountsSynced === data && !costChanged) {
    return { data, project };
  }
  return {
    data: {
      ...withSales,
      projects: withSales.projects.map((item) => item.id === projectId ? project : item),
    },
    autoDetail,
    project,
  };
}

export type ProjectProgressStep = {
  label: string;
  done: boolean;
  current?: boolean;
};

function orderPaid(status: string) {
  return status === "已付款";
}

function orderPaymentClosed(status: string) {
  return status === "已付款" || status === "取消" || status === "退款";
}

function purchaseClosed(status: string) {
  return status === "已完成" || status === "已取消";
}

/** 顶部履约进度条：按真实业务状态点亮。 */
export function projectProgressSteps(
  project: Project,
  data: Pick<AppData, "salesOrders" | "purchaseOrders" | "serviceOrders" | "invoices" | "platformAccounts">,
): ProjectProgressStep[] {
  const sales = data.salesOrders.filter((order) => order.projectId === project.id);
  const purchases = data.purchaseOrders.filter((order) => order.projectId === project.id);
  const services = data.serviceOrders.filter((order) => order.projectId === project.id);
  const fulfillment = project.type === "商品项目"
    ? aggregateFulfillmentFromPurchaseOrders(activePurchaseOrders(data, project.id))
    : null;

  const contractDone = project.contractStatus === "已签" || project.contractStatus === "无需";

  let paymentDone = false;
  if (project.type === "商品项目") {
    if (sales.length > 0) {
      paymentDone = sales.every((order) => orderPaymentClosed(order.status)) && sales.some((order) => orderPaid(order.status));
    } else {
      paymentDone = orderPaid(mapLegacyPaymentStatus(project.paymentStatus));
    }
  } else if (services.length > 0) {
    paymentDone = services.every((order) => orderPaymentClosed(order.status)) && services.some((order) => orderPaid(order.status));
  } else {
    paymentDone = orderPaid(mapLegacyPaymentStatus(project.paymentStatus));
  }

  let purchaseDone = false;
  if (project.type === "商品项目") {
    if (project.purchaseStatus === "无需采购") {
      purchaseDone = true;
    } else if (purchases.length > 0) {
      purchaseDone = purchases.every((order) => purchaseClosed(order.status)) && purchases.some((order) => order.status === "已完成");
    } else {
      purchaseDone = project.purchaseStatus === "已完成";
    }
  } else {
    purchaseDone = data.platformAccounts.some((account) =>
      account.projectId === project.id
      || (account.customerOrgId === project.customerOrgId && (!project.sourcePlatform || account.platform === project.sourcePlatform)),
    ) || ["服务中", "服务交付完成", "服务到期结束", "已完成", "结束"].includes(project.status);
  }

  const deliveryDone = project.type === "商品项目"
    ? !!fulfillment
      && fulfillment.logisticsStatus === "已签收"
      && fulfillment.acceptanceStatus === "已验收"
      && fulfillment.deliveryStatus === "已交付"
    : ["服务交付完成", "服务到期结束", "已完成", "结束"].includes(project.status);

  const invoiceDone = project.invoiceStatus === "已开全部"
    || project.invoiceStatus === "无需"
    || data.invoices.some((invoice) =>
      invoice.status !== "作废" && invoiceBelongsToProject(data, invoice, project.id),
    );

  const settleDone = project.status === "已完成"
    || project.status === "服务到期结束"
    || project.status === "结束";

  const steps: ProjectProgressStep[] = [
    { label: "合同", done: contractDone },
    { label: "收款", done: paymentDone },
    { label: "采购/平台", done: purchaseDone },
    { label: "交付", done: deliveryDone },
    { label: "开票", done: invoiceDone },
    { label: "结算", done: settleDone },
  ];
  const currentIndex = steps.findIndex((step) => !step.done);
  return steps.map((step, index) => ({
    ...step,
    current: currentIndex === index,
  }));
}
