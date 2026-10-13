import { createId } from "./db";
import {
  applyProductProjectSync,
  buildProjectScopedProduct,
  canAppendPurchaseOrderItems,
  DEFAULT_ACCEPTANCE_STATUS,
  DEFAULT_CONTRACT_STATUS,
  DEFAULT_DELIVERY_STATUS,
  DEFAULT_LOGISTICS_STATUS,
  DEFAULT_ORDER_PAYMENT_STATUS,
  DEFAULT_RECONCILE_STATUS,
  nextPrefixedOrderNo,
  salesOrderItemsAmount,
  salesOrderItemsEditBlockReason,
  salesOrderLineItems,
} from "./productProjectFlow";
import type { AppData, OperationLog, Product, Project, ProjectItem, PurchaseOrder, SalesOrder } from "./types";

export type SalesChannelLineDraft = {
  key: string;
  productId: string;
  quantity: string;
  salesUnitPrice: string;
  directProductName: string;
  directPlatformPrice: string;
  supplierOrgId: string;
  purchaseOrderId: string;
  purchaseUnitPrice: string;
};

export type SalesComposerDraft = {
  targetOrderId?: string;
  orderedAt: string;
  platformOrderNo: string;
  note: string;
  purchaserCompany: string;
  purchaserAddress: string;
  purchaserName: string;
  purchaserPhone: string;
  lines: SalesChannelLineDraft[];
};

export function purchaserDraftFromProject(data: Pick<AppData, "organizations">, project?: Project) {
  const org = project ? data.organizations.find((item) => item.id === project.customerOrgId) : undefined;
  return {
    purchaserCompany: org?.name ?? "",
    purchaserAddress: [org?.city, org?.district, org?.address].filter(Boolean).join(""),
    purchaserName: org?.legalPerson ?? "",
    purchaserPhone: org?.phone ?? "",
  };
}

const PURCHASER_LINE_CODE = /[[［【]\s*(\d{2,8})\s*[\]］】]\s*$/;

export type PurchaserQuickFill = {
  purchaserName: string;
  purchaserPhone: string;
  purchaserAddress: string;
};

/** 三行：姓名[编号]、电话、收货地址[编号]。编号接到电话后，用 - 连接。 */
export function parsePurchaserQuickText(raw: string): PurchaserQuickFill | null {
  const lines = raw.split(/\r?\n/).map((line) => line.trim()).filter(Boolean);
  if (lines.length < 3) return null;
  const nameLine = lines[0];
  const phoneLine = lines[1].replace(/\s+/g, "");
  const addressLine = lines.slice(2).join("");
  const code = nameLine.match(PURCHASER_LINE_CODE)?.[1] || addressLine.match(PURCHASER_LINE_CODE)?.[1];
  const purchaserName = nameLine.replace(PURCHASER_LINE_CODE, "").trim();
  const purchaserAddress = addressLine.replace(PURCHASER_LINE_CODE, "").trim();
  if (!purchaserName || !phoneLine || !purchaserAddress) return null;
  const purchaserPhone = code && !phoneLine.endsWith(`-${code}`) ? `${phoneLine}-${code}` : phoneLine;
  return { purchaserName, purchaserPhone, purchaserAddress };
}

export type PurchaseOrderComposerLine = {
  productId: string;
  productName: string;
  quantity: number;
  supplierOrgId: string;
  unitPrice: number;
  supplierPriceId?: string;
  note?: string;
};

type CommitFn = (data: AppData, log?: Omit<OperationLog, "id" | "createdAt">) => Promise<void>;

function nowIso() {
  return new Date().toISOString();
}

function fromDateTimeLocalValue(value: string) {
  if (!value) return nowIso();
  const parsed = new Date(value);
  return Number.isNaN(parsed.getTime()) ? nowIso() : parsed.toISOString();
}

function isPurchaseLineItem(item: { salesOrderId?: string; purchaseOrderId?: string; actualPrice?: number; costPrice?: number }) {
  if (!item.salesOrderId) return true;
  return Number(item.actualPrice) === 0 && Number(item.costPrice) > 0;
}

export function blankSalesChannelLine(supplierOrgId = ""): SalesChannelLineDraft {
  return {
    key: createId("line"),
    productId: "",
    quantity: "1",
    salesUnitPrice: "",
    directProductName: "",
    directPlatformPrice: "",
    supplierOrgId,
    purchaseOrderId: "",
    purchaseUnitPrice: "",
  };
}

export function applySalesCostFromPurchaseLine(
  projectItems: AppData["projectItems"],
  projectId: string,
  line: { productId: string; supplierOrgId: string; unitPrice: number; supplierPriceId?: string },
) {
  return projectItems.map((projectItem) => {
    if (projectItem.projectId !== projectId || projectItem.productId !== line.productId) return projectItem;
    if (isPurchaseLineItem(projectItem)) return projectItem;
    return {
      ...projectItem,
      supplierOrgId: projectItem.supplierOrgId || line.supplierOrgId,
      supplierPriceId: projectItem.supplierPriceId || line.supplierPriceId,
      costPrice: Number(projectItem.costPrice) > 0 ? projectItem.costPrice : line.unitPrice,
    };
  });
}

export function buildGroupedPurchaseOrders(
  project: Project,
  lines: PurchaseOrderComposerLine[],
  startIndex: number,
  sourceData: AppData,
  orderedAt?: string,
) {
  const now = orderedAt || nowIso();
  const groups = new Map<string, PurchaseOrderComposerLine[]>();
  lines.forEach((line) => {
    const key = line.supplierOrgId;
    const current = groups.get(key) ?? [];
    current.push(line);
    groups.set(key, current);
  });
  let nextProjectItems = [...sourceData.projectItems];
  const createdOrders: PurchaseOrder[] = [];
  let totalAmount = 0;
  let orderIndex = 0;
  groups.forEach((groupLines, supplierOrgId) => {
    const amount = groupLines.reduce((sum, line) => sum + line.unitPrice * line.quantity, 0);
    totalAmount += amount;
    const orderNo = nextPrefixedOrderNo(
      [
        ...sourceData.purchaseOrders.filter((item) => item.projectId === project.id).map((item) => item.orderNo),
        ...createdOrders.map((item) => item.orderNo),
      ],
      `PO-${project.projectNo}-`,
    );
    const order: PurchaseOrder = {
      id: createId("po"),
      projectId: project.id,
      orderNo,
      supplierOrgId,
      ownCompanyOrgId: project.ownCompanyOrgId,
      amount,
      status: "待下单",
      paymentStatus: DEFAULT_ORDER_PAYMENT_STATUS,
      reconcileStatus: DEFAULT_RECONCILE_STATUS,
      contractStatus: DEFAULT_CONTRACT_STATUS,
      logisticsStatus: DEFAULT_LOGISTICS_STATUS,
      acceptanceStatus: DEFAULT_ACCEPTANCE_STATUS,
      deliveryStatus: DEFAULT_DELIVERY_STATUS,
      createdAt: now,
      updatedAt: now,
      batchNo: String(startIndex + orderIndex + 1),
      note: groupLines.find((line) => line.note)?.note,
    };
    createdOrders.push(order);
    groupLines.forEach((line) => {
      const item = {
        id: createId("pi"),
        projectId: project.id,
        purchaseOrderId: order.id,
        supplierOrgId: order.supplierOrgId,
        supplierPriceId: line.supplierPriceId,
        productId: line.productId,
        productName: line.productName,
        quantity: line.quantity,
        deliveredQuantity: 0,
        actualPrice: 0,
        costPrice: line.unitPrice,
      };
      nextProjectItems = applySalesCostFromPurchaseLine(nextProjectItems, project.id, {
        productId: line.productId,
        supplierOrgId: order.supplierOrgId,
        unitPrice: line.unitPrice,
        supplierPriceId: line.supplierPriceId,
      });
      nextProjectItems = [item, ...nextProjectItems];
    });
    orderIndex += 1;
  });
  const projects = sourceData.projects.map((item) => item.id === project.id
    ? { ...item, totalCost: item.totalCost + totalAmount, updatedAt: now, purchaseStatus: "待采购" as const }
    : item);
  return {
    data: {
      ...sourceData,
      projects,
      purchaseOrders: [...createdOrders, ...sourceData.purchaseOrders],
      projectItems: nextProjectItems,
    },
    orderNos: createdOrders.map((order) => order.orderNo),
    totalAmount,
  };
}

export function appendProductsToPurchaseOrder(
  project: Project,
  order: PurchaseOrder,
  lines: PurchaseOrderComposerLine[],
  sourceData: AppData,
  extraNote?: string,
) {
  const now = nowIso();
  const addedAmount = lines.reduce((sum, line) => sum + line.unitPrice * line.quantity, 0);
  let nextProjectItems = [...sourceData.projectItems];
  const newItems = lines.map((line) => {
    nextProjectItems = applySalesCostFromPurchaseLine(nextProjectItems, project.id, {
      productId: line.productId,
      supplierOrgId: order.supplierOrgId,
      unitPrice: line.unitPrice,
      supplierPriceId: line.supplierPriceId,
    });
    return {
      id: createId("pi"),
      projectId: project.id,
      purchaseOrderId: order.id,
      supplierOrgId: order.supplierOrgId,
      supplierPriceId: line.supplierPriceId,
      productId: line.productId,
      productName: line.productName,
      quantity: line.quantity,
      deliveredQuantity: 0,
      actualPrice: 0,
      costPrice: line.unitPrice,
    };
  });
  nextProjectItems = [...newItems, ...nextProjectItems];
  const nextPurchaseOrders = sourceData.purchaseOrders.map((item) => item.id === order.id
    ? {
        ...item,
        amount: item.amount + addedAmount,
        note: extraNote || item.note,
        updatedAt: now,
      }
    : item);
  const projects = sourceData.projects.map((item) => item.id === project.id
    ? { ...item, totalCost: item.totalCost + addedAmount, updatedAt: now, purchaseStatus: "待采购" as const }
    : item);
  return {
    data: {
      ...sourceData,
      projects,
      purchaseOrders: nextPurchaseOrders,
      projectItems: nextProjectItems,
    },
    orderNos: [order.orderNo],
    totalAmount: addedAmount,
  };
}

export async function submitSalesOrderComposer(params: {
  data: AppData;
  commit: CommitFn;
  project: Project;
  composer: SalesComposerDraft;
  latestSupplierPrice: (prices: AppData["supplierPrices"], productId: string, supplierOrgId: string) => { id?: string; purchasePrice?: number } | undefined;
}): Promise<boolean> {
  const { data, commit, project, composer } = params;
  if (project.status === "已完成") {
    window.alert("已完成的项目不可添加销售订单。");
    return false;
  }
  const existingOrder = composer.targetOrderId
    ? data.salesOrders.find((item) => item.id === composer.targetOrderId && item.projectId === project.id)
    : undefined;
  if (composer.targetOrderId) {
    if (!existingOrder) {
      window.alert("未找到要追加的销售订单。");
      return false;
    }
    const blocked = salesOrderItemsEditBlockReason(data, existingOrder);
    if (blocked) {
      window.alert(blocked);
      return false;
    }
  }
  const purchaserCompany = composer.purchaserCompany.trim();
  const purchaserAddress = composer.purchaserAddress.trim();
  const purchaserName = composer.purchaserName.trim();
  const purchaserPhone = composer.purchaserPhone.trim();
  if (!existingOrder && (!purchaserCompany || !purchaserAddress || !purchaserName || !purchaserPhone)) {
    window.alert("请填写采购人公司名称、地址、姓名和电话。");
    return false;
  }
  if (composer.lines.length === 0) {
    window.alert("请先添加商品。");
    return false;
  }
  const now = nowIso();
  const orderedAt = existingOrder ? now : fromDateTimeLocalValue(composer.orderedAt);
  let workingProducts = [...data.products];
  const resolved: Array<{
    product: Product;
    quantity: number;
    unitPrice: number;
    supplierOrgId: string;
    purchaseOrderId: string;
    purchaseUnitPrice: number;
    supplierPriceId?: string;
  }> = [];
  for (const line of composer.lines) {
    const quantity = Number(line.quantity) || 1;
    const isDirect = line.directProductName.trim().length > 0;
    let product: Product | undefined;
    if (isDirect) {
      const platformPrice = Number(line.directPlatformPrice);
      product = buildProjectScopedProduct({
        id: createId("prd"),
        projectId: project.id,
        projectNo: project.projectNo,
        name: line.directProductName.trim(),
        platformPrice,
        createdAt: new Date().toISOString(),
      });
      workingProducts = [product, ...workingProducts];
    } else {
      product = workingProducts.find((item) => item.id === line.productId);
    }
    if (!product) {
      window.alert("请选择商品或填写快捷商品名称。");
      return false;
    }
    if (!line.supplierOrgId) {
      window.alert(`请为「${product.name}」选择渠道供应商。`);
      return false;
    }
    const unitPrice = isDirect
      ? Number(line.directPlatformPrice) || 0
      : Number(line.salesUnitPrice) || product.quotePrice;
    const supplierPrice = params.latestSupplierPrice(data.supplierPrices, product.id, line.supplierOrgId);
    const purchaseUnitPrice = Number(line.purchaseUnitPrice) || supplierPrice?.purchasePrice || product.costPrice || 0;
    resolved.push({
      product,
      quantity,
      unitPrice,
      supplierOrgId: line.supplierOrgId,
      purchaseOrderId: line.purchaseOrderId,
      purchaseUnitPrice,
      supplierPriceId: supplierPrice?.id,
    });
  }
  let working: AppData = { ...data, products: workingProducts };
  const newPurchaseLines = resolved.filter((line) => !line.purchaseOrderId).map((line) => ({
    productId: line.product.id,
    productName: line.product.name,
    quantity: line.quantity,
    supplierOrgId: line.supplierOrgId,
    unitPrice: line.purchaseUnitPrice,
    supplierPriceId: line.supplierPriceId,
  }));
  if (newPurchaseLines.length > 0) {
    const created = buildGroupedPurchaseOrders(
      project,
      newPurchaseLines,
      working.purchaseOrders.filter((item) => item.projectId === project.id).length,
      working,
      existingOrder ? undefined : orderedAt,
    );
    working = created.data;
  }
  const appendGroups = new Map<string, PurchaseOrderComposerLine[]>();
  resolved.filter((line) => line.purchaseOrderId).forEach((line) => {
    const current = appendGroups.get(line.purchaseOrderId) ?? [];
    current.push({
      productId: line.product.id,
      productName: line.product.name,
      quantity: line.quantity,
      supplierOrgId: line.supplierOrgId,
      unitPrice: line.purchaseUnitPrice,
      supplierPriceId: line.supplierPriceId,
    });
    appendGroups.set(line.purchaseOrderId, current);
  });
  for (const [purchaseOrderId, lines] of appendGroups) {
    const order = working.purchaseOrders.find((item) => item.id === purchaseOrderId);
    if (!order) continue;
    if (!canAppendPurchaseOrderItems(order)) {
      window.alert(`采购订单 ${order.orderNo} 当前状态不可追加商品。`);
      return false;
    }
    working = appendProductsToPurchaseOrder(project, order, lines, working).data;
  }
  const poIdForLine = (line: (typeof resolved)[number]) => {
    if (line.purchaseOrderId) return line.purchaseOrderId;
    return working.purchaseOrders.find((order) => order.projectId === project.id && order.supplierOrgId === line.supplierOrgId)?.id ?? "";
  };
  const orderId = existingOrder?.id ?? createId("so");
  const orderNo = existingOrder?.orderNo ?? nextPrefixedOrderNo(
    working.salesOrders.filter((item) => item.projectId === project.id).map((item) => item.orderNo),
    `SO-${project.projectNo}-`,
  );
  const newSalesItems: ProjectItem[] = resolved.map((line) => ({
    id: createId("pi"),
    projectId: project.id,
    salesOrderId: orderId,
    sourcePurchaseOrderId: poIdForLine(line) || undefined,
    supplierOrgId: line.supplierOrgId,
    productId: line.product.id,
    productName: line.product.name,
    quantity: line.quantity,
    actualPrice: line.unitPrice,
    costPrice: line.purchaseUnitPrice,
  }));
  const nextItems = [...newSalesItems, ...working.projectItems];
  const lineAmount = salesOrderItemsAmount(salesOrderLineItems(nextItems, orderId));
  const linkedPurchaseIds = [...new Set(resolved.map(poIdForLine).filter(Boolean))];
  const order: SalesOrder = existingOrder
    ? {
      ...existingOrder,
      amount: lineAmount,
      receivableAmount: lineAmount,
      platformOrderNo: composer.platformOrderNo || existingOrder.platformOrderNo,
      note: composer.note || existingOrder.note,
      purchaserCompany: purchaserCompany || existingOrder.purchaserCompany,
      purchaserAddress: purchaserAddress || existingOrder.purchaserAddress,
      purchaserName: purchaserName || existingOrder.purchaserName,
      purchaserPhone: purchaserPhone || existingOrder.purchaserPhone,
      purchaseOrderIds: [...new Set([...(existingOrder.purchaseOrderIds ?? []), ...linkedPurchaseIds])],
      updatedAt: now,
    }
    : {
      id: orderId,
      projectId: project.id,
      orderNo,
      platform: project.sourcePlatform,
      platformOrderNo: composer.platformOrderNo || project.platformOrderNo,
      customerOrgId: project.customerOrgId,
      ownCompanyOrgId: project.ownCompanyOrgId,
      amount: lineAmount,
      receivableAmount: lineAmount,
      receivedAmount: 0,
      status: "待付款",
      createdAt: orderedAt,
      updatedAt: orderedAt,
      note: composer.note || undefined,
      purchaserCompany,
      purchaserAddress,
      purchaserName,
      purchaserPhone,
      purchaseOrderIds: linkedPurchaseIds,
    };
  working = {
    ...working,
    products: workingProducts,
    salesOrders: existingOrder
      ? working.salesOrders.map((item) => item.id === existingOrder.id ? order : item)
      : [order, ...working.salesOrders],
    projectItems: nextItems,
  };
  const synced = applyProductProjectSync(working, project.id);
  await commit(
    synced.data,
    {
      action: existingOrder ? "追加销售订单商品" : "新增销售订单",
      targetType: "项目",
      targetName: project.name,
      operator: "当前用户",
      detail: `${orderNo} / ${newSalesItems.length} 个商品，已关联渠道采购${synced.autoDetail ? `；${synced.autoDetail}` : ""}`,
    },
  );
  return true;
}
