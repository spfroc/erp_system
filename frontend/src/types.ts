export type EntityType = "企业" | "个体户" | "政府" | "事业单位" | "学校" | "医院" | "其他";

export type OrganizationRole = "平台入驻商" | "中间销售商" | "上游供应商" | "使用单位" | "终端采购人" | "自有主体" | "客户" | "供应商" | "平台入驻客户" | "本方主体";
export type TaxpayerType = "一般纳税人" | "小规模纳税人" | "非企业单位";

export type ProjectType = "商品项目" | "服务项目";

export type ProjectStatus =
  | "初始化"
  | "进行中"
  | "已完成"
  | "终止"
  // 兼容历史商品项目状态（迁移前）
  | "已付款待办理"
  | "待签/待收款"
  | "待采购/平台操作"
  | "履约中"
  | "待开票/待结算"
  | "异常"
  // 服务项目状态
  | "入驻中"
  | "服务中"
  | "终止合作"
  | "到期"
  | "结束"
  | "服务交付完成"
  | "服务到期结束"
  | "服务完成"
  | "服务到期"
  | "项目终止";

export type LogisticsStatus = "待发货" | "已发货" | "已签收";
export type AcceptanceStatus = "待验收" | "验收中" | "已验收";
export type DeliveryStatus = "待交付" | "部分交付" | "交付中" | "已交付";
/** @deprecated 已由 DeliveryStatus 替代，仅迁移读取 */
export type InstallationStatus = "未安装" | "安装中" | "已安装" | DeliveryStatus;

export type ContractStatus = "无需" | "待签" | "已签" | "已发送";
export type OrderPaymentStatus = "待付款" | "部分付款" | "已付款" | "退款" | "取消";
export type ReconcileStatus = "待对账" | "已对账";
export type InvoiceDisplayStatus = "待开" | "已开部分" | "已开全部" | "无需";

export type ServiceType = "周期" | "按次";
export type ServiceCustomerKind = "首次服务" | "续费客户";
export type ServicePeriodUnit = "年" | "月";
export type ServiceOrderStatus = "待付款" | "部分付款" | "已付款" | "退款" | "取消";

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
  taxpayerType?: TaxpayerType;
  taxpayerTypeHistory?: Array<{ type: TaxpayerType; effectiveAt: string; endedAt?: string; changedAt: string }>;
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
  updatedAt?: string;
  licenseFileId?: string;
  licenseFileName?: string;
}

export interface Product {
  id: string;
  code: string;
  name: string;
  kind: "实体商品" | "虚拟服务";
  category: string;
  capacity?: string;
  energyLevel?: string;
  shape?: string;
  frameworkPrice?: number;
  passThroughPrice?: number;
  quotePrice: number;
  costPrice: number;
  platformCode?: string;
  orderInfo?: string;
  area?: string;
  description?: string;
  platformIds?: string[];
  /** 项目内直接添加的商品，不进入商品及价格体系。 */
  source?: "catalog" | "project";
  sourceProjectId?: string;
  createdAt?: string;
  updatedAt?: string;
}

export interface SupplierPrice {
  id: string;
  productId: string;
  supplierOrgId: string;
  purchasePrice: number;
  effectiveDate?: string;
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
  platformOrderNo?: string;
  ownCompanyOrgId?: string;
  owner: string;
  status: ProjectStatus;
  contractStatus: ContractStatus;
  contractFileId?: string;
  contractFileName?: string;
  paymentStatus: OrderPaymentStatus;
  purchaseStatus: "无需采购" | "待采购" | "已下单" | "已发货" | "已完成";
  invoiceStatus: InvoiceDisplayStatus;
  reconcileStatus?: ReconcileStatus;
  totalAmount: number;
  totalCost: number;
  serviceProductId?: string;
  serviceProductName?: string;
  serviceType?: ServiceType;
  /** 服务项目：首次入驻还是老客续费。 */
  serviceCustomerKind?: ServiceCustomerKind;
  serviceStartDate?: string;
  serviceEndDate?: string;
  servicePeriodUnit?: ServicePeriodUnit;
  servicePeriodValue?: number;
  serviceGiftMonths?: number;
  serviceGiftUnit?: "天" | "月";
  serviceGiftValue?: number;
  serviceSalesUserId?: string;
  serviceSalesName?: string;
  serviceOperatorUserId?: string;
  serviceOperatorName?: string;
  serviceRemark?: string;
  /** 商品项目备注，会写入项目名称（日期前）。 */
  remark?: string;
  currentBlocker?: string;
  /** 由采购订单履约汇总派生（只读展示） */
  logisticsStatus?: LogisticsStatus;
  acceptanceStatus?: AcceptanceStatus;
  deliveryStatus?: DeliveryStatus;
  /** @deprecated 迁移后写入 deliveryStatus */
  installationStatus?: InstallationStatus;
  acceptanceRemark?: string;
  installationRemark?: string;
  deliveryRemark?: string;
  createdAt?: string;
  updatedAt: string;
  /** 合同状态/文件变更时间；合同管理排序与展示用，业务更新勿写入 */
  contractUpdatedAt?: string;
}

export interface ProjectItem {
  id: string;
  projectId: string;
  salesOrderId?: string;
  purchaseOrderId?: string;
  /** 销售明细关联的渠道采购订单 */
  sourcePurchaseOrderId?: string;
  productId: string;
  productName: string;
  supplierOrgId?: string;
  supplierPriceId?: string;
  quantity: number;
  deliveredQuantity?: number;
  actualPrice: number;
  costPrice: number;
}

export interface SalesOrder {
  id: string;
  projectId: string;
  orderNo: string;
  platform?: string;
  platformOrderNo?: string;
  customerOrgId: string;
  ownCompanyOrgId?: string;
  amount: number;
  receivableAmount?: number;
  receivedAmount?: number;
  status: OrderPaymentStatus;
  paymentMethod?: string;
  collectionAccount?: string;
  payerAccount?: string;
  voucherFileId?: string;
  voucherName?: string;
  /** 由采购订单履约汇总派生（只读） */
  logisticsStatus?: LogisticsStatus;
  acceptanceStatus?: AcceptanceStatus;
  deliveryStatus?: DeliveryStatus;
  createdAt: string;
  updatedAt?: string;
  paidAt?: string;
  refundedAt?: string;
  cancelledAt?: string;
  note?: string;
  /** 终端采购人，按订单录入，可与客户主体不同。 */
  purchaserCompany?: string;
  purchaserAddress?: string;
  purchaserName?: string;
  purchaserPhone?: string;
  /** 本销售单关联的渠道采购订单 */
  purchaseOrderIds?: string[];
}

export interface PurchaseOrder {
  id: string;
  projectId: string;
  orderNo: string;
  supplierOrgId: string;
  ownCompanyOrgId?: string;
  amount: number;
  /** 采购执行状态 */
  status: "草稿" | "待下单" | "已下单" | "部分到货" | "已完成" | "已取消";
  paymentStatus?: OrderPaymentStatus;
  paidAmount?: number;
  paidAt?: string;
  collectionAccount?: string;
  payerAccount?: string;
  voucherFileId?: string;
  voucherName?: string;
  reconcileStatus?: ReconcileStatus;
  contractStatus?: ContractStatus;
  contractFileId?: string;
  contractFileName?: string;
  logisticsStatus?: LogisticsStatus;
  logisticsNo?: string;
  acceptanceStatus?: AcceptanceStatus;
  deliveryStatus?: DeliveryStatus;
  acceptanceRemark?: string;
  deliveryRemark?: string;
  createdAt: string;
  updatedAt?: string;
  /** 合同状态/文件变更时间；合同管理排序与展示用，业务更新勿写入 */
  contractUpdatedAt?: string;
  batchNo?: string;
  note?: string;
}

export interface ServiceOrder {
  id: string;
  orderNo: string;
  projectId: string;
  serviceId: string;
  customerOrgId: string;
  amount: number;
  receivableAmount?: number;
  receivedAmount?: number;
  status: ServiceOrderStatus;
  paymentMethod?: string;
  paymentAccount?: string;
  collectionAccount?: string;
  payerAccount?: string;
  voucherFileId?: string;
  voucherName?: string;
  salesUserId?: string;
  salesName?: string;
  createdAt: string;
  updatedAt: string;
  paidAt?: string;
  refundedAt?: string;
  cancelledAt?: string;
  note?: string;
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

export interface PlatformAccount {
  id: string;
  projectId?: string;
  customerOrgId: string;
  platform: "泉E采" | "青慧采" | "齐鲁云采" | "政采云" | "公采云" | "国铁" | "其他";
  accountName?: string;
  accountPasswordMasked?: string;
  merchantId?: string;
  shopId?: string;
  shopName?: string;
  supplierAccount?: string;
  supplierPasswordMasked?: string;
  cloudAccount?: string;
  cloudPasswordMasked?: string;
  domain?: string;
  icpRecordNo?: string;
  licenseDisplayStatus: "未处理" | "已完成";
  publicSecurityStatus: "未处理" | "已完成";
  backendTemplateStatus: "未录入" | "已录入";
  caAccount?: string;
  caPasswordMasked?: string;
  caStatus: "未办理" | "办理中" | "已完成";
  serviceYears?: number;
  expireDate?: string;
  salesOwner?: string;
  currentStatus: string;
  note?: string;
  createdAt?: string;
  updatedAt?: string;
}

export interface InvoiceServiceAllocation {
  projectId: string;
  serviceOrderId?: string;
  amount: number;
}

export interface Invoice {
  id: string;
  projectId?: string;
  projectIds?: string[];
  salesOrderIds?: string[];
  purchaseOrderIds?: string[];
  /** 服务项目/服务订单按金额拆分关联；缺省时旧数据仍按 projectIds 整票占用。 */
  serviceAllocations?: InvoiceServiceAllocation[];
  type: "销项" | "进项";
  counterpartyOrgId: string;
  invoiceNo?: string;
  invoiceDate?: string;
  buyerOrgId?: string;
  buyerName?: string;
  buyerTaxNo?: string;
  sellerOrgId?: string;
  sellerName?: string;
  sellerTaxNo?: string;
  amountWithoutTax?: number;
  taxAmount?: number;
  amount: number;
  status: "草稿" | "待确认" | "已确认" | "作废" | "已开" | "已收";
  date?: string;
  lineItems?: InvoiceLineItem[];
  fileId?: string;
  fileName?: string;
  createdAt?: string;
}

export interface InvoiceLineItem {
  productId?: string;
  productName: string;
  specification?: string;
  unit?: string;
  quantity?: number;
  unitPrice?: number;
  amount?: number;
  taxRate?: string;
  taxAmount?: number;
  raw?: string;
  salesOrderId?: string;
  purchaseOrderId?: string;
}

export type FinanceStatementKind = "服务" | "商品" | "采购" | "未归属";

export interface FinanceStatementRow {
  id: string;
  businessKind: FinanceStatementKind;
  customerOrgId?: string;
  customerName: string;
  serviceCustomerKind?: ServiceCustomerKind | "";
  ownCompanyOrgId?: string;
  companyName: string;
  accountText: string;
  bankName?: string;
  accountNumber?: string;
  salesperson: string;
  salespersonId?: string;
  amount: number;
  occurredAt: string;
  txType: Transaction["type"] | string;
}

export interface Transaction {
  id: string;
  projectId: string;
  salesOrderId?: string;
  purchaseOrderId?: string;
  serviceOrderId?: string;
  type: "收款" | "付款" | "垫付" | "后返" | "退款";
  amount: number;
  date: string;
  status: "待匹配" | "已匹配";
  account?: string;
  counterpartyOrgId?: string;
  remark?: string;
  transactionNo?: string;
  occurredAt?: string;
  createdAt?: string;
  voucherName?: string;
  voucherFileId?: string;
  projectName?: string;
}

export interface OperationLog {
  id: string;
  action: string;
  targetType: "项目" | "实体" | "商品" | "发票" | "流水" | "用户" | "权限" | "系统";
  targetName: string;
  operator: string;
  createdAt: string;
  detail?: string;
}

export interface OcrJob {
  id: string;
  type: "营业执照" | "发票";
  fileName: string;
  status: "待确认" | "已确认";
  result: Record<string, string>;
  createdAt: string;
}

export interface WebsiteLeadMemo {
  id: string;
  content: string;
  createdBy: string;
  createdAt: string;
}

export interface WebsiteLead {
  id: string;
  companyName: string;
  phone: string;
  contactName: string;
  platform: "泉E采" | "齐鲁云采" | "青慧采" | "政采云" | "公采云" | "国铁" | "其他";
  remark?: string;
  status: "未跟进" | "已跟进" | "已成交" | "放弃";
  createdAt: string;
  handledAt?: string;
  lastOperatorName?: string;
  memos?: WebsiteLeadMemo[];
}

export type ReminderWorkContent =
  | "绑定账期"
  | "产品上架"
  | "产品审核"
  | "服务类入池"
  | "产品类入池"
  | "加分类"
  | "加品牌"
  | "服务类上架"
  | "开发票"
  | "做合同";

export interface ProjectReminder {
  id: string;
  projectId: string;
  workContent: ReminderWorkContent;
  status: "进行中" | "已完成";
  createdByUserId: string;
  createdByName: string;
  createdAt: string;
  updatedAt: string;
  completedAt?: string;
}

export interface ProjectMemo {
  id: string;
  projectId: string;
  content: string;
  createdBy: string;
  createdAt: string;
}

export interface TrademarkAttachment {
  id: string;
  fileId: string;
  fileName: string;
  uploadedAt?: string;
  note?: string;
}

export interface TrademarkCertificate {
  id: string;
  registrationNo: string;
  registrant: string;
  registrantAddress: string;
  internationalClass: string;
  approvedGoods?: string;
  registrationDate: string;
  validUntil: string;
  trademarkName?: string;
  fileId?: string;
  fileName?: string;
  attachments?: TrademarkAttachment[];
  note?: string;
  createdAt: string;
  updatedAt?: string;
}

export type NoticeKind =
  | "采购公告"
  | "意向公开"
  | "结果公告"
  | "更正公告"
  | "终止公告"
  | "合同公告"
  | "验收公告"
  | "单一来源公示"
  | "竞价项目"
  | "其他";

export type NoticeBidStatus = "竞价中" | "已完成" | "终止" | "失败" | "结果待确认" | "";

export interface Notice {
  id: string;
  title: string;
  projectNumber?: string;
  planNumber?: string;
  supplierName?: string;
  department?: string;
  category?: string;
  noticeKind: NoticeKind;
  bidStatus?: NoticeBidStatus;
  amount?: number;
  contactName?: string;
  contactPhone?: string;
  detailUrl?: string;
  content?: string;
  publisher?: string;
  startAt?: string;
  endAt?: string;
  publishedAt?: string;
  isPublic: boolean;
  source: "manual" | "import" | "collect";
  externalId?: string;
  sourceId?: string;
  matchedKeywords?: string[];
  createdAt: string;
  updatedAt?: string;
}

export interface NoticeCollectionSource {
  id: string;
  name: string;
  kind: "sample" | "http_json" | string;
  enabled: boolean;
  keywords?: string[];
  endpointUrl?: string;
  defaultIsPublic?: boolean;
  lastRunAt?: string;
  lastStatus?: string;
  lastError?: string;
  createdAt: string;
  updatedAt?: string;
}

export interface NoticeCollectionRun {
  id: string;
  sourceId: string;
  sourceName: string;
  status: "进行中" | "成功" | "失败";
  fetchedCount: number;
  createdCount: number;
  updatedCount: number;
  leadCount: number;
  errorMessage?: string;
  startedAt: string;
  finishedAt?: string;
  createdAt?: string;
  updatedAt?: string;
}

export interface OfficialSite {
  id: string;
  key: string;
  name: string;
  domain: string;
  brand: string;
  companyName?: string;
  phone?: string;
  email?: string;
  address?: string;
  logoUrl?: string;
  primaryColor?: string;
  seoTitle?: string;
  seoDescription?: string;
  seoKeywords?: string;
  ogImageUrl?: string;
  robotsTxt?: string;
  sitemapUrls?: string[];
  jsonLd?: string;
  baiduSiteVerification?: string;
  googleSiteVerification?: string;
  status: "启用" | "停用";
  createdAt: string;
  updatedAt?: string;
}

export interface OfficialPageBlock {
  type: string;
  data: Record<string, unknown>;
}

export interface OfficialPage {
  id: string;
  siteId: string;
  slug: string;
  title: string;
  template: string;
  status: "draft" | "published";
  seoTitle?: string;
  seoDescription?: string;
  blocks: OfficialPageBlock[];
  sortOrder?: number;
  createdAt: string;
  updatedAt?: string;
}

export interface OptionItem {
  id: string;
  label: string;
  value: string;
  enabled: boolean;
  sortOrder: number;
  note?: string;
  ownCompanyOrgId?: string;
  bankName?: string;
  accountNumber?: string;
}

export interface OptionGroup {
  id: string;
  key: string;
  name: string;
  description?: string;
  usages: string[];
  items: OptionItem[];
}

export type PermissionKey =
  | "dashboard.view"
  | "project.view"
  | "project.create"
  | "project.edit"
  | "entity.view"
  | "entity.create"
  | "product.view"
  | "product.manage"
  | "purchase.manage"
  | "serviceOrder.view"
  | "serviceOrder.manage"
  | "salesOrder.view"
  | "salesOrder.manage"
  | "purchaseOrder.view"
  | "purchaseOrder.manage"
  | "finance.view"
  | "finance.manage"
  | "invoice.manage"
  | "onboarding.manage"
  | "platformAccount.view"
  | "platformAccount.manage"
  | "trademarkCertificate.view"
  | "trademarkCertificate.manage"
  | "notice.view"
  | "notice.manage"
  | "site.view"
  | "site.manage"
  | "lead.manage"
  | "sensitive.view"
  | "profit.view"
  | "user.manage";

export interface Role {
  id: string;
  name: string;
  description: string;
  permissions: PermissionKey[];
}

export interface User {
  id: string;
  name: string;
  phone?: string;
  password?: string;
  roleIds: string[];
  status: "启用" | "停用";
  createdAt: string;
}

export interface AppData {
  users: User[];
  roles: Role[];
  organizations: Organization[];
  products: Product[];
  supplierPrices: SupplierPrice[];
  projects: Project[];
  projectItems: ProjectItem[];
  salesOrders: SalesOrder[];
  purchaseOrders: PurchaseOrder[];
  serviceOrders: ServiceOrder[];
  onboardingRecords: OnboardingRecord[];
  platformAccounts: PlatformAccount[];
  websiteLeads: WebsiteLead[];
  projectReminders: ProjectReminder[];
  projectMemos: ProjectMemo[];
  optionGroups: OptionGroup[];
  invoices: Invoice[];
  transactions: Transaction[];
  operationLogs: OperationLog[];
  ocrJobs: OcrJob[];
  trademarkCertificates: TrademarkCertificate[];
  notices: Notice[];
  noticeCollectionSources: NoticeCollectionSource[];
  noticeCollectionRuns: NoticeCollectionRun[];
  officialSites: OfficialSite[];
  officialPages: OfficialPage[];
}
