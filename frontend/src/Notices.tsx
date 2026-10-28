import { useCallback, useEffect, useState, type ReactNode } from "react";
import { FileText, RefreshCw, Search, X } from "lucide-react";
import { backendApiUrl } from "./apiConfig";
import { DateTimeField } from "./DateTimeField";
import { AuthExpiredError } from "./db";
import { CopyableLine, SearchField } from "./listUi";
import {
  fetchNoticeDetail,
  NoticeDetailModal,
  type NoticeDetail,
  type NoticeListItem,
} from "./NoticeDetailModal";
import { NoticeKindMultiSelect } from "./noticeKindMultiSelect";

export type { NoticeDetail, NoticeListItem };

type NoticeQuery = {
  search: string;
  projectCode: string;
  projectName: string;
  buyerName: string;
  supplierName: string;
  goodsName: string;
  siteId: string;
  noticeKinds: string[];
  regionName: string;
  parseStatus: string;
  progress: string;
  publishDateFrom: string;
  publishDateTo: string;
  startDateFrom: string;
  startDateTo: string;
  endDateFrom: string;
  endDateTo: string;
};

function defaultPublishFrom() {
  const date = new Date();
  date.setDate(date.getDate() - 29);
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, "0");
  const day = String(date.getDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
}

const EMPTY_NOTICE_QUERY: NoticeQuery = {
  search: "",
  projectCode: "",
  projectName: "",
  buyerName: "",
  supplierName: "",
  goodsName: "",
  siteId: "",
  noticeKinds: [],
  regionName: "",
  parseStatus: "",
  progress: "",
  // 默认近 30 天，避免无日期条件扫全表
  publishDateFrom: defaultPublishFrom(),
  publishDateTo: "",
  startDateFrom: "",
  startDateTo: "",
  endDateFrom: "",
  endDateTo: "",
};

function NoticeClearable({
  value,
  onClear,
  clearLabel,
  variant = "input",
  children,
}: {
  value: string;
  onClear: () => void;
  clearLabel: string;
  variant?: "input" | "select";
  children: ReactNode;
}) {
  const hasValue = Boolean(value);
  return (
    <div className={`notice-clearable${hasValue ? " has-value" : ""}${variant === "select" ? " is-select" : ""}`}>
      {children}
      {hasValue ? (
        <button
          type="button"
          className="notice-field-clear"
          aria-label={clearLabel}
          title={clearLabel}
          onClick={(event) => {
            event.preventDefault();
            event.stopPropagation();
            onClear();
          }}
        >
          <X size={14} />
        </button>
      ) : null}
    </div>
  );
}

type SiteOption = { id: string; label: string };

type NoticeListResponse = {
  items: NoticeListItem[];
  total: number;
  page: number;
  pageSize: number;
  sites?: SiteOption[];
  noticeKinds?: string[];
  regionNames?: string[];
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

const ORG_TAG_TONES: Record<string, string> = {
  幼儿园: "mint",
  小学: "mint",
  中学: "mint",
  大专: "mint",
  大学: "mint",
  教育: "teal",
  医疗卫生: "rose",
  公安系统: "navy",
  司法: "indigo",
  财税: "amber",
  公共资源: "cyan",
  文化: "purple",
  科研: "violet",
  交通: "sky",
  住建: "orange",
  农业: "lime",
  民政: "pink",
  应急: "red",
  群团: "fuchsia",
  机关: "slate",
  其他: "gray",
};

const NATURE_TAG_TONES: Record<string, string> = {
  政府: "blue",
  事业单位: "green",
  国企: "orange",
  央企: "red",
  其他: "gray",
};

function orgTagTone(label: string | null | undefined) {
  const name = (label || "").trim();
  return ORG_TAG_TONES[name] || "gray";
}

function natureTagTone(label: string | null | undefined) {
  const name = (label || "").trim();
  return NATURE_TAG_TONES[name] || "gray";
}

function dealKindTagTone(label: string | null | undefined) {
  const name = (label || "").trim();
  if (name === "商品") return "deal-goods";
  if (name === "服务") return "deal-service";
  if (name === "工程") return "deal-engineering";
  if (name === "未识别") return "deal-unknown";
  return "gray";
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

export function Notices({
  onNotice,
}: {
  onNotice: (notice: { type: "success" | "error"; message: string }) => void;
}) {
  const [draft, setDraft] = useState<NoticeQuery>(EMPTY_NOTICE_QUERY);
  const [request, setRequest] = useState({ filters: EMPTY_NOTICE_QUERY, page: 1, nonce: 0 });
  const [pageSize] = useState(15);
  const [total, setTotal] = useState(0);
  const [items, setItems] = useState<NoticeListItem[]>([]);
  const [sites, setSites] = useState<SiteOption[]>([]);
  const [noticeKinds, setNoticeKinds] = useState<string[]>([]);
  const [regionNames, setRegionNames] = useState<string[]>([]);
  const [loading, setLoading] = useState(false);
  const [detail, setDetail] = useState<NoticeDetail | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);

  const page = request.page;
  const patchDraft = useCallback((patch: Partial<NoticeQuery>) => {
    setDraft((prev) => ({ ...prev, ...patch }));
  }, []);

  const applyQuery = useCallback((filters: NoticeQuery, nextPage = 1) => {
    setDraft(filters);
    setRequest({ filters, page: nextPage, nonce: Date.now() });
  }, []);

  const runQuery = useCallback(() => {
    applyQuery({ ...draft }, 1);
  }, [applyQuery, draft]);

  const clearFilters = useCallback(() => {
    applyQuery({ ...EMPTY_NOTICE_QUERY }, 1);
  }, [applyQuery]);

  const load = useCallback(async () => {
    const filters = request.filters;
    setLoading(true);
    try {
      const params = new URLSearchParams({
        page: String(request.page),
        pageSize: String(pageSize),
      });
      if (filters.search.trim()) params.set("search", filters.search.trim());
      if (filters.projectCode.trim()) params.set("projectCode", filters.projectCode.trim());
      if (filters.projectName.trim()) params.set("projectName", filters.projectName.trim());
      if (filters.buyerName.trim()) params.set("buyerName", filters.buyerName.trim());
      if (filters.supplierName.trim()) params.set("supplierName", filters.supplierName.trim());
      if (filters.goodsName.trim()) params.set("goodsName", filters.goodsName.trim());
      if (filters.siteId) params.set("siteId", filters.siteId);
      if (filters.noticeKinds.length) params.set("noticeKinds", filters.noticeKinds.join(","));
      if (filters.regionName) params.set("regionName", filters.regionName);
      if (filters.parseStatus) params.set("parseStatus", filters.parseStatus);
      if (filters.progress) params.set("progress", filters.progress);
      if (filters.publishDateFrom) params.set("publishDateFrom", filters.publishDateFrom);
      if (filters.publishDateTo) params.set("publishDateTo", filters.publishDateTo);
      if (filters.startDateFrom) params.set("startDateFrom", filters.startDateFrom);
      if (filters.startDateTo) params.set("startDateTo", filters.startDateTo);
      if (filters.endDateFrom) params.set("endDateFrom", filters.endDateFrom);
      if (filters.endDateTo) params.set("endDateTo", filters.endDateTo);
      const data = await fetchNotices(params);
      setItems(data.items || []);
      setTotal(data.total || 0);
      if (data.sites?.length) setSites(data.sites);
      const kinds = data.noticeKinds || [];
      setNoticeKinds(kinds);
      const regions = data.regionNames || [];
      setRegionNames(regions);
      const nextKinds = filters.noticeKinds.filter((kind) => kinds.length === 0 || kinds.includes(kind));
      const kindInvalid = nextKinds.length !== filters.noticeKinds.length;
      const regionInvalid = Boolean(filters.regionName) && (regions.length === 0 || !regions.includes(filters.regionName));
      if (kindInvalid || regionInvalid) {
        const cleaned = {
          ...filters,
          noticeKinds: nextKinds,
          regionName: regionInvalid ? "" : filters.regionName,
        };
        setDraft(cleaned);
        setRequest((prev) => ({ ...prev, filters: cleaned }));
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
  }, [onNotice, pageSize, request]);

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
        <div className="page-toolbar">
          <div className="segmented" role="tablist" aria-label="公告进度">
            {[
              { id: "", label: "全部" },
              { id: "ongoing", label: "进行中" },
              { id: "upcoming", label: "未开始" },
              { id: "ended", label: "已截止" },
            ].map((item) => (
              <button
                key={item.id || "all"}
                type="button"
                className={draft.progress === item.id ? "active" : ""}
                onClick={() => {
                  applyQuery({ ...draft, progress: item.id }, 1);
                }}
              >
                {item.label}
              </button>
            ))}
          </div>
          <div className="page-toolbar-actions">
            <SearchField
              value={draft.search}
              onChange={(value) => patchDraft({ search: value })}
              onSubmit={runQuery}
              clearReveal="hover"
              placeholder="搜索标题、项目编号、采购单位、供应商"
              className="notice-title-search"
            />
            <button className="ghost" type="button" onClick={() => void load()} disabled={loading}>
              <RefreshCw size={16} />
              刷新
            </button>
          </div>
        </div>
        <div className="notice-filters">
          <div className="notice-filters-row notice-filters-kinds">
            <NoticeKindMultiSelect
              options={noticeKinds}
              value={draft.noticeKinds}
              onChange={(next) => patchDraft({ noticeKinds: next })}
            />
          </div>
          <div className="notice-filters-row notice-filters-selects">
            <label className="orders-filter-field">
              <span>站点</span>
              <NoticeClearable
                value={draft.siteId}
                clearLabel="清空站点"
                variant="select"
                onClear={() => patchDraft({ siteId: "", noticeKinds: [], regionName: "" })}
              >
                <select
                  value={draft.siteId}
                  onChange={(event) => patchDraft({ siteId: event.target.value, noticeKinds: [], regionName: "" })}
                >
                  <option value="">全部站点</option>
                  {sites.map((site) => (
                    <option key={site.id} value={site.id}>
                      {site.label}
                    </option>
                  ))}
                </select>
              </NoticeClearable>
            </label>
            <label className="orders-filter-field">
              <span>区域</span>
              <NoticeClearable value={draft.regionName} clearLabel="清空区域" variant="select" onClear={() => patchDraft({ regionName: "" })}>
                <select value={draft.regionName} onChange={(event) => patchDraft({ regionName: event.target.value })}>
                  <option value="">全部区域</option>
                  {regionNames.map((region) => (
                    <option key={region} value={region}>
                      {region}
                    </option>
                  ))}
                </select>
              </NoticeClearable>
            </label>
            <label className="orders-filter-field">
              <span>解析状态</span>
              <NoticeClearable value={draft.parseStatus} clearLabel="清空解析状态" variant="select" onClear={() => patchDraft({ parseStatus: "" })}>
                <select value={draft.parseStatus} onChange={(event) => patchDraft({ parseStatus: event.target.value })}>
                  <option value="">全部解析状态</option>
                  <option value="pending">待解析</option>
                  <option value="parsed">已解析</option>
                  <option value="parse_fail">解析失败</option>
                  <option value="skipped">已跳过</option>
                </select>
              </NoticeClearable>
            </label>
          </div>
          <div className="notice-filters-row notice-filters-texts">
            <label className="orders-filter-field">
              <span>项目编号</span>
              <NoticeClearable value={draft.projectCode} clearLabel="清空项目编号" onClear={() => patchDraft({ projectCode: "" })}>
                <input
                  value={draft.projectCode}
                  onChange={(event) => patchDraft({ projectCode: event.target.value })}
                  onKeyDown={(event) => {
                    if (event.key === "Enter") runQuery();
                  }}
                  placeholder="项目编号"
                />
              </NoticeClearable>
            </label>
            <label className="orders-filter-field">
              <span>项目名称</span>
              <NoticeClearable value={draft.projectName} clearLabel="清空项目名称" onClear={() => patchDraft({ projectName: "" })}>
                <input
                  value={draft.projectName}
                  onChange={(event) => patchDraft({ projectName: event.target.value })}
                  onKeyDown={(event) => {
                    if (event.key === "Enter") runQuery();
                  }}
                  placeholder="项目名称"
                />
              </NoticeClearable>
            </label>
            <label className="orders-filter-field">
              <span>采购单位</span>
              <NoticeClearable value={draft.buyerName} clearLabel="清空采购单位" onClear={() => patchDraft({ buyerName: "" })}>
                <input
                  value={draft.buyerName}
                  onChange={(event) => patchDraft({ buyerName: event.target.value })}
                  onKeyDown={(event) => {
                    if (event.key === "Enter") runQuery();
                  }}
                  placeholder="采购单位"
                />
              </NoticeClearable>
            </label>
            <label className="orders-filter-field">
              <span>供应商名称</span>
              <NoticeClearable value={draft.supplierName} clearLabel="清空供应商名称" onClear={() => patchDraft({ supplierName: "" })}>
                <input
                  value={draft.supplierName}
                  onChange={(event) => patchDraft({ supplierName: event.target.value })}
                  onKeyDown={(event) => {
                    if (event.key === "Enter") runQuery();
                  }}
                  placeholder="供应商名称"
                />
              </NoticeClearable>
            </label>
            <label className="orders-filter-field">
              <span>商品名称</span>
              <NoticeClearable value={draft.goodsName} clearLabel="清空商品名称" onClear={() => patchDraft({ goodsName: "" })}>
                <input
                  value={draft.goodsName}
                  onChange={(event) => patchDraft({ goodsName: event.target.value })}
                  onKeyDown={(event) => {
                    if (event.key === "Enter") runQuery();
                  }}
                  placeholder="商品名称"
                />
              </NoticeClearable>
            </label>
          </div>
          <div className="notice-filters-row notice-filters-dates">
            <label className="orders-filter-field notice-date-range-field">
              <span>发布日期</span>
              <div className="notice-date-range-inputs">
                <NoticeClearable value={draft.publishDateFrom} clearLabel="清空发布开始日期" onClear={() => patchDraft({ publishDateFrom: "" })}>
                  <DateTimeField
                    mode="date"
                    format="iso"
                    value={draft.publishDateFrom}
                    onChange={(value) => patchDraft({ publishDateFrom: value })}
                    placeholder="开始日期"
                    ariaLabel="发布开始日期"
                  />
                </NoticeClearable>
                <span className="notice-date-range-sep">至</span>
                <NoticeClearable value={draft.publishDateTo} clearLabel="清空发布结束日期" onClear={() => patchDraft({ publishDateTo: "" })}>
                  <DateTimeField
                    mode="date"
                    format="iso"
                    value={draft.publishDateTo}
                    onChange={(value) => patchDraft({ publishDateTo: value })}
                    placeholder="结束日期"
                    ariaLabel="发布结束日期"
                  />
                </NoticeClearable>
              </div>
            </label>
            <label className="orders-filter-field notice-date-range-field">
              <span>开始日期</span>
              <div className="notice-date-range-inputs">
                <NoticeClearable value={draft.startDateFrom} clearLabel="清空开始时间起" onClear={() => patchDraft({ startDateFrom: "" })}>
                  <DateTimeField
                    mode="date"
                    format="iso"
                    value={draft.startDateFrom}
                    onChange={(value) => patchDraft({ startDateFrom: value })}
                    placeholder="开始日期"
                    ariaLabel="开始时间起"
                  />
                </NoticeClearable>
                <span className="notice-date-range-sep">至</span>
                <NoticeClearable value={draft.startDateTo} clearLabel="清空开始时间止" onClear={() => patchDraft({ startDateTo: "" })}>
                  <DateTimeField
                    mode="date"
                    format="iso"
                    value={draft.startDateTo}
                    onChange={(value) => patchDraft({ startDateTo: value })}
                    placeholder="结束日期"
                    ariaLabel="开始时间止"
                  />
                </NoticeClearable>
              </div>
            </label>
            <label className="orders-filter-field notice-date-range-field">
              <span>结束日期</span>
              <div className="notice-date-range-inputs">
                <NoticeClearable value={draft.endDateFrom} clearLabel="清空结束时间起" onClear={() => patchDraft({ endDateFrom: "" })}>
                  <DateTimeField
                    mode="date"
                    format="iso"
                    value={draft.endDateFrom}
                    onChange={(value) => patchDraft({ endDateFrom: value })}
                    placeholder="开始日期"
                    ariaLabel="结束时间起"
                  />
                </NoticeClearable>
                <span className="notice-date-range-sep">至</span>
                <NoticeClearable value={draft.endDateTo} clearLabel="清空结束时间止" onClear={() => patchDraft({ endDateTo: "" })}>
                  <DateTimeField
                    mode="date"
                    format="iso"
                    value={draft.endDateTo}
                    onChange={(value) => patchDraft({ endDateTo: value })}
                    placeholder="结束日期"
                    ariaLabel="结束时间止"
                  />
                </NoticeClearable>
              </div>
            </label>
          </div>
          <div className="notice-filters-actions">
            <button className="ghost" type="button" onClick={clearFilters} disabled={loading}>
              清除
            </button>
            <button className="primary" type="button" onClick={runQuery} disabled={loading}>
              <Search size={15} />
              查询
            </button>
          </div>
        </div>
        <div className="table">
          <div className="table-row notice-table head">
            <span>名称/编号</span>
            <span>站点/区域</span>
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
          {items.map((item) => {
            const displayName = item.projectName || item.title || "";
            const displayCode = item.projectCode || item.noticeKey || "";
            return (
              <div className="table-row notice-table" key={item.id}>
                <span className="notice-main-cell">
                  <CopyableLine text={displayName} label="项目名称">
                    <strong>{text(displayName)}</strong>
                  </CopyableLine>
                  {displayCode ? (
                    <CopyableLine
                      text={displayCode}
                      label="项目编号"
                      className="is-secondary"
                      onOpen={
                        item.projectCode
                          ? () => {
                              applyQuery({ ...EMPTY_NOTICE_QUERY, projectCode: item.projectCode || "" }, 1);
                            }
                          : undefined
                      }
                    >
                      <em>{displayCode}</em>
                    </CopyableLine>
                  ) : (
                    <em>—</em>
                  )}
                  {(item.tagDealKind || item.tagOrgType || item.tagNature || item.tagProvince || item.tagCity || item.tagDistrict) && (
                    <span className="notice-list-tags">
                      {item.tagDealKind ? (
                        <span className={`notice-list-tag tone-${dealKindTagTone(item.tagDealKind)}`}>{item.tagDealKind}</span>
                      ) : null}
                      {item.tagOrgType ? (
                        <span className={`notice-list-tag tone-${orgTagTone(item.tagOrgType)}`}>{item.tagOrgType}</span>
                      ) : null}
                      {item.tagNature ? (
                        <span className={`notice-list-tag tone-${natureTagTone(item.tagNature)}`}>{item.tagNature}</span>
                      ) : null}
                      {item.tagProvince ? (
                        <span className="notice-list-tag tone-region-province">{item.tagProvince}</span>
                      ) : null}
                      {item.tagCity ? (
                        <span className="notice-list-tag tone-region-city">{item.tagCity}</span>
                      ) : null}
                      {item.tagDistrict ? (
                        <span className="notice-list-tag tone-region-district">{item.tagDistrict}</span>
                      ) : null}
                    </span>
                  )}
                </span>
                <span>
                  {text(item.siteLabel)}
                  <em>{text(item.regionName)}</em>
                </span>
                <span>{text(item.buyerName)}</span>
                <span>{text(item.dealSupplier)}</span>
                <span>
                  <strong>{money(item.dealAmount)}</strong>
                  <em>预算 {money(item.budgetAmount)}</em>
                </span>
                <span>
                  {text(item.noticeKind)}
                  <em>{text(item.procurementMode)}</em>
                  {(item.siblingKinds || []).length > 0 && (
                    <em className="notice-sibling-kinds">
                      另有 {(item.siblingKinds || []).join("、")}
                    </em>
                  )}
                </span>
                <span className="notice-times">
                  <em>发布 {text(item.publishTime)}</em>
                  <em>开始 {text(item.startTime)}</em>
                  <em>结束 {text(item.endTime)}</em>
                  <em>采集 {text(item.crawledAt)}</em>
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
            );
          })}
        </div>
        <div className="pager">
          <button
            className="ghost"
            disabled={page <= 1 || loading}
            onClick={() => setRequest((prev) => ({ ...prev, page: prev.page - 1, nonce: Date.now() }))}
          >
            上一页
          </button>
          <span>
            第 {page} / {totalPages} 页 · 共 {total} 条
          </span>
          <button
            className="ghost"
            disabled={page >= totalPages || loading}
            onClick={() => setRequest((prev) => ({ ...prev, page: prev.page + 1, nonce: Date.now() }))}
          >
            下一页
          </button>
        </div>
      </div>

      {detail && (
        <NoticeDetailModal
          detail={detail}
          loading={detailLoading}
          onClose={() => setDetail(null)}
          onSelectRelated={(id) => void openDetail(id)}
        />
      )}
    </div>
  );
}
