import { createId } from "./db";
import type { AppData, OrderPaymentStatus, PurchaseOrder, SalesOrder, ServiceOrder, Transaction } from "./types";

export type CollectionPaymentInput = {
  amount: number;
  paymentMethod?: string;
  collectionAccount?: string;
  payerAccount?: string;
  occurredAt?: string;
  transactionNo?: string;
  voucherName?: string;
  voucherFileId?: string;
  remark?: string;
};

export function roundMoney(value: number) {
  return Math.round((Number(value) + Number.EPSILON) * 100) / 100;
}

export function collectionTxTotalForOrder(
  transactions: Array<{ type?: string; status?: string; amount?: number; salesOrderId?: string; serviceOrderId?: string }>,
  orderId: string,
  kind: "sales" | "service",
) {
  return roundMoney(transactions.reduce((sum, tx) => {
    if (tx.type !== "收款" || tx.status === "作废") return sum;
    const linked = kind === "sales" ? tx.salesOrderId === orderId : tx.serviceOrderId === orderId;
    return linked ? sum + (Number(tx.amount) || 0) : sum;
  }, 0));
}

export function missingCollectionAmount(receivedAmount: number | undefined, txTotal: number) {
  const missing = roundMoney((Number(receivedAmount) || 0) - txTotal);
  return missing > 0.01 ? missing : 0;
}

function isLinkedCollectionTx(
  tx: { type?: string; status?: string; salesOrderId?: string; serviceOrderId?: string },
  orderId: string,
  kind: "sales" | "service",
) {
  if (tx.type !== "收款" || tx.status === "作废") return false;
  return kind === "sales" ? tx.salesOrderId === orderId : tx.serviceOrderId === orderId;
}

function txOccurredStamp(tx: { occurredAt?: string; date?: string; createdAt?: string }) {
  const raw = tx.occurredAt || tx.date || tx.createdAt || "";
  const stamp = Date.parse(raw);
  return Number.isNaN(stamp) ? 0 : stamp;
}

export function latestCollectionOccurredAt(
  transactions: Array<{ type?: string; status?: string; occurredAt?: string; date?: string; createdAt?: string; salesOrderId?: string; serviceOrderId?: string }>,
  orderId: string,
  kind: "sales" | "service",
  fallback?: string,
) {
  const latest = transactions
    .filter((tx) => isLinkedCollectionTx(tx, orderId, kind))
    .reduce<(typeof transactions)[number] | undefined>((current, tx) => {
      if (!current || txOccurredStamp(tx) >= txOccurredStamp(current)) return tx;
      return current;
    }, undefined);
  return latest?.occurredAt || latest?.date || latest?.createdAt || fallback || "";
}

export function resolveOrderCollectionVoucher(
  order: { voucherFileId?: string; voucherName?: string },
  transactions: Array<{ type?: string; status?: string; voucherFileId?: string; voucherName?: string; occurredAt?: string; date?: string; createdAt?: string; salesOrderId?: string; serviceOrderId?: string }>,
  orderId: string,
  kind: "sales" | "service",
) {
  if (order.voucherFileId) {
    return { voucherFileId: order.voucherFileId, voucherName: order.voucherName || "" };
  }
  const latestWithVoucher = transactions
    .filter((tx) => isLinkedCollectionTx(tx, orderId, kind) && tx.voucherFileId)
    .reduce<(typeof transactions)[number] | undefined>((current, tx) => {
      if (!current || txOccurredStamp(tx) >= txOccurredStamp(current)) return tx;
      return current;
    }, undefined);
  if (!latestWithVoucher?.voucherFileId) return undefined;
  return { voucherFileId: latestWithVoucher.voucherFileId, voucherName: latestWithVoucher.voucherName || "" };
}

function collectionRemark(kindLabel: string, orderNo: string, payment: CollectionPaymentInput, fallbackMethod?: string) {
  const method = payment.paymentMethod || fallbackMethod || "收款";
  const payer = payment.payerAccount ? `；付款账号：${payment.payerAccount}` : "";
  return `${kindLabel} ${orderNo} ${method}${payer}`;
}

export function buildSalesCollectionTransaction(
  order: SalesOrder,
  paidAt: string,
  payment: CollectionPaymentInput,
): Transaction {
  const occurredAt = payment.occurredAt || paidAt;
  return {
    id: createId("tx"),
    createdAt: new Date().toISOString(),
    projectId: order.projectId,
    salesOrderId: order.id,
    type: "收款",
    amount: payment.amount,
    date: occurredAt.slice(0, 10),
    occurredAt,
    transactionNo: payment.transactionNo,
    voucherName: payment.voucherName,
    voucherFileId: payment.voucherFileId,
    status: "已匹配",
    account: payment.collectionAccount || order.collectionAccount || order.paymentMethod || "未录入",
    counterpartyOrgId: order.customerOrgId,
    remark: collectionRemark("销售订单", order.orderNo, payment, order.paymentMethod),
  };
}

export function buildServiceCollectionTransaction(
  order: ServiceOrder,
  paidAt: string,
  payment: CollectionPaymentInput,
): Transaction {
  const occurredAt = payment.occurredAt || paidAt;
  return {
    id: createId("tx"),
    createdAt: new Date().toISOString(),
    projectId: order.projectId,
    serviceOrderId: order.id,
    type: "收款",
    amount: payment.amount,
    date: occurredAt.slice(0, 10),
    occurredAt,
    transactionNo: payment.transactionNo,
    voucherName: payment.voucherName,
    voucherFileId: payment.voucherFileId,
    status: "已匹配",
    account: payment.collectionAccount || order.collectionAccount || order.paymentAccount || order.paymentMethod || "未录入",
    counterpartyOrgId: order.customerOrgId,
    remark: collectionRemark("服务订单", order.orderNo, payment, order.paymentMethod),
  };
}

export function defaultServiceRefundAmount(order: Pick<ServiceOrder, "amount" | "receivableAmount" | "receivedAmount">) {
  const received = Number(order.receivedAmount) || 0;
  if (received > 0.009) return roundMoney(received);
  return roundMoney(Number(order.receivableAmount ?? order.amount) || 0);
}

export function buildServiceRefundTransaction(
  order: ServiceOrder,
  refund: CollectionPaymentInput,
): Transaction {
  const occurredAt = refund.occurredAt || new Date().toISOString();
  const remark = refund.remark?.trim() || `服务订单 ${order.orderNo} 退款`;
  return {
    id: createId("tx"),
    createdAt: new Date().toISOString(),
    projectId: order.projectId,
    serviceOrderId: order.id,
    type: "退款",
    amount: refund.amount,
    date: occurredAt.slice(0, 10),
    occurredAt,
    transactionNo: refund.transactionNo,
    voucherName: refund.voucherName,
    voucherFileId: refund.voucherFileId,
    status: "已匹配",
    account: refund.collectionAccount || order.collectionAccount || order.paymentAccount || "未录入",
    counterpartyOrgId: order.customerOrgId,
    remark,
  };
}

export function applyServiceRefundToData(
  data: AppData,
  order: ServiceOrder,
  refund: CollectionPaymentInput,
  now: string,
): AppData {
  const transaction = buildServiceRefundTransaction(order, refund);
  const nextReceived = Math.max(0, roundMoney((Number(order.receivedAmount) || 0) - refund.amount));
  const refundNote = refund.remark?.trim();
  return {
    ...data,
    serviceOrders: data.serviceOrders.map((item) => item.id === order.id
      ? {
        ...item,
        status: "退款" as const,
        receivedAmount: nextReceived,
        paymentMethod: refund.paymentMethod || item.paymentMethod,
        collectionAccount: refund.collectionAccount || item.collectionAccount,
        payerAccount: refund.payerAccount || item.payerAccount,
        voucherName: refund.voucherName ?? item.voucherName,
        voucherFileId: refund.voucherFileId ?? item.voucherFileId,
        updatedAt: now,
        refundedAt: refund.occurredAt || now,
        note: refundNote ? [item.note, `退款：${refundNote}`].filter(Boolean).join("；") : item.note,
      }
      : item),
    transactions: [transaction, ...data.transactions],
  };
}

export function purchasePaymentTxTotal(
  transactions: Array<{ type?: string; status?: string; amount?: number; purchaseOrderId?: string }>,
  orderId: string,
) {
  return roundMoney(transactions.reduce((sum, tx) => {
    if ((tx.type !== "付款" && tx.type !== "垫付") || tx.status === "作废") return sum;
    return tx.purchaseOrderId === orderId ? sum + (Number(tx.amount) || 0) : sum;
  }, 0));
}

export function purchaseOrderPaidAmount(
  order: Pick<PurchaseOrder, "id" | "amount" | "paymentStatus" | "paidAmount">,
  transactions: Array<{ type?: string; status?: string; amount?: number; purchaseOrderId?: string }>,
) {
  const stored = Number(order.paidAmount) || 0;
  const txPaid = purchasePaymentTxTotal(transactions, order.id);
  if (stored > 0.009 || txPaid > 0.009) return roundMoney(Math.max(stored, txPaid));
  if (order.paymentStatus === "已付款") return Number(order.amount) || 0;
  return 0;
}

export function buildPurchasePaymentTransaction(
  order: PurchaseOrder,
  payment: CollectionPaymentInput,
): Transaction {
  const occurredAt = payment.occurredAt || new Date().toISOString();
  const remark = payment.remark?.trim() || `采购订单 ${order.orderNo} 付款`;
  return {
    id: createId("tx"),
    createdAt: new Date().toISOString(),
    projectId: order.projectId,
    purchaseOrderId: order.id,
    type: "付款",
    amount: payment.amount,
    date: occurredAt.slice(0, 10),
    occurredAt,
    transactionNo: payment.transactionNo,
    voucherName: payment.voucherName,
    voucherFileId: payment.voucherFileId,
    status: "已匹配",
    account: payment.collectionAccount || "未录入",
    counterpartyOrgId: order.supplierOrgId,
    remark,
  };
}

export function applyPurchasePaymentToData(
  data: AppData,
  order: PurchaseOrder,
  payment: CollectionPaymentInput,
  now: string,
  payable = Number(order.amount) || 0,
) {
  const currentPaid = purchaseOrderPaidAmount(order, data.transactions);
  const nextPaid = roundMoney(currentPaid + payment.amount);
  const paymentStatus: OrderPaymentStatus = nextPaid + 0.01 >= payable ? "已付款" : "部分付款";
  const transaction = buildPurchasePaymentTransaction(order, payment);
  const note = payment.remark?.trim();
  const nextOrder: PurchaseOrder = {
    ...order,
    paymentStatus,
    paidAmount: nextPaid,
    paidAt: payment.occurredAt || now,
    collectionAccount: payment.collectionAccount || order.collectionAccount,
    payerAccount: payment.payerAccount || order.payerAccount,
    voucherName: payment.voucherName ?? order.voucherName,
    voucherFileId: payment.voucherFileId ?? order.voucherFileId,
    updatedAt: now,
    note: note ? [order.note, `付款：${note}`].filter(Boolean).join("；") : order.note,
  };
  return {
    data: {
      ...data,
      purchaseOrders: data.purchaseOrders.map((item) => item.id === order.id ? nextOrder : item),
      transactions: [transaction, ...data.transactions],
    },
    order: nextOrder,
    paidAmount: nextPaid,
    paymentStatus,
    transaction,
  };
}
