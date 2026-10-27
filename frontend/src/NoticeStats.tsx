import { useEffect, useMemo, useState } from "react";
import { backendApiUrl } from "./apiConfig";
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

const PERIODS = [
  { id: "this_week", label: "本周" },
  { id: "this_month", label: "当月" },
  { id: "last_month", label: "上月" },
  { id: "custom", label: "自定义" },
];

const DEAL_KIND_FILTERS = ["全部", "商品", "服务", "工程", "未识别"];

function formatLocalDate(date: Date) {
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, "0");
  const day = String(date.getDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
}

function moneyLabel(value: string) {
  const amount = Number(value);
  if (!Number.isFinite(amount)) return "0.00";
  if (Math.abs(amount) >= 10000) return `${(amount / 10000).toFixed(2)}万`;
  return amount.toLocaleString("zh-CN", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

export function NoticeStats({ onNotice }: { onNotice: (notice: { type: "success" | "error"; message: string }) => void }) {
  const [period, setPeriod] = useState("this_month");
  const [customStart, setCustomStart] = useState(() => formatLocalDate(new Date(new Date().getFullYear(), new Date().getMonth(), 1)));
  const [customEnd, setCustomEnd] = useState(() => formatLocalDate(new Date()));
  const [province, setProvince] = useState("");
  const [buyer, setBuyer] = useState("");
  const [dealKind, setDealKind] = useState("全部");
  const [noticeKinds, setNoticeKinds] = useState<string[]>([]);
  const [kindOptions, setKindOptions] = useState<string[]>(() => noticeKindOptions());
  const [queryProvince, setQueryProvince] = useState("");
  const [queryBuyer, setQueryBuyer] = useState("");
  const [stats, setStats] = useState<Stats | null>(null);
  const [chartProvince, setChartProvince] = useState("");

  useEffect(() => {
    const timer = window.setTimeout(() => {
      setQueryProvince(province.trim());
      setQueryBuyer(buyer.trim());
    }, 300);
    return () => window.clearTimeout(timer);
  }, [province, buyer]);

  useEffect(() => {
    setChartProvince("");
  }, [period, customStart, customEnd, queryProvince, queryBuyer, dealKind, noticeKinds]);

  useEffect(() => {
    if (period === "custom" && (!customStart || !customEnd)) return;
    const params = new URLSearchParams({ period });
    if (period === "custom") {
      params.set("startDate", customStart);
      params.set("endDate", customEnd);
    }
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
  }, [period, customStart, customEnd, queryProvince, queryBuyer, dealKind, noticeKinds, onNotice]);

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
              <button key={item.id} type="button" className={period === item.id ? "active" : ""} onClick={() => setPeriod(item.id)}>
                {item.label}
              </button>
            ))}
            {period === "custom" && (
              <div className="cashflow-custom-range notice-stats-custom-range">
                <input type="date" value={customStart} onChange={(event) => setCustomStart(event.target.value)} aria-label="开始日期" />
                <span>至</span>
                <input type="date" value={customEnd} onChange={(event) => setCustomEnd(event.target.value)} aria-label="结束日期" />
              </div>
            )}
          </div>
          <div className="page-toolbar-actions notice-stats-filters">
            <SearchField value={province} onChange={setProvince} placeholder="筛选地区，如山东省" />
            <SearchField value={buyer} onChange={setBuyer} placeholder="筛选采购人" />
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
