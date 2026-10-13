import type { AppData, OptionItem, Organization, Project } from "./types";

export const SERVICE_CONTRACT_PLATFORMS = ["泉E采", "青慧采"] as const;

export type ServiceContractPlatform = (typeof SERVICE_CONTRACT_PLATFORMS)[number];
export type ServiceContractFileFormat = "word" | "pdf";

export const SHOP_CATEGORY_OPTIONS = [
  { value: "服务类", label: "（政企专用）服务/工程类" },
  { value: "产品类", label: "货物类" },
] as const;

export const OWN_COMPANY_SHORT_NAMES: Record<string, string> = {
  "山东壹知产数字科技有限公司": "壹知产",
  "济南云集企业管理有限公司": "云集",
};

export type ServiceContractDraft = {
  partyAName: string;
  partyAAddress: string;
  partyAPhone: string;
  partyBName: string;
  partyBAddress: string;
  partyBPhone: string;
  shopName: string;
  shopCategories: string[];
  shopCategory: string;
  listingLimit: string;
  startDate: string;
  endDate: string;
  signDate: string;
  amount: string;
  bankName: string;
  accountName: string;
  accountNumber: string;
};

const COMPANY_SUFFIXES = ["有限责任公司", "有限公司"] as const;
/** 合同模板内固定收款信息，生成时不再改写。 */
export const TEMPLATE_BANK_BY_PLATFORM: Record<ServiceContractPlatform, string> = {
  "泉E采": "中信银行济南市中支行",
  "青慧采": "广发银行股份有限公司济南分行营业部",
};
export const TEMPLATE_ACCOUNT_BY_PLATFORM: Record<ServiceContractPlatform, string> = {
  "泉E采": "8112501012401497344",
  "青慧采": "9550880219307000169",
};
export const TEMPLATE_BANK_NAME = TEMPLATE_BANK_BY_PLATFORM["泉E采"];
export const TEMPLATE_ACCOUNT_NUMBER = TEMPLATE_ACCOUNT_BY_PLATFORM["泉E采"];

export function templateBankAccount(platform?: string): { bankName: string; accountNumber: string } {
  const key = normalizeContractPlatform(platform);
  if (!key) {
    return { bankName: TEMPLATE_BANK_NAME, accountNumber: TEMPLATE_ACCOUNT_NUMBER };
  }
  return {
    bankName: TEMPLATE_BANK_BY_PLATFORM[key],
    accountNumber: TEMPLATE_ACCOUNT_BY_PLATFORM[key],
  };
}
const PLATFORM_DEFAULTS: Record<ServiceContractPlatform, { shopCategories: string[]; listingLimit: string; amount: string }> = {
  "泉E采": { shopCategories: ["服务类"], listingLimit: "300", amount: "3000" },
  "青慧采": { shopCategories: ["产品类"], listingLimit: "不限数量", amount: "4000" },
};
const CN_DIGITS = "零壹贰叁肆伍陆柒捌玖";

export function normalizeContractPlatform(platform?: string): ServiceContractPlatform | "" {
  const text = (platform || "").trim();
  if (!text) return "";
  const folded = text.replaceAll("Ｅ", "E").replaceAll("ｅ", "e").replaceAll("E", "e");
  if (folded === "泉e采") return "泉E采";
  if (text === "青慧采") return "青慧采";
  return "";
}

export function hasServiceContractTemplate(platform?: string) {
  return Boolean(normalizeContractPlatform(platform));
}

export function contractNeedsCollectionAccount(platform?: string) {
  return Boolean(normalizeContractPlatform(platform));
}

export function shopNameFromCompany(name?: string) {
  let text = (name || "").trim();
  for (const suffix of COMPANY_SUFFIXES) {
    if (text.endsWith(suffix)) {
      text = text.slice(0, -suffix.length);
      break;
    }
  }
  text = text.trim();
  if (text && !text.endsWith("店")) return `${text}店`;
  return text;
}

export function ownCompanyShortName(name?: string) {
  const text = (name || "").trim();
  return OWN_COMPANY_SHORT_NAMES[text] || text;
}

export function formatShopCategories(values: string[]) {
  const selected = new Set(values.map((item) => item.trim()).filter(Boolean));
  return SHOP_CATEGORY_OPTIONS.filter((item) => selected.has(item.value)).map((item) => item.label).join("/");
}

export function hasOrganizationContact(org?: Organization) {
  return Boolean(org?.name?.trim() && org.address?.trim() && org.phone?.trim());
}

export function findProjectCollectionAccount(data: AppData, project: Project): OptionItem | undefined {
  const items = (data.optionGroups.find((group) => group.key === "collection_account")?.items ?? [])
    .filter((item) => item.enabled !== false && (item.accountNumber || item.value));
  const orders = data.serviceOrders
    .filter((order) => order.projectId === project.id && order.status !== "取消" && order.status !== "退款")
    .slice()
    .sort((left, right) => String(right.updatedAt || right.createdAt || "").localeCompare(String(left.updatedAt || left.createdAt || "")));
  const raw = orders.find((order) => order.collectionAccount)?.collectionAccount?.trim() || "";
  const matched = raw ? matchCollectionAccount(raw, items) : undefined;
  if (matched) return matched;
  const ownAccounts = items.filter((item) => !project.ownCompanyOrgId || item.ownCompanyOrgId === project.ownCompanyOrgId);
  return ownAccounts[0];
}

export function canGenerateServiceContract(_data: AppData, project: Project) {
  return project.type === "服务项目" && hasServiceContractTemplate(project.sourcePlatform);
}

export function projectAmountOrDefault(totalAmount: number | string | undefined, fallback: string) {
  const amount = Number(totalAmount) || 0;
  return amount > 0 ? String(amount) : fallback;
}

export function platformContractDefaults(platform?: string) {
  const key = normalizeContractPlatform(platform);
  return key ? PLATFORM_DEFAULTS[key] : { shopCategories: ["服务类"], listingLimit: "300", amount: "3000" };
}

export function findOwnCompanyCollectionAccount(data: AppData, ownCompanyOrgId?: string): OptionItem | undefined {
  const items = (data.optionGroups.find((group) => group.key === "collection_account")?.items ?? [])
    .filter((item) => item.enabled !== false && (item.accountNumber || item.value));
  const ownAccounts = items.filter((item) => !ownCompanyOrgId || item.ownCompanyOrgId === ownCompanyOrgId);
  return ownAccounts[0];
}

export function buildStandaloneContractDraft(
  data: AppData,
  platform: ServiceContractPlatform,
  partyA?: Organization,
  partyB?: Organization,
): ServiceContractDraft {
  const defaults = PLATFORM_DEFAULTS[platform];
  const partyAName = partyA?.name?.trim() || "";
  const partyBName = partyB?.name?.trim() || "";
  const startDate = todayIsoDate();
  return {
    partyAName,
    partyAAddress: partyA?.address?.trim() || "",
    partyAPhone: partyA?.phone?.trim() || "",
    partyBName,
    partyBAddress: partyB?.address?.trim() || "",
    partyBPhone: partyB?.phone?.trim() || "",
    shopName: shopNameFromCompany(partyAName),
    shopCategories: [...defaults.shopCategories],
    shopCategory: formatShopCategories(defaults.shopCategories),
    listingLimit: defaults.listingLimit,
    startDate,
    endDate: addYearsIso(startDate, 1),
    signDate: startDate,
    amount: defaults.amount,
    bankName: templateBankAccount(platform).bankName,
    accountName: partyBName,
    accountNumber: templateBankAccount(platform).accountNumber,
  };
}

export function mergeStandaloneDraft(
  data: AppData,
  platform: ServiceContractPlatform,
  partyA: Organization | undefined,
  partyB: Organization | undefined,
  previous: ServiceContractDraft | null,
  options?: { resetPlatformDefaults?: boolean },
): ServiceContractDraft {
  const next = buildStandaloneContractDraft(data, platform, partyA, partyB);
  if (!previous) return next;
  const reset = options?.resetPlatformDefaults === true;
  return {
    ...next,
    partyAName: partyA ? next.partyAName : previous.partyAName,
    partyAAddress: partyA ? next.partyAAddress : previous.partyAAddress,
    partyAPhone: partyA ? next.partyAPhone : previous.partyAPhone,
    partyBName: partyB ? next.partyBName : previous.partyBName,
    partyBAddress: partyB ? next.partyBAddress : previous.partyBAddress,
    partyBPhone: partyB ? next.partyBPhone : previous.partyBPhone,
    shopName: partyA ? next.shopName : previous.shopName,
    shopCategories: reset ? next.shopCategories : previous.shopCategories,
    shopCategory: reset ? next.shopCategory : previous.shopCategory,
    listingLimit: reset ? next.listingLimit : previous.listingLimit,
    startDate: previous.startDate || next.startDate,
    endDate: previous.endDate || next.endDate,
    signDate: previous.signDate || next.signDate,
    amount: reset ? next.amount : previous.amount,
    bankName: templateBankAccount(platform).bankName,
    accountName: partyB ? next.accountName : previous.accountName,
    accountNumber: templateBankAccount(platform).accountNumber,
  };
}

export function buildServiceContractDraft(data: AppData, project: Project): ServiceContractDraft {
  const platform = normalizeContractPlatform(project.sourcePlatform);
  const defaults = platform ? PLATFORM_DEFAULTS[platform] : { shopCategories: ["服务类"], listingLimit: "300", amount: "3000" };
  const customer = data.organizations.find((org) => org.id === project.customerOrgId);
  const ownCompany = data.organizations.find((org) => org.id === project.ownCompanyOrgId);
  const partyAName = customer?.name?.trim() || "";
  const partyBName = ownCompany?.name?.trim() || "";
  const startDate = datePart(project.serviceStartDate);
  const endDate = datePart(project.serviceEndDate);
  return {
    partyAName,
    partyAAddress: customer?.address?.trim() || "",
    partyAPhone: customer?.phone?.trim() || "",
    partyBName,
    partyBAddress: ownCompany?.address?.trim() || "",
    partyBPhone: ownCompany?.phone?.trim() || "",
    shopName: shopNameFromCompany(partyAName),
    shopCategories: [...defaults.shopCategories],
    shopCategory: formatShopCategories(defaults.shopCategories),
    listingLimit: defaults.listingLimit,
    startDate,
    endDate,
    signDate: startDate,
    amount: projectAmountOrDefault(project.totalAmount, defaults.amount),
    bankName: templateBankAccount(platform || undefined).bankName,
    accountName: partyBName,
    accountNumber: templateBankAccount(platform || undefined).accountNumber,
  };
}

export function serviceContractDraftErrors(draft: ServiceContractDraft, platform?: string) {
  const missing: string[] = [];
  const required: Array<keyof ServiceContractDraft> = [
    "partyAName",
    "partyAAddress",
    "partyAPhone",
    "partyBName",
    "partyBAddress",
    "partyBPhone",
    "shopName",
    "listingLimit",
    "startDate",
    "endDate",
    "signDate",
  ];
  if (contractNeedsCollectionAccount(platform)) {
    required.push("accountName");
  }
  for (const key of required) {
    if (!String(draft[key] || "").trim()) missing.push(key);
  }
  if (!formatShopCategories(draft.shopCategories)) missing.push("shopCategories");
  if (!(Number(draft.amount) > 0)) missing.push("amount");
  return missing;
}

export function amountToChinese(value: number | string) {
  const amount = roundMoney(Number(value) || 0);
  const negative = amount < 0;
  const abs = Math.abs(amount);
  const yuan = Math.trunc(abs);
  const cents = Math.round((abs - yuan) * 100);
  const jiao = Math.trunc(cents / 10);
  const fen = cents % 10;
  const yuanPart = yuan ? `${integerToChinese(yuan)}元` : "";
  let text: string;
  if (jiao === 0 && fen === 0) {
    text = `${yuanPart || "零元"}整`;
  } else {
    const parts = [yuanPart || "零元"];
    if (jiao) parts.push(`${CN_DIGITS[jiao]}角`);
    else if (fen) parts.push("零");
    if (fen) parts.push(`${CN_DIGITS[fen]}分`);
    text = parts.join("");
  }
  return negative ? `负${text}` : text;
}

function matchCollectionAccount(account: string, items: OptionItem[]) {
  const byId = items.find((item) => item.id === account);
  if (byId) return byId;
  const numbered = items.filter((item) => {
    const number = item.accountNumber || item.value || "";
    return Boolean(number) && (account === number || account.includes(number));
  });
  return numbered[0];
}

function todayIsoDate() {
  const now = new Date();
  return `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, "0")}-${String(now.getDate()).padStart(2, "0")}`;
}

function addYearsIso(value: string, years: number) {
  const match = value.match(/^(\d{4})-(\d{2})-(\d{2})$/);
  if (!match) return value;
  const year = Number(match[1]) + years;
  return `${year}-${match[2]}-${match[3]}`;
}

function datePart(value?: string) {
  const match = String(value || "").trim().match(/(\d{4})\D+(\d{1,2})\D+(\d{1,2})/);
  if (!match) return "";
  const [, year, month, day] = match;
  return `${year}-${month.padStart(2, "0")}-${day.padStart(2, "0")}`;
}

function roundMoney(value: number) {
  return Math.round((value + Number.EPSILON) * 100) / 100;
}

function integerToChinese(value: number) {
  if (value === 0) return "零";
  const units = ["", "万", "亿"];
  const parts: string[] = [];
  let unitIndex = 0;
  let pendingZero = false;
  let number = value;
  while (number > 0) {
    const section = number % 10000;
    number = Math.trunc(number / 10000);
    const sectionText = sectionToChinese(section);
    if (section === 0) {
      if (parts.length > 0) pendingZero = true;
    } else {
      if (pendingZero) {
        parts.push("零");
        pendingZero = false;
      }
      parts.push(sectionText + units[unitIndex]);
    }
    unitIndex += 1;
  }
  return parts.reverse().join("");
}

function sectionToChinese(value: number) {
  const digits = [Math.trunc(value / 1000), Math.trunc(value / 100) % 10, Math.trunc(value / 10) % 10, value % 10];
  const names = ["仟", "佰", "拾", ""];
  const result: string[] = [];
  let seenNonZero = false;
  let pendingZero = false;
  digits.forEach((digit, index) => {
    if (digit === 0) {
      if (seenNonZero) pendingZero = true;
      return;
    }
    if (pendingZero) {
      result.push("零");
      pendingZero = false;
    }
    seenNonZero = true;
    result.push(`${CN_DIGITS[digit]}${names[index]}`);
  });
  return result.join("");
}
