import type { Invoice, OrderPaymentStatus, Project, ProjectStatus, PurchaseOrder, SalesOrder, ServiceOrder } from "./types";

type StatusTransitionMap<T extends string> = Partial<Record<T, T[]>>;

const serviceProjectTransitions: StatusTransitionMap<ProjectStatus> = {
  入驻中: ["服务中", "项目终止", "终止合作"],
  服务中: ["服务完成", "服务到期", "服务交付完成", "服务到期结束", "项目终止", "到期", "结束", "终止合作"],
  到期: ["服务中", "项目终止", "终止合作"],
  结束: [],
  终止合作: [],
  服务交付完成: [],
  服务到期结束: [],
  服务完成: [],
  服务到期: [],
  项目终止: [],
};

const productProjectTransitions: StatusTransitionMap<ProjectStatus> = {
  初始化: ["进行中", "终止"],
  进行中: ["已完成", "终止"],
  已完成: [],
  终止: [],
};

const serviceOrderTransitions: StatusTransitionMap<ServiceOrder["status"]> = {
  待付款: ["部分付款", "已付款", "退款", "取消"],
  部分付款: ["已付款", "退款", "取消"],
  已付款: ["退款"],
  退款: [],
  取消: [],
};

const salesOrderTransitions: StatusTransitionMap<SalesOrder["status"]> = {
  待付款: ["部分付款", "已付款", "退款", "取消"],
  部分付款: ["已付款", "退款", "取消"],
  已付款: ["退款"],
  退款: [],
  取消: [],
};

const purchaseOrderTransitions: StatusTransitionMap<PurchaseOrder["status"]> = {
  草稿: ["待下单", "已取消"],
  待下单: ["已下单", "已取消"],
  已下单: ["部分到货", "已完成", "已取消"],
  部分到货: ["已完成", "已取消"],
  已完成: [],
  已取消: [],
};

const invoiceTransitions: StatusTransitionMap<Invoice["status"]> = {
  草稿: ["待确认", "作废"],
  待确认: ["已确认", "作废"],
  已确认: ["作废"],
  作废: [],
  // 兼容旧演示数据。
  已开: ["作废"],
  已收: ["作废"],
};

function uniqueStatuses<T extends string>(statuses: T[]) {
  return Array.from(new Set(statuses));
}

function allowedStatuses<T extends string>(current: T, transitions: StatusTransitionMap<T>, configured: T[]) {
  const next = transitions[current] ?? [];
  const filteredNext = next.filter((status) => configured.length === 0 || configured.includes(status));
  return uniqueStatuses([current, ...filteredNext]);
}

export function getAllowedProjectStatuses(project: Project, configured: ProjectStatus[]) {
  // 冒烟测试阶段：服务项目允许在全部配置状态间往返切换，便于验证各状态页面。
  // 正式验收后可恢复 serviceProjectTransitions 的单向限制。
  if (project.type === "服务项目") {
    return configured.length
      ? uniqueStatuses([project.status, ...configured])
      : allowedStatuses(project.status, serviceProjectTransitions, configured);
  }
  return allowedStatuses(
    project.status,
    productProjectTransitions,
    configured,
  );
}

export function getAllowedServiceOrderStatuses(order: ServiceOrder, configured: ServiceOrder["status"][]) {
  return allowedStatuses(order.status, serviceOrderTransitions, configured);
}

export function getAllowedSalesOrderStatuses(order: SalesOrder, configured: SalesOrder["status"][]) {
  return allowedStatuses(order.status, salesOrderTransitions, configured);
}

export function getAllowedOrderPaymentStatuses(status: OrderPaymentStatus, configured: OrderPaymentStatus[]) {
  return allowedStatuses(status, salesOrderTransitions, configured);
}

export function getAllowedPurchaseOrderStatuses(order: PurchaseOrder, configured: PurchaseOrder["status"][]) {
  return allowedStatuses(order.status, purchaseOrderTransitions, configured);
}

export function getAllowedInvoiceStatuses(invoice: Invoice, configured: Invoice["status"][]) {
  return allowedStatuses(invoice.status, invoiceTransitions, configured);
}

export function canTransition<T extends string>(current: T, next: T, allowed: T[]) {
  return current === next || allowed.includes(next);
}
