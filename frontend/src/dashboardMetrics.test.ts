import { describe, expect, it } from "vitest";

import { calculateDashboardMetrics, projectPaidAmount, projectPendingInvoiceAmount, projectReceivedAmount, projectSalesAmount } from "./dashboardMetrics";
import { seedData } from "./seed";

describe("dashboard metrics", () => {
  it("includes service orders and excludes refunded orders from sales amount", () => {
    const data = {
      ...seedData,
      salesOrders: [],
      serviceOrders: [
        { ...seedData.serviceOrders[0], id: "svc-a", projectId: "pj-1", amount: 1000, status: "待付款" as const },
        { ...seedData.serviceOrders[0], id: "svc-b", projectId: "pj-1", amount: 500, status: "退款" as const },
      ],
    };
    expect(projectSalesAmount(data, "pj-1")).toBe(1000);
  });

  it("sums remaining received amounts, including partial refunds", () => {
    const data = {
      ...seedData,
      salesOrders: [
        { ...seedData.salesOrders[0], id: "so-a", projectId: "pj-1", receivedAmount: 800, status: "部分付款" as const },
        { ...seedData.salesOrders[0], id: "so-b", projectId: "pj-1", receivedAmount: 200, status: "退款" as const },
        { ...seedData.salesOrders[0], id: "so-c", projectId: "pj-1", receivedAmount: 90, status: "取消" as const },
      ],
      serviceOrders: [
        { ...seedData.serviceOrders[0], id: "svc-a", projectId: "pj-1", receivedAmount: 150, status: "已付款" as const },
        { ...seedData.serviceOrders[0], id: "svc-b", projectId: "pj-1", receivedAmount: 500, status: "退款" as const },
      ],
    };
    expect(projectReceivedAmount(data, "pj-1")).toBe(1650);
  });

  it("uses purchase payment transactions, then paid purchase orders, for paid amount", () => {
    const data = {
      ...seedData,
      purchaseOrders: [
        { ...seedData.purchaseOrders[0], id: "po-a", projectId: "pj-1", amount: 1000, status: "已下单" as const, paymentStatus: "部分付款" as const },
        { ...seedData.purchaseOrders[0], id: "po-b", projectId: "pj-1", amount: 400, status: "已完成" as const, paymentStatus: "已付款" as const },
        { ...seedData.purchaseOrders[0], id: "po-c", projectId: "pj-1", amount: 200, status: "已取消" as const, paymentStatus: "已付款" as const },
      ],
      transactions: [
        { ...seedData.transactions[0], id: "tx-pay", projectId: "pj-1", type: "付款" as const, amount: 300, purchaseOrderId: "po-a", salesOrderId: undefined, serviceOrderId: undefined },
      ],
    };
    expect(projectPaidAmount(data, "pj-1")).toBe(700);
  });

  it("calculates pending invoice amount from project amount minus issued invoices", () => {
    const project = { ...seedData.projects[0], id: "pj-dashboard", totalAmount: 3000 };
    const data = {
      ...seedData,
      projects: [project],
      salesOrders: [{ ...seedData.salesOrders[0], id: "so-dashboard", projectId: project.id, amount: 3000 }],
      serviceOrders: [],
      invoices: [{
        ...seedData.invoices[0],
        id: "inv-dashboard",
        projectId: project.id,
        projectIds: [project.id],
        type: "销项" as const,
        status: "已确认" as const,
        amount: 1200,
      }],
    };
    expect(projectPendingInvoiceAmount(data, project.id)).toBe(1800);
  });

  it("does not count completed service projects as active", () => {
    const active = { ...seedData.projects[0], id: "pj-active", type: "服务项目" as const, status: "入驻中" as const };
    const completed = { ...seedData.projects[0], id: "pj-completed", type: "服务项目" as const, status: "服务完成" as const };
    const data = { ...seedData, projects: [active, completed], salesOrders: [], serviceOrders: [], purchaseOrders: [], invoices: [], onboardingRecords: [] };
    const metrics = calculateDashboardMetrics(data);
    expect(metrics.active).toBe(1);
    expect(metrics.onboarding).toBe(1);
  });

  it("calculates project amount from project records instead of order totals", () => {
    const first = { ...seedData.projects[0], id: "pj-amount-1", totalAmount: 1200 };
    const second = { ...seedData.projects[0], id: "pj-amount-2", totalAmount: 800 };
    const data = { ...seedData, projects: [first, second], salesOrders: [], serviceOrders: [] };

    expect(calculateDashboardMetrics(data).projectAmount).toBe(2000);
  });

  it("allocates a multi-project invoice without subtracting it in full from every project", () => {
    const first = { ...seedData.projects[0], id: "pj-first", totalAmount: 1000 };
    const second = { ...seedData.projects[0], id: "pj-second", totalAmount: 3000 };
    const data = {
      ...seedData,
      projects: [first, second],
      salesOrders: [
        { ...seedData.salesOrders[0], id: "so-first", projectId: first.id, amount: 1000 },
        { ...seedData.salesOrders[0], id: "so-second", projectId: second.id, amount: 3000 },
      ],
      serviceOrders: [],
      invoices: [{
        ...seedData.invoices[0],
        id: "inv-shared",
        projectId: first.id,
        projectIds: [first.id, second.id],
        type: "销项" as const,
        status: "已确认" as const,
        amount: 2000,
      }],
    };
    expect(projectPendingInvoiceAmount(data, first.id)).toBe(500);
    expect(projectPendingInvoiceAmount(data, second.id)).toBe(1500);
  });
});
