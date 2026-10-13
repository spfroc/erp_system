import { describe, expect, it } from "vitest";

import { collectionTxTotalForOrder, missingCollectionAmount, roundMoney, latestCollectionOccurredAt, resolveOrderCollectionVoucher, defaultServiceRefundAmount, applyServiceRefundToData, applyPurchasePaymentToData, purchaseOrderPaidAmount } from "./financeBackfill";
import { seedData } from "./seed";

describe("finance backfill", () => {
  it("sums linked collection transactions and ignores voided ones", () => {
    const total = collectionTxTotalForOrder(
      [
        { type: "收款", status: "已匹配", amount: 600, salesOrderId: "so-1" },
        { type: "收款", status: "作废", amount: 200, salesOrderId: "so-1" },
        { type: "付款", status: "已匹配", amount: 100, salesOrderId: "so-1" },
        { type: "收款", status: "已匹配", amount: 50, serviceOrderId: "so-1" },
      ],
      "so-1",
      "sales",
    );
    expect(total).toBe(600);
  });

  it("returns the gap when received exceeds collection transactions", () => {
    expect(missingCollectionAmount(1000, 600)).toBe(400);
    expect(missingCollectionAmount(1000, 1000)).toBe(0);
    expect(missingCollectionAmount(1000, 1000.004)).toBe(0);
    expect(roundMoney(990.1 + 9.9)).toBe(1000);
    expect(roundMoney(95.84 + 12.46)).toBe(108.3);
    expect(roundMoney(95.84 + 12.46) > roundMoney(108.3)).toBe(false);
  });

  it("uses the latest linked collection time and falls back to order paidAt", () => {
    const latest = latestCollectionOccurredAt(
      [
        { type: "收款", status: "已匹配", occurredAt: "2026-08-01T10:00:00.000Z", salesOrderId: "so-1" },
        { type: "收款", status: "已匹配", occurredAt: "2026-08-13T15:30:00.000Z", salesOrderId: "so-1" },
        { type: "收款", status: "已匹配", occurredAt: "2026-08-20T09:00:00.000Z", salesOrderId: "so-2" },
        { type: "收款", status: "作废", occurredAt: "2026-08-21T09:00:00.000Z", salesOrderId: "so-1" },
      ],
      "so-1",
      "sales",
      "2026-07-01T00:00:00.000Z",
    );
    expect(latest).toBe("2026-08-13T15:30:00.000Z");
    expect(latestCollectionOccurredAt([], "so-1", "sales", "2026-07-01T08:00:00.000Z")).toBe("2026-07-01T08:00:00.000Z");
  });

  it("prefers the order voucher and otherwise the latest collection voucher", () => {
    expect(resolveOrderCollectionVoucher(
      { voucherFileId: "file-order", voucherName: "订单凭证.pdf" },
      [{ type: "收款", status: "已匹配", voucherFileId: "file-tx", voucherName: "流水凭证.pdf", salesOrderId: "so-1" }],
      "so-1",
      "sales",
    )).toEqual({ voucherFileId: "file-order", voucherName: "订单凭证.pdf" });
    expect(resolveOrderCollectionVoucher(
      {},
      [
        { type: "收款", status: "已匹配", voucherFileId: "file-old", occurredAt: "2026-08-01T10:00:00.000Z", salesOrderId: "so-1" },
        { type: "收款", status: "已匹配", voucherFileId: "file-new", voucherName: "新凭证.png", occurredAt: "2026-08-13T15:30:00.000Z", salesOrderId: "so-1" },
      ],
      "so-1",
      "sales",
    )).toEqual({ voucherFileId: "file-new", voucherName: "新凭证.png" });
    expect(resolveOrderCollectionVoucher({}, [], "so-1", "sales")).toBeUndefined();
  });

  it("defaults service refund to received amount, otherwise the order amount", () => {
    expect(defaultServiceRefundAmount({ amount: 1500, receivableAmount: 1500, receivedAmount: 1500 })).toBe(1500);
    expect(defaultServiceRefundAmount({ amount: 1500, receivableAmount: 1500, receivedAmount: 800 })).toBe(800);
    expect(defaultServiceRefundAmount({ amount: 1500, receivableAmount: 1500, receivedAmount: 0 })).toBe(1500);
  });

  it("writes a refund transaction without changing project status", () => {
    const order = {
      ...seedData.serviceOrders[0],
      id: "svc-refund",
      amount: 1500,
      receivableAmount: 1500,
      receivedAmount: 1500,
      status: "已付款" as const,
      note: "原备注",
    };
    const projectId = order.projectId;
    const originalProject = seedData.projects.find((project) => project.id === projectId);
    const originalStatus = originalProject?.status;
    const originalUpdatedAt = originalProject?.updatedAt;
    const next = applyServiceRefundToData({
      ...seedData,
      serviceOrders: [order, ...seedData.serviceOrders],
    }, order, {
      amount: 600,
      occurredAt: "2026-08-24T14:00:00.000Z",
      collectionAccount: "acc-1",
      remark: "客户要求部分退",
      voucherName: "退款凭证.pdf",
      voucherFileId: "file-refund",
    }, "2026-08-24T14:05:00.000Z");
    const savedOrder = next.serviceOrders.find((item) => item.id === "svc-refund");
    const tx = next.transactions.find((item) => item.serviceOrderId === "svc-refund" && item.type === "退款");
    expect(savedOrder?.status).toBe("退款");
    expect(savedOrder?.receivedAmount).toBe(900);
    expect(savedOrder?.note).toContain("客户要求部分退");
    expect(tx?.amount).toBe(600);
    expect(tx?.voucherFileId).toBe("file-refund");
    expect(savedOrder?.voucherFileId).toBe("file-refund");
    expect(next.projects.find((project) => project.id === projectId)?.status).toBe(originalStatus);
    // 退款不得改写项目（含 updatedAt），否则合同管理会误按业务更新时间排序
    expect(next.projects).toEqual(seedData.projects);
    expect(next.projects.find((project) => project.id === projectId)?.updatedAt).toBe(originalUpdatedAt);
  });

  it("records purchase payment as 付款 flow and updates paid amount", () => {
    const order = { ...seedData.purchaseOrders[0], id: "po-pay", amount: 1000, paymentStatus: "待付款" as const, paidAmount: 0 };
    const data = {
      ...seedData,
      purchaseOrders: [order, ...seedData.purchaseOrders],
      transactions: [...seedData.transactions],
    };
    const result = applyPurchasePaymentToData(data, order, {
      amount: 400,
      collectionAccount: "acc-1",
      occurredAt: "2026-08-25T10:00:00.000Z",
      remark: "对公转账",
    }, "2026-08-25T10:01:00.000Z", 1000);
    expect(result.paymentStatus).toBe("部分付款");
    expect(result.paidAmount).toBe(400);
    expect(result.order.note).toContain("对公转账");
    expect(result.transaction.type).toBe("付款");
    expect(result.transaction.purchaseOrderId).toBe("po-pay");
    expect(purchaseOrderPaidAmount(result.order, result.data.transactions)).toBe(400);
    const full = applyPurchasePaymentToData(result.data, result.order, {
      amount: 600,
      collectionAccount: "acc-1",
      occurredAt: "2026-08-25T11:00:00.000Z",
    }, "2026-08-25T11:00:00.000Z", 1000);
    expect(full.paymentStatus).toBe("已付款");
    expect(full.paidAmount).toBe(1000);
  });
});
