import { describe, expect, it } from "vitest";

import { formatOrganizationReferences, organizationReferenceCounts, organizationReferenceTotal } from "./dataIntegrity";
import { seedData } from "./seed";

describe("organization references", () => {
  it("finds projects that use an organization in any organization role", () => {
    const references = organizationReferenceCounts(seedData, "org-2");

    expect(references.projects).toBeGreaterThan(0);
    expect(organizationReferenceTotal(seedData, "org-2")).toBeGreaterThan(0);
  });

  it("allows an unreferenced organization to be deleted", () => {
    expect(organizationReferenceTotal(seedData, "not-used")).toBe(0);
  });

  it("formats referenced collections for the delete warning", () => {
    expect(formatOrganizationReferences({
      projects: 2,
      supplierPrices: 0,
      salesOrders: 1,
      purchaseOrders: 0,
      serviceOrders: 0,
      onboardingRecords: 0,
      platformAccounts: 3,
      invoices: 0,
      transactions: 0,
    })).toBe("项目 2 条、销售订单 1 条、平台账号 3 条");
    expect(formatOrganizationReferences({ projects: 0, invoices: 0 })).toBe("");
  });
});
