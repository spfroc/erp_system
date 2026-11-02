import { useEffect, useRef } from "react";
import { BarChart, LineChart } from "echarts/charts";
import {
  GridComponent,
  LegendComponent,
  TitleComponent,
  TooltipComponent,
} from "echarts/components";
import * as echarts from "echarts/core";
import { CanvasRenderer } from "echarts/renderers";

echarts.use([
  BarChart,
  LineChart,
  GridComponent,
  LegendComponent,
  TitleComponent,
  TooltipComponent,
  CanvasRenderer,
]);

export type AssistantChartSpec = {
  type?: string;
  title?: string;
  categories?: string[];
  series?: Array<{ name?: string; data?: Array<number | string> }>;
};

function money(value: number) {
  return new Intl.NumberFormat("zh-CN", {
    style: "currency",
    currency: "CNY",
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(value);
}

export function AssistantStatsChart({ chart }: { chart: AssistantChartSpec }) {
  const elRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<echarts.ECharts | null>(null);
  const chartType = chart.type === "line" ? "line" : "bar";
  const categories = Array.isArray(chart.categories) ? chart.categories.map(String) : [];
  const series = Array.isArray(chart.series) ? chart.series : [];
  const chartKey = JSON.stringify({
    type: chartType,
    title: chart.title || "",
    categories,
    series,
  });

  useEffect(() => {
    if (!elRef.current) return;
    const instance = echarts.init(elRef.current);
    chartRef.current = instance;
    const onResize = () => instance.resize();
    window.addEventListener("resize", onResize);
    return () => {
      window.removeEventListener("resize", onResize);
      instance.dispose();
      chartRef.current = null;
    };
  }, []);

  useEffect(() => {
    const instance = chartRef.current;
    if (!instance) return;
    const parsed = JSON.parse(chartKey) as {
      type: "bar" | "line";
      title: string;
      categories: string[];
      series: Array<{ name?: string; data?: Array<number | string> }>;
    };
    instance.setOption(
      {
        color: ["#1f7a4d", "#2563eb", "#d97706", "#7c3aed"],
        title: {
          text: parsed.title,
          left: 0,
          top: 0,
          textStyle: { color: "#0f172a", fontSize: 14, fontWeight: 650 },
        },
        tooltip: {
          trigger: "axis",
          valueFormatter: (value: unknown) => money(Number(value) || 0),
        },
        legend: { top: parsed.title ? 28 : 0, right: 0 },
        grid: {
          left: 48,
          right: 16,
          top: parsed.title ? 64 : 36,
          bottom: parsed.categories.length > 8 ? 48 : 28,
        },
        xAxis: {
          type: "category",
          data: parsed.categories,
          axisLabel: {
            color: "#667085",
            hideOverlap: true,
            rotate: parsed.categories.length > 10 ? 35 : 0,
          },
        },
        yAxis: {
          type: "value",
          axisLabel: {
            color: "#98a2b3",
            formatter: (value: number) => {
              if (Math.abs(value) >= 10000) return `${(value / 10000).toFixed(1)}万`;
              return String(value);
            },
          },
          splitLine: { lineStyle: { color: "#eef2f6" } },
        },
        series: parsed.series.map((item) => ({
          name: String(item.name || "数值"),
          type: parsed.type,
          data: (item.data || []).map((value) => Number(value) || 0),
          smooth: parsed.type === "line",
          barMaxWidth: 36,
          itemStyle: { borderRadius: parsed.type === "bar" ? [6, 6, 0, 0] : 0 },
          areaStyle: parsed.type === "line" ? { opacity: 0.08 } : undefined,
        })),
      },
      { notMerge: true }
    );
  }, [chartKey]);

  if (!categories.length || !series.length) return null;

  return <div className="assistant-chart" ref={elRef} />;
}
