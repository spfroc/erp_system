export type EntityType = "企业" | "个体户" | "政府" | "事业单位" | "学校" | "医院" | "其他";

export type OrganizationRole = "客户" | "供应商" | "使用单位" | "平台入驻客户";

export type ProjectType = "实体商品" | "平台入驻服务" | "混合项目";

export type ProjectStatus =
  | "已付款待办理"
  | "待签/待收款"
  | "待采购/平台操作"
  | "履约中"
  | "待开票/待结算"
  | "已完成"
  | "异常";

export type OnboardingStep =
  | "已付款待办理"
  | "待营业执照"
  | "营业执照已落库"
  | "待注册账号"
  | "账号已注册"
  | "域名备案中"
  | "待亮照"
  | "待公安备案"
  | "待后台模板录入"
  | "CA办理中"
  | "待平台审核"
  | "平台审核通过"
  | "待续费"
  | "已完成"
  | "异常";

export interface Organization {
  id: string;
  name: string;
  entityType: EntityType;
  roles: OrganizationRole[];
  unifiedCreditCode?: string;
  legalPerson?: string;
  phone?: string;
  email?: string;
  city?: string;
  district?: string;
  address?: string;
  invoiceInfo?: string;
  bankInfo?: string;
  status: "正常" | "停用" | "归档";
  createdAt: string;
}

export interface Product {
  id: string;
  code: string;
  name: string;
  kind: "实体商品" | "虚拟服务";
  category: string;
  quotePrice: number;
  costPrice: number;
  platformCode?: string;
  description?: string;
}

export interface SupplierPrice {
  id: string;
  productId: string;
  supplierOrgId: string;
  purchasePrice: number;
  note?: string;
}

export interface Project {
  id: string;
  projectNo: string;
  name: string;
  type: ProjectType;
  customerOrgId: string;
  usageUnitOrgId?: string;
  sourcePlatform?: string;
  owner: string;
  status: ProjectStatus;
  contractStatus: "无需" | "待签" | "已签";
  paymentStatus: "未收" | "部分收" | "已收" | "垫付未清" | "垫付已清";
  purchaseStatus: "无需采购" | "待采购" | "已下单" | "已发货" | "已完成";
  invoiceStatus: "未开" | "部分开" | "已开" | "无需";
  totalAmount: number;
  totalCost: number;
  currentBlocker?: string;
  updatedAt: string;
}

export interface ProjectItem {
  id: string;
  projectId: string;
  productId: string;
  productName: string;
  quantity: number;
  actualPrice: number;
  costPrice: number;
}

export interface OnboardingRecord {
  id: string;
  projectId: string;
  customerOrgId: string;
  platform: "泉E采" | "青慧采" | "齐鲁云采" | "政采云" | "国铁";
  step: OnboardingStep;
  salesOwner: string;
  businessLicenseNo?: string;
  qiluAccount?: string;
  supplierAccount?: string;
  domain?: string;
  icpRecordNo?: string;
  licenseDisplayStatus: "未处理" | "已完成";
  publicSecurityStatus: "未处理" | "已完成";
  backendTemplateStatus: "未录入" | "已录入";
  caStatus: "未办理" | "办理中" | "已完成";
  serviceYears: number;
  expireDate?: string;
  note?: string;
}

export interface Invoice {
  id: string;
  projectId: string;
  type: "销项" | "进项";
  counterpartyOrgId: string;
  amount: number;
  status: "草稿" | "待确认" | "已开" | "已收";
  invoiceNo?: string;
  date?: string;
}

export interface Transaction {
  id: string;
  projectId: string;
  type: "收款" | "付款" | "垫付" | "后返";
  amount: number;
  date: string;
  status: "待匹配" | "已匹配";
}

export interface OcrJob {
  id: string;
  type: "营业执照" | "发票";
  fileName: string;
  status: "待确认" | "已确认";
  result: Record<string, string>;
  createdAt: string;
}

export interface AppData {
  organizations: Organization[];
  products: Product[];
  supplierPrices: SupplierPrice[];
  projects: Project[];
  projectItems: ProjectItem[];
  onboardingRecords: OnboardingRecord[];
  invoices: Invoice[];
  transactions: Transaction[];
  ocrJobs: OcrJob[];
}
