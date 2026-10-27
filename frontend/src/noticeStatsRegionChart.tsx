import { useEffect, useMemo, useRef } from "react";
import { PieChart } from "echarts/charts";
import {
  LegendComponent,
  TitleComponent,
  TooltipComponent,
} from "echarts/components";
import * as echarts from "echarts/core";
import { CanvasRenderer } from "echarts/renderers";
import { ChevronLeft } from "lucide-react";

echarts.use([PieChart, TitleComponent, TooltipComponent, LegendComponent, CanvasRenderer]);

export type ProvinceStat = {
  province: string;
  count: number;
  amount: string;
  cities: Array<{ city: string; count: number; amount: string }>;
};

const PIE_COLORS = [
  "#1f7a4d",
  "#2563eb",
  "#d97706",
  "#7c3aed",
  "#0d9488",
  "#db2777",
  "#0891b2",
  "#ca8a04",
  "#dc2626",
  "#4338ca",
  "#65a30d",
  "#ea580c",
];

function moneyLabel(value: string | number) {
  const amount = typeof value === "number" ? value : Number(value);
  if (!Number.isFinite(amount)) return "0.00";
  if (Math.abs(amount) >= 10000) return `${(amount / 10000).toFixed(2)}万`;
  return amount.toLocaleString("zh-CN", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

function sliceData(rows: Array<{ name: string; count: number; amount: string }>) {
  const total = rows.reduce((sum, row) => sum + row.count, 0) || 1;
  return rows.map((row, index) => ({
    name: row.name,
    value: row.count,
    amount: row.amount,
    share: row.count / total,
    itemStyle: { color: PIE_COLORS[index % PIE_COLORS.length] },
  }));
}

export function NoticeStatsRegionChart({
  provinces,
  selectedProvince,
  onSelectProvince,
}: {
  provinces: ProvinceStat[];
  selectedProvince: string;
  onSelectProvince: (province: string) => void;
}) {
  const elRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<echarts.ECharts | null>(null);

  const active = useMemo(
    () => provinces.find((item) => item.province === selectedProvince) || null,
    [provinces, selectedProvince],
  );

  const chartRows = useMemo(() => {
    if (active) {
      return sliceData(
        active.cities.map((city) => ({
          name: city.city,
          count: city.count,
          amount: city.amount,
        })),
      );
    }
    return sliceData(
      provinces.map((item) => ({
        name: item.province,
        count: item.count,
        amount: item.amount,
      })),
    );
  }, [active, provinces]);

  const totalCount = chartRows.reduce((sum, row) => sum + row.value, 0);
  const totalAmount = chartRows.reduce((sum, row) => sum + Number(row.amount || 0), 0);

  useEffect(() => {
    if (!elRef.current) return;
    const chart = echarts.init(elRef.current);
    chartRef.current = chart;
    const onResize = () => chart.resize();
    window.addEventListener("resize", onResize);
    return () => {
      window.removeEventListener("resize", onResize);
      chart.dispose();
      chartRef.current = null;
    };
  }, []);

  useEffect(() => {
    const chart = chartRef.current;
    if (!chart) return;
    const levelLabel = active ? `${active.province} · 各市` : "各省份";
    chart.setOption(
      {
        color: PIE_COLORS,
        title: {
          text: `按地区 · ${levelLabel}`,
          subtext: `公告 ${totalCount} 条  ·  金额 ${moneyLabel(totalAmount)}`,
          left: 0,
          top: 0,
          textStyle: { color: "#0f172a", fontSize: 16, fontWeight: 700 },
          subtextStyle: { color: "#64748b", fontSize: 13, lineHeight: 22 },
        },
        tooltip: {
          trigger: "item",
          backgroundColor: "rgba(15, 23, 42, 0.92)",
          borderWidth: 0,
          padding: [10, 12],
          textStyle: { color: "#f8fafc", fontSize: 12, lineHeight: 20 },
          extraCssText: "border-radius:10px;box-shadow:0 10px 24px rgba(15,23,42,.18);",
          formatter: (params: unknown) => {
            const point = params as { name?: string; value?: number; percent?: number; data?: { amount?: string } };
            return [
              `<strong>${point.name || ""}</strong>`,
              `公告数 ${point.value ?? 0}`,
              `成交额 ${moneyLabel(point.data?.amount || 0)}`,
              `占比 ${(point.percent ?? 0).toFixed(1)}%`,
            ].join("<br/>");
          },
        },
        legend: {
          type: "scroll",
          orient: "vertical",
          right: 0,
          top: 56,
          bottom: 12,
          textStyle: { color: "#475569", fontSize: 12 },
        },
        series: [
          {
            type: "pie",
            name: levelLabel,
            radius: ["42%", "68%"],
            center: ["38%", "58%"],
            avoidLabelOverlap: true,
            itemStyle: {
              borderRadius: 6,
              borderColor: "#ffffff",
              borderWidth: 2,
            },
            label: {
              color: "#334155",
              formatter: "{b}\n{d}%",
            },
            labelLine: { length: 12, length2: 8 },
            data: chartRows,
            emphasis: {
              scale: true,
              scaleSize: 6,
              itemStyle: { shadowBlur: 12, shadowColor: "rgba(15, 23, 42, 0.18)" },
            },
          },
        ],
      },
      true,
    );

    const onClick = (params: { name?: string; componentType?: string }) => {
      if (params.componentType !== "series" || !params.name) return;
      if (!active) {
        onSelectProvince(params.name);
      }
    };
    chart.off("click");
    chart.on("click", onClick);
    return () => {
      chart.off("click", onClick);
    };
  }, [active, chartRows, onSelectProvince, totalAmount, totalCount]);

  return (
    <div className="notice-stats-chart-panel">
      <div className="notice-stats-chart-toolbar">
        {active ? (
          <button type="button" className="copy-link" onClick={() => onSelectProvince("")}>
            <ChevronLeft size={15} /> 返回省份
          </button>
        ) : (
          <span className="notice-stats-chart-hint">点击省份查看各市分布</span>
        )}
      </div>
      <div className="notice-stats-chart" ref={elRef} />
      {provinces.length === 0 && <div className="table-empty">这个范围没有结果公告</div>}
    </div>
  );
}
