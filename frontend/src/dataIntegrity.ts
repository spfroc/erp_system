import type { AppData } from "./types";

export function organizationReferenceCounts(data: AppData, organizationId: string) {
  return {
    projects: data.projects.filter((item) =>
      item.customerOrgId === organizationId
      || item.usageUnitOrgId === organizationId
      || item.ownCompanyOrgId === organizationId,
    ).length,
    supplierPrices: data.supplierPrices.filter((item) => item.supplierOrgId === organizationId).length,
    salesOrders: data.salesOrders.filter((item) =>
      item.customerOrgId === organizationId || item.ownCompanyOrgId === organizationId,
    ).length,
    purchaseOrders: data.purchaseOrders.filter((item) =>
      item.supplierOrgId === organizationId || item.ownCompanyOrgId === organizationId,
    ).length,
    serviceOrders: data.serviceOrders.filter((item) => item.customerOrgId === organizationId).length,
    onboardingRecords: data.onboardingRecords.filter((item) => item.customerOrgId === organizationId).length,
    platformAccounts: data.platformAccounts.filter((item) => item.customerOrgId === organizationId).length,
    invoices: data.invoices.filter((item) =>
      item.buyerOrgId === organizationId
      || item.sellerOrgId === organizationId
      || item.counterpartyOrgId === organizationId,
    ).length,
    transactions: data.transactions.filter((item) => item.counterpartyOrgId === organizationId).length,
  };
}

export function organizationReferenceTotal(data: AppData, organizationId: string) {
  return Object.values(organizationReferenceCounts(data, organizationId)).reduce((sum, count) => sum + count, 0);
}

const ORGANIZATION_REFERENCE_LABELS: Record<string, string> = {
  projects: "项目",
  supplierPrices: "渠道价格",
  salesOrders: "销售订单",
  purchaseOrders: "采购订单",
  serviceOrders: "服务订单",
  onboardingRecords: "入驻记录",
  platformAccounts: "平台账号",
  invoices: "发票",
  transactions: "流水",
};

export function formatOrganizationReferences(counts: Record<string, number>) {
  return Object.entries(counts)
    .filter(([, count]) => count > 0)
    .map(([key, count]) => `${ORGANIZATION_REFERENCE_LABELS[key] ?? key} ${count} 条`)
    .join("、");
}
