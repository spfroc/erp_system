import { describe, expect, it } from "vitest";

import { seedData } from "./seed";
import {
  amountToChinese,
  buildServiceContractDraft,
  buildStandaloneContractDraft,
  canGenerateServiceContract,
  formatShopCategories,
  hasServiceContractTemplate,
  mergeStandaloneDraft,
    ownCompanyShortName,
    serviceContractDraftErrors,
    shopNameFromCompany,
} from "./serviceContract";
import type { AppData, Project } from "./types";

function readyData(): AppData {
  const data = structuredClone(seedData) as AppData;
  data.organizations = data.organizations.map((org) => {
    if (org.id === "org-5") {
      return { ...org, address: "济南市高新区示例路 1 号", phone: "13065056229" };
    }
    if (org.id === "org-8") {
      return { ...org, address: "济南市市中区示例路 8 号", phone: "18600000001" };
    }
    return org;
  });
  data.optionGroups = [
    ...data.optionGroups.filter((group) => group.key !== "collection_account"),
    {
      id: "opt-collection-account",
      key: "collection_account",
      name: "收款账号",
      usages: [],
      items: [
        {
          id: "acc-own-8",
          label: "中信银行 8112501012401497344",
          value: "8112501012401497344",
          enabled: true,
          sortOrder: 1,
          ownCompanyOrgId: "org-8",
          bankName: "中信银行济南市中支行",
          accountNumber: "8112501012401497344",
        },
      ],
    },
  ];
  data.serviceOrders = data.serviceOrders.map((order) => (
    order.projectId === "pj-2" ? { ...order, collectionAccount: "acc-own-8" } : order
  ));
  return data;
}

describe("serviceContract", () => {
  it("strips company suffixes for the shop name", () => {
    expect(shopNameFromCompany("山东壹知产数字科技有限公司")).toBe("山东壹知产数字科技店");
    expect(shopNameFromCompany("济南示例有限责任公司")).toBe("济南示例店");
    expect(shopNameFromCompany("示例智能科技有限公司")).toBe("示例智能科技店");
    expect(shopNameFromCompany("示例智能科技店")).toBe("示例智能科技店");
  });

  it("only enables platforms that have a template", () => {
    expect(hasServiceContractTemplate("泉E采")).toBe(true);
    expect(hasServiceContractTemplate("泉e采")).toBe(true);
    expect(hasServiceContractTemplate("青慧采")).toBe(true);
    expect(hasServiceContractTemplate("齐鲁云采")).toBe(false);
  });

  it("shows generate for templated platforms even if contact details are incomplete", () => {
    const data = readyData();
    const project = data.projects.find((item) => item.id === "pj-2") as Project;
    expect(canGenerateServiceContract(data, project)).toBe(true);
    data.organizations = data.organizations.map((org) => org.id === "org-5" ? { ...org, address: "" } : org);
    expect(canGenerateServiceContract(data, project)).toBe(true);
  });

  it("hides generate when the platform has no template", () => {
    const data = readyData();
    const project = { ...data.projects.find((item) => item.id === "pj-2") as Project, sourcePlatform: "齐鲁云采" };
    expect(canGenerateServiceContract(data, project)).toBe(false);
  });

  it("fills defaults from the project, company name and collection account", () => {
    const data = readyData();
    const project = data.projects.find((item) => item.id === "pj-2") as Project;
    const draft = buildServiceContractDraft(data, project);
    expect(draft.shopName).toBe("示例智能科技店");
    expect(draft.shopCategories).toEqual(["服务类"]);
    expect(draft.shopCategory).toBe("（政企专用）服务/工程类");
    expect(draft.listingLimit).toBe("300");
    expect(draft.signDate).toBe("2026-06-24");
    expect(draft.amount).toBe("2000");
    expect(draft.bankName).toBe("中信银行济南市中支行");
    expect(draft.accountName).toBe("示例数字科技有限公司");
    expect(draft.accountNumber).toBe("8112501012401497344");
  });

  it("uses platform default fees and shop-category labels", () => {
    const data = readyData();
    const qec = data.projects.find((item) => item.id === "pj-2") as Project;
    const qhc = { ...qec, sourcePlatform: "青慧采" as const };
    expect(buildServiceContractDraft(data, qhc).amount).toBe("2000");
    expect(buildServiceContractDraft(data, { ...qec, totalAmount: 0 }).amount).toBe("3000");
    expect(buildServiceContractDraft(data, { ...qhc, totalAmount: 0 }).amount).toBe("4000");
    expect(buildServiceContractDraft(data, qhc).shopCategories).toEqual(["产品类"]);
    expect(formatShopCategories(["服务类", "产品类"])).toBe("（政企专用）服务/工程类/货物类");
    expect(ownCompanyShortName("山东壹知产数字科技有限公司")).toBe("壹知产");
    expect(ownCompanyShortName("济南云集企业管理有限公司")).toBe("云集");
  });

  it("fills standalone drafts from selected organizations", () => {
    const data = readyData();
    const partyA = data.organizations.find((org) => org.id === "org-5");
    const partyB = data.organizations.find((org) => org.id === "org-8");
    const draft = buildStandaloneContractDraft(data, "青慧采", partyA, partyB);
    expect(draft.partyAName).toBe("示例智能科技有限公司");
    expect(draft.shopName).toBe("示例智能科技店");
    expect(draft.amount).toBe("4000");
    expect(draft.accountName).toBe("示例数字科技有限公司");
    expect(draft.bankName).toBe("广发银行股份有限公司济南分行营业部");
    expect(draft.accountNumber).toBe("9550880219307000169");
    expect(serviceContractDraftErrors({ ...draft, bankName: "", accountName: "", accountNumber: "" }, "青慧采")).toEqual(
      expect.arrayContaining(["accountName"]),
    );
    expect(serviceContractDraftErrors({ ...draft, bankName: "", accountNumber: "" }, "泉E采")).not.toEqual(
      expect.arrayContaining(["bankName", "accountNumber"]),
    );
  });

  it("keeps typed fields when switching platform, and refreshes platform defaults", () => {
    const data = readyData();
    const partyA = data.organizations.find((org) => org.id === "org-5");
    const partyB = data.organizations.find((org) => org.id === "org-8");
    const typed = {
      ...buildStandaloneContractDraft(data, "青慧采", undefined, partyB),
      partyAName: "潜在客户有限公司",
      partyAAddress: "青岛市示例路 9 号",
      partyAPhone: "13000000000",
      shopName: "潜在客户店",
      startDate: "2026-08-01",
      endDate: "2027-08-01",
      signDate: "2026-08-01",
      amount: "8888",
    };
    const switched = mergeStandaloneDraft(data, "泉E采", undefined, partyB, typed, { resetPlatformDefaults: true });
    expect(switched.partyAName).toBe("潜在客户有限公司");
    expect(switched.shopName).toBe("潜在客户店");
    expect(switched.amount).toBe("3000");
    expect(switched.shopCategories).toEqual(["服务类"]);
    expect(switched.listingLimit).toBe("300");
    expect(switched.startDate).toBe("2026-08-01");
    const filledA = mergeStandaloneDraft(data, "泉E采", partyA, partyB, switched);
    expect(filledA.partyAName).toBe("示例智能科技有限公司");
    expect(filledA.shopName).toBe("示例智能科技店");
    expect(filledA.amount).toBe("3000");
  });

  it("converts amounts to Chinese uppercase", () => {
    expect(amountToChinese(3000)).toBe("叁仟元整");
    expect(amountToChinese(4000)).toBe("肆仟元整");
    expect(amountToChinese(108.3)).toBe("壹佰零捌元叁角");
    expect(amountToChinese(10)).toBe("壹拾元整");
  });
});
