import { X } from "lucide-react";
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
  siblingKinds?: string[];
  projectNoticeKinds?: string[];
  tagOrgType?: string | null;
  tagNature?: string | null;
  tagDealKind?: string | null;
  tagProvince?: string | null;
  tagCity?: string | null;
  tagDistrict?: string | null;
  tagRegion?: string | null;
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
  relatedNotices?: NoticeListItem[];
};

const NOTICE_FLOW_KIND_ORDER = [
  "竞价公告",
  "询比公告",
  "采购公告",
  "成交公告",
  "成交结果公告",
  "失败公告",
  "终止公告",
  "废标公告",
  "公示公告",
];

function noticeFlowKindRank(kind: string | null | undefined) {
  const label = (kind || "").trim();
  const index = NOTICE_FLOW_KIND_ORDER.indexOf(label);
  return index >= 0 ? index : NOTICE_FLOW_KIND_ORDER.length;
}

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

function noticeFlowTone(kind: string | null | undefined): "open" | "deal" | "fail" | "stop" | "other" {
  const label = kind || "";
  if (label.includes("成交")) return "deal";
  if (label.includes("失败") || label.includes("废标")) return "fail";
  if (label.includes("终止")) return "stop";
  if (label.includes("竞价") || label.includes("询比") || label.includes("采购")) return "open";
  return "other";
}

function buildProjectFlow(detail: NoticeDetail): NoticeListItem[] {
  const nodes: NoticeListItem[] = [
    {
      id: detail.id,
      siteId: detail.siteId,
      siteLabel: detail.siteLabel,
      noticeKey: detail.noticeKey,
      title: detail.title,
      projectCode: detail.projectCode,
      projectName: detail.projectName,
      buyerName: detail.buyerName,
      dealSupplier: detail.dealSupplier,
      dealAmount: detail.dealAmount,
      budgetAmount: detail.budgetAmount,
      noticeKind: detail.noticeKind,
      procurementMode: detail.procurementMode,
      publishTime: detail.publishTime,
      progressStatus: detail.progressStatus,
      progressLabel: detail.progressLabel,
    },
    ...(detail.relatedNotices || []),
  ];
  const seen = new Set<number>();
  return nodes
    .filter((item) => {
      if (seen.has(item.id)) return false;
      seen.add(item.id);
      return true;
    })
    .sort((a, b) => {
      const kindDiff = noticeFlowKindRank(a.noticeKind) - noticeFlowKindRank(b.noticeKind);
      if (kindDiff !== 0) return kindDiff;
      return String(a.publishTime || "").localeCompare(String(b.publishTime || ""));
    });
}

export async function fetchNoticeDetail(id: number): Promise<NoticeDetail> {
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

function Info({ label, value }: { label: string; value?: string | number | null }) {
  return (
    <div className="info">
      <span>{label}</span>
      <strong>{text(value)}</strong>
    </div>
  );
}

function ProjectNoticeFlow({
  detail,
  loading,
  onSelect,
}: {
  detail: NoticeDetail;
  loading: boolean;
  onSelect: (id: number) => void;
}) {
  const flow = buildProjectFlow(detail);
  if (flow.length < 2) return null;

  return (
    <div className="notice-flow">
      <div className="notice-flow-head">
        <h4>项目公告流程</h4>
        <span>
          {detail.projectCode ? `编号 ${detail.projectCode} · ` : ""}
          按竞价 → 成交 / 失败 / 终止串联，点击节点切换详情
        </span>
      </div>
      <ol className="notice-flow-track">
        {flow.map((node, index) => {
          const current = node.id === detail.id;
          const tone = noticeFlowTone(node.noticeKind);
          return (
            <li
              key={node.id}
              className={`notice-flow-step notice-flow-${tone}${current ? " is-current" : ""}`}
            >
              {index > 0 && <span className="notice-flow-line" aria-hidden="true" />}
              <button
                type="button"
                className="notice-flow-node"
                disabled={current || loading}
                onClick={() => {
                  if (!current) onSelect(node.id);
                }}
                title={current ? "当前公告" : `查看${node.noticeKind || "公告"}`}
              >
                <span className="notice-flow-dot" />
                <strong>{text(node.noticeKind)}</strong>
                <em>{text(node.publishTime).slice(0, 16)}</em>
                {node.dealSupplier ? <em>{node.dealSupplier}</em> : null}
                {node.dealAmount != null ? <em>{money(node.dealAmount)}</em> : null}
                {current ? <span className="notice-flow-badge">当前</span> : null}
              </button>
            </li>
          );
        })}
      </ol>
    </div>
  );
}

export function NoticeDetailModal({
  detail,
  loading = false,
  onClose,
  onSelectRelated,
}: {
  detail: NoticeDetail;
  loading?: boolean;
  onClose: () => void;
  onSelectRelated: (id: number) => void;
}) {
  return (
    <div className="modal-backdrop" role="presentation" onClick={onClose}>
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
          <button className="icon-button" type="button" onClick={onClose} aria-label="关闭">
            <X size={18} />
          </button>
        </div>

        <ProjectNoticeFlow detail={detail} loading={loading} onSelect={onSelectRelated} />

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
  );
}
