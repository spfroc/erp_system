import { describe, expect, it } from "vitest";

import { diffPartialAppData, migrateData } from "./db";
import { seedData } from "./seed";
import type { ProjectStatus } from "./types";

describe("migrateData", () => {
  it("does not resurrect deleted seed organizations", () => {
    const migrated = migrateData({ ...seedData, organizations: [] });

    expect(migrated.organizations).toEqual([]);
  });

  it("uses seed organizations only when the collection is absent", () => {
    const migrated = migrateData({});

    expect(migrated.organizations).toEqual(seedData.organizations);
  });

  it("preserves legacy completed service-project statuses after reload", () => {
    const project = { ...seedData.projects[0], type: "服务项目" as const, status: "结束" as const };
    const migrated = migrateData({ ...seedData, projects: [project] });

    expect(migrated.projects[0].status).toBe("结束");
  });

  it("preserves configured service completion statuses after reload", () => {
    const project = { ...seedData.projects[0], type: "服务项目" as const, status: "服务完成" as const };
    const migrated = migrateData({ ...seedData, projects: [project] });

    expect(migrated.projects[0].status).toBe("服务完成");
  });

  it("preserves renamed service statuses configured in option settings", () => {
    const project = { ...seedData.projects[0], type: "服务项目" as const, status: "交付完成" as ProjectStatus };
    const optionGroups = seedData.optionGroups.map((group) => group.key === "service_project_status"
      ? {
          ...group,
          items: [...group.items, { id: "opt-service-renamed", label: "交付完成", value: "交付完成", enabled: true, sortOrder: 99 }],
        }
      : group);
    const migrated = migrateData({ ...seedData, optionGroups, projects: [project] });

    expect(migrated.projects[0].status).toBe("交付完成");
  });

  it("repairs auto-generated purchase order amount and item cost from supplier price", () => {
    const project = {
      ...seedData.projects[0],
      id: "pj-repair",
      type: "商品项目" as const,
      projectNo: "XM20260810999",
      totalCost: 0,
      totalAmount: 21000,
    };
    const product = {
      ...seedData.products[0],
      id: "prd-repair",
      costPrice: 4050,
      quotePrice: 4200,
    };
    const supplier = seedData.organizations.find((org) => org.roles.includes("上游供应商")) ?? seedData.organizations[0];
    const migrated = migrateData({
      ...seedData,
      projects: [project],
      products: [product],
      salesOrders: [{
        ...seedData.salesOrders[0],
        id: "so-repair",
        projectId: project.id,
        amount: 21000,
      }],
      purchaseOrders: [{
        id: "po-pj-repair",
        projectId: project.id,
        orderNo: "PO-XM20260810999",
        supplierOrgId: supplier.id,
        amount: 0,
        status: "待下单" as const,
        createdAt: "2026-08-10T00:00:00.000Z",
        note: "由旧项目数据自动生成",
      }],
      projectItems: [{
        id: "pi-repair",
        projectId: project.id,
        purchaseOrderId: "po-pj-repair",
        productId: product.id,
        productName: product.name,
        quantity: 5,
        actualPrice: 0,
        costPrice: 0,
        supplierOrgId: supplier.id,
      }],
      supplierPrices: [{
        id: "sp-repair",
        productId: product.id,
        supplierOrgId: supplier.id,
        purchasePrice: 4050,
        effectiveDate: "2026-08-10",
        note: "测试渠道价",
      }],
    });

    const order = migrated.purchaseOrders.find((item) => item.id === "po-pj-repair");
    const item = migrated.projectItems.find((entry) => entry.id === "pi-repair");
    expect(item?.purchaseOrderId).toBe("po-pj-repair");
    expect(item?.costPrice).toBe(4050);
    expect(order?.amount).toBe(20250);
    expect(migrated.projects[0].totalCost).toBe(20250);
  });

  it("sums product project totalCost from active purchase orders as numbers", () => {
    const project = {
      ...seedData.projects[0],
      id: "pj-cost-sum",
      type: "商品项目" as const,
      totalCost: 210,
    };
    const migrated = migrateData({
      ...seedData,
      projects: [project],
      purchaseOrders: [
        { ...seedData.purchaseOrders[0], id: "po-a", projectId: project.id, amount: "100.1" as unknown as number, status: "待下单" },
        { ...seedData.purchaseOrders[0], id: "po-b", projectId: project.id, amount: "200.2" as unknown as number, status: "待下单" },
        { ...seedData.purchaseOrders[0], id: "po-c", projectId: project.id, amount: "999" as unknown as number, status: "已取消" },
      ],
    });
    expect(migrated.projects[0].totalCost).toBe(300.3);
  });

  it("maps legacy product project statuses during migrateData", () => {
    const legacy = {
      ...seedData.projects[0],
      id: "pj-legacy",
      type: "商品项目" as const,
      status: "履约中" as const,
    };
    const migrated = migrateData({
      ...seedData,
      projects: [legacy],
      salesOrders: [{ ...seedData.salesOrders[0], projectId: "pj-legacy" }],
      purchaseOrders: [{ ...seedData.purchaseOrders[0], projectId: "pj-legacy" }],
    });
    expect(migrated.projects[0].status).toBe("进行中");
    expect(migrated.projects[0].logisticsStatus).toBe("待发货");
    expect(migrated.optionGroups.find((group) => group.key === "project_status")?.items.map((item) => item.value)).toEqual([
      "初始化",
      "进行中",
      "已完成",
      "终止",
    ]);
  });

  it("repairs purchase order amount even when project item is not linked yet", () => {
    const project = {
      ...seedData.projects[0],
      id: "pj-unlinked",
      type: "商品项目" as const,
      projectNo: "XM20260810998",
      totalCost: 0,
    };
    const product = { ...seedData.products[0], id: "prd-unlinked", costPrice: 4050 };
    const supplier = seedData.organizations.find((org) => org.roles.includes("上游供应商")) ?? seedData.organizations[0];
    const migrated = migrateData({
      ...seedData,
      projects: [project],
      products: [product],
      purchaseOrders: [{
        id: "po-unlinked",
        projectId: project.id,
        orderNo: "PO-XM20260810998",
        supplierOrgId: supplier.id,
        amount: 0,
        status: "待下单" as const,
        createdAt: "2026-08-10T00:00:00.000Z",
        note: "由旧项目数据自动生成",
      }],
      projectItems: [{
        id: "pi-unlinked",
        projectId: project.id,
        productId: product.id,
        productName: product.name,
        quantity: 5,
        actualPrice: 0,
        costPrice: 0,
        supplierOrgId: supplier.id,
      }],
      supplierPrices: [{
        id: "sp-unlinked",
        productId: product.id,
        supplierOrgId: supplier.id,
        purchasePrice: 4050,
        effectiveDate: "2026-08-10",
      }],
      salesOrders: [],
    });

    expect(migrated.purchaseOrders.find((item) => item.id === "po-unlinked")?.amount).toBe(20250);
    expect(migrated.projectItems.find((item) => item.id === "pi-unlinked")?.purchaseOrderId).toBe("po-unlinked");
  });

  it("splits a dual-tagged sales/purchase project item so sales orders keep line details", () => {
    const project = {
      ...seedData.projects[0],
      id: "pj-dual",
      type: "商品项目" as const,
      projectNo: "XM20260810023",
    };
    const product = { ...seedData.products[0], id: "prd-dual", name: "KFR-72GW/G1-1A/美的/挂机/3匹/1级" };
    const supplier = seedData.organizations.find((org) => org.roles.includes("上游供应商")) ?? seedData.organizations[0];
    const migrated = migrateData({
      ...seedData,
      projects: [project],
      products: [product],
      salesOrders: [{
        ...seedData.salesOrders[0],
        id: "so-dual",
        projectId: project.id,
        orderNo: "SO-XM20260810023-01",
        amount: 21000,
      }],
      purchaseOrders: [{
        id: "po-pj-dual",
        projectId: project.id,
        orderNo: "PO-XM20260810023",
        supplierOrgId: supplier.id,
        amount: 20250,
        status: "待下单" as const,
        createdAt: "2026-08-10T00:00:00.000Z",
      }],
      projectItems: [{
        id: "pi-dual",
        projectId: project.id,
        salesOrderId: "so-dual",
        purchaseOrderId: "po-pj-dual",
        productId: product.id,
        productName: product.name,
        quantity: 5,
        actualPrice: 4200,
        costPrice: 4050,
        supplierOrgId: supplier.id,
      }],
    });

    const salesItem = migrated.projectItems.find((item) => item.id === "pi-dual");
    const purchaseItem = migrated.projectItems.find((item) => item.id === "pi-po-pi-dual");
    expect(salesItem?.salesOrderId).toBe("so-dual");
    expect(salesItem?.purchaseOrderId).toBeUndefined();
    expect(salesItem?.sourcePurchaseOrderId).toBe("po-pj-dual");
    expect(salesItem?.actualPrice).toBe(4200);
    expect(purchaseItem?.purchaseOrderId).toBe("po-pj-dual");
    expect(purchaseItem?.salesOrderId).toBeUndefined();
    expect(purchaseItem?.actualPrice).toBe(0);
    expect(purchaseItem?.costPrice).toBe(4050);
  });

  it("keeps edited role permissions instead of merging seed permissions back", () => {
    const admin = seedData.roles.find((role) => role.id === "role-admin");
    expect(admin).toBeTruthy();
    const reduced = {
      ...admin!,
      permissions: ["dashboard.view", "user.manage"] as typeof seedData.roles[number]["permissions"],
    };
    const migrated = migrateData({
      ...seedData,
      roles: seedData.roles.map((role) => (role.id === reduced.id ? reduced : role)),
    });

    expect(migrated.roles.find((role) => role.id === reduced.id)?.permissions).toEqual(reduced.permissions);
  });

  it("drops leftover service or product project ids from mixed invoice links", () => {
    const mixedProduct = {
      ...seedData.invoices[0],
      id: "inv-mixed-product",
      projectId: "pj-2",
      projectIds: ["pj-2", "pj-1"],
      salesOrderIds: ["so-1"],
      lineItems: [{ productName: "挂机", amount: 1830, salesOrderId: "so-1" }],
    };
    const mixedService = {
      ...seedData.invoices[0],
      id: "inv-mixed-service",
      projectId: "pj-2",
      projectIds: ["pj-2", "pj-1"],
      salesOrderIds: [],
      purchaseOrderIds: [],
      lineItems: [],
    };
    const migrated = migrateData({
      ...seedData,
      invoices: [mixedProduct, mixedService],
    });
    expect(migrated.invoices.find((item) => item.id === mixedProduct.id)?.projectIds).toEqual(["pj-1"]);
    expect(migrated.invoices.find((item) => item.id === mixedService.id)?.projectIds).toEqual(["pj-2"]);
  });
});

describe("diffPartialAppData", () => {
  it("only upserts the changed record and new operation log", () => {
    const updated = { ...seedData.products[0], name: "新名称" };
    const log = { ...seedData.operationLogs[0], id: "log-new" };
    const next = {
      ...seedData,
      products: seedData.products.map((item) => (item.id === updated.id ? updated : item)),
      operationLogs: [log, ...seedData.operationLogs],
    };
    const { upserts, deleteIds } = diffPartialAppData(seedData, next);
    expect(upserts.products).toEqual([updated]);
    expect(upserts.operationLogs).toEqual([log]);
    expect(upserts.organizations).toBeUndefined();
    expect(deleteIds).toEqual({});
  });

  it("records deleted ids without sending the remaining collection", () => {
    const removed = seedData.products[0];
    const next = {
      ...seedData,
      products: seedData.products.filter((item) => item.id !== removed.id),
    };
    const { upserts, deleteIds } = diffPartialAppData(seedData, next);
    expect(upserts.products).toBeUndefined();
    expect(deleteIds.products).toEqual([removed.id]);
  });
});
