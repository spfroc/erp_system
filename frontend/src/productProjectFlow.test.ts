import { describe, expect, it } from "vitest";

import { seedData } from "./seed";
import {
  aggregateFulfillmentFromPurchaseOrders,
  invoicesEligibleToLink,
  invoiceTypeForLinkTarget,
  invoiceLinkBlockReason,
  invoiceRemainingAmount,
  invoiceAllocatedAmount,
  invoiceFullyMatchesItems,
  invoiceCompletelyMatchingProjectId,
  reconcileInvoiceProjectIds,
  invoiceHasProductOrderLinks,
  applyProductProjectSync,
  invoiceBelongsToProject,
  isPurchaseFulfillmentComplete,
  mapLegacyProductProjectStatus,
  nextPrefixedOrderNo,
  canAppendSalesOrderItems,
  canEditSalesOrderItems,
  isSalesOrderLogisticsLocked,
  salesOrderItemsEditBlockReason,
  canAppendPurchaseOrderItems,
  buildProductProjectName,
  invoicesForOrder,
  invoiceAmountForOrder,
  invoiceAmountForServiceOrder,
  serviceOrderInvoicedAmount,
  invoiceLineGrossAmount,
  allocatedInvoiceLineGross,
  applyInvoiceLineAllocations,
  applyServiceInvoiceAllocation,
  defaultInvoiceLinePickIndexes,
  orderInvoiceOverview,
  productProjectCompletionIssues,
  projectLinkedInvoices,
  projectVisibleInvoices,
  allocatedPurchaseCosts,
  applySalesOrderPurchaseLinks,
  purchaseOrderIdsTakenBySalesOrders,
  salesOrderItemsAmount,
  salesOrderLineItems,
  salesOrderProfit,
  syncSalesOrderAmountsFromItems,
  syncProductProjectStatus,
  withAutoCompletedPurchaseOrderStatus,
  buildProjectScopedProduct,
  isCatalogProduct,
  isProjectScopedProduct,
} from "./productProjectFlow";
import type { Project, PurchaseOrder } from "./types";

const baseProject: Project = {
  ...seedData.projects[0],
  id: "pj-flow",
  type: "商品项目",
  status: "初始化",
  logisticsStatus: "待发货",
  acceptanceStatus: "待验收",
  deliveryStatus: "待交付",
  paymentStatus: "待付款",
  invoiceStatus: "待开",
  reconcileStatus: "待对账",
  totalAmount: 0,
  totalCost: 0,
};

describe("productProjectFlow", () => {
  it("maps legacy product statuses", () => {
    const data = {
      salesOrders: [{ ...seedData.salesOrders[0], projectId: "pj-flow" }],
      purchaseOrders: [{ ...seedData.purchaseOrders[0], projectId: "pj-flow" }],
    };
    expect(mapLegacyProductProjectStatus("异常", data, "pj-flow")).toBe("终止");
    expect(mapLegacyProductProjectStatus("已完成", data, "pj-flow")).toBe("已完成");
    expect(mapLegacyProductProjectStatus("履约中", data, "pj-flow")).toBe("进行中");
    expect(mapLegacyProductProjectStatus("履约中", { salesOrders: [], purchaseOrders: [] }, "pj-flow")).toBe("初始化");
  });

  it("auto advances from 初始化 to 进行中 when sales and purchase exist", () => {
    const data = {
      salesOrders: [{ ...seedData.salesOrders[0], projectId: "pj-flow" }],
      purchaseOrders: [{ ...seedData.purchaseOrders[0], projectId: "pj-flow" }],
      invoices: [],
    };
    const result = syncProductProjectStatus(baseProject, data);
    expect(result.project.status).toBe("进行中");
    expect(result.autoDetail).toContain("系统自动");
    expect(result.changed).toBe(true);
  });

  it("does not leave terminal statuses automatically", () => {
    const data = {
      salesOrders: [{ ...seedData.salesOrders[0], projectId: "pj-flow", status: "已付款" as const }],
      purchaseOrders: [{ ...seedData.purchaseOrders[0], projectId: "pj-flow", status: "已完成" as const }],
      invoices: [],
    };
    const done = syncProductProjectStatus({
      ...baseProject,
      status: "已完成",
      logisticsStatus: "已签收",
      acceptanceStatus: "已验收",
      deliveryStatus: "已交付",
    }, data);
    expect(done.project.status).toBe("已完成");
    expect(done.autoDetail).toBeUndefined();

    const terminated = syncProductProjectStatus({ ...baseProject, status: "终止" }, data);
    expect(terminated.project.status).toBe("终止");
  });

  it("does not auto complete when orders and fulfillment are done", () => {
    const data = {
      salesOrders: [{ ...seedData.salesOrders[0], projectId: "pj-flow", status: "已付款" as const }],
      purchaseOrders: [{
        ...seedData.purchaseOrders[0],
        projectId: "pj-flow",
        status: "已完成" as const,
        paymentStatus: "已付款" as const,
        logisticsStatus: "已签收" as const,
        acceptanceStatus: "已验收" as const,
        deliveryStatus: "已交付" as const,
      }],
      invoices: [],
    };
    const result = syncProductProjectStatus({
      ...baseProject,
      status: "进行中",
      logisticsStatus: "待发货",
      acceptanceStatus: "待验收",
      deliveryStatus: "待交付",
    }, data);
    expect(productProjectCompletionIssues(result.project, data)).toEqual([]);
    expect(result.project.status).toBe("进行中");
    expect(result.project.logisticsStatus).toBe("已签收");
    expect(result.autoDetail).toBeUndefined();
  });

  it("allocates the next unused prefixed order number", () => {
    expect(nextPrefixedOrderNo([], "SO-XM1-")).toBe("SO-XM1-01");
    expect(nextPrefixedOrderNo(["SO-XM1-01", "SO-XM1-03"], "SO-XM1-")).toBe("SO-XM1-04");
    expect(nextPrefixedOrderNo(["SO-OTHER-09"], "SO-XM1-")).toBe("SO-XM1-01");
  });

  it("puts product-project remarks before the date in the generated name", () => {
    expect(buildProductProjectName({
      customerName: "青慧采",
      usageUnitName: "使用单位A",
      platform: "京东",
      remark: "加急",
      projectAt: "2026-08-20T15:00",
    })).toBe("青慧采 - 使用单位A - 京东 - 加急 - 2026年08月20日");
    expect(buildProductProjectName({
      customerName: "青慧采",
      projectAt: "2026-08-20",
    })).toBe("青慧采 - 2026年08月20日");
  });

  it("only allows appending items to unpaid sales orders", () => {
    expect(canAppendSalesOrderItems({ status: "待付款" })).toBe(true);
    expect(canAppendSalesOrderItems({ status: "部分付款" })).toBe(false);
    expect(canAppendSalesOrderItems({ status: "已付款" })).toBe(false);
  });

  it("locks sales order item edits after linked purchase is shipped or signed", () => {
    const unpaid = { id: "so-lock", status: "待付款" as const, purchaseOrderIds: ["po-lock"] };
    const waitingPo = { ...seedData.purchaseOrders[0], id: "po-lock", logisticsStatus: "待发货" as const };
    const shippedPo = { ...waitingPo, logisticsStatus: "已发货" as const };
    const signedPo = { ...waitingPo, logisticsStatus: "已签收" as const };
    const otherShipped = { ...waitingPo, id: "po-other", logisticsStatus: "已发货" as const };
    const items = [
      { id: "pi-lock", projectId: "pj-flow", salesOrderId: "so-lock", sourcePurchaseOrderId: "po-lock", productId: "prd-1", productName: "A", quantity: 1, actualPrice: 1, costPrice: 0 },
    ];
    expect(canEditSalesOrderItems({ purchaseOrders: [waitingPo], projectItems: items }, unpaid)).toBe(true);
    expect(isSalesOrderLogisticsLocked({ purchaseOrders: [shippedPo], projectItems: items }, unpaid)).toBe(true);
    expect(canEditSalesOrderItems({ purchaseOrders: [shippedPo], projectItems: items }, unpaid)).toBe(false);
    expect(canEditSalesOrderItems({ purchaseOrders: [signedPo], projectItems: items }, unpaid)).toBe(false);
    expect(salesOrderItemsEditBlockReason({ purchaseOrders: [signedPo], projectItems: items }, unpaid)).toContain("已发货或已签收");
    expect(canEditSalesOrderItems({ purchaseOrders: [waitingPo, otherShipped], projectItems: items }, unpaid)).toBe(true);
  });

  it("keeps dual-tagged sales lines when listing sales order items", () => {
    const items = [
      { id: "pi-dual", salesOrderId: "so-1", purchaseOrderId: "po-1", actualPrice: 4200, costPrice: 4050, productId: "prd-1", productName: "空调", quantity: 5, projectId: "pj-1" },
      { id: "pi-buy", salesOrderId: "so-1", purchaseOrderId: "po-1", actualPrice: 0, costPrice: 4050, productId: "prd-1", productName: "空调", quantity: 5, projectId: "pj-1" },
    ];
    expect(salesOrderLineItems(items, "so-1").map((item) => item.id)).toEqual(["pi-dual"]);
  });

  it("rebuilds sales order amount from line items", () => {
    expect(salesOrderItemsAmount([
      { quantity: 2, actualPrice: 939 },
      { quantity: 1, actualPrice: 5200 },
    ])).toBe(7078);
    const data = {
      ...seedData,
      projects: [{ ...baseProject, totalAmount: 100 }],
      salesOrders: [{ ...seedData.salesOrders[0], id: "so-fix", projectId: "pj-flow", amount: 100, receivableAmount: 100, status: "待付款" as const }],
      projectItems: [
        { id: "pi-a", projectId: "pj-flow", salesOrderId: "so-fix", productId: "prd-1", productName: "A", quantity: 2, actualPrice: 500, costPrice: 0 },
      ],
      purchaseOrders: [],
      invoices: [],
    };
    const synced = syncSalesOrderAmountsFromItems(data, "pj-flow");
    expect(synced.salesOrders.find((order) => order.id === "so-fix")?.amount).toBe(1000);
    expect(synced.salesOrders.find((order) => order.id === "so-fix")?.receivableAmount).toBe(1000);
    expect(synced.projects.find((project) => project.id === "pj-flow")?.totalAmount).toBe(1000);
  });

  it("aggregates multi-channel purchase fulfillment conservatively", () => {
    const orders: PurchaseOrder[] = [
      {
        ...seedData.purchaseOrders[0],
        id: "po-a",
        logisticsStatus: "已签收",
        acceptanceStatus: "已验收",
        deliveryStatus: "已交付",
      },
      {
        ...seedData.purchaseOrders[0],
        id: "po-b",
        logisticsStatus: "已发货",
        acceptanceStatus: "验收中",
        deliveryStatus: "部分交付",
      },
    ];
    expect(aggregateFulfillmentFromPurchaseOrders(orders)).toEqual({
      logisticsStatus: "已发货",
      acceptanceStatus: "验收中",
      deliveryStatus: "部分交付",
    });
  });

  it("marks purchase order status 已完成 when logistics/acceptance/delivery are all done", () => {
    const incomplete: PurchaseOrder = {
      ...seedData.purchaseOrders[0],
      status: "已下单",
      logisticsStatus: "已签收",
      acceptanceStatus: "已验收",
      deliveryStatus: "待交付",
    };
    expect(isPurchaseFulfillmentComplete(incomplete)).toBe(false);
    expect(withAutoCompletedPurchaseOrderStatus(incomplete).status).toBe("已下单");

    const complete: PurchaseOrder = {
      ...incomplete,
      deliveryStatus: "已交付",
    };
    expect(isPurchaseFulfillmentComplete(complete)).toBe(true);
    expect(withAutoCompletedPurchaseOrderStatus(complete).status).toBe("已完成");
    expect(withAutoCompletedPurchaseOrderStatus({ ...complete, status: "已取消" }).status).toBe("已取消");

    const data = {
      ...seedData,
      projects: [{ ...baseProject, id: "pj-flow", status: "进行中" as const }],
      salesOrders: [{ ...seedData.salesOrders[0], projectId: "pj-flow", status: "已付款" as const }],
      purchaseOrders: [{
        ...seedData.purchaseOrders[0],
        id: "po-auto",
        orderNo: "PO-AUTO",
        projectId: "pj-flow",
        status: "已下单" as const,
        paymentStatus: "已付款" as const,
        logisticsStatus: "已签收" as const,
        acceptanceStatus: "已验收" as const,
        deliveryStatus: "已交付" as const,
      }],
      invoices: [],
    };
    const synced = applyProductProjectSync(data, "pj-flow");
    expect(synced.data.purchaseOrders.find((order) => order.id === "po-auto")?.status).toBe("已完成");
    expect(synced.autoDetail).toContain("PO-AUTO");
    expect(synced.autoDetail).toContain("执行状态标记为已完成");
  });

  it("syncs project totalCost from active purchase orders", () => {
    const data = {
      ...seedData,
      projects: [{ ...baseProject, id: "pj-flow", status: "进行中" as const, totalCost: 13846.83 }],
      salesOrders: [{ ...seedData.salesOrders[0], projectId: "pj-flow" }],
      purchaseOrders: [
        { ...seedData.purchaseOrders[0], id: "po-live", projectId: "pj-flow", amount: 14056.83, status: "已下单" as const },
        { ...seedData.purchaseOrders[0], id: "po-cancel", projectId: "pj-flow", amount: 210, status: "已取消" as const },
      ],
      invoices: [],
    };
    const synced = applyProductProjectSync(data, "pj-flow");
    expect(synced.project?.totalCost).toBe(14056.83);
    expect(synced.data.projects.find((project) => project.id === "pj-flow")?.totalCost).toBe(14056.83);
  });

  it("aggregates project invoices via order links even without projectIds", () => {
    const data = {
      ...seedData,
      salesOrders: [{ ...seedData.salesOrders[0], id: "so-x", projectId: "pj-flow" }],
      purchaseOrders: [{ ...seedData.purchaseOrders[0], id: "po-x", projectId: "pj-flow" }],
      invoices: [
        {
          ...seedData.invoices[0],
          id: "inv-sales-only",
          projectId: undefined,
          projectIds: [],
          salesOrderIds: ["so-x"],
          purchaseOrderIds: [],
        },
        {
          ...seedData.invoices[0],
          id: "inv-purchase-only",
          type: "进项" as const,
          projectId: undefined,
          projectIds: [],
          salesOrderIds: [],
          purchaseOrderIds: ["po-x"],
        },
        {
          ...seedData.invoices[0],
          id: "inv-other",
          projectId: "pj-other",
          projectIds: ["pj-other"],
          salesOrderIds: [],
          purchaseOrderIds: [],
        },
        {
          ...seedData.invoices[0],
          id: "inv-project-only",
          projectId: "pj-flow",
          projectIds: ["pj-flow"],
          salesOrderIds: [],
          purchaseOrderIds: [],
        },
        {
          ...seedData.invoices[0],
          id: "inv-void",
          status: "作废" as const,
          projectId: undefined,
          projectIds: [],
          salesOrderIds: ["so-x"],
          purchaseOrderIds: [],
        },
      ],
    };
    expect(invoiceBelongsToProject(data, data.invoices[0], "pj-flow")).toBe(true);
    expect(invoiceBelongsToProject(data, data.invoices[1], "pj-flow")).toBe(true);
    expect(invoiceBelongsToProject(data, data.invoices[2], "pj-flow")).toBe(false);
    expect(invoiceBelongsToProject(data, data.invoices[3], "pj-flow")).toBe(true);
    // 详情页签与订单关联一致：仅订单挂载计入，排除仅挂项目与作废
    expect(projectLinkedInvoices(data, "pj-flow").map((invoice) => invoice.id)).toEqual([
      "inv-sales-only",
      "inv-purchase-only",
    ]);
    expect(projectVisibleInvoices(data, { id: "pj-flow", type: "商品项目" }).map((invoice) => invoice.id)).toEqual([
      "inv-sales-only",
      "inv-purchase-only",
    ]);
  });

  it("shows project-linked invoices on service project details", () => {
    const serviceProject = seedData.projects.find((project) => project.type === "服务项目");
    expect(serviceProject).toBeTruthy();
    const projectId = serviceProject!.id;
    const data = {
      ...seedData,
      salesOrders: [],
      purchaseOrders: [],
      invoices: [
        {
          ...seedData.invoices[0],
          id: "inv-service-project",
          projectId,
          projectIds: [projectId],
          salesOrderIds: [],
          purchaseOrderIds: [],
        },
        {
          ...seedData.invoices[0],
          id: "inv-other-service",
          projectId: "pj-other",
          projectIds: ["pj-other"],
          salesOrderIds: [],
          purchaseOrderIds: [],
        },
      ],
    };
    expect(projectVisibleInvoices(data, serviceProject!).map((invoice) => invoice.id)).toEqual([
      "inv-service-project",
    ]);
    expect(projectLinkedInvoices(data, projectId)).toEqual([]);
  });

  it("marks project-scoped products separately from catalog products", () => {
    const product = buildProjectScopedProduct({
      id: "prd-demo",
      projectId: "pj-flow",
      projectNo: "XM20260820001",
      name: " 项目专用空调 ",
      platformPrice: 1990,
      createdAt: "2026-08-20T01:00:00.000Z",
    });
    expect(product.source).toBe("project");
    expect(product.sourceProjectId).toBe("pj-flow");
    expect(product.name).toBe("项目专用空调");
    expect(product.frameworkPrice).toBe(1990);
    expect(product.quotePrice).toBe(1990);
    expect(isCatalogProduct(product)).toBe(false);
    expect(isProjectScopedProduct(product, "pj-flow")).toBe(true);
    expect(isProjectScopedProduct(product, "pj-other")).toBe(false);
    expect(isCatalogProduct({ source: "catalog" })).toBe(true);
    expect(isCatalogProduct({})).toBe(true);
  });

  it("summarizes linked invoices on an order", () => {
    const data = {
      ...seedData,
      serviceOrders: [{ ...seedData.serviceOrders[0], id: "svc-x", projectId: "pj-svc" }],
      invoices: [
        {
          ...seedData.invoices[0],
          id: "inv-so",
          invoiceNo: "DX-001",
          amount: 800,
          status: "已确认" as const,
          salesOrderIds: ["so-x"],
          purchaseOrderIds: [],
        },
        {
          ...seedData.invoices[0],
          id: "inv-po",
          invoiceNo: "JX-001",
          type: "进项" as const,
          amount: 300,
          status: "已收" as const,
          salesOrderIds: [],
          purchaseOrderIds: ["po-x"],
        },
        {
          ...seedData.invoices[0],
          id: "inv-svc",
          invoiceNo: "SV-001",
          type: "销项" as const,
          amount: 2000,
          status: "已开" as const,
          projectId: "pj-svc",
          projectIds: ["pj-svc"],
          salesOrderIds: [],
          purchaseOrderIds: [],
        },
      ],
    };
    expect(invoicesForOrder(data, "so-x", "sales").map((invoice) => invoice.id)).toEqual(["inv-so"]);
    expect(orderInvoiceOverview(data, "so-x", "sales", 1830).statusLabel).toBe("已开部分");
    expect(orderInvoiceOverview(data, "missing", "sales", 1000).statusLabel).toBe("未开票");
    expect(orderInvoiceOverview(data, "po-x", "purchase", 300).statusLabel).toBe("已收全部");
    expect(orderInvoiceOverview(data, "svc-x", "service", 2000).statusLabel).toBe("已开全部");
    expect(invoicesForOrder(data, "svc-x", "service").map((invoice) => invoice.invoiceNo)).toEqual(["SV-001"]);
  });

  it("splits one invoice across orders by line item amounts", () => {
    const invoice = {
      ...seedData.invoices[0],
      id: "inv-split",
      amount: 12470.04,
      salesOrderIds: ["so-a", "so-b"],
      purchaseOrderIds: [],
      lineItems: [
        { productName: "拉链袋", amount: 39.82, taxAmount: 5.18, salesOrderId: "so-a" },
        { productName: "红茶", amount: 5498.62, taxAmount: 714.82, salesOrderId: "so-a" },
        { productName: "绿茶", amount: 4811.29, taxAmount: 625.47, salesOrderId: "so-b" },
      ],
    };
    const data = { ...seedData, invoices: [invoice] };
    expect(invoiceLineGrossAmount(invoice.lineItems[0])).toBe(45);
    expect(invoiceAmountForOrder(invoice, "so-a", "sales")).toBe(6258.44);
    expect(invoiceAmountForOrder(invoice, "so-b", "sales")).toBe(5436.76);
    expect(invoicesForOrder(data, "so-a", "sales").map((item) => item.id)).toEqual(["inv-split"]);
    expect(invoicesForOrder(data, "so-b", "sales").map((item) => item.id)).toEqual(["inv-split"]);
    expect(orderInvoiceOverview(data, "so-a", "sales", 6258.44).invoiced).toBe(6258.44);
  });

  it("defaults invoice pick indexes to lines whose tax-inclusive total matches an order line amount", () => {
    const lines = [
      { productName: "拉链袋", amount: 39.82, taxAmount: 5.18 },
      { productName: "红茶", amount: 5498.62, taxAmount: 714.82 },
      { productName: "绿茶", amount: 4811.29, taxAmount: 625.47 },
      { productName: "重复拉链袋", amount: 39.82, taxAmount: 5.18 },
    ];
    expect(defaultInvoiceLinePickIndexes(lines, [{ lineAmount: 45 }])).toEqual([0]);
    expect(defaultInvoiceLinePickIndexes(lines, [{ lineAmount: 45 }, { lineAmount: 45 }])).toEqual([0, 3]);
    expect(defaultInvoiceLinePickIndexes(lines, [{ lineAmount: 6213.44 }, { lineAmount: 45 }])).toEqual([0, 1]);
    expect(defaultInvoiceLinePickIndexes(lines, [{ lineAmount: 1830 }])).toEqual([]);
    expect(defaultInvoiceLinePickIndexes(
      [
        { ...lines[0], salesOrderId: "so-other" },
        lines[1],
      ],
      [{ lineAmount: 45 }, { lineAmount: 6213.44 }],
      "so-current",
      "sales",
    )).toEqual([1]);
    expect(defaultInvoiceLinePickIndexes(
      [
        { ...lines[0], salesOrderId: "so-current" },
        lines[1],
      ],
      [{ lineAmount: 45 }, { lineAmount: 6213.44 }],
      "so-current",
      "sales",
    )).toEqual([1]);
  });

  it("splits invoice lines when only part of the quantity is linked", () => {
    const invoice = {
      ...seedData.invoices[0],
      id: "inv-qty",
      amount: 113,
      lineItems: [
        { productName: "拉链袋", quantity: 10, unitPrice: 10, amount: 100, taxAmount: 13 },
      ],
    };
    expect(allocatedInvoiceLineGross(invoice.lineItems[0], 3)).toBe(33.9);
    const next = applyInvoiceLineAllocations(invoice, "sales", [{ index: 0, quantity: 3 }], "so-a");
    expect(next.lineItems).toEqual([
      { productName: "拉链袋", quantity: 3, unitPrice: 10, amount: 30, taxAmount: 3.9, salesOrderId: "so-a", purchaseOrderId: undefined },
      { productName: "拉链袋", quantity: 7, unitPrice: 10, amount: 70, taxAmount: 9.1 },
    ]);
    expect(next.salesOrderIds).toEqual(["so-a"]);
  });

  it("does not round a split VAT line one cent over the order amount", () => {
    const invoice = {
      ...seedData.invoices[0],
      id: "inv-ac-split",
      amount: 3500,
      lineItems: [
        { productName: "空调 KFR-35GW/KS2", quantity: 2, unitPrice: 1548.67, amount: 3097.35, taxAmount: 402.65 },
      ],
    };
    expect(allocatedInvoiceLineGross(invoice.lineItems[0], 1)).toBe(1750);
    const next = applyInvoiceLineAllocations(invoice, "purchase", [{ index: 0, quantity: 1 }], "po-a");
    expect(next.lineItems![0]).toMatchObject({
      quantity: 1,
      amount: 1548.68,
      taxAmount: 201.32,
      purchaseOrderId: "po-a",
    });
    expect(next.lineItems![1]).toMatchObject({
      quantity: 1,
      amount: 1548.67,
      taxAmount: 201.33,
    });
    expect(invoiceLineGrossAmount(next.lineItems![0])).toBe(1750);
    expect(invoiceLineGrossAmount(next.lineItems![1])).toBe(1750);
    expect(invoiceAmountForOrder(next, "po-a", "purchase")).toBe(1750);
    expect(Number(next.lineItems![0].amount) + Number(next.lineItems![1].amount)).toBeCloseTo(3097.35, 2);
    expect(Number(next.lineItems![0].taxAmount) + Number(next.lineItems![1].taxAmount)).toBeCloseTo(402.65, 2);
  });

  it("does not re-split invoice lines already linked to another order", () => {
    const invoice = {
      ...seedData.invoices[0],
      id: "inv-locked",
      amount: 113,
      lineItems: [
        { productName: "拉链袋", quantity: 3, unitPrice: 10, amount: 30, taxAmount: 3.9, salesOrderId: "so-other" },
        { productName: "拉链袋", quantity: 7, unitPrice: 10, amount: 70, taxAmount: 9.1 },
      ],
    };
    const next = applyInvoiceLineAllocations(invoice, "sales", [{ index: 0, quantity: 1 }, { index: 1, quantity: 7 }], "so-a");
    expect(next.lineItems?.[0]).toMatchObject({ quantity: 3, salesOrderId: "so-other" });
    expect(next.lineItems?.[1]).toMatchObject({ quantity: 7, salesOrderId: "so-a" });
    expect(next.salesOrderIds).toEqual(["so-other", "so-a"]);
  });

  it("reconciles mixed product/service project ids onto the real order side", () => {
    const mixed = {
      ...seedData.invoices[0],
      id: "inv-mixed",
      projectId: "pj-2",
      projectIds: ["pj-2", "pj-1"],
      salesOrderIds: ["so-1"],
      purchaseOrderIds: [],
      lineItems: [{ productName: "挂机", amount: 1830, salesOrderId: "so-1" }],
    };
    const reconciled = reconcileInvoiceProjectIds(seedData, mixed);
    expect(reconciled.projectIds).toEqual(["pj-1"]);
    expect(reconciled.projectId).toBe("pj-1");
    expect(invoiceHasProductOrderLinks(mixed)).toBe(true);

    const leftoverProduct = reconcileInvoiceProjectIds(seedData, {
      ...seedData.invoices[0],
      id: "inv-svc-leftover",
      projectId: "pj-2",
      projectIds: ["pj-2", "pj-1"],
      salesOrderIds: [],
      purchaseOrderIds: [],
      lineItems: [],
    });
    expect(leftoverProduct.projectIds).toEqual(["pj-2"]);
  });

  it("locks further links when invoice amount is fully allocated or a project completely matches", () => {
    const partial = {
      ...seedData.invoices[0],
      id: "inv-partial",
      amount: 90,
      projectId: "pj-1",
      projectIds: ["pj-1"],
      salesOrderIds: ["so-1"],
      lineItems: [
        { productName: "拉链袋", amount: 39.82, taxAmount: 5.18, salesOrderId: "so-1" },
        { productName: "票夹", amount: 39.82, taxAmount: 5.18 },
      ],
    };
    expect(invoiceRemainingAmount(seedData, partial)).toBe(45);
    expect(invoiceLinkBlockReason(seedData, partial, { kind: "service", projectId: "pj-2" })).toContain("商品订单");
    expect(invoiceLinkBlockReason(seedData, partial, { kind: "sales", projectId: "pj-1", orderId: "so-other" })).toBeNull();

    const full = {
      ...partial,
      id: "inv-full",
      lineItems: partial.lineItems.map((item) => ({ ...item, salesOrderId: "so-1" })),
    };
    expect(invoiceRemainingAmount(seedData, full)).toBe(0);
    expect(invoiceLinkBlockReason(seedData, full, { kind: "sales", projectId: "pj-1", orderId: "so-other" })).toContain("额度已全部关联");

    const serviceInvoice = {
      ...seedData.invoices[0],
      id: "inv-svc-lock",
      amount: 2000,
      type: "销项" as const,
      projectId: "pj-2",
      projectIds: ["pj-2"],
      salesOrderIds: [],
      purchaseOrderIds: [],
      lineItems: [],
    };
    expect(invoiceRemainingAmount(seedData, serviceInvoice)).toBe(0);
    expect(invoiceFullyMatchesItems(serviceInvoice, [{ lineAmount: 2000 }])).toBe(true);
    expect(invoiceLinkBlockReason(seedData, serviceInvoice, { kind: "sales", projectId: "pj-1", orderId: "so-1" })).toContain("服务项目");
    expect(invoicesEligibleToLink({ ...seedData, invoices: [serviceInvoice, full] }, { kind: "service", projectId: "pj-3" })).toEqual([]);
  });

  it("locks an invoice to the project whose items completely match it", () => {
    const invoice = {
      ...seedData.invoices[0],
      id: "inv-exact",
      amount: 90,
      projectId: "pj-1",
      projectIds: ["pj-1"],
      salesOrderIds: ["so-1"],
      lineItems: [
        { productName: "拉链袋", amount: 39.82, taxAmount: 5.18, salesOrderId: "so-1" },
        { productName: "票夹", amount: 39.82, taxAmount: 5.18 },
      ],
    };
    const data = {
      ...seedData,
      projectItems: [
        { ...seedData.projectItems[0], quantity: 1, actualPrice: 45 },
        { ...seedData.projectItems[0], id: "pi-clip", productName: "票夹", quantity: 1, actualPrice: 45, salesOrderId: "so-1" },
      ],
    };
    expect(invoiceRemainingAmount(data, invoice)).toBe(45);
    expect(invoiceCompletelyMatchingProjectId(data, invoice)).toBe("pj-1");
    expect(invoiceLinkBlockReason(data, invoice, { kind: "service", projectId: "pj-2" })).toContain("商品订单");
    expect(invoiceLinkBlockReason(data, invoice, { kind: "sales", projectId: "pj-1", orderId: "so-1" })).toBeNull();
    expect(invoiceLinkBlockReason(data, invoice, { kind: "sales", projectId: "pj-other", orderId: "so-other" })).toContain("完全匹配");
  });

  it("hides product-linked invoices from service projects and service orders", () => {
    const invoice = {
      ...seedData.invoices[0],
      id: "inv-cross",
      type: "销项" as const,
      projectId: "pj-2",
      projectIds: ["pj-2", "pj-1"],
      salesOrderIds: ["so-1"],
      lineItems: [{ productName: "挂机", amount: 1830, salesOrderId: "so-1" }],
    };
    const data = { ...seedData, invoices: [invoice], serviceOrders: [{ ...seedData.serviceOrders[0], id: "svc-x", projectId: "pj-2" }] };
    expect(projectVisibleInvoices(data, seedData.projects[1]).map((item) => item.id)).not.toContain("inv-cross");
    expect(invoicesForOrder(data, "svc-x", "service").map((item) => item.id)).not.toContain("inv-cross");
    expect(invoicesForOrder(data, "so-1", "sales").map((item) => item.id)).toContain("inv-cross");
  });

  it("only offers 销项 invoices to sales orders and 进项 invoices to purchase orders", () => {
    const salesInvoice = { ...seedData.invoices[0], id: "inv-sales-type", type: "销项" as const, amount: 100, lineItems: [], salesOrderIds: [], purchaseOrderIds: [], projectIds: [] };
    const purchaseInvoice = { ...seedData.invoices[0], id: "inv-purchase-type", type: "进项" as const, amount: 100, lineItems: [], salesOrderIds: [], purchaseOrderIds: [], projectIds: [] };
    const data = { ...seedData, invoices: [salesInvoice, purchaseInvoice] };
    expect(invoiceTypeForLinkTarget({ kind: "sales", projectId: "pj-1", orderId: "so-1" })).toBe("销项");
    expect(invoiceTypeForLinkTarget({ kind: "purchase", projectId: "pj-1", orderId: "po-1" })).toBe("进项");
    expect(invoiceLinkBlockReason(data, purchaseInvoice, { kind: "sales", projectId: "pj-1", orderId: "so-1" })).toContain("销项");
    expect(invoiceLinkBlockReason(data, salesInvoice, { kind: "purchase", projectId: "pj-1", orderId: "po-1" })).toContain("进项");
    expect(invoicesEligibleToLink(data, { kind: "sales", projectId: "pj-1", orderId: "so-1" }).map((item) => item.id)).toEqual(["inv-sales-type"]);
    expect(invoicesEligibleToLink(data, { kind: "purchase", projectId: "pj-1", orderId: "po-1" }).map((item) => item.id)).toEqual(["inv-purchase-type"]);
  });

  it("splits one service invoice across projects and orders by allocation amount", () => {
    const baseInvoice = {
      ...seedData.invoices[0],
      id: "inv-svc-split",
      invoiceNo: "SV-SPLIT",
      type: "销项" as const,
      amount: 3000,
      status: "已开" as const,
      projectId: undefined,
      projectIds: [] as string[],
      salesOrderIds: [] as string[],
      purchaseOrderIds: [] as string[],
      lineItems: [],
      serviceAllocations: undefined as undefined,
    };
    const afterFirst = applyServiceInvoiceAllocation(seedData, baseInvoice, {
      projectId: "pj-3",
      serviceOrderId: "svc-2",
      amount: 1000,
    });
    expect(invoiceAllocatedAmount(seedData, afterFirst)).toBe(1000);
    expect(invoiceRemainingAmount(seedData, afterFirst)).toBe(2000);
    expect(invoiceLinkBlockReason(seedData, afterFirst, { kind: "service", projectId: "pj-3", orderId: "svc-2" })).toBeNull();
    expect(invoiceLinkBlockReason(seedData, afterFirst, { kind: "service", projectId: "pj-2", orderId: "svc-1" })).toBeNull();
    expect(invoicesEligibleToLink({ ...seedData, invoices: [afterFirst] }, { kind: "service", projectId: "pj-2" }).map((item) => item.id)).toEqual(["inv-svc-split"]);

    const afterSecond = applyServiceInvoiceAllocation(seedData, afterFirst, {
      projectId: "pj-2",
      serviceOrderId: "svc-1",
      amount: 2000,
    });
    expect(invoiceRemainingAmount(seedData, afterSecond)).toBe(0);
    expect(afterSecond.projectIds).toEqual(expect.arrayContaining(["pj-2", "pj-3"]));

    const data = {
      ...seedData,
      invoices: [afterSecond],
    };
    expect(invoiceAmountForServiceOrder(data, afterSecond, "svc-2")).toBe(1000);
    expect(invoiceAmountForServiceOrder(data, afterSecond, "svc-1")).toBe(2000);
    expect(serviceOrderInvoicedAmount(data, "svc-2")).toBe(1000);
    expect(orderInvoiceOverview(data, "svc-2", "service", 1000)).toMatchObject({
      invoiced: 1000,
      statusLabel: "已开全部",
    });
    expect(orderInvoiceOverview(data, "svc-1", "service", 2000)).toMatchObject({
      invoiced: 2000,
      statusLabel: "已开全部",
    });
    expect(invoicesForOrder(data, "svc-1", "service").map((item) => item.id)).toEqual(["inv-svc-split"]);
    expect(invoicesForOrder(data, "svc-2", "service").map((item) => item.id)).toEqual(["inv-svc-split"]);
  });

  it("allocates purchase cost across linked sales orders and keeps the cents", () => {
    const purchase = { ...seedData.purchaseOrders[0], id: "po-share", amount: 100, status: "待下单" as const };
    const salesA = { ...seedData.salesOrders[0], id: "so-a", amount: 100, status: "待付款" as const, purchaseOrderIds: ["po-share"] };
    const salesB = { ...seedData.salesOrders[0], id: "so-b", amount: 300, status: "已付款" as const, purchaseOrderIds: ["po-share"] };
    const cancelled = { ...seedData.salesOrders[0], id: "so-cancel", amount: 900, status: "取消" as const, purchaseOrderIds: ["po-share"] };
    const data = {
      ...seedData,
      salesOrders: [salesA, salesB, cancelled],
      purchaseOrders: [purchase],
      projectItems: [],
    };
    expect(allocatedPurchaseCosts(data, purchase).get("so-a")).toBe(25);
    expect(allocatedPurchaseCosts(data, purchase).get("so-b")).toBe(75);
    expect(salesOrderProfit(data, salesA)).toMatchObject({ salesAmount: 100, costAmount: 25, profit: 75, margin: 0.75 });
    expect(salesOrderProfit(data, salesB).profit).toBe(225);
    expect(salesOrderProfit(data, cancelled)).toMatchObject({ salesAmount: 0, costAmount: 0, profit: 0, margin: null });
    expect([...purchaseOrderIdsTakenBySalesOrders(data)]).toEqual(["po-share"]);
    const released = {
      ...data,
      salesOrders: data.salesOrders.map((order) => order.id === "so-b" ? { ...order, status: "退款" as const } : order.status === "待付款" ? { ...order, status: "取消" as const, purchaseOrderIds: [] } : order),
      projectItems: [],
    };
    expect([...purchaseOrderIdsTakenBySalesOrders(released)]).toEqual([]);
  });

  it("replaces manual purchase links and clears detached line pointers", () => {
    const data = {
      ...seedData,
      salesOrders: [{ ...seedData.salesOrders[0], id: "so-link", purchaseOrderIds: ["po-old"] }],
      projectItems: [{
        ...seedData.projectItems[0],
        id: "pi-link",
        salesOrderId: "so-link",
        sourcePurchaseOrderId: "po-old",
      }],
    };
    const next = applySalesOrderPurchaseLinks(data, "so-link", ["po-new", "po-new"]);
    expect(next.salesOrders.find((order) => order.id === "so-link")?.purchaseOrderIds).toEqual(["po-new"]);
    expect(next.projectItems.find((item) => item.id === "pi-link")?.sourcePurchaseOrderId).toBeUndefined();
  });

  it("keeps legacy service project links as fully allocated", () => {
    const legacy = {
      ...seedData.invoices[0],
      id: "inv-svc-legacy",
      amount: 2000,
      type: "销项" as const,
      projectId: "pj-2",
      projectIds: ["pj-2"],
      salesOrderIds: [],
      purchaseOrderIds: [],
      lineItems: [],
    };
    expect(invoiceAllocatedAmount(seedData, legacy)).toBe(2000);
    expect(invoiceRemainingAmount(seedData, legacy)).toBe(0);
    expect(invoiceLinkBlockReason(seedData, legacy, { kind: "service", projectId: "pj-3" })).toBeTruthy();
  });
});
