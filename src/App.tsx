import { useEffect, useMemo, useState } from "react";
import {
  AlertTriangle,
  BadgeCheck,
  Banknote,
  Boxes,
  Building2,
  ClipboardList,
  FileScan,
  FileText,
  Home,
  PackagePlus,
  RefreshCw,
  Search,
  ShieldCheck,
  Trash2,
  UserPlus,
} from "lucide-react";
import { createId, loadData, resetData, saveData } from "./db";
import type { AppData, EntityType, Organization, OrganizationRole, Project, ProjectStatus } from "./types";

type View = "dashboard" | "projects" | "organizations" | "products" | "onboarding" | "finance" | "ocr";

const navItems: Array<{ id: View; label: string; icon: typeof Home }> = [
  { id: "dashboard", label: "总览", icon: Home },
  { id: "projects", label: "项目", icon: ClipboardList },
  { id: "organizations", label: "往来单位", icon: Building2 },
  { id: "products", label: "商品", icon: Boxes },
  { id: "onboarding", label: "入驻服务", icon: ShieldCheck },
  { id: "finance", label: "发票流水", icon: Banknote },
  { id: "ocr", label: "OCR", icon: FileScan },
];

const statusColumns: ProjectStatus[] = ["已付款待办理", "待采购/平台操作", "履约中", "待开票/待结算", "已完成", "异常"];
const entityTypes: EntityType[] = ["企业", "个体户", "政府", "事业单位", "学校", "医院", "其他"];
const orgRoles: OrganizationRole[] = ["客户", "供应商", "使用单位", "平台入驻客户"];

function money(value: number) {
  return new Intl.NumberFormat("zh-CN", { style: "currency", currency: "CNY", maximumFractionDigits: 0 }).format(value);
}

function today() {
  return new Date().toISOString();
}

export default function App() {
  const [data, setData] = useState<AppData | null>(null);
  const [view, setView] = useState<View>("dashboard");
  const [selectedProjectId, setSelectedProjectId] = useState<string | null>(null);
  const [query, setQuery] = useState("");

  useEffect(() => {
    loadData().then(setData);
  }, []);

  async function commit(next: AppData) {
    setData(next);
    await saveData(next);
  }

  if (!data) {
    return <div className="loading">正在加载本地演示数据...</div>;
  }

  const selectedProject = data.projects.find((project) => project.id === selectedProjectId) ?? data.projects[0];

  return (
    <div className="shell">
      <aside className="sidebar">
        <div className="brand">
          <div className="brand-mark">壹</div>
          <div>
            <strong>壹采 ERP</strong>
            <span>产品验证版</span>
          </div>
        </div>
        <nav>
          {navItems.map((item) => {
            const Icon = item.icon;
            return (
              <button key={item.id} className={view === item.id ? "active" : ""} onClick={() => setView(item.id)}>
                <Icon size={18} />
                {item.label}
              </button>
            );
          })}
        </nav>
        <div className="sidebar-note">
          <DatabaseHint />
          <button
            className="ghost danger"
            onClick={async () => {
              const next = await resetData();
              setData(next);
              setSelectedProjectId(null);
            }}
            title="重置浏览器本地 IndexedDB 演示数据"
          >
            <RefreshCw size={16} />
            重置演示数据
          </button>
        </div>
      </aside>

      <main className="main">
        <header className="topbar">
          <div>
            <h1>{navItems.find((item) => item.id === view)?.label}</h1>
            <p>浏览器本地数据库版本，用于验证流程、页面和字段设计。</p>
          </div>
          <div className="search">
            <Search size={18} />
            <input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="搜索项目、客户、商品" />
          </div>
        </header>

        {view === "dashboard" && <Dashboard data={data} onOpenProject={(id) => { setSelectedProjectId(id); setView("projects"); }} />}
        {view === "projects" && <Projects data={data} query={query} selectedProject={selectedProject} onSelectProject={setSelectedProjectId} />}
        {view === "organizations" && <Organizations data={data} commit={commit} query={query} />}
        {view === "products" && <Products data={data} />}
        {view === "onboarding" && <Onboarding data={data} />}
        {view === "finance" && <Finance data={data} />}
        {view === "ocr" && <Ocr data={data} commit={commit} />}
      </main>
    </div>
  );
}

function DatabaseHint() {
  return (
    <div className="db-hint">
      <ShieldCheck size={16} />
      <span>数据保存在当前浏览器 IndexedDB，不上传服务器。</span>
    </div>
  );
}

function Dashboard({ data, onOpenProject }: { data: AppData; onOpenProject: (id: string) => void }) {
  const metrics = useMemo(() => {
    const revenue = data.projects.reduce((sum, project) => sum + project.totalAmount, 0);
    const cost = data.projects.reduce((sum, project) => sum + project.totalCost, 0);
    const unpaidInvoice = data.invoices.filter((invoice) => invoice.status !== "已开" && invoice.status !== "已收").reduce((sum, invoice) => sum + invoice.amount, 0);
    return {
      active: data.projects.filter((project) => project.status !== "已完成").length,
      exception: data.projects.filter((project) => project.status === "异常").length,
      revenue,
      profit: revenue - cost,
      unpaidInvoice,
      onboarding: data.onboardingRecords.filter((record) => record.step !== "已完成").length,
    };
  }, [data]);

  return (
    <section className="stack">
      <div className="metric-grid">
        <Metric label="进行中项目" value={metrics.active.toString()} icon={ClipboardList} />
        <Metric label="异常项目" value={metrics.exception.toString()} icon={AlertTriangle} tone="warn" />
        <Metric label="销售金额" value={money(metrics.revenue)} icon={Banknote} />
        <Metric label="项目毛利" value={money(metrics.profit)} icon={BadgeCheck} />
        <Metric label="待开票金额" value={money(metrics.unpaidInvoice)} icon={FileText} />
        <Metric label="入驻待办" value={metrics.onboarding.toString()} icon={ShieldCheck} />
      </div>

      <div className="two-col">
        <div className="panel">
          <PanelTitle title="项目进度看板" subtitle="按当前状态聚合项目，点击卡片进入详情。" />
          <div className="kanban">
            {statusColumns.map((status) => (
              <div className="kanban-col" key={status}>
                <div className="kanban-head">
                  <span>{status}</span>
                  <b>{data.projects.filter((project) => project.status === status).length}</b>
                </div>
                {data.projects
                  .filter((project) => project.status === status)
                  .map((project) => (
                    <button className="project-card" key={project.id} onClick={() => onOpenProject(project.id)}>
                      <strong>{project.name}</strong>
                      <span>{project.projectNo}</span>
                      <em>{project.currentBlocker || "节点正常"}</em>
                    </button>
                  ))}
              </div>
            ))}
          </div>
        </div>
        <div className="panel">
          <PanelTitle title="今日待办" subtitle="产品验证版按规则自动生成示例待办。" />
          <TodoList data={data} />
        </div>
      </div>
    </section>
  );
}

function Metric({ label, value, icon: Icon, tone }: { label: string; value: string; icon: typeof Home; tone?: "warn" }) {
  return (
    <div className={`metric ${tone ?? ""}`}>
      <Icon size={20} />
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  );
}

function TodoList({ data }: { data: AppData }) {
  const todos = [
    ...data.projects.filter((project) => project.contractStatus === "待签").map((project) => ({ title: "合同待签", detail: project.name, owner: project.owner })),
    ...data.projects.filter((project) => project.invoiceStatus === "未开").map((project) => ({ title: "销售发票未开", detail: project.name, owner: "财务" })),
    ...data.onboardingRecords.filter((record) => record.step !== "已完成").map((record) => ({ title: record.step, detail: data.organizations.find((org) => org.id === record.customerOrgId)?.name ?? "入驻客户", owner: record.salesOwner })),
  ].slice(0, 8);

  return (
    <div className="todo-list">
      {todos.map((todo, index) => (
        <div className="todo" key={`${todo.title}-${index}`}>
          <span>{todo.title}</span>
          <strong>{todo.detail}</strong>
          <em>{todo.owner}</em>
        </div>
      ))}
    </div>
  );
}

function Projects({
  data,
  query,
  selectedProject,
  onSelectProject,
}: {
  data: AppData;
  query: string;
  selectedProject: Project;
  onSelectProject: (id: string) => void;
}) {
  const filtered = data.projects.filter((project) => JSON.stringify(project).includes(query));
  const customer = data.organizations.find((org) => org.id === selectedProject.customerOrgId);
  const usageUnit = data.organizations.find((org) => org.id === selectedProject.usageUnitOrgId);
  const items = data.projectItems.filter((item) => item.projectId === selectedProject.id);
  const onboarding = data.onboardingRecords.find((record) => record.projectId === selectedProject.id);

  return (
    <div className="split">
      <div className="panel list-panel">
        <PanelTitle title="项目列表" subtitle="项目汇总客户、商品、发票、负责人和流程。" />
        {filtered.map((project) => (
          <button key={project.id} className={`row-card ${selectedProject.id === project.id ? "selected" : ""}`} onClick={() => onSelectProject(project.id)}>
            <span>{project.projectNo}</span>
            <strong>{project.name}</strong>
            <em>{project.status}</em>
          </button>
        ))}
      </div>
      <div className="panel detail-panel">
        <div className="detail-head">
          <div>
            <span className="tag">{selectedProject.type}</span>
            <h2>{selectedProject.name}</h2>
            <p>{selectedProject.projectNo} · {selectedProject.owner} · {selectedProject.sourcePlatform || "无平台"}</p>
          </div>
          <strong className="amount">{money(selectedProject.totalAmount)}</strong>
        </div>
        <div className="progress-line">
          {["合同", "收款", "采购/平台", "交付", "开票", "结算"].map((step, index) => (
            <div key={step} className={index < 3 ? "done" : ""}>{step}</div>
          ))}
        </div>
        <div className="info-grid">
          <Info label="客户" value={customer?.name} />
          <Info label="使用单位" value={usageUnit?.name ?? "无"} />
          <Info label="合同状态" value={selectedProject.contractStatus} />
          <Info label="收款状态" value={selectedProject.paymentStatus} />
          <Info label="采购状态" value={selectedProject.purchaseStatus} />
          <Info label="开票状态" value={selectedProject.invoiceStatus} />
          <Info label="毛利" value={money(selectedProject.totalAmount - selectedProject.totalCost)} />
          <Info label="当前阻塞" value={selectedProject.currentBlocker ?? "无"} />
        </div>
        <h3>商品/服务明细</h3>
        <div className="table">
          <div className="table-row head"><span>名称</span><span>数量</span><span>销售价</span><span>成本</span></div>
          {items.map((item) => (
            <div className="table-row" key={item.id}>
              <span>{item.productName}</span>
              <span>{item.quantity}</span>
              <span>{money(item.actualPrice)}</span>
              <span>{money(item.costPrice)}</span>
            </div>
          ))}
        </div>
        {onboarding && (
          <>
            <h3>平台入驻</h3>
            <div className="info-grid">
              <Info label="平台" value={onboarding.platform} />
              <Info label="步骤" value={onboarding.step} />
              <Info label="营业执照编号" value={onboarding.businessLicenseNo} />
              <Info label="域名" value={onboarding.domain ?? "未录入"} />
              <Info label="亮照" value={onboarding.licenseDisplayStatus} />
              <Info label="公安备案" value={onboarding.publicSecurityStatus} />
            </div>
          </>
        )}
      </div>
    </div>
  );
}

function Organizations({ data, commit, query }: { data: AppData; commit: (data: AppData) => Promise<void>; query: string }) {
  const [name, setName] = useState("");
  const [creditCode, setCreditCode] = useState("");
  const [entityType, setEntityType] = useState<EntityType>("企业");
  const [role, setRole] = useState<OrganizationRole>("客户");

  const filtered = data.organizations.filter((org) => `${org.name}${org.unifiedCreditCode}${org.roles.join("")}`.includes(query));

  async function addOrganization() {
    if (!name.trim()) return;
    const duplicate = creditCode ? data.organizations.find((org) => org.unifiedCreditCode === creditCode) : undefined;
    if (duplicate) {
      const updated = data.organizations.map((org) =>
        org.id === duplicate.id ? { ...org, roles: Array.from(new Set([...org.roles, role])) as OrganizationRole[] } : org,
      );
      await commit({ ...data, organizations: updated });
      setName("");
      setCreditCode("");
      return;
    }
    const organization: Organization = {
      id: createId("org"),
      name,
      entityType,
      roles: [role],
      unifiedCreditCode: creditCode || undefined,
      status: "正常",
      createdAt: today(),
    };
    await commit({ ...data, organizations: [organization, ...data.organizations] });
    setName("");
    setCreditCode("");
  }

  return (
    <div className="stack">
      <div className="panel">
        <PanelTitle title="快速添加往来单位" subtitle="客户、供应商、使用单位共用一个实体，营业执照编号用于企业去重。" />
        <div className="form-grid">
          <input value={name} onChange={(event) => setName(event.target.value)} placeholder="单位名称" />
          <input value={creditCode} onChange={(event) => setCreditCode(event.target.value)} placeholder="营业执照编号/统一社会信用代码" />
          <select value={entityType} onChange={(event) => setEntityType(event.target.value as EntityType)}>
            {entityTypes.map((type) => <option key={type}>{type}</option>)}
          </select>
          <select value={role} onChange={(event) => setRole(event.target.value as OrganizationRole)}>
            {orgRoles.map((item) => <option key={item}>{item}</option>)}
          </select>
          <button className="primary" onClick={addOrganization}><UserPlus size={16} />添加/合并身份</button>
        </div>
      </div>
      <div className="panel">
        <PanelTitle title="往来单位台账" subtitle="无删除功能；验证版展示停用/归档规则入口。" />
        <div className="org-grid">
          {filtered.map((org) => (
            <article className="org-card" key={org.id}>
              <div>
                <strong>{org.name}</strong>
                <span>{org.entityType} · {org.status}</span>
              </div>
              <p>{org.unifiedCreditCode || "暂无统一社会信用代码"}</p>
              <div className="tags">{org.roles.map((item) => <em key={item}>{item}</em>)}</div>
              <button className="ghost" title="产品规则：不提供物理删除，仅支持停用、作废或归档。"><Trash2 size={15} />无物理删除</button>
            </article>
          ))}
        </div>
      </div>
    </div>
  );
}

function Products({ data }: { data: AppData }) {
  return (
    <div className="stack">
      <div className="panel">
        <PanelTitle title="商品与供应商价格" subtitle="商品编码唯一，同一商品可维护多个进货渠道。" />
        <div className="product-list">
          {data.products.map((product) => {
            const prices = data.supplierPrices.filter((price) => price.productId === product.id);
            return (
              <article className="product-card" key={product.id}>
                <div>
                  <span className="tag">{product.kind}</span>
                  <h3>{product.name}</h3>
                  <p>{product.code} · {product.category}</p>
                </div>
                <strong>{money(product.quotePrice)}</strong>
                <div className="supplier-prices">
                  {prices.length === 0 && <span>无采购渠道</span>}
                  {prices.map((price) => {
                    const supplier = data.organizations.find((org) => org.id === price.supplierOrgId);
                    return <span key={price.id}>{supplier?.name}: {money(price.purchasePrice)}</span>;
                  })}
                </div>
              </article>
            );
          })}
        </div>
      </div>
    </div>
  );
}

function Onboarding({ data }: { data: AppData }) {
  return (
    <div className="panel">
      <PanelTitle title="平台入驻服务" subtitle="政采客户付款后启动；泉E采/青慧采共用流程模板。" />
      <div className="onboarding-list">
        {data.onboardingRecords.map((record) => {
          const customer = data.organizations.find((org) => org.id === record.customerOrgId);
          return (
            <article className="onboarding-card" key={record.id}>
              <div className="onboarding-top">
                <div>
                  <span className="tag">{record.platform}</span>
                  <h3>{customer?.name}</h3>
                  <p>{record.note || "无备注"}</p>
                </div>
                <strong>{record.step}</strong>
              </div>
              <div className="flow">
                {["营业执照", "账号注册", "域名备案", "亮照", "公安备案", "后台录入", "CA办理", "审核"].map((step, index) => (
                  <span key={step} className={index < 3 ? "done" : ""}>{step}</span>
                ))}
              </div>
              <div className="info-grid compact">
                <Info label="营业执照" value={record.businessLicenseNo} />
                <Info label="齐鲁云采账号" value={record.qiluAccount ? mask(record.qiluAccount) : "未录入"} />
                <Info label="供应商账号" value={record.supplierAccount ? mask(record.supplierAccount) : "未录入"} />
                <Info label="域名" value={record.domain ?? "未录入"} />
                <Info label="CA" value={record.caStatus} />
                <Info label="服务年限" value={`${record.serviceYears} 年`} />
              </div>
            </article>
          );
        })}
      </div>
    </div>
  );
}

function Finance({ data }: { data: AppData }) {
  return (
    <div className="two-col">
      <div className="panel">
        <PanelTitle title="发票台账" subtitle="OCR 识别后生成待确认发票草稿。" />
        <div className="table">
          <div className="table-row head"><span>项目</span><span>类型</span><span>金额</span><span>状态</span></div>
          {data.invoices.map((invoice) => {
            const project = data.projects.find((item) => item.id === invoice.projectId);
            return <div className="table-row" key={invoice.id}><span>{project?.name}</span><span>{invoice.type}</span><span>{money(invoice.amount)}</span><span>{invoice.status}</span></div>;
          })}
        </div>
      </div>
      <div className="panel">
        <PanelTitle title="交易流水" subtitle="收款、付款、垫付和后返统一关联项目。" />
        <div className="table">
          <div className="table-row head"><span>项目</span><span>类型</span><span>金额</span><span>状态</span></div>
          {data.transactions.map((tx) => {
            const project = data.projects.find((item) => item.id === tx.projectId);
            return <div className="table-row" key={tx.id}><span>{project?.name}</span><span>{tx.type}</span><span>{money(tx.amount)}</span><span>{tx.status}</span></div>;
          })}
        </div>
      </div>
    </div>
  );
}

function Ocr({ data, commit }: { data: AppData; commit: (data: AppData) => Promise<void> }) {
  async function confirmJob(id: string) {
    const job = data.ocrJobs.find((item) => item.id === id);
    if (!job) return;
    const code = job.result["统一社会信用代码"];
    const exists = data.organizations.some((org) => org.unifiedCreditCode === code);
    const organizations = exists
      ? data.organizations
      : [
          {
            id: createId("org"),
            name: job.result["企业名称"] || "OCR识别客户",
            entityType: "企业" as const,
            roles: ["客户", "平台入驻客户"] as OrganizationRole[],
            unifiedCreditCode: code,
            legalPerson: job.result["法定代表人"],
            status: "正常" as const,
            createdAt: today(),
          },
          ...data.organizations,
        ];
    await commit({
      ...data,
      organizations,
      ocrJobs: data.ocrJobs.map((item) => (item.id === id ? { ...item, status: "已确认" } : item)),
    });
  }

  return (
    <div className="stack">
      <div className="panel">
        <PanelTitle title="OCR 工作台" subtitle="独立 Python 容器提供接口；前端验证版模拟识别结果确认和落库。" />
        <div className="api-box">
          <code>POST /ocr/business-license</code>
          <code>POST /ocr/invoice</code>
          <span>识别结果先进入待确认，员工确认后写入组织实体或发票台账。</span>
        </div>
      </div>
      <div className="panel">
        <PanelTitle title="待确认识别结果" subtitle="营业执照编号用于企业客户唯一去重。" />
        <div className="ocr-list">
          {data.ocrJobs.map((job) => (
            <article className="ocr-card" key={job.id}>
              <div>
                <span className="tag">{job.type}</span>
                <h3>{job.fileName}</h3>
                <p>{Object.entries(job.result).map(([key, value]) => `${key}: ${value}`).join(" / ")}</p>
              </div>
              <button className="primary" disabled={job.status === "已确认"} onClick={() => confirmJob(job.id)}>
                <PackagePlus size={16} />
                {job.status === "已确认" ? "已落库" : "确认落库"}
              </button>
            </article>
          ))}
        </div>
      </div>
    </div>
  );
}

function PanelTitle({ title, subtitle }: { title: string; subtitle: string }) {
  return (
    <div className="panel-title">
      <div>
        <h2>{title}</h2>
        <p>{subtitle}</p>
      </div>
    </div>
  );
}

function Info({ label, value }: { label: string; value?: string | number }) {
  return (
    <div className="info">
      <span>{label}</span>
      <strong>{value || "未录入"}</strong>
    </div>
  );
}

function mask(value: string) {
  if (value.length <= 4) return "****";
  return `${value.slice(0, 2)}***${value.slice(-2)}`;
}
