import { roundMoney } from "./financeBackfill";
import { isPurchaseLineItem } from "./productProjectFlow";
import type { AppData, Transaction } from "./types";

export const UNASSIGNED_ID = "__unassigned__";
export const UNASSIGNED_NAME = "未归属";
export const UNALLOCATED_PRODUCT_ID = "__unallocated_product__";
export const UNALLOCATED_PRODUCT_NAME = "未分摊商品";
export const OTHER_ID = "__other__";
export const OTHER_NAME = "其他";

export type PeriodPreset = "yesterday" | "this_week" | "last_week" | "this_month" | "last_month" | "custom";

export type DateRange = {
  start: Date;
  endExclusive: Date;
};

export type CashflowRow = {
  id: string;
  name: string;
  amount: number;
  count: number;
  refundAmount?: number;
  share: number;
};

export type DimensionResult = {
  rows: CashflowRow[];
  totalAmount: number;
  totalCount: number;
  refundAmount: number;
};

export type ReceiptDimension = "customer" | "company" | "salesperson" | "bank";
export type ReceiptScope = "product" | "service";
export type PaymentDimension = "company" | "channel" | "project" | "product" | "bank";

export type ReceiptStats = {
  totals: {
    receiptAmount: number;
    receiptCount: number;
    refundAmount: number;
    refundCount: number;
    netAmount: number;
  };
  byCustomer: DimensionResult;
  byCompany: DimensionResult;
  bySalesperson: DimensionResult;
  byBank: DimensionResult;
};

export type PaymentStats = {
  totals: {
    paymentAmount: number;
    paymentCount: number;
    advanceAmount: number;
    advanceCount: number;
  };
  byCompany: DimensionResult;
  byChannel: DimensionResult;
  byProject: DimensionResult;
  byProduct: DimensionResult;
  byBank: DimensionResult;
};

export const PERIOD_PRESETS: Array<{ id: PeriodPreset; label: string }> = [
  { id: "yesterday", label: "昨天" },
  { id: "this_week", label: "本周" },
  { id: "last_week", label: "上周" },
  { id: "this_month", label: "本月" },
  { id: "last_month", label: "上月" },
  { id: "custom", label: "自定义" },
];

type NamedKey = { id: string; name: string };

type Bucket = {
  id: string;
  name: string;
  receiptAmount: number;
  receiptCount: number;
  refundAmount: number;
  paymentAmount: number;
  paymentCount: number;
};

function startOfLocalDay(date: Date) {
  return new Date(date.getFullYear(), date.getMonth(), date.getDate());
}

function addDays(date: Date, days: number) {
  return new Date(date.getFullYear(), date.getMonth(), date.getDate() + days);
}

export function formatLocalYmd(date: Date) {
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, "0");
  const day = String(date.getDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
}

export function parseLocalDate(value?: string) {
  if (!value) return null;
  const match = value.trim().match(/^(\d{4})-(\d{2})-(\d{2})/);
  if (!match) return null;
  const date = new Date(Number(match[1]), Number(match[2]) - 1, Number(match[3]));
  return Number.isNaN(date.getTime()) ? null : startOfLocalDay(date);
}

export function parseTransactionTime(tx: Pick<Transaction, "occurredAt" | "date" | "createdAt">) {
  const raw = tx.occurredAt || tx.date || tx.createdAt || "";
  if (!raw) return null;
  if (/^\d{4}-\d{2}-\d{2}$/.test(raw.trim())) return parseLocalDate(raw);
  const parsed = new Date(raw);
  return Number.isNaN(parsed.getTime()) ? null : parsed;
}

export function periodRange(preset: PeriodPreset, now = new Date(), custom?: { start?: string; end?: string }): DateRange {
  const today = startOfLocalDay(now);
  if (preset === "yesterday") {
    const start = addDays(today, -1);
    return { start, endExclusive: today };
  }
  if (preset === "this_week" || preset === "last_week") {
    const mondayOffset = (today.getDay() + 6) % 7;
    const thisMonday = addDays(today, -mondayOffset);
    if (preset === "this_week") {
      return { start: thisMonday, endExclusive: addDays(thisMonday, 7) };
    }
    return { start: addDays(thisMonday, -7), endExclusive: thisMonday };
  }
  if (preset === "this_month") {
    const start = new Date(today.getFullYear(), today.getMonth(), 1);
    return { start, endExclusive: new Date(today.getFullYear(), today.getMonth() + 1, 1) };
  }
  if (preset === "last_month") {
    const start = new Date(today.getFullYear(), today.getMonth() - 1, 1);
    return { start, endExclusive: new Date(today.getFullYear(), today.getMonth(), 1) };
  }
  const parsedStart = parseLocalDate(custom?.start) ?? today;
  const parsedEnd = parseLocalDate(custom?.end) ?? today;
  const start = parsedStart <= parsedEnd ? parsedStart : parsedEnd;
  const endDay = parsedStart <= parsedEnd ? parsedEnd : parsedStart;
  return { start, endExclusive: addDays(endDay, 1) };
}

export function formatPeriodRange(range: DateRange) {
  return `${formatLocalYmd(range.start)} 至 ${formatLocalYmd(addDays(range.endExclusive, -1))}`;
}

export function isTransactionInRange(tx: Pick<Transaction, "occurredAt" | "date" | "createdAt">, range: DateRange) {
  const time = parseTransactionTime(tx);
  if (!time) return false;
  return time >= range.start && time < range.endExclusive;
}

function isActiveTransaction(tx: Transaction) {
  return (tx.status as string) !== "作废";
}

function orgName(data: AppData, id?: string) {
  if (!id) return "";
  return data.organizations.find((org) => org.id === id)?.name || "";
}

function unassigned(): NamedKey {
  return { id: UNASSIGNED_ID, name: UNASSIGNED_NAME };
}

function namedOrUnassigned(id?: string, name?: string): NamedKey {
  const resolved = (name || "").trim();
  if (!resolved) return unassigned();
  return { id: id || `name:${resolved}`, name: resolved };
}

function findCollectionAccount(data: AppData, account?: string) {
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

function salesOrderOf(data: AppData, tx: Transaction) {
  return tx.salesOrderId ? data.salesOrders.find((order) => order.id === tx.salesOrderId) : undefined;
}

function serviceOrderOf(data: AppData, tx: Transaction) {
  return tx.serviceOrderId ? data.serviceOrders.find((order) => order.id === tx.serviceOrderId) : undefined;
}

function purchaseOrderOf(data: AppData, tx: Transaction) {
  return tx.purchaseOrderId ? data.purchaseOrders.find((order) => order.id === tx.purchaseOrderId) : undefined;
}

function projectOf(data: AppData, tx: Transaction) {
  const projectId = tx.projectId
    || salesOrderOf(data, tx)?.projectId
    || serviceOrderOf(data, tx)?.projectId
    || purchaseOrderOf(data, tx)?.projectId
    || "";
  return projectId ? data.projects.find((project) => project.id === projectId) : undefined;
}

export function receiptBusinessKind(data: AppData, tx: Transaction): ReceiptScope | "unknown" {
  const project = projectOf(data, tx);
  if (project?.type === "服务项目") return "service";
  if (project?.type === "商品项目") return "product";
  if (tx.serviceOrderId) return "service";
  if (tx.salesOrderId) return "product";
  return "unknown";
}

function receiptCustomer(data: AppData, tx: Transaction): NamedKey {
  const id = salesOrderOf(data, tx)?.customerOrgId
    || serviceOrderOf(data, tx)?.customerOrgId
    || tx.counterpartyOrgId
    || "";
  return namedOrUnassigned(id, orgName(data, id));
}

function ownCompany(data: AppData, tx: Transaction): NamedKey {
  const id = salesOrderOf(data, tx)?.ownCompanyOrgId
    || purchaseOrderOf(data, tx)?.ownCompanyOrgId
    || projectOf(data, tx)?.ownCompanyOrgId
    || findCollectionAccount(data, tx.account)?.ownCompanyOrgId
    || "";
  return namedOrUnassigned(id, orgName(data, id));
}

function salesperson(data: AppData, tx: Transaction): NamedKey {
  const serviceOrder = serviceOrderOf(data, tx);
  if (serviceOrder?.salesUserId || serviceOrder?.salesName) {
    const userName = data.users.find((user) => user.id === serviceOrder.salesUserId)?.name;
    const name = userName || serviceOrder.salesName || UNASSIGNED_NAME;
    return { id: serviceOrder.salesUserId || `name:${name}`, name };
  }
  const project = projectOf(data, tx);
  if (project?.type === "服务项目" && (project.serviceSalesUserId || project.serviceSalesName)) {
    const userName = data.users.find((user) => user.id === project.serviceSalesUserId)?.name;
    const name = userName || project.serviceSalesName || UNASSIGNED_NAME;
    return { id: project.serviceSalesUserId || `name:${name}`, name };
  }
  if (project?.type === "商品项目" && project.owner?.trim()) {
    const name = project.owner.trim();
    return { id: `owner:${name}`, name };
  }
  return unassigned();
}

function paymentChannel(data: AppData, tx: Transaction): NamedKey {
  const id = purchaseOrderOf(data, tx)?.supplierOrgId || tx.counterpartyOrgId || "";
  return namedOrUnassigned(id, orgName(data, id));
}

function paymentProject(data: AppData, tx: Transaction): NamedKey {
  const project = projectOf(data, tx);
  if (project) return { id: project.id, name: project.name };
  if (tx.projectName?.trim()) return { id: `name:${tx.projectName.trim()}`, name: tx.projectName.trim() };
  return unassigned();
}

function bankAccount(data: AppData, tx: Transaction): NamedKey {
  const option = findCollectionAccount(data, tx.account);
  if (option) {
    const bank = (option.bankName || "未设置银行").trim();
    const number = (option.accountNumber || tx.account || "").trim();
    const name = [bank, number].filter(Boolean).join(" ");
    return { id: option.id || `account:${number || bank}`, name: name || UNASSIGNED_NAME };
  }
  const raw = (tx.account || "").trim();
  if (raw) return { id: `raw:${raw}`, name: raw };
  return unassigned();
}

export function allocatePaymentToProducts(data: AppData, tx: Transaction): Array<{ id: string; name: string; amount: number }> {
  const amount = roundMoney(Number(tx.amount) || 0);
  const unallocated = [{ id: UNALLOCATED_PRODUCT_ID, name: UNALLOCATED_PRODUCT_NAME, amount }];
  if (!tx.purchaseOrderId) return unallocated;
  const items = data.projectItems.filter((item) => item.purchaseOrderId === tx.purchaseOrderId && isPurchaseLineItem(item));
  if (items.length === 0) return unallocated;
  const weights = items.map((item) => Math.max(0, (Number(item.quantity) || 0) * (Number(item.costPrice) || 0)));
  const weightSum = weights.reduce((sum, weight) => sum + weight, 0);
  if (weightSum <= 0) return unallocated;

  const rounded = weights.map((weight) => roundMoney(amount * (weight / weightSum)));
  const allocated = roundMoney(rounded.reduce((sum, value) => sum + value, 0));
  const remainder = roundMoney(amount - allocated);
  if (remainder !== 0) {
    let index = 0;
    for (let i = 1; i < rounded.length; i += 1) {
      if (rounded[i] > rounded[index] || (rounded[i] === rounded[index] && weights[i] > weights[index])) {
        index = i;
      }
    }
    rounded[index] = roundMoney(rounded[index] + remainder);
  }

  const merged = new Map<string, { id: string; name: string; amount: number }>();
  items.forEach((item, index) => {
    const id = item.productId || `line:${item.id}`;
    const current = merged.get(id);
    const lineAmount = rounded[index];
    if (current) {
      current.amount = roundMoney(current.amount + lineAmount);
      return;
    }
    merged.set(id, { id, name: item.productName || id, amount: lineAmount });
  });
  return [...merged.values()];
}

function emptyBucket(key: NamedKey): Bucket {
  return {
    id: key.id,
    name: key.name,
    receiptAmount: 0,
    receiptCount: 0,
    refundAmount: 0,
    paymentAmount: 0,
    paymentCount: 0,
  };
}

function takeBucket(map: Map<string, Bucket>, key: NamedKey) {
  const current = map.get(key.id);
  if (current) return current;
  const created = emptyBucket(key);
  map.set(key.id, created);
  return created;
}

function toRows(buckets: Map<string, Bucket>, mode: "receipt" | "payment"): DimensionResult {
  const list = [...buckets.values()];
  const totalAmount = roundMoney(list.reduce((sum, bucket) => (
    sum + (mode === "receipt" ? bucket.receiptAmount - bucket.refundAmount : bucket.paymentAmount)
  ), 0));
  const totalCount = list.reduce((sum, bucket) => sum + (mode === "receipt" ? bucket.receiptCount : bucket.paymentCount), 0);
  const refundAmount = roundMoney(list.reduce((sum, bucket) => sum + bucket.refundAmount, 0));
  const rows = list
    .map((bucket) => {
      const amount = roundMoney(mode === "receipt" ? bucket.receiptAmount - bucket.refundAmount : bucket.paymentAmount);
      return {
        id: bucket.id,
        name: bucket.name,
        amount,
        count: mode === "receipt" ? bucket.receiptCount : bucket.paymentCount,
        refundAmount: mode === "receipt" ? roundMoney(bucket.refundAmount) : undefined,
        share: totalAmount === 0 ? 0 : amount / totalAmount,
      };
    })
    .filter((row) => row.amount !== 0 || row.count > 0 || (row.refundAmount ?? 0) > 0)
    .sort((left, right) => right.amount - left.amount || left.name.localeCompare(right.name, "zh"));
  return { rows, totalAmount, totalCount, refundAmount };
}

export function chartRows(rows: CashflowRow[], limit = 10): CashflowRow[] {
  if (rows.length <= limit) return rows;
  const top = rows.slice(0, limit);
  const rest = rows.slice(limit);
  const amount = roundMoney(rest.reduce((sum, row) => sum + row.amount, 0));
  const count = rest.reduce((sum, row) => sum + row.count, 0);
  const refundAmount = rest.some((row) => row.refundAmount != null)
    ? roundMoney(rest.reduce((sum, row) => sum + (row.refundAmount ?? 0), 0))
    : undefined;
  const totalAmount = roundMoney(rows.reduce((sum, row) => sum + row.amount, 0));
  return [
    ...top,
    {
      id: OTHER_ID,
      name: OTHER_NAME,
      amount,
      count,
      refundAmount,
      share: totalAmount === 0 ? 0 : amount / totalAmount,
    },
  ];
}

function rangedTransactions(data: AppData, range: DateRange) {
  return data.transactions.filter((tx) => (
    isActiveTransaction(tx)
    && isTransactionInRange(tx, range)
    && transactionHasLiveLink(data, tx)
  ));
}

export function transactionHasLiveLink(data: AppData, tx: Transaction) {
  const referenced = Boolean(tx.projectId || tx.salesOrderId || tx.serviceOrderId || tx.purchaseOrderId);
  if (!referenced) return true;
  return Boolean(
    projectOf(data, tx)
    || salesOrderOf(data, tx)
    || serviceOrderOf(data, tx)
    || purchaseOrderOf(data, tx)
  );
}

export function buildReceiptStats(data: AppData, range: DateRange, scope?: ReceiptScope): ReceiptStats {
  const customers = new Map<string, Bucket>();
  const companies = new Map<string, Bucket>();
  const salespeople = new Map<string, Bucket>();
  const banks = new Map<string, Bucket>();
  let receiptAmount = 0;
  let receiptCount = 0;
  let refundAmount = 0;
  let refundCount = 0;

  for (const tx of rangedTransactions(data, range)) {
    if (tx.type !== "收款" && tx.type !== "退款") continue;
    if (scope && receiptBusinessKind(data, tx) !== scope) continue;
    const amount = roundMoney(Number(tx.amount) || 0);
    const dims = [receiptCustomer(data, tx), ownCompany(data, tx), salesperson(data, tx), bankAccount(data, tx)];
    const maps = [customers, companies, salespeople, banks];
    maps.forEach((map, index) => {
      const bucket = takeBucket(map, dims[index]);
      if (tx.type === "收款") {
        bucket.receiptAmount = roundMoney(bucket.receiptAmount + amount);
        bucket.receiptCount += 1;
      } else {
        bucket.refundAmount = roundMoney(bucket.refundAmount + amount);
      }
    });
    if (tx.type === "收款") {
      receiptAmount = roundMoney(receiptAmount + amount);
      receiptCount += 1;
    } else {
      refundAmount = roundMoney(refundAmount + amount);
      refundCount += 1;
    }
  }

  return {
    totals: {
      receiptAmount,
      receiptCount,
      refundAmount,
      refundCount,
      netAmount: roundMoney(receiptAmount - refundAmount),
    },
    byCustomer: toRows(customers, "receipt"),
    byCompany: toRows(companies, "receipt"),
    bySalesperson: toRows(salespeople, "receipt"),
    byBank: toRows(banks, "receipt"),
  };
}

export function buildPaymentStats(data: AppData, range: DateRange): PaymentStats {
  const companies = new Map<string, Bucket>();
  const channels = new Map<string, Bucket>();
  const projects = new Map<string, Bucket>();
  const products = new Map<string, Bucket>();
  const banks = new Map<string, Bucket>();
  let paymentAmount = 0;
  let paymentCount = 0;
  let advanceAmount = 0;
  let advanceCount = 0;

  for (const tx of rangedTransactions(data, range)) {
    if (tx.type === "垫付") {
      advanceAmount = roundMoney(advanceAmount + (Number(tx.amount) || 0));
      advanceCount += 1;
      continue;
    }
    if (tx.type !== "付款") continue;
    const amount = roundMoney(Number(tx.amount) || 0);
    paymentAmount = roundMoney(paymentAmount + amount);
    paymentCount += 1;

    const company = takeBucket(companies, ownCompany(data, tx));
    company.paymentAmount = roundMoney(company.paymentAmount + amount);
    company.paymentCount += 1;

    const channel = takeBucket(channels, paymentChannel(data, tx));
    channel.paymentAmount = roundMoney(channel.paymentAmount + amount);
    channel.paymentCount += 1;

    const project = takeBucket(projects, paymentProject(data, tx));
    project.paymentAmount = roundMoney(project.paymentAmount + amount);
    project.paymentCount += 1;

    const bank = takeBucket(banks, bankAccount(data, tx));
    bank.paymentAmount = roundMoney(bank.paymentAmount + amount);
    bank.paymentCount += 1;

    for (const part of allocatePaymentToProducts(data, tx)) {
      const product = takeBucket(products, { id: part.id, name: part.name });
      product.paymentAmount = roundMoney(product.paymentAmount + part.amount);
      product.paymentCount += 1;
    }
  }

  return {
    totals: { paymentAmount, paymentCount, advanceAmount, advanceCount },
    byCompany: toRows(companies, "payment"),
    byChannel: toRows(channels, "payment"),
    byProject: toRows(projects, "payment"),
    byProduct: toRows(products, "payment"),
    byBank: toRows(banks, "payment"),
  };
}
