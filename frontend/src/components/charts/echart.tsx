"use client";

import { BarChart, BoxplotChart, HeatmapChart, LineChart, ScatterChart } from "echarts/charts";
import {
  DataZoomComponent, GridComponent, LegendComponent, MarkAreaComponent, MarkLineComponent, TooltipComponent,
  VisualMapComponent,
} from "echarts/components";
import * as echarts from "echarts/core";
import { CanvasRenderer } from "echarts/renderers";
import ReactEChartsCore from "echarts-for-react/lib/core";
import { useMemo } from "react";
import { useTheme } from "@/components/providers";

echarts.use([LineChart, BarChart, HeatmapChart, ScatterChart, BoxplotChart, GridComponent, TooltipComponent,
  LegendComponent, VisualMapComponent, MarkLineComponent, MarkAreaComponent, DataZoomComponent, CanvasRenderer]);

/** Theme tokens for charts (mirror globals.css). One categorical palette, validated for both modes. */
export function useChartTokens(forceDark?: boolean) {
  const { resolved } = useTheme();
  return useMemo(() => {
    const dark = forceDark || resolved === "dark";
    return {
      dark,
      text: dark ? "#9db0c4" : "#4a5a6c",
      textStrong: dark ? "#e8eef5" : "#0b1726",
      grid: dark ? "rgba(157,176,196,0.12)" : "rgba(15,23,42,0.07)",
      axis: dark ? "rgba(157,176,196,0.3)" : "rgba(15,23,42,0.18)",
      tooltipBg: dark ? "#0d1622" : "#ffffff",
      tooltipBorder: dark ? "#273a50" : "#e2e8ee",
      brand: "#12b89a",
      brandSoft: dark ? "rgba(18,184,154,0.18)" : "rgba(18,184,154,0.14)",
      series: ["#12b89a", "#3b82f6", "#f59e0b", "#a855f7", "#ef4444", "#14b8a6", "#ec4899", "#84cc16", "#64748b", "#0ea5e9"],
      danger: "#e04f4f",
      muted: dark ? "#6c8299" : "#94a3b8",
    };
  }, [resolved, forceDark]);
}

export type ChartTokens = ReturnType<typeof useChartTokens>;

export function baseOption(t: ChartTokens) {
  return {
    backgroundColor: "transparent",
    color: t.series,
    textStyle: { fontFamily: "var(--font-inter), system-ui, sans-serif", color: t.text },
    grid: { left: 8, right: 16, top: 28, bottom: 8, containLabel: true },
    tooltip: {
      trigger: "axis",
      backgroundColor: t.tooltipBg,
      borderColor: t.tooltipBorder,
      borderWidth: 1,
      padding: [8, 12],
      textStyle: { color: t.textStrong, fontSize: 12 },
      extraCssText: "border-radius:12px;box-shadow:0 12px 32px -8px rgba(0,0,0,.25);",
      axisPointer: { lineStyle: { color: t.axis }, crossStyle: { color: t.axis } },
    },
    legend: { top: 0, right: 0, icon: "roundRect", itemWidth: 10, itemHeight: 10, textStyle: { color: t.text, fontSize: 12 } },
  };
}

export function axis(t: ChartTokens, extra: Record<string, unknown> = {}) {
  return {
    axisLine: { lineStyle: { color: t.axis } },
    axisTick: { show: false },
    axisLabel: { color: t.text, fontSize: 11 },
    splitLine: { lineStyle: { color: t.grid } },
    ...extra,
  };
}

export function EChart({ option, height = 300, ariaLabel, onEvents }: {
  option: Record<string, unknown>; height?: number; ariaLabel: string; onEvents?: Record<string, (p: unknown) => void>;
}) {
  return (
    <div role="img" aria-label={ariaLabel} style={{ height }}>
      <ReactEChartsCore echarts={echarts} option={option} notMerge lazyUpdate style={{ height: "100%", width: "100%" }}
        opts={{ renderer: "canvas" }} onEvents={onEvents} />
    </div>
  );
}
