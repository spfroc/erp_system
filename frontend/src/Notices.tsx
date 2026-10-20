import { useCallback, useEffect, useState } from "react";
import { FileText, RefreshCw, X } from "lucide-react";
import { backendApiUrl } from "./apiConfig";
import { AuthExpiredError } from "./db";

export type NoticeListItem = {
  id: number;
  siteId: string;
  siteLabel: string;
  noticeKey: string;
  title?: string | null;
  projectCode?: string | null;
  projectName?: string | null;
  buyerName?: string | null;
  dealSupplier?: string | null;
  dealAmount?: number | null;
  budgetAmount?: number | null;
  noticeKind?: string | null;
  procurementMode?: string | null;
  regionName?: string | null;
  publishTime?: string | null;
  startTime?: string | null;
  endTime?: string | null;
  progressStatus?: "ongoing" | "upcoming" | "ended" | "unknown" | string | null;
  progressLabel?: string | null;
  crawlStatus?: string | null;
  parseStatus?: string | null;
  sourceUrl?: string | null;
  crawledAt?: string | null;
};

export type NoticeGoodsItem = {
  id: number;
  lineNo: number;
  productName?: string | null;
  category?: string | null;
  quantity?: number | null;
  unit?: string | null;
  brand?: string | null;
  model?: string | null;
  unitPrice?: number | null;
  spec?: string | null;
  amount?: number | null;
};

export type NoticeDetail = NoticeListItem & {
  buyerContactName?: string | null;
  buyerPhone?: string | null;
  buyerAddress?: string | null;
  buyerContact?: string | null;
  dealSupplierPhone?: string | null;
  dealSupplierAddress?: string | null;
  deliveryAddress?: string | null;
  quoteCount?: number | null;
  quotes?: unknown;
  suppliers?: unknown;
  modelName?: string | null;
  confidence?: number | null;
  contentText?: string | null;
  goods?: NoticeGoodsItem[];
};

type SiteOption = { id: string; label: string };

type NoticeListResponse = {
  items: NoticeListItem[];
  total: number;
  page: number;
  pageSize: number;
  sites?: SiteOption[];
  noticeKinds?: string[];
  detail?: string;
};

function money(value: number | null | undefined) {
  if (value == null || Number.isNaN(value)) return "—";
  return new Intl.NumberFormat("zh-CN", {
    style: "currency",
    currency: "CNY",
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(value);
}

function text(value: string | number | null | undefined) {
  if (value == null || value === "") return "—";
  return String(value);
}

async function fetchNotices(params: URLSearchParams): Promise<NoticeListResponse> {
  const response = await fetch(backendApiUrl(`/api/notices/?${params.toString()}`), {
    credentials: "include",
  });
  if (response.status === 401) throw new AuthExpiredError();
  const data = (await response.json()) as NoticeListResponse;
  if (!response.ok && response.status !== 503) {
    throw new Error(data.detail || "加载公告失败");
  }
  return data;
}

async function fetchNoticeDetail(id: number): Promise<NoticeDetail> {
  const response = await fetch(backendApiUrl(`/api/notices/${id}/`), {
    credentials: "include",
  });
  if (response.status === 401) throw new AuthExpiredError();
  const data = await response.json();
  if (!response.ok) {
    throw new Error(data.detail || "加载公告详情失败");
  }
  return data as NoticeDetail;
}

export function Notices({
  onNotice,
}: {
  onNotice: (notice: { type: "success" | "error"; message: string }) => void;
}) {
  const [search, setSearch] = useState("");
  const [projectCode, setProjectCode] = useState("");
  const [projectName, setProjectName] = useState("");
  const [buyerName, setBuyerName] = useState("");
  const [supplierName, setSupplierName] = useState("");
  const [goodsName, setGoodsName] = useState("");
  const [siteId, setSiteId] = useState("");
  const [noticeKind, setNoticeKind] = useState("");
  const [parseStatus, setParseStatus] = useState("");
  const [progress, setProgress] = useState("");
  const [page, setPage] = useState(1);
  const [pageSize] = useState(15);
  const [total, setTotal] = useState(0);
  const [items, setItems] = useState<NoticeListItem[]>([]);
  const [sites, setSites] = useState<SiteOption[]>([]);
  const [noticeKinds, setNoticeKinds] = useState<string[]>([]);
  const [loading, setLoading] = useState(false);
  const [detail, setDetail] = useState<NoticeDetail | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const params = new URLSearchParams({
        page: String(page),
        pageSize: String(pageSize),
      });
      if (search.trim()) params.set("search", search.trim());
      if (projectCode.trim()) params.set("projectCode", projectCode.trim());
      if (projectName.trim()) params.set("projectName", projectName.trim());
      if (buyerName.trim()) params.set("buyerName", buyerName.trim());
      if (supplierName.trim()) params.set("supplierName", supplierName.trim());
      if (goodsName.trim()) params.set("goodsName", goodsName.trim());
      if (siteId) params.set("siteId", siteId);
      if (noticeKind) params.set("noticeKind", noticeKind);
      if (parseStatus) params.set("parseStatus", parseStatus);
      if (progress) params.set("progress", progress);
      const data = await fetchNotices(params);
      setItems(data.items || []);
      setTotal(data.total || 0);
      if (data.sites?.length) setSites(data.sites);
      const kinds = data.noticeKinds || [];
      setNoticeKinds(kinds);
      // 切换站点后，当前类型若不在该站选项里则清空，避免筛空
      if (noticeKind && kinds.length > 0 && !kinds.includes(noticeKind)) {
        setNoticeKind("");
      } else if (noticeKind && kinds.length === 0) {
        setNoticeKind("");
      }
      if (data.detail && data.total === 0) {
        onNotice({ type: "error", message: data.detail });
      }
    } catch (error) {
      if (error instanceof AuthExpiredError) return;
      onNotice({ type: "error", message: error instanceof Error ? error.message : "加载失败" });
    } finally {
      setLoading(false);
    }
  }, [
    buyerName,
    goodsName,
    noticeKind,
    onNotice,
    page,
    pageSize,
    parseStatus,
    progress,
    projectCode,
    projectName,
    search,
    siteId,
    supplierName,
  ]);

  useEffect(() => {
    void load();
  }, [load]);

  async function openDetail(id: number) {
    setDetailLoading(true);
    try {
      const data = await fetchNoticeDetail(id);
      setDetail(data);
    } catch (error) {
      if (error instanceof AuthExpiredError) return;
      onNotice({ type: "error", message: error instanceof Error ? error.message : "加载详情失败" });
    } finally {
      setDetailLoading(false);
    }
  }

  const totalPages = Math.max(1, Math.ceil(total / pageSize));

  return (
    <div className="stack">
      <div className="panel">
        <div className="panel-title action-title">
          <div>
            <h2>公告管理</h2>
            <p>展示抓取并解析后的政府采购公告，可按项目编号、项目名称、采购单位、供应商和商品名称筛选。</p>
          </div>
          <button className="ghost" onClick={() => void load()} disabled={loading}>
            <RefreshCw size={16} />
            刷新
          </button>
        </div>
        <div className="segmented">
          {[
            { id: "", label: "全部" },
            { id: "ongoing", label: "进行中" },
            { id: "upcoming", label: "未开始" },
            { id: "ended", label: "已截止" },
          ].map((item) => (
            <button
              key={item.id || "all"}
              className={progress === item.id ? "active" : ""}
              onClick={() => {
                setPage(1);
                setProgress(item.id);
              }}
            >
              {item.label}
            </button>
          ))}
        </div>
        <div className="orders-toolbar">
          <input
            value={search}
            onChange={(event) => {
              setPage(1);
              setSearch(event.target.value);
            }}
            placeholder="搜索标题、项目编号、采购单位、供应商"
          />
          <select
            className="toolbar-select"
            value={siteId}
            onChange={(event) => {
              setPage(1);
              setNoticeKind("");
              setSiteId(event.target.value);
            }}
          >
            <option value="">全部站点</option>
            {sites.map((site) => (
              <option key={site.id} value={site.id}>
                {site.label}
              </option>
            ))}
          </select>
          <select
            className="toolbar-select"
            value={noticeKind}
            onChange={(event) => {
              setPage(1);
              setNoticeKind(event.target.value);
            }}
          >
            <option value="">全部公告类型</option>
            {noticeKinds.map((kind) => (
              <option key={kind} value={kind}>
                {kind}
              </option>
            ))}
          </select>
          <select
            className="toolbar-select"
            value={parseStatus}
            onChange={(event) => {
              setPage(1);
              setParseStatus(event.target.value);
            }}
          >
            <option value="">全部解析状态</option>
            <option value="pending">待解析</option>
            <option value="parsed">已解析</option>
            <option value="parse_fail">解析失败</option>
            <option value="skipped">已跳过</option>
          </select>
        </div>
        <div className="orders-toolbar notice-field-filters">
          <div className="orders-toolbar-main">
            <label className="orders-filter-field">
              <span>项目编号</span>
              <input
                value={projectCode}
                onChange={(event) => {
                  setPage(1);
                  setProjectCode(event.target.value);
                }}
                placeholder="项目编号"
              />
            </label>
            <label className="orders-filter-field">
              <span>项目名称</span>
              <input
                value={projectName}
                onChange={(event) => {
                  setPage(1);
                  setProjectName(event.target.value);
                }}
                placeholder="项目名称"
              />
            </label>
            <label className="orders-filter-field">
              <span>采购单位</span>
              <input
                value={buyerName}
                onChange={(event) => {
                  setPage(1);
                  setBuyerName(event.target.value);
                }}
                placeholder="采购单位"
              />
            </label>
            <label className="orders-filter-field">
              <span>供应商名称</span>
              <input
                value={supplierName}
                onChange={(event) => {
                  setPage(1);
                  setSupplierName(event.target.value);
                }}
                placeholder="供应商名称"
              />
            </label>
            <label className="orders-filter-field">
              <span>商品名称</span>
              <input
                value={goodsName}
                onChange={(event) => {
                  setPage(1);
                  setGoodsName(event.target.value);
                }}
                placeholder="商品名称"
              />
            </label>
          </div>
        </div>
        <div className="table">
          <div className="table-row notice-table head">
            <span>标题/编号</span>
            <span>站点</span>
            <span>采购单位</span>
            <span>成交供应商</span>
            <span>金额</span>
            <span>种类/方式</span>
            <span>时间</span>
            <span>进度/解析</span>
            <span>操作</span>
          </div>
          {loading && items.length === 0 && (
            <div className="empty-hint">加载中…</div>
          )}
          {!loading && items.length === 0 && (
            <div className="empty-hint">暂无公告数据，请先运行 notice_crawler 抓取。</div>
          )}
          {items.map((item) => (
            <div className="table-row notice-table" key={item.id}>
              <span>
                <strong>{text(item.title)}</strong>
                <em>{text(item.projectCode || item.noticeKey)}</em>
              </span>
              <span>{text(item.siteLabel)}</span>
              <span>{text(item.buyerName)}</span>
              <span>{text(item.dealSupplier)}</span>
              <span>
                <strong>{money(item.dealAmount)}</strong>
                <em>预算 {money(item.budgetAmount)}</em>
              </span>
              <span>
                {text(item.noticeKind)}
                <em>{text(item.procurementMode)}</em>
              </span>
              <span className="notice-times">
                <em>采集 {text(item.crawledAt)}</em>
                <em>发布 {text(item.publishTime)}</em>
                <em>报价开始 {text(item.startTime)}</em>
                <em>结束 {text(item.endTime)}</em>
              </span>
              <span>
                <strong className={`notice-progress notice-progress-${item.progressStatus || "unknown"}`}>
                  {text(item.progressLabel || "未知")}
                </strong>
                <em>{text(item.parseStatus)}</em>
              </span>
              <span>
                <button className="copy-link" onClick={() => void openDetail(item.id)} disabled={detailLoading}>
                  <FileText size={14} />
                  详情
                </button>
              </span>
            </div>
          ))}
        </div>
        <div className="pager">
          <button className="ghost" disabled={page <= 1 || loading} onClick={() => setPage((p) => p - 1)}>
            上一页
          </button>
          <span>
            第 {page} / {totalPages} 页 · 共 {total} 条
          </span>
          <button
            className="ghost"
            disabled={page >= totalPages || loading}
            onClick={() => setPage((p) => p + 1)}
          >
            下一页
          </button>
        </div>
      </div>

      {detail && (
        <div className="modal-backdrop" role="presentation" onClick={() => setDetail(null)}>
          <div
            className="modal notice-detail-modal"
            role="dialog"
            aria-modal="true"
            aria-label="公告详情"
            onClick={(event) => event.stopPropagation()}
          >
            <div className="modal-head">
              <div>
                <h2>{text(detail.title)}</h2>
                <p>
                  {text(detail.siteLabel)} · {text(detail.projectCode || detail.noticeKey)}
                </p>
              </div>
              <button className="icon-button" onClick={() => setDetail(null)} aria-label="关闭">
                <X size={18} />
              </button>
            </div>
            <div className="info-grid">
              <Info label="项目名称" value={detail.projectName} />
              <Info label="采购单位" value={detail.buyerName} />
              <Info label="项目联系人" value={detail.buyerContactName} />
              <Info label="联系电话" value={detail.buyerPhone} />
              <Info label="项目地址" value={detail.buyerAddress} />
              <Info label="成交供应商" value={detail.dealSupplier} />
              <Info label="供应商电话" value={detail.dealSupplierPhone} />
              <Info label="供应商地址" value={detail.dealSupplierAddress} />
              <Info label="预算金额" value={money(detail.budgetAmount)} />
              <Info label="成交金额" value={money(detail.dealAmount)} />
              <Info label="公告种类" value={detail.noticeKind} />
              <Info label="采购方式" value={detail.procurementMode} />
              <Info label="区域" value={detail.regionName} />
              <Info label="交货地点" value={detail.deliveryAddress} />
              <Info label="采集时间" value={detail.crawledAt} />
              <Info label="公告发布时间" value={detail.publishTime} />
              <Info label="报价开始时间" value={detail.startTime} />
              <Info label="结束时间" value={detail.endTime} />
              <Info label="解析状态" value={detail.parseStatus} />
            </div>

            <h4>产品明细</h4>
            <div className="table">
              <div className="table-row notice-goods-table head">
                <span>#</span>
                <span>产品</span>
                <span>分类</span>
                <span>品牌/型号</span>
                <span>数量</span>
                <span>单价</span>
                <span>参数</span>
                <span>小计</span>
              </div>
              {(detail.goods || []).length === 0 && <div className="empty-hint">暂无产品明细</div>}
              {(detail.goods || []).map((g) => (
                <div className="table-row notice-goods-table" key={g.id}>
                  <span>{g.lineNo}</span>
                  <span>{text(g.productName)}</span>
                  <span>{text(g.category)}</span>
                  <span>
                    {text(g.brand)}
                    <em>{text(g.model)}</em>
                  </span>
                  <span>
                    {text(g.quantity)}
                    {g.unit ? ` ${g.unit}` : ""}
                  </span>
                  <span>{money(g.unitPrice)}</span>
                  <span className="wrap">{text(g.spec)}</span>
                  <span>{money(g.amount)}</span>
                </div>
              ))}
            </div>

            {detail.contentText && (
              <>
                <h4>正文摘要</h4>
                <pre className="notice-content">{detail.contentText.slice(0, 4000)}</pre>
              </>
            )}
            {detail.sourceUrl && (
              <p className="notice-source">
                来源：{" "}
                <a href={detail.sourceUrl} target="_blank" rel="noreferrer">
                  {detail.sourceUrl}
                </a>
              </p>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

function Info({ label, value }: { label: string; value?: string | number | null }) {
  return (
    <div className="info">
      <span>{label}</span>
      <strong>{text(value)}</strong>
    </div>
  );
}
