"use client";

import { axis, baseOption, EChart, useChartTokens } from "./echart";
import { fmt } from "@/lib/format";
import type { Forecast, Series } from "@/lib/types";

/** Observed PM2.5 history followed by the model forecast with its 80 % interval band. */
export function HistoryForecastChart({ history, forecast, threshold = 60, height = 320, forceDark }: {
  history: Series | undefined; forecast: Forecast | undefined; threshold?: number; height?: number; forceDark?: boolean;
}) {
  const t = useChartTokens(forceDark);
  const obs = (history?.points ?? []).map((p) => [p.ts, p.value === null ? null : Math.round(p.value * 10) / 10]);
  const fc = forecast?.points ?? [];
  const lower = fc.map((p) => [p.target_time, p.lower]);
  const band = fc.map((p) => [p.target_time, Math.round((p.upper - p.lower) * 10) / 10]);
  const mean = forecast ? [[forecast.issued_at, forecast.latest_pm25], ...fc.map((p) => [p.target_time, p.pm25])] : [];

  const option = {
    ...baseOption(t),
    grid: { left: 8, right: 18, top: 36, bottom: 8, containLabel: true },
    xAxis: axis(t, { type: "time", splitLine: { show: false }, axisLabel: { color: t.text, fontSize: 11, hideOverlap: true,
      formatter: (v: number) => {
        const iso = new Date(v).toISOString();
        return fmt.time(iso) === "00:00" ? `{d|${fmt.dayShort(iso)}}` : fmt.time(iso);
      }, rich: { d: { fontWeight: 600, color: t.textStrong, fontSize: 11 } } } }),
    yAxis: axis(t, { type: "value", name: "µg/m³", nameTextStyle: { color: t.text, fontSize: 11, align: "left" }, min: 0 }),
    tooltip: { ...baseOption(t).tooltip, valueFormatter: (v: number) => (v === null || v === undefined ? "—" : `${v.toFixed(1)} µg/m³`) },
    series: [
      { name: "Observed", type: "line", data: obs, showSymbol: false, lineStyle: { width: 1.6, color: t.textStrong }, itemStyle: { color: t.textStrong }, connectNulls: false,
        markLine: { silent: true, symbol: "none", label: { formatter: `${threshold} µg/m³`, color: t.danger, fontSize: 10, position: "insideEndTop" },
          lineStyle: { color: t.danger, type: "dashed", width: 1 }, data: [{ yAxis: threshold }] } },
      { name: "lower", type: "line", data: lower, stack: "band", lineStyle: { opacity: 0 }, showSymbol: false, tooltip: { show: false }, silent: true },
      { name: "80% interval", type: "line", data: band, stack: "band", lineStyle: { opacity: 0 }, showSymbol: false, areaStyle: { color: t.brandSoft }, tooltip: { show: false }, silent: true },
      { name: "Forecast", type: "line", data: mean, showSymbol: false, smooth: 0.25, lineStyle: { width: 2.4, color: t.brand }, itemStyle: { color: t.brand },
        markArea: forecast ? { silent: true, itemStyle: { color: t.dark ? "rgba(255,255,255,0.025)" : "rgba(15,23,42,0.025)" },
          label: { show: true, position: "insideTop", color: t.text, fontSize: 10.5, formatter: "Forecast" }, data: [[{ xAxis: forecast.issued_at }, { xAxis: fc[fc.length - 1]?.target_time }]] } : undefined },
    ],
    legend: { ...baseOption(t).legend, data: ["Observed", "Forecast", "80% interval"] },
  };
  return <EChart option={option} height={height} ariaLabel="Observed PM2.5 over the past week followed by the 24-hour forecast with uncertainty band" />;
}
