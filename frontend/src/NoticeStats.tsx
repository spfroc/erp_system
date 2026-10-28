import { useEffect, useMemo, useState, type ReactNode } from "react";
import { Search, X } from "lucide-react";
import { backendApiUrl } from "./apiConfig";
import { DateTimeField } from "./DateTimeField";
import { AuthExpiredError } from "./db";
import { CopyableLine, SearchField } from "./listUi";
import { NoticeKindMultiSelect, noticeKindOptions } from "./noticeKindMultiSelect";
import { NoticeStatsRegionChart, type ProvinceStat } from "./noticeStatsRegionChart";

type DealKindStat = { dealKind: string; count: number; amount: string };
type NoticeKindStat = { noticeKind: string; count: number; amount: string };

type Stats = {
  noticeCount: number;
  dealAmount: string;
  buyerCount: number;
  goodsCount: number;
  byDealKind?: DealKindStat[];
  byNoticeKind?: NoticeKindStat[];
  byProvince?: ProvinceStat[];
  byRegion: Array<{ region: string; count: number; amount: string }>;
  byBuyer: Array<{ buyerName: string; orgType: string; nature: string; count: number; amount: string }>;
  detail?: string;
};

type DateFilters = {
  publishDateFrom: string;
  publishDateTo: string;
  startDateFrom: string;
  startDateTo: string;
  endDateFrom: string;
  endDateTo: string;
};

const EMPTY_DATES: DateFilters = {
  publishDateFrom: "",
  publishDateTo: "",
  startDateFrom: "",
  startDateTo: "",
  endDateFrom: "",
  endDateTo: "",
};

const PERIODS = [
  { id: "today", label: "今日" },
  { id: "last_30_days", label: "近30天" },
  { id: "this_week", label: "本周" },
  { id: "this_month", label: "当月" },
  { id: "last_month", label: "上月" },
  { id: "this_year", label: "本年" },
  { id: "custom", label: "自定义" },
];
const STATS_MAX_SPAN_DAYS = 366;

const DEAL_KIND_FILTERS = ["全部", "商品", "服务", "工程", "未识别"];

function moneyLabel(value: string) {
  const amount = Number(value);
  if (!Number.isFinite(amount)) return "0.00";
  if (Math.abs(amount) >= 10000) return `${(amount / 10000).toFixed(2)}万`;
  return amount.toLocaleString("zh-CN", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

function StatsClearable({
  value,
  onClear,
  clearLabel,
  children,
}: {
  value: string;
  onClear: () => void;
  clearLabel: string;
  children: ReactNode;
}) {
  const hasValue = Boolean(value);
  return (
    <div className={`notice-clearable${hasValue ? " has-value" : ""}`}>
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

export function NoticeStats({ onNotice }: { onNotice: (notice: { type: "success" | "error"; message: string }) => void }) {
  const [period, setPeriod] = useState("last_30_days");
  const [draftDates, setDraftDates] = useState<DateFilters>(EMPTY_DATES);
  const [appliedDates, setAppliedDates] = useState<DateFilters>(EMPTY_DATES);
  const [province, setProvince] = useState("");
  const [buyer, setBuyer] = useState("");
  const [dealKind, setDealKind] = useState("全部");
  const [noticeKinds, setNoticeKinds] = useState<string[]>([]);
  const [kindOptions, setKindOptions] = useState<string[]>(() => noticeKindOptions());
  const [queryProvince, setQueryProvince] = useState("");
  const [queryBuyer, setQueryBuyer] = useState("");
  const [stats, setStats] = useState<Stats | null>(null);
  const [chartProvince, setChartProvince] = useState("");
  const [queryNonce, setQueryNonce] = useState(0);

  useEffect(() => {
    const timer = window.setTimeout(() => {
      setQueryProvince(province.trim());
      setQueryBuyer(buyer.trim());
    }, 300);
    return () => window.clearTimeout(timer);
  }, [province, buyer]);

  useEffect(() => {
    setChartProvince("");
  }, [period, appliedDates, queryProvince, queryBuyer, dealKind, noticeKinds, queryNonce]);

  useEffect(() => {
    const hasPublishRange = Boolean(appliedDates.publishDateFrom || appliedDates.publishDateTo);
    const effectivePeriod = hasPublishRange ? "custom" : period;
    if (effectivePeriod === "custom" && !appliedDates.publishDateFrom && !appliedDates.publishDateTo) {
      // 选了自定义但还没点查询填日期时，等用户查询
      if (!appliedDates.startDateFrom && !appliedDates.startDateTo && !appliedDates.endDateFrom && !appliedDates.endDateTo) {
        return;
      }
    }
    const params = new URLSearchParams({ period: hasPublishRange ? "custom" : period });
    // 只传实际填写的一端；后端按「有起无止=从该日起」「有止无起=截至该日」处理
    if (appliedDates.publishDateFrom) params.set("publishDateFrom", appliedDates.publishDateFrom);
    if (appliedDates.publishDateTo) params.set("publishDateTo", appliedDates.publishDateTo);
    if (appliedDates.startDateFrom) params.set("startDateFrom", appliedDates.startDateFrom);
    if (appliedDates.startDateTo) params.set("startDateTo", appliedDates.startDateTo);
    if (appliedDates.endDateFrom) params.set("endDateFrom", appliedDates.endDateFrom);
    if (appliedDates.endDateTo) params.set("endDateTo", appliedDates.endDateTo);
    if (queryProvince) params.set("province", queryProvince);
    if (queryBuyer) params.set("buyer", queryBuyer);
    if (dealKind !== "全部") params.set("deal_kind", dealKind);
    if (noticeKinds.length) params.set("noticeKinds", noticeKinds.join(","));
    let cancelled = false;
    fetch(backendApiUrl(`/api/notices/stats/?${params.toString()}`), { credentials: "include" })
      .then(async (response) => {
        const text = await response.text();
        let data: Stats;
        try {
          data = JSON.parse(text) as Stats;
        } catch {
          throw new Error(response.ok ? "响应不是 JSON" : `请求失败（${response.status}）`);
        }
        if (response.status === 401) throw new AuthExpiredError();
        if (!response.ok && response.status !== 503) throw new Error(data.detail || "加载统计失败");
        return data;
      })
      .then((data) => {
        if (cancelled) return;
        setStats(data);
        const fromStats = (data.byNoticeKind || []).map((item) => item.noticeKind).filter(Boolean);
        if (fromStats.length) setKindOptions(noticeKindOptions(fromStats));
        if (data.detail) onNotice({ type: "error", message: data.detail });
      })
      .catch((error: Error) => {
        if (!cancelled) onNotice({ type: "error", message: error.message || "加载统计失败" });
      });
    return () => {
      cancelled = true;
    };
  }, [period, appliedDates, queryProvince, queryBuyer, dealKind, noticeKinds, onNotice, queryNonce]);

  function patchDraft(patch: Partial<DateFilters>) {
    setDraftDates((current) => ({ ...current, ...patch }));
  }

  function selectPeriod(next: string) {
    setPeriod(next);
    if (next !== "custom") {
      setDraftDates((current) => ({
        ...current,
        publishDateFrom: "",
        publishDateTo: "",
      }));
      setAppliedDates((current) => ({
        ...current,
        publishDateFrom: "",
        publishDateTo: "",
      }));
    }
  }

  function runDateQuery() {
    if (period === "custom" || draftDates.publishDateFrom || draftDates.publishDateTo) {
      if (!draftDates.publishDateFrom && !draftDates.publishDateTo && period === "custom") {
        onNotice({ type: "error", message: "自定义周期请填写发布日期起止（可只填一端）。" });
        return;
      }
      if (draftDates.publishDateFrom && draftDates.publishDateTo) {
        const from = new Date(`${draftDates.publishDateFrom}T00:00:00`).getTime();
        const to = new Date(`${draftDates.publishDateTo}T00:00:00`).getTime();
        if (Number.isFinite(from) && Number.isFinite(to)) {
          const days = Math.floor(Math.abs(to - from) / 86400000) + 1;
          if (days > STATS_MAX_SPAN_DAYS) {
            onNotice({ type: "error", message: `统计跨度最长 ${STATS_MAX_SPAN_DAYS} 天，请缩小发布日期范围。` });
            return;
          }
        }
      }
      setPeriod("custom");
    }
    setAppliedDates({ ...draftDates });
    setQueryNonce((value) => value + 1);
  }

  function clearDateFilters() {
    setDraftDates(EMPTY_DATES);
    setAppliedDates(EMPTY_DATES);
    setPeriod("last_30_days");
    setQueryNonce((value) => value + 1);
  }

  const provinces = stats?.byProvince || [];
  const dealKindRows = stats?.byDealKind || [];
  const noticeKindRows = stats?.byNoticeKind || [];
  const regionRows = useMemo(() => {
    if (!chartProvince) {
      return provinces.map((item) => ({
        name: item.province,
        count: item.count,
        amount: item.amount,
      }));
    }
    const active = provinces.find((item) => item.province === chartProvince);
    return (active?.cities || []).map((item) => ({
      name: item.city,
      count: item.count,
      amount: item.amount,
    }));
  }, [chartProvince, provinces]);

  return (
    <div className="stack">
      <div className="panel">
        <div className="page-toolbar">
          <div className="segmented cashflow-period-row" role="tablist" aria-label="统计周期">
            {PERIODS.map((item) => (
              <button key={item.id} type="button" className={period === item.id ? "active" : ""} onClick={() => selectPeriod(item.id)}>
                {item.label}
              </button>
            ))}
          </div>
          <div className="page-toolbar-actions notice-stats-filters">
            <SearchField value={province} onChange={setProvince} placeholder="筛选地区，如山东省" />
            <SearchField value={buyer} onChange={setBuyer} placeholder="筛选采购人" />
          </div>
        </div>

        <div className="notice-filters notice-stats-date-filters">
          <div className="notice-filters-row notice-filters-dates">
            <label className="orders-filter-field notice-date-range-field">
              <span>发布日期</span>
              <div className="notice-date-range-inputs">
                <StatsClearable value={draftDates.publishDateFrom} clearLabel="清空发布开始日期" onClear={() => patchDraft({ publishDateFrom: "" })}>
                  <DateTimeField
                    mode="date"
                    format="iso"
                    value={draftDates.publishDateFrom}
                    onChange={(value) => patchDraft({ publishDateFrom: value })}
                    placeholder="开始日期"
                    ariaLabel="发布开始日期"
                  />
                </StatsClearable>
                <span className="notice-date-range-sep">至</span>
                <StatsClearable value={draftDates.publishDateTo} clearLabel="清空发布结束日期" onClear={() => patchDraft({ publishDateTo: "" })}>
                  <DateTimeField
                    mode="date"
                    format="iso"
                    value={draftDates.publishDateTo}
                    onChange={(value) => patchDraft({ publishDateTo: value })}
                    placeholder="结束日期"
                    ariaLabel="发布结束日期"
                  />
                </StatsClearable>
              </div>
            </label>
            <label className="orders-filter-field notice-date-range-field">
              <span>开始日期</span>
              <div className="notice-date-range-inputs">
                <StatsClearable value={draftDates.startDateFrom} clearLabel="清空开始时间起" onClear={() => patchDraft({ startDateFrom: "" })}>
                  <DateTimeField
                    mode="date"
                    format="iso"
                    value={draftDates.startDateFrom}
                    onChange={(value) => patchDraft({ startDateFrom: value })}
                    placeholder="开始日期"
                    ariaLabel="开始时间起"
                  />
                </StatsClearable>
                <span className="notice-date-range-sep">至</span>
                <StatsClearable value={draftDates.startDateTo} clearLabel="清空开始时间止" onClear={() => patchDraft({ startDateTo: "" })}>
                  <DateTimeField
                    mode="date"
                    format="iso"
                    value={draftDates.startDateTo}
                    onChange={(value) => patchDraft({ startDateTo: value })}
                    placeholder="结束日期"
                    ariaLabel="开始时间止"
                  />
                </StatsClearable>
              </div>
            </label>
            <label className="orders-filter-field notice-date-range-field">
              <span>结束日期</span>
              <div className="notice-date-range-inputs">
                <StatsClearable value={draftDates.endDateFrom} clearLabel="清空结束时间起" onClear={() => patchDraft({ endDateFrom: "" })}>
                  <DateTimeField
                    mode="date"
                    format="iso"
                    value={draftDates.endDateFrom}
                    onChange={(value) => patchDraft({ endDateFrom: value })}
                    placeholder="开始日期"
                    ariaLabel="结束时间起"
                  />
                </StatsClearable>
                <span className="notice-date-range-sep">至</span>
                <StatsClearable value={draftDates.endDateTo} clearLabel="清空结束时间止" onClear={() => patchDraft({ endDateTo: "" })}>
                  <DateTimeField
                    mode="date"
                    format="iso"
                    value={draftDates.endDateTo}
                    onChange={(value) => patchDraft({ endDateTo: value })}
                    placeholder="结束日期"
                    ariaLabel="结束时间止"
                  />
                </StatsClearable>
              </div>
            </label>
          </div>
          <div className="notice-filters-actions">
            <button className="ghost" type="button" onClick={clearDateFilters}>
              清除
            </button>
            <button className="primary" type="button" onClick={runDateQuery}>
              <Search size={15} />
              查询
            </button>
          </div>
        </div>

        <NoticeKindMultiSelect options={kindOptions} value={noticeKinds} onChange={setNoticeKinds} />
        <div className="segmented" role="tablist" aria-label="成交类型">
          {DEAL_KIND_FILTERS.map((item) => (
            <button key={item} type="button" className={dealKind === item ? "active" : ""} onClick={() => setDealKind(item)}>
              {item}
            </button>
          ))}
        </div>
        <div className="metric-grid notice-stats-metrics">
          <div className="metric">
            <span>公告数</span>
            <strong>{stats?.noticeCount ?? "—"}</strong>
          </div>
          <div className="metric">
            <span>成交金额</span>
            <strong>{stats ? moneyLabel(stats.dealAmount) : "—"}</strong>
          </div>
          <div className="metric">
            <span>采购人数</span>
            <strong>{stats?.buyerCount ?? "—"}</strong>
          </div>
          <div className="metric">
            <span>商品行数</span>
            <strong>{stats?.goodsCount ?? "—"}</strong>
          </div>
        </div>

        <div className="two-col notice-stats-columns">
          <div className="notice-stats-deal-block">
            <h3>按公告类型</h3>
            <div className="table">
              <div className="table-row notice-stats-deal-table head">
                <span>类型</span>
                <span>公告数</span>
                <span>金额</span>
              </div>
              {noticeKindRows.map((item) => (
                <div
                  className={`table-row notice-stats-deal-table${noticeKinds.length === 0 ? " clickable-row" : ""}`}
                  key={item.noticeKind}
                  onClick={() => {
                    if (noticeKinds.length === 0) setNoticeKinds([item.noticeKind]);
                  }}
                >
                  <span>{item.noticeKind}</span>
                  <span>{item.count}</span>
                  <span>{moneyLabel(item.amount)}</span>
                </div>
              ))}
              {stats && noticeKindRows.length === 0 && <div className="table-empty">这个范围没有公告</div>}
            </div>
          </div>
          <div className="notice-stats-deal-block">
            <h3>按成交类型</h3>
            <div className="table">
              <div className="table-row notice-stats-deal-table head">
                <span>类型</span>
                <span>公告数</span>
                <span>成交金额</span>
              </div>
              {dealKindRows.map((item) => (
                <div
                  className={`table-row notice-stats-deal-table${dealKind === "全部" ? " clickable-row" : ""}`}
                  key={item.dealKind}
                  onClick={() => {
                    if (dealKind === "全部") setDealKind(item.dealKind);
                  }}
                >
                  <span>{item.dealKind}</span>
                  <span>{item.count}</span>
                  <span>{moneyLabel(item.amount)}</span>
                </div>
              ))}
              {stats && dealKindRows.length === 0 && <div className="table-empty">这个范围没有公告</div>}
            </div>
          </div>
        </div>

        <NoticeStatsRegionChart
          provinces={provinces}
          selectedProvince={chartProvince}
          onSelectProvince={setChartProvince}
        />

        <div className="two-col notice-stats-columns">
          <div>
            <h3>{chartProvince ? `${chartProvince} · 各市` : "按省份"}</h3>
            <div className="table">
              <div className="table-row notice-stats-region-table head">
                <span>{chartProvince ? "城市" : "省份"}</span>
                <span>公告数</span>
                <span>成交金额</span>
              </div>
              {regionRows.map((item) => (
                <div
                  className={`table-row notice-stats-region-table${chartProvince ? "" : " clickable-row"}`}
                  key={item.name}
                  onClick={() => {
                    if (!chartProvince) setChartProvince(item.name);
                  }}
                >
                  <span>{item.name}</span>
                  <span>{item.count}</span>
                  <span>{moneyLabel(item.amount)}</span>
                </div>
              ))}
              {stats && regionRows.length === 0 && <div className="table-empty">这个范围没有公告</div>}
            </div>
          </div>
          <div>
            <h3>按采购人</h3>
            <div className="table">
              <div className="table-row notice-stats-buyer-table head">
                <span>采购人</span>
                <span>公告数</span>
                <span>成交金额</span>
              </div>
              {(stats?.byBuyer || []).map((item) => (
                <div className="table-row notice-stats-buyer-table" key={item.buyerName}>
                  <div className="notice-tag-main">
                    <CopyableLine text={item.buyerName} label="采购人">
                      <strong>{item.buyerName}</strong>
                    </CopyableLine>
                    <em>{[item.orgType, item.nature].filter(Boolean).join(" · ")}</em>
                  </div>
                  <span>{item.count}</span>
                  <span>{moneyLabel(item.amount)}</span>
                </div>
              ))}
              {stats && stats.byBuyer.length === 0 && <div className="table-empty">这个范围没有公告</div>}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
