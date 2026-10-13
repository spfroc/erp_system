import { describe, expect, it } from "vitest";

import {
  OTHER_ID,
  UNALLOCATED_PRODUCT_NAME,
  UNASSIGNED_NAME,
  allocatePaymentToProducts,
  buildPaymentStats,
  buildReceiptStats,
  chartRows,
  periodRange,
} from "./cashflowStats";
import { seedData } from "./seed";
import type { AppData, Transaction } from "./types";

const NOW = new Date(2026, 8, 4, 15, 30, 0);

function tx(partial: Partial<Transaction> & Pick<Transaction, "id" | "type" | "amount">): Transaction {
  return {
    projectId: "",
    date: "2026-09-02",
    status: "已匹配",
    ...partial,
  };
}

function withTransactions(transactions: Transaction[], extra?: Partial<AppData>): AppData {
  return {
    ...seedData,
    transactions,
    ...extra,
  };
}

describe("periodRange", () => {
  it("uses Monday as the first day of this week and last week", () => {
    const thisWeek = periodRange("this_week", NOW);
    expect(thisWeek.start).toEqual(new Date(2026, 7, 31));
    expect(thisWeek.endExclusive).toEqual(new Date(2026, 8, 7));

    const lastWeek = periodRange("last_week", NOW);
    expect(lastWeek.start).toEqual(new Date(2026, 7, 24));
    expect(lastWeek.endExclusive).toEqual(new Date(2026, 7, 31));
  });

  it("covers local calendar months and yesterday", () => {
    expect(periodRange("this_month", NOW)).toEqual({
      start: new Date(2026, 8, 1),
      endExclusive: new Date(2026, 9, 1),
    });
    expect(periodRange("last_month", NOW)).toEqual({
      start: new Date(2026, 7, 1),
      endExclusive: new Date(2026, 8, 1),
    });
    expect(periodRange("yesterday", NOW)).toEqual({
      start: new Date(2026, 8, 3),
      endExclusive: new Date(2026, 8, 4),
    });
  });

  it("treats custom dates as local start-of-day through end-of-day", () => {
    const range = periodRange("custom", NOW, { start: "2026-06-19", end: "2026-06-24" });
    expect(range.start).toEqual(new Date(2026, 5, 19));
    expect(range.endExclusive).toEqual(new Date(2026, 5, 25));
  });
});

describe("buildReceiptStats", () => {
  it("deducts refunds from the net total and keeps a refund column", () => {
    const data = withTransactions([
      tx({ id: "r1", type: "收款", amount: 1000, salesOrderId: "so-1", occurredAt: "2026-09-02T10:00:00" }),
      tx({ id: "r2", type: "退款", amount: 200, salesOrderId: "so-1", occurredAt: "2026-09-03T10:00:00" }),
      tx({ id: "void", type: "收款", amount: 500, salesOrderId: "so-1", occurredAt: "2026-09-02T12:00:00", status: "作废" as Transaction["status"] }),
    ]);
    const stats = buildReceiptStats(data, periodRange("this_month", NOW));
    expect(stats.totals).toMatchObject({
      receiptAmount: 1000,
      receiptCount: 1,
      refundAmount: 200,
      refundCount: 1,
      netAmount: 800,
    });
    const customer = stats.byCustomer.rows.find((row) => row.id === "org-1");
    expect(customer).toMatchObject({ amount: 800, count: 1, refundAmount: 200 });
  });

  it("puts unmatched receipts into 未归属", () => {
    const data = withTransactions([
      tx({ id: "r1", type: "收款", amount: 80, occurredAt: "2026-09-02T10:00:00", projectId: "", counterpartyOrgId: undefined }),
    ]);
    const stats = buildReceiptStats(data, periodRange("this_month", NOW));
    expect(stats.byCustomer.rows[0]).toMatchObject({ name: UNASSIGNED_NAME, amount: 80, count: 1 });
    expect(stats.byCompany.rows[0].name).toBe(UNASSIGNED_NAME);
    expect(stats.bySalesperson.rows[0].name).toBe(UNASSIGNED_NAME);
  });

  it("resolves salesperson from the service order, then the service project owner for product projects", () => {
    const data = withTransactions([
      tx({ id: "svc", type: "收款", amount: 300, serviceOrderId: "svc-1", occurredAt: "2026-09-01T09:00:00" }),
      tx({ id: "so", type: "收款", amount: 400, salesOrderId: "so-1", projectId: "pj-1", occurredAt: "2026-09-01T10:00:00" }),
    ]);
    const stats = buildReceiptStats(data, periodRange("this_month", NOW));
    const names = stats.bySalesperson.rows.map((row) => row.name).sort();
    expect(names).toEqual(["业务同事", "王云磊"]);
  });

  it("ignores receipts whose project and order were removed", () => {
    const data = withTransactions([
      tx({ id: "live", type: "收款", amount: 1000, serviceOrderId: "svc-1", occurredAt: "2026-09-02T10:00:00" }),
      tx({
        id: "orphan",
        type: "收款",
        amount: 1000,
        projectId: "pj-deleted",
        serviceOrderId: "svc-deleted",
        counterpartyOrgId: "org-5",
        occurredAt: "2026-09-02T11:00:00",
      }),
    ]);
    const stats = buildReceiptStats(data, periodRange("this_month", NOW), "service");
    expect(stats.totals).toMatchObject({ receiptAmount: 1000, receiptCount: 1, netAmount: 1000 });
    expect(stats.byCustomer.rows).toHaveLength(1);
    expect(stats.byCustomer.rows[0].count).toBe(1);
  });

  it("splits product and service receipts by the linked project type", () => {
    const data = withTransactions([
      tx({ id: "product", type: "收款", amount: 1000, salesOrderId: "so-1", occurredAt: "2026-09-02T10:00:00" }),
      tx({ id: "service-order", type: "收款", amount: 300, serviceOrderId: "svc-1", occurredAt: "2026-09-02T11:00:00" }),
      tx({ id: "service-sales", type: "收款", amount: 200, salesOrderId: "so-2", occurredAt: "2026-09-02T12:00:00" }),
      tx({ id: "unknown", type: "收款", amount: 50, occurredAt: "2026-09-02T13:00:00" }),
    ]);
    const product = buildReceiptStats(data, periodRange("this_month", NOW), "product");
    const service = buildReceiptStats(data, periodRange("this_month", NOW), "service");
    expect(product.totals).toMatchObject({ receiptAmount: 1000, receiptCount: 1, netAmount: 1000 });
    expect(service.totals).toMatchObject({ receiptAmount: 500, receiptCount: 2, netAmount: 500 });
  });

  it("shows 未归属 instead of a leftover organization id", () => {
    const data = withTransactions(
      [tx({ id: "r1", type: "收款", amount: 59, salesOrderId: "so-ghost", occurredAt: "2026-09-02T10:00:00" })],
      {
        salesOrders: [{ ...seedData.salesOrders[0], id: "so-ghost", ownCompanyOrgId: "org-missing" }],
        organizations: seedData.organizations.filter((org) => org.id !== "org-7"),
      },
    );
    const stats = buildReceiptStats(data, periodRange("this_month", NOW), "product");
    expect(stats.byCompany.rows[0]).toMatchObject({ name: UNASSIGNED_NAME, amount: 59 });
    expect(stats.byCompany.rows.some((row) => row.name === "org-missing")).toBe(false);
  });

  it("groups receipts by bank account", () => {
    const data = withTransactions(
      [
        tx({ id: "r1", type: "收款", amount: 1000, salesOrderId: "so-1", account: "acc-a", occurredAt: "2026-09-02T10:00:00" }),
        tx({ id: "r2", type: "收款", amount: 300, salesOrderId: "so-1", account: "acc-b", occurredAt: "2026-09-02T11:00:00" }),
        tx({ id: "r3", type: "退款", amount: 100, salesOrderId: "so-1", account: "acc-a", occurredAt: "2026-09-03T10:00:00" }),
      ],
      {
        optionGroups: [
          {
            id: "opt-collection",
            key: "collection_account",
            name: "收款账号",
            usages: ["交易流水：收款账户"],
            items: [
              { id: "acc-a", label: "工行", value: "111", enabled: true, sortOrder: 1, bankName: "工商银行", accountNumber: "111", ownCompanyOrgId: "org-7" },
              { id: "acc-b", label: "建行", value: "222", enabled: true, sortOrder: 2, bankName: "建设银行", accountNumber: "222", ownCompanyOrgId: "org-7" },
            ],
          },
        ],
      },
    );
    const stats = buildReceiptStats(data, periodRange("this_month", NOW), "product");
    expect(stats.byBank.rows).toHaveLength(2);
    const icbc = stats.byBank.rows.find((row) => row.id === "acc-a");
    expect(icbc).toMatchObject({ name: "工商银行 111", amount: 900, count: 1, refundAmount: 100 });
  });
});

describe("buildPaymentStats", () => {
  it("keeps advances out of the payment total", () => {
    const data = withTransactions([
      tx({ id: "p1", type: "付款", amount: 500, purchaseOrderId: "po-1", occurredAt: "2026-09-02T10:00:00" }),
      tx({ id: "a1", type: "垫付", amount: 120, purchaseOrderId: "po-1", occurredAt: "2026-09-02T11:00:00" }),
    ]);
    const stats = buildPaymentStats(data, periodRange("this_month", NOW));
    expect(stats.totals).toEqual({
      paymentAmount: 500,
      paymentCount: 1,
      advanceAmount: 120,
      advanceCount: 1,
    });
    expect(stats.byCompany.totalAmount).toBe(500);
  });

  it("groups payments by bank account", () => {
    const data = withTransactions(
      [
        tx({ id: "p1", type: "付款", amount: 500, purchaseOrderId: "po-1", account: "acc-pay", occurredAt: "2026-09-02T10:00:00" }),
      ],
      {
        optionGroups: [
          {
            id: "opt-collection",
            key: "collection_account",
            name: "收款账号",
            usages: ["交易流水：收款账户"],
            items: [
              { id: "acc-pay", label: "中信", value: "333", enabled: true, sortOrder: 1, bankName: "中信银行", accountNumber: "333", ownCompanyOrgId: "org-7" },
            ],
          },
        ],
      },
    );
    const stats = buildPaymentStats(data, periodRange("this_month", NOW));
    expect(stats.byBank.rows).toEqual([
      expect.objectContaining({ id: "acc-pay", name: "中信银行 333", amount: 500, count: 1 }),
    ]);
  });

  it("allocates a payment across purchase lines and sticks the remainder on the largest row", () => {
    const data = withTransactions(
      [tx({ id: "p1", type: "付款", amount: 10, purchaseOrderId: "po-split", occurredAt: "2026-09-02T10:00:00" })],
      {
        purchaseOrders: [{ ...seedData.purchaseOrders[0], id: "po-split", projectId: "pj-1" }],
        projectItems: [
          { id: "pi-a", projectId: "pj-1", purchaseOrderId: "po-split", productId: "prd-1", productName: "商品A", quantity: 1, actualPrice: 0, costPrice: 100 },
          { id: "pi-b", projectId: "pj-1", purchaseOrderId: "po-split", productId: "prd-2", productName: "商品B", quantity: 1, actualPrice: 0, costPrice: 100 },
          { id: "pi-c", projectId: "pj-1", purchaseOrderId: "po-split", productId: "prd-3", productName: "商品C", quantity: 1, actualPrice: 0, costPrice: 100 },
        ],
      },
    );
    const parts = allocatePaymentToProducts(data, data.transactions[0]);
    expect(parts.map((part) => part.amount).sort((a, b) => a - b)).toEqual([3.33, 3.33, 3.34]);
    expect(parts.reduce((sum, part) => sum + part.amount, 0)).toBe(10);

    const stats = buildPaymentStats(data, periodRange("this_month", NOW));
    expect(stats.byProduct.rows).toHaveLength(3);
    expect(stats.byProduct.totalAmount).toBe(10);
  });

  it("records payments without purchase lines as 未分摊商品", () => {
    const data = withTransactions([
      tx({ id: "p1", type: "付款", amount: 88, occurredAt: "2026-09-02T10:00:00" }),
    ]);
    const stats = buildPaymentStats(data, periodRange("this_month", NOW));
    expect(stats.byProduct.rows[0]).toMatchObject({ name: UNALLOCATED_PRODUCT_NAME, amount: 88, count: 1 });
  });
});

describe("chartRows", () => {
  it("keeps the top 10 rows and merges the rest as 其他", () => {
    const rows = Array.from({ length: 12 }, (_, index) => ({
      id: `r${index}`,
      name: `行${index}`,
      amount: 12 - index,
      count: 1,
      share: (12 - index) / 78,
    }));
    const chart = chartRows(rows, 10);
    expect(chart).toHaveLength(11);
    expect(chart[10]).toMatchObject({ id: OTHER_ID, name: "其他", amount: 3, count: 2 });
  });
});
