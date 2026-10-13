import type { AppData, Project } from "./types";

const TERMINAL_PROJECT_STATUSES = new Set([
  "已完成",
  "终止",
  "服务完成",
  "服务交付完成",
  "服务到期",
  "服务到期结束",
  "结束",
  "到期",
  "终止合作",
  "项目终止",
]);

const ISSUED_INVOICE_STATUSES = new Set(["已确认", "已开", "已收"]);

export function isTerminalProject(project: Project) {
  return TERMINAL_PROJECT_STATUSES.has(project.status);
}

export function projectSalesAmount(data: AppData, projectId: string) {
  const sales = data.salesOrders
    .filter((order) => order.projectId === projectId && order.status !== "取消" && order.status !== "退款")
    .reduce((sum, order) => sum + order.amount, 0);
  const services = data.serviceOrders
    .filter((order) => order.projectId === projectId && order.status !== "取消" && order.status !== "退款")
    .reduce((sum, order) => sum + order.amount, 0);
  return sales + services;
}

function countsTowardReceived(status?: string) {
  return status !== "取消";
}

export function projectPurchaseAmount(data: AppData, projectId: string) {
  return data.purchaseOrders
    .filter((order) => order.projectId === projectId && order.status !== "已取消")
    .reduce((sum, order) => sum + order.amount, 0);
}

export function projectReceivedAmount(data: AppData, projectId: string) {
  const fromSales = data.salesOrders
    .filter((order) => order.projectId === projectId && countsTowardReceived(order.status))
    .reduce((sum, order) => sum + (Number(order.receivedAmount) || 0), 0);
  const fromService = data.serviceOrders
    .filter((order) => order.projectId === projectId && countsTowardReceived(order.status))
    .reduce((sum, order) => sum + (Number(order.receivedAmount) || 0), 0);
  return fromSales + fromService;
}

export function projectPaidAmount(data: AppData, projectId: string) {
  const purchaseOrders = data.purchaseOrders.filter((order) => order.projectId === projectId && order.status !== "已取消");
  const purchaseIds = new Set(purchaseOrders.map((order) => order.id));
  const paidByOrder = new Map<string, number>();
  let unlinked = 0;
  for (const tx of data.transactions) {
    if ((tx.status as string) === "作废") continue;
    if (tx.type !== "付款" && tx.type !== "垫付") continue;
    const amount = Number(tx.amount) || 0;
    if (tx.purchaseOrderId && purchaseIds.has(tx.purchaseOrderId)) {
      paidByOrder.set(tx.purchaseOrderId, (paidByOrder.get(tx.purchaseOrderId) ?? 0) + amount);
      continue;
    }
    if (!tx.purchaseOrderId && !tx.salesOrderId && !tx.serviceOrderId && tx.projectId === projectId) {
      unlinked += amount;
    }
  }
  const fromOrders = purchaseOrders.reduce((sum, order) => {
    const stored = Number(order.paidAmount) || 0;
    const txPaid = paidByOrder.get(order.id) ?? 0;
    const paid = Math.max(stored, txPaid);
    if (paid > 0) return sum + paid;
    if (order.paymentStatus === "已付款") return sum + (Number(order.amount) || 0);
    return sum;
  }, 0);
  return fromOrders + unlinked;
}

function invoiceProjectIds(data: AppData, invoice: AppData["invoices"][number]) {
  const ids = new Set(invoice.projectIds ?? (invoice.projectId ? [invoice.projectId] : []));
  for (const orderId of invoice.salesOrderIds ?? []) {
    const order = data.salesOrders.find((item) => item.id === orderId);
    if (order) ids.add(order.projectId);
  }
  for (const orderId of invoice.purchaseOrderIds ?? []) {
    const order = data.purchaseOrders.find((item) => item.id === orderId);
    if (order) ids.add(order.projectId);
  }
  return ids;
}

export function projectIssuedInvoiceAmount(data: AppData, projectId: string) {
  return data.invoices
    .filter((invoice) => invoice.type === "销项" && ISSUED_INVOICE_STATUSES.has(invoice.status))
    .reduce((sum, invoice) => {
      const projectIds = [...invoiceProjectIds(data, invoice)];
      if (!projectIds.includes(projectId)) return sum;
      if (projectIds.length <= 1) return sum + invoice.amount;
      const projectAmounts = projectIds.map((id) => Number(data.projects.find((project) => project.id === id)?.totalAmount) || 0);
      const totalProjectAmount = projectAmounts.reduce((total, amount) => total + amount, 0);
      const projectAmount = Number(data.projects.find((project) => project.id === projectId)?.totalAmount) || 0;
      const allocation = totalProjectAmount > 0
        ? invoice.amount * projectAmount / totalProjectAmount
        : invoice.amount / projectIds.length;
      return sum + allocation;
    }, 0);
}

export function projectPendingInvoiceAmount(data: AppData, projectId: string) {
  const projectAmount = Number(data.projects.find((project) => project.id === projectId)?.totalAmount) || 0;
  return Math.max(projectAmount - projectIssuedInvoiceAmount(data, projectId), 0);
}

export function calculateDashboardMetrics(data: AppData) {
  const revenue = data.projects.reduce((sum, project) => sum + projectSalesAmount(data, project.id), 0);
  const projectAmount = data.projects.reduce((sum, project) => sum + (Number(project.totalAmount) || 0), 0);
  const cost = data.projects.reduce((sum, project) => sum + projectPurchaseAmount(data, project.id), 0);
  const onboardingProjectIds = new Set(
    data.projects
      .filter((project) => project.type === "服务项目" && project.status === "入驻中")
      .map((project) => project.id),
  );
  for (const record of data.onboardingRecords) {
    if (record.step !== "已完成") onboardingProjectIds.add(record.projectId);
  }
  return {
    active: data.projects.filter((project) => !isTerminalProject(project)).length,
    exception: data.projects.filter((project) => project.status === "终止" || project.status === "异常").length,
    revenue,
    projectAmount,
    cost,
    profit: revenue - cost,
    pendingInvoice: data.projects.reduce((sum, project) => sum + projectPendingInvoiceAmount(data, project.id), 0),
    onboarding: onboardingProjectIds.size,
    reminders: data.projectReminders.filter((reminder) => reminder.status === "进行中").length,
  };
}
