import { useEffect, useRef } from "react";
import { BarChart } from "echarts/charts";
import {
  GridComponent,
  TitleComponent,
  TooltipComponent,
} from "echarts/components";
import * as echarts from "echarts/core";
import { CanvasRenderer } from "echarts/renderers";
import type { CashflowRow } from "./cashflowStats";

echarts.use([BarChart, GridComponent, TitleComponent, TooltipComponent, CanvasRenderer]);

const RECEIPT_COLORS = ["#1f7a4d", "#2563eb", "#d97706", "#7c3aed", "#0d9488", "#db2777", "#0891b2", "#ca8a04", "#dc2626", "#4338ca"];
const PAYMENT_COLORS = ["#c2410c", "#2563eb", "#7c3aed", "#0f766e", "#db2777", "#ca8a04", "#1d4ed8", "#be123c", "#0369a1", "#4f46e5"];
const OTHER_COLOR = "#64748b";

function money(value: number) {
  return new Intl.NumberFormat("zh-CN", { style: "currency", currency: "CNY", minimumFractionDigits: 2, maximumFractionDigits: 2 }).format(value);
}

function percentLabel(share: number) {
  return `${(share * 100).toFixed(1)}%`;
}

function mixHex(hex: string, ratio: number) {
  const value = hex.replace("#", "");
  const r = Number.parseInt(value.slice(0, 2), 16);
  const g = Number.parseInt(value.slice(2, 4), 16);
  const b = Number.parseInt(value.slice(4, 6), 16);
  const blend = (channel: number) => Math.round(channel + (255 - channel) * ratio);
  return `#${[blend(r), blend(g), blend(b)].map((channel) => channel.toString(16).padStart(2, "0")).join("")}`;
}

function barColor(name: string, index: number, kind: "receipt" | "payment") {
  if (name === "其他") return OTHER_COLOR;
  const palette = kind === "receipt" ? RECEIPT_COLORS : PAYMENT_COLORS;
  return palette[index % palette.length];
}

function barFill(name: string, index: number, kind: "receipt" | "payment") {
  const color = barColor(name, index, kind);
  return {
    type: "linear" as const,
    x: 0,
    y: 0,
    x2: 1,
    y2: 0,
    colorStops: [
      { offset: 0, color: mixHex(color, 0.28) },
      { offset: 1, color },
    ],
  };
}

export function CashflowStatsChart({
  rows,
  nameLabel,
  totalAmount,
  totalCount,
  refundAmount,
  kind,
}: {
  rows: CashflowRow[];
  nameLabel: string;
  totalAmount: number;
  totalCount: number;
  refundAmount?: number;
  kind: "receipt" | "payment";
}) {
  const elRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<echarts.ECharts | null>(null);

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
    const ordered = [...rows].reverse();
    const refundText = kind === "receipt" ? `  ·  退款 ${money(refundAmount ?? 0)}` : "";
    chart.setOption({
      color: kind === "receipt" ? RECEIPT_COLORS : PAYMENT_COLORS,
      title: {
        text: `${nameLabel}金额`,
        subtext: `合计 ${money(totalAmount)}  ·  ${totalCount} 笔  ·  占比 100.0%${refundText}`,
        left: 0,
        top: 0,
        textStyle: { color: "#0f172a", fontSize: 16, fontWeight: 700 },
        subtextStyle: { color: "#64748b", fontSize: 13, lineHeight: 22 },
      },
      tooltip: {
        trigger: "axis",
        axisPointer: { type: "shadow", shadowStyle: { color: "rgba(15, 23, 42, 0.06)" } },
        backgroundColor: "rgba(15, 23, 42, 0.92)",
        borderWidth: 0,
        padding: [10, 12],
        textStyle: { color: "#f8fafc", fontSize: 12, lineHeight: 20 },
        extraCssText: "border-radius:10px;box-shadow:0 10px 24px rgba(15,23,42,.18);",
        formatter: (params: unknown) => {
          const item = Array.isArray(params) ? params[0] : params;
          const point = item as { dataIndex?: number; marker?: string; name?: string };
          const row = ordered[point.dataIndex ?? 0];
          if (!row) return "";
          const lines = [
            `<strong>${row.name}</strong>`,
            `金额 ${money(row.amount)}`,
            `笔数 ${row.count}`,
            `占比 ${percentLabel(row.share)}`,
          ];
          if (kind === "receipt") lines.push(`退款 ${money(row.refundAmount ?? 0)}`);
          return lines.join("<br/>");
        },
      },
      grid: { left: 8, right: 118, top: 72, bottom: 8, containLabel: true },
      xAxis: {
        type: "value",
        axisLabel: {
          color: "#64748b",
          formatter: (value: number) => {
            if (Math.abs(value) >= 10000) return `${(value / 10000).toFixed(value % 10000 === 0 ? 0 : 1)}万`;
            return String(value);
          },
        },
        splitLine: { lineStyle: { color: "#eef2f6", type: "dashed" } },
        axisLine: { show: false },
        axisTick: { show: false },
      },
      yAxis: {
        type: "category",
        data: ordered.map((row) => row.name),
        axisLabel: {
          color: "#334155",
          width: 132,
          overflow: "truncate",
          ellipsis: "…",
        },
        axisLine: { show: false },
        axisTick: { show: false },
      },
      series: [
        {
          type: "bar",
          name: "金额",
          barMaxWidth: 18,
          barMinHeight: 4,
          data: ordered.map((row, index) => ({
            value: row.amount,
            itemStyle: {
              color: barFill(row.name, ordered.length - 1 - index, kind),
              borderRadius: [0, 8, 8, 0],
            },
          })),
          emphasis: {
            itemStyle: {
              shadowBlur: 8,
              shadowColor: "rgba(15, 23, 42, 0.18)",
            },
          },
          label: {
            show: true,
            position: "right",
            color: "#334155",
            fontSize: 11,
            formatter: (params: { dataIndex?: number }) => {
              const row = ordered[params.dataIndex ?? 0];
              if (!row) return "";
              return `${money(row.amount)}  ${percentLabel(row.share)}`;
            },
          },
        },
      ],
    }, true);
  }, [kind, nameLabel, refundAmount, rows, totalAmount, totalCount]);

  return (
    <div className="cashflow-echart-wrap">
      <div
        ref={elRef}
        className="cashflow-echart"
        style={{ height: Math.max(360, rows.length * 44 + 108) }}
        role="img"
        aria-label={`${nameLabel}金额合计 ${money(totalAmount)}`}
      />
    </div>
  );
}
