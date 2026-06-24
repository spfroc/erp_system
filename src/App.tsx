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
  Package,
  RefreshCw,
  Search,
  ShieldCheck,
  Trash2,
  UserPlus,
  Users,
} from "lucide-react";
import { createId, loadData, resetData, saveData } from "./db";
import type { AppData, EntityType, Organization, OrganizationRole, PermissionKey, Product, Project, ProjectStatus, SupplierPrice, User } from "./types";

type View = "dashboard" | "projects" | "entities" | "products" | "onboarding" | "finance" | "access";

const navItems: Array<{ id: View; label: string; icon: typeof Home }> = [
  { id: "dashboard", label: "总览", icon: Home },
  { id: "projects", label: "项目", icon: ClipboardList },
  { id: "entities", label: "实体", icon: Building2 },
  { id: "products", label: "商品", icon: Boxes },
  { id: "onboarding", label: "入驻服务", icon: ShieldCheck },
  { id: "finance", label: "发票流水", icon: Banknote },
  { id: "access", label: "用户权限", icon: Users },
];

const statusColumns: ProjectStatus[] = ["已付款待办理", "待采购/平台操作", "履约中", "待开票/待结算", "已完成", "异常"];
const entityTypes: EntityType[] = ["企业", "个体户", "政府", "事业单位", "学校", "医院", "其他"];
const orgRoles: OrganizationRole[] = ["客户", "供应商", "使用单位", "平台入驻客户"];
const permissionLabels: Record<PermissionKey, string> = {
  "dashboard.view": "查看总览",
  "project.view": "查看项目",
  "project.create": "新建项目",
  "project.edit": "编辑项目",
  "entity.view": "查看实体",
  "entity.create": "新建实体",
  "product.view": "查看商品",
  "product.manage": "管理商品",
  "purchase.manage": "管理采购履约",
  "finance.view": "查看财务",
  "finance.manage": "管理流水",
  "invoice.manage": "管理发票",
  "onboarding.manage": "管理入驻服务",
  "sensitive.view": "查看敏感信息",
  "profit.view": "查看利润",
  "user.manage": "管理用户权限",
};
const permissionGroups: Array<{ title: string; keys: PermissionKey[] }> = [
  { title: "基础", keys: ["dashboard.view", "project.view", "entity.view", "product.view"] },
  { title: "业务", keys: ["project.create", "project.edit", "entity.create", "product.manage", "purchase.manage", "onboarding.manage"] },
  { title: "财务", keys: ["finance.view", "finance.manage", "invoice.manage", "profit.view"] },
  { title: "安全", keys: ["sensitive.view", "user.manage"] },
];

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
            <input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="搜索项目、实体、商品" />
          </div>
        </header>

        {view === "dashboard" && <Dashboard data={data} onOpenProject={(id) => { setSelectedProjectId(id); setView("projects"); }} />}
        {view === "projects" && <Projects data={data} query={query} selectedProject={selectedProject} onSelectProject={setSelectedProjectId} />}
        {view === "entities" && <Entities data={data} commit={commit} query={query} />}
        {view === "products" && <Products data={data} commit={commit} />}
        {view === "onboarding" && <Onboarding data={data} />}
        {view === "finance" && <Finance data={data} />}
        {view === "access" && <AccessControl data={data} commit={commit} />}
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

function Entities({ data, commit, query }: { data: AppData; commit: (data: AppData) => Promise<void>; query: string }) {
  const [name, setName] = useState("");
  const [creditCode, setCreditCode] = useState("");
  const [legalPerson, setLegalPerson] = useState("");
  const [phone, setPhone] = useState("");
  const [entityType, setEntityType] = useState<EntityType>("企业");
  const [role, setRole] = useState<OrganizationRole>("客户");
  const [roleFilter, setRoleFilter] = useState<OrganizationRole | "全部">("全部");

  const filtered = data.organizations.filter((org) => {
    const matchesQuery = `${org.name}${org.unifiedCreditCode}${org.roles.join("")}`.includes(query);
    const matchesRole = roleFilter === "全部" || org.roles.includes(roleFilter);
    return matchesQuery && matchesRole;
  });

  function fillFromLicenseOcr() {
    setName("示例 OCR 科技有限公司");
    setCreditCode("91370000OCR001");
    setLegalPerson("李识别");
    setPhone("18600000000");
    setEntityType("企业");
    setRole("客户");
  }

  async function addOrganization() {
    if (!name.trim()) return;
    const duplicate = creditCode ? data.organizations.find((org) => org.unifiedCreditCode === creditCode) : undefined;
    if (duplicate) {
      const updated = data.organizations.map((org) =>
        org.id === duplicate.id
          ? {
              ...org,
              name: name || org.name,
              legalPerson: legalPerson || org.legalPerson,
              phone: phone || org.phone,
              roles: Array.from(new Set([...org.roles, role])) as OrganizationRole[],
            }
          : org,
      );
      await commit({ ...data, organizations: updated });
      setName("");
      setCreditCode("");
      setLegalPerson("");
      setPhone("");
      return;
    }
    const organization: Organization = {
      id: createId("org"),
      name,
      entityType,
      roles: [role],
      unifiedCreditCode: creditCode || undefined,
      legalPerson: legalPerson || undefined,
      phone: phone || undefined,
      status: "正常",
      createdAt: today(),
    };
    await commit({ ...data, organizations: [organization, ...data.organizations] });
    setName("");
    setCreditCode("");
    setLegalPerson("");
    setPhone("");
  }

  return (
    <div className="stack">
      <div className="panel">
        <PanelTitle title="快速添加实体" subtitle="实体是客户、供应商、使用单位等身份的统一基础资料；同一实体可拥有多个身份。" />
        <div className="form-grid entity-form">
          <input value={name} onChange={(event) => setName(event.target.value)} placeholder="单位名称" />
          <input value={creditCode} onChange={(event) => setCreditCode(event.target.value)} placeholder="营业执照编号/统一社会信用代码" />
          <input value={legalPerson} onChange={(event) => setLegalPerson(event.target.value)} placeholder="法人/负责人" />
          <input value={phone} onChange={(event) => setPhone(event.target.value)} placeholder="联系电话" />
          <select value={entityType} onChange={(event) => setEntityType(event.target.value as EntityType)}>
            {entityTypes.map((type) => <option key={type}>{type}</option>)}
          </select>
          <select value={role} onChange={(event) => setRole(event.target.value as OrganizationRole)}>
            {orgRoles.map((item) => <option key={item}>{item}</option>)}
          </select>
          <button className="ghost" onClick={fillFromLicenseOcr}><FileScan size={16} />营业执照 OCR</button>
          <button className="primary" onClick={addOrganization}><UserPlus size={16} />添加/合并身份</button>
        </div>
      </div>
      <div className="panel">
        <PanelTitle title="实体台账" subtitle="按身份查看客户、供应商、使用单位；无物理删除，只能停用或归档。" />
        <div className="segmented">
          {["全部", ...orgRoles].map((item) => (
            <button key={item} className={roleFilter === item ? "active" : ""} onClick={() => setRoleFilter(item as OrganizationRole | "全部")}>{item}</button>
          ))}
        </div>
        <div className="org-grid">
          {filtered.map((org) => (
            <article className="org-card" key={org.id}>
              <div>
                <strong>{org.name}</strong>
                <span>{org.entityType} · {org.status}</span>
              </div>
              <p>{org.unifiedCreditCode || "暂无统一社会信用代码"}</p>
              <p>{org.legalPerson || "暂无法人"} · {org.phone || "暂无电话"}</p>
              <div className="tags">{org.roles.map((item) => <em key={item}>{item}</em>)}</div>
              <button className="ghost" title="产品规则：不提供物理删除，仅支持停用、作废或归档。"><Trash2 size={15} />无物理删除</button>
            </article>
          ))}
        </div>
      </div>
    </div>
  );
}

function Products({ data, commit }: { data: AppData; commit: (data: AppData) => Promise<void> }) {
  const [form, setForm] = useState({
    code: "",
    name: "",
    category: "空调",
    capacity: "",
    energyLevel: "",
    shape: "",
    frameworkPrice: "",
    quotePrice: "",
    passThroughPrice: "",
    costPrice: "",
    platformCode: "",
    orderInfo: "",
  });
  const [supplierOrgId, setSupplierOrgId] = useState(data.organizations.find((org) => org.roles.includes("供应商"))?.id ?? "");
  const [supplierPrice, setSupplierPrice] = useState("");
  const suppliers = data.organizations.filter((org) => org.roles.includes("供应商"));

  async function addProduct() {
    if (!form.code.trim() || !form.name.trim()) return;
    const exists = data.products.some((product) => product.code === form.code);
    if (exists) return;
    const product: Product = {
      id: createId("prd"),
      code: form.code,
      name: form.name,
      kind: form.category === "平台入驻" ? "虚拟服务" : "实体商品",
      category: form.category,
      capacity: form.capacity || undefined,
      energyLevel: form.energyLevel || undefined,
      shape: form.shape || undefined,
      frameworkPrice: Number(form.frameworkPrice) || undefined,
      quotePrice: Number(form.quotePrice) || 0,
      passThroughPrice: Number(form.passThroughPrice) || undefined,
      costPrice: Number(form.costPrice) || 0,
      platformCode: form.platformCode || undefined,
      orderInfo: form.orderInfo || undefined,
    };
    const newSupplierPrice: SupplierPrice | null = supplierOrgId && supplierPrice
      ? { id: createId("sp"), productId: product.id, supplierOrgId, purchasePrice: Number(supplierPrice), note: "新建商品默认渠道" }
      : null;
    await commit({
      ...data,
      products: [product, ...data.products],
      supplierPrices: newSupplierPrice ? [newSupplierPrice, ...data.supplierPrices] : data.supplierPrices,
    });
    setForm({ code: "", name: "", category: "空调", capacity: "", energyLevel: "", shape: "", frameworkPrice: "", quotePrice: "", passThroughPrice: "", costPrice: "", platformCode: "", orderInfo: "" });
    setSupplierPrice("");
  }

  return (
    <div className="stack">
      <div className="panel">
        <PanelTitle title="新建商品" subtitle="字段参考价格体系表：商品编码唯一，价格体系和供应商进货价分开维护。" />
        <div className="product-form">
          <input value={form.code} onChange={(event) => setForm({ ...form, code: event.target.value })} placeholder="商品编码，如 25MDKT-001" />
          <input value={form.name} onChange={(event) => setForm({ ...form, name: event.target.value })} placeholder="商品名称/型号/品牌/规格" />
          <select value={form.category} onChange={(event) => setForm({ ...form, category: event.target.value })}>
            {["空调", "冰箱", "办公用品", "平台入驻"].map((item) => <option key={item}>{item}</option>)}
          </select>
          <input value={form.capacity} onChange={(event) => setForm({ ...form, capacity: event.target.value })} placeholder="匹数/规格" />
          <input value={form.energyLevel} onChange={(event) => setForm({ ...form, energyLevel: event.target.value })} placeholder="能效" />
          <input value={form.shape} onChange={(event) => setForm({ ...form, shape: event.target.value })} placeholder="形状/类型" />
          <input value={form.frameworkPrice} onChange={(event) => setForm({ ...form, frameworkPrice: event.target.value })} placeholder="框架批量价" />
          <input value={form.quotePrice} onChange={(event) => setForm({ ...form, quotePrice: event.target.value })} placeholder="报价" />
          <input value={form.passThroughPrice} onChange={(event) => setForm({ ...form, passThroughPrice: event.target.value })} placeholder="过单价" />
          <input value={form.costPrice} onChange={(event) => setForm({ ...form, costPrice: event.target.value })} placeholder="默认成本进价" />
          <input value={form.platformCode} onChange={(event) => setForm({ ...form, platformCode: event.target.value })} placeholder="美云销/平台编码" />
          <select value={supplierOrgId} onChange={(event) => setSupplierOrgId(event.target.value)}>
            <option value="">不绑定供应商</option>
            {suppliers.map((supplier) => <option value={supplier.id} key={supplier.id}>{supplier.name}</option>)}
          </select>
          <input value={supplierPrice} onChange={(event) => setSupplierPrice(event.target.value)} placeholder="供应商进货价" />
          <button className="primary" onClick={addProduct}><Package size={16} />新建商品</button>
          <textarea value={form.orderInfo} onChange={(event) => setForm({ ...form, orderInfo: event.target.value })} placeholder="下单信息/链接/备注" />
        </div>
      </div>
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
                  <p>{product.code} · {product.category} · {product.capacity || "无规格"} · {product.energyLevel || "无能效"}</p>
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

function AccessControl({ data, commit }: { data: AppData; commit: (data: AppData) => Promise<void> }) {
  const [name, setName] = useState("");
  const [phone, setPhone] = useState("");
  const [roleId, setRoleId] = useState(data.roles[0]?.id ?? "");

  async function addUser() {
    if (!name.trim() || !roleId) return;
    const user: User = {
      id: createId("user"),
      name,
      phone: phone || undefined,
      roleIds: [roleId],
      status: "启用",
      createdAt: today(),
    };
    await commit({ ...data, users: [user, ...data.users] });
    setName("");
    setPhone("");
  }

  async function toggleUser(userId: string) {
    await commit({
      ...data,
      users: data.users.map((user) => (user.id === userId ? { ...user, status: user.status === "启用" ? "停用" : "启用" } : user)),
    });
  }

  function roleNames(user: User) {
    return user.roleIds.map((id) => data.roles.find((role) => role.id === id)?.name).filter(Boolean).join("、");
  }

  return (
    <div className="stack">
      <div className="two-col access-layout">
        <div className="panel">
          <PanelTitle title="用户管理" subtitle="验证用户、角色和启停规则；不做物理删除。" />
          <div className="user-form">
            <input value={name} onChange={(event) => setName(event.target.value)} placeholder="姓名" />
            <input value={phone} onChange={(event) => setPhone(event.target.value)} placeholder="手机号" />
            <select value={roleId} onChange={(event) => setRoleId(event.target.value)}>
              {data.roles.map((role) => <option value={role.id} key={role.id}>{role.name}</option>)}
            </select>
            <button className="primary" onClick={addUser}><UserPlus size={16} />新增用户</button>
          </div>
          <div className="user-list">
            {data.users.map((user) => (
              <article className="user-card" key={user.id}>
                <div>
                  <strong>{user.name}</strong>
                  <span>{user.phone || "暂无手机号"} · {roleNames(user)}</span>
                </div>
                <em className={user.status === "启用" ? "status-on" : "status-off"}>{user.status}</em>
                <button className="ghost" onClick={() => toggleUser(user.id)}>{user.status === "启用" ? "停用" : "启用"}</button>
              </article>
            ))}
          </div>
        </div>
        <div className="panel">
          <PanelTitle title="角色说明" subtitle="小团队可一人多角色，系统按角色叠加权限。" />
          <div className="role-list">
            {data.roles.map((role) => (
              <article className="role-card" key={role.id}>
                <strong>{role.name}</strong>
                <p>{role.description}</p>
                <span>{role.permissions.length} 个权限点</span>
              </article>
            ))}
          </div>
        </div>
      </div>
      <div className="panel">
        <PanelTitle title="权限矩阵" subtitle="当前为产品验证矩阵，后续后端按相同权限点做接口鉴权。" />
        <div className="permission-table">
          <div className="permission-row permission-head">
            <span>权限点</span>
            {data.roles.map((role) => <strong key={role.id}>{role.name}</strong>)}
          </div>
          {permissionGroups.map((group) => (
            <div className="permission-group" key={group.title}>
              <div className="permission-section">{group.title}</div>
              {group.keys.map((key) => (
                <div className="permission-row" key={key}>
                  <span>{permissionLabels[key]}</span>
                  {data.roles.map((role) => (
                    <b key={role.id} className={role.permissions.includes(key) ? "allowed" : "denied"}>
                      {role.permissions.includes(key) ? "允许" : "无"}
                    </b>
                  ))}
                </div>
              ))}
            </div>
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
