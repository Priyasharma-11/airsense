"use client";

import { useQuery } from "@tanstack/react-query";
import { CalendarRange, Clock, CloudRain, GitCompareArrows, Grid3x3, Lightbulb, LineChart, Sigma, Table2 } from "lucide-react";
import { useMemo, useState } from "react";
import { axis, baseOption, EChart, useChartTokens } from "@/components/charts/echart";
import { Badge, Button, Card, CardHeader, ChartSkeleton, ErrorState, PageHeader, Segmented, Select, Skeleton } from "@/components/ui/primitives";
import { api } from "@/lib/api";
import { categoryColor, cn, fmt, POLLUTANT_LABEL, POLLUTANTS, shortStation } from "@/lib/format";
import { useStations } from "@/lib/hooks";
import type { Pollutant } from "@/lib/types";

const RANGES = [
  { value: "all", label: "All data" },
  { value: "365", label: "12 months" },
  { value: "90", label: "90 days" },
  { value: "30", label: "30 days" },
];

function Loader<T>({ q, children, height = 300 }: { q: { isLoading: boolean; error: unknown; data?: T; refetch: () => void }; children: (d: T) => React.ReactNode; height?: number }) {
  if (q.isLoading) return <ChartSkeleton height={height} />;
  if (q.error) return <ErrorState error={q.error} onRetry={q.refetch} />;
  return q.data ? <>{children(q.data)}</> : null;
}

export default function AnalyticsPage() {
  const t = useChartTokens();
  const stations = useStations();
  const [param, setParam] = useState<Pollutant>("pm25");
  const [range, setRange] = useState("all");
  const [selected, setSelected] = useState<number[]>([]);
  const [trendStation, setTrendStation] = useState<number>();
  const [resolution, setResolution] = useState<"day" | "month">("day");
  const [wxVar, setWxVar] = useState("wind_speed_10m");

  const summary = useQuery({ queryKey: ["summary"], queryFn: api.summary });
  const end = summary.data?.period_end;
  const start = useMemo(() => (range === "all" || !end ? undefined : new Date(new Date(end).getTime() - Number(range) * 86400_000).toISOString()), [range, end]);
  const base = { parameter: param, station_ids: selected.length ? selected : undefined, start };

  const insights = useQuery({ queryKey: ["insights"], queryFn: api.insights });
  const diurnal = useQuery({ queryKey: ["diurnal", base], queryFn: () => api.diurnal(base) });
  const monthly = useQuery({ queryKey: ["monthly", base], queryFn: () => api.monthly(base) });
  const heat = useQuery({ queryKey: ["heatmap", base], queryFn: () => api.heatmap(base) });
  const corr = useQuery({ queryKey: ["corr", selected, start], queryFn: () => api.correlation({ station_ids: selected.length ? selected : undefined, start }) });
  const dist = useQuery({ queryKey: ["dist", base], queryFn: () => api.distribution(base) });
  const comp = useQuery({ queryKey: ["comp", param, start], queryFn: () => api.stationComparison({ parameter: param, start }) });
  const wx = useQuery({ queryKey: ["wx", wxVar, selected, start], queryFn: () => api.weatherRelationship({ variable: wxVar, station_ids: selected.length ? selected : undefined, start, sample: 2000 }) });
  const trendIds = trendStation ? [trendStation] : (selected.length ? selected.slice(0, 4) : (stations.data ?? []).filter((s) => s.used_in_model).slice(0, 4).map((s) => s.id));
  const trend = useQuery({ queryKey: ["compare", trendIds, param, resolution, start], queryFn: () => api.compare(trendIds, param, resolution, start), enabled: trendIds.length > 0 });

  const unit = diurnal.data?.unit ?? "µg/m³";
  const toggle = (id: number) => setSelected((s) => (s.includes(id) ? s.filter((x) => x !== id) : [...s, id]));

  return (
    <div>
      <PageHeader title="Historical analysis" description="Exploratory analysis of every quality-controlled hourly measurement - trends, seasonality, daily cycles, pollutant relationships and weather effects."
        eyebrow={summary.data && <Badge tone="brand">{fmt.num(summary.data.hourly_records)} hourly PM2.5 records · {fmt.date(summary.data.period_start)} – {fmt.date(summary.data.period_end)}</Badge>} />

      {/* ---------- filters ---------- */}
      <Card className="mb-4 p-4">
        <div className="flex flex-wrap items-end gap-4">
          <div>
            <label htmlFor="param" className="mb-1.5 block text-[12px] font-medium text-muted">Pollutant</label>
            <Select id="param" value={param} onChange={(e) => setParam(e.target.value as Pollutant)}>
              {POLLUTANTS.map((p) => <option key={p} value={p}>{POLLUTANT_LABEL[p]}</option>)}
            </Select>
          </div>
          <div>
            <p className="mb-1.5 text-[12px] font-medium text-muted">Period</p>
            <Segmented label="Period" value={range} onChange={setRange} options={RANGES} />
          </div>
          <div className="w-full min-w-0 border-t border-line pt-3">
            <p className="mb-1.5 text-[12px] font-medium text-muted">Stations {selected.length ? `(${selected.length} selected)` : "(all - click to filter)"}</p>
            <div className="flex flex-wrap gap-1.5">
              {(stations.data ?? []).map((s) => (
                <button key={s.id} onClick={() => toggle(s.id)} aria-pressed={selected.includes(s.id)}
                  className={cn("rounded-full border px-2.5 py-1 text-[12px] font-medium transition",
                    selected.includes(s.id) ? "border-brand-500 bg-brand-50 text-brand-700 dark:text-brand-400" : "border-line text-muted hover:border-line-strong hover:text-fg")}>
                  {shortStation(s.name)}
                </button>
              ))}
              {selected.length > 0 && <Button size="sm" variant="ghost" onClick={() => setSelected([])}>Clear</Button>}
            </div>
          </div>
        </div>
      </Card>

      {/* ---------- insights ---------- */}
      <Card className="mb-4">
        <CardHeader title="What the data says" subtitle="Automatically generated from the full dataset - every number is computed, none are hand-written" icon={<Lightbulb className="size-4" />} />
        <div className="grid gap-3 px-5 pb-5 md:grid-cols-2 xl:grid-cols-3">
          {insights.isLoading && [0, 1, 2, 3, 4, 5].map((i) => <Skeleton key={i} className="h-24" />)}
          {insights.error && <ErrorState error={insights.error} compact onRetry={() => insights.refetch()} />}
          {insights.data?.insights.map((i) => (
            <div key={i.id} className="rounded-[14px] border border-line bg-subtle/60 p-4">
              <p className="text-[12px] font-semibold uppercase tracking-wide text-brand-600">{i.question}</p>
              <p className="mt-1.5 text-[13.5px] leading-relaxed text-fg">{i.answer}</p>
            </div>
          ))}
        </div>
      </Card>

      {/* ---------- trend ---------- */}
      <Card className="mb-4">
        <CardHeader title={`${POLLUTANT_LABEL[param]} over time`} icon={<LineChart className="size-4" />}
          subtitle="Daily means require ≥18 valid hours; monthly means ≥240 - incomplete periods are shown as gaps, never filled"
          action={<div className="flex flex-wrap items-center gap-2">
            <Select aria-label="Trend station" value={trendStation ?? ""} onChange={(e) => setTrendStation(e.target.value ? Number(e.target.value) : undefined)} className="h-8 text-[13px]">
              <option value="">Compare up to 4 stations</option>
              {(stations.data ?? []).map((s) => <option key={s.id} value={s.id}>{shortStation(s.name)}</option>)}
            </Select>
            <Segmented size="sm" label="Resolution" value={resolution} onChange={setResolution} options={[{ value: "day", label: "Daily" }, { value: "month", label: "Monthly" }]} />
          </div>} />
        <div className="px-3 pb-3">
          <Loader q={trend}>{(d) => (
            <EChart ariaLabel="Pollutant trend line chart" height={320} option={{
              ...baseOption(t),
              xAxis: axis(t, { type: "time", splitLine: { show: false } }),
              yAxis: axis(t, { type: "value", name: d[0]?.unit, nameTextStyle: { color: t.text, align: "left" } }),
              dataZoom: [{ type: "inside" }, { type: "slider", height: 18, bottom: 0, borderColor: "transparent", textStyle: { color: t.text } }],
              grid: { left: 8, right: 16, top: 36, bottom: 36, containLabel: true },
              legend: { ...baseOption(t).legend, type: "scroll" },
              series: d.map((s) => ({ name: shortStation(s.station_name), type: "line", showSymbol: false, connectNulls: false, lineStyle: { width: 1.6 },
                data: s.points.map((p) => [p.ts, p.value === null ? null : +p.value.toFixed(1)]) })),
            }} />
          )}</Loader>
        </div>
      </Card>

      <div className="grid gap-4 xl:grid-cols-2">
        {/* ---------- seasonal ---------- */}
        <Card>
          <CardHeader title="Monthly pattern" subtitle="Monthly mean and 90th percentile across selected stations" icon={<CalendarRange className="size-4" />} />
          <div className="px-3 pb-3">
            <Loader q={monthly}>{(d) => (
              <EChart ariaLabel="Monthly mean bar chart" option={{
                ...baseOption(t),
                xAxis: axis(t, { type: "category", data: d.series.map((s) => s.month), splitLine: { show: false }, axisLabel: { color: t.text, fontSize: 11, formatter: (v: string) => fmt.monthYear(`${v}-15`) } }),
                yAxis: axis(t, { type: "value", name: d.unit, nameTextStyle: { color: t.text, align: "left" } }),
                series: [
                  { name: "Monthly mean", type: "bar", barMaxWidth: 22, data: d.series.map((s) => ({ value: s.mean === null ? null : +s.mean.toFixed(1), itemStyle: { borderRadius: [5, 5, 0, 0], color: param === "pm25" ? categoryColor(s.mean === null ? null : (s.mean <= 30 ? "Good" : s.mean <= 60 ? "Satisfactory" : s.mean <= 90 ? "Moderate" : s.mean <= 120 ? "Poor" : "Very Poor")) : t.brand } })) },
                  { name: "90th percentile", type: "line", smooth: true, symbolSize: 5, data: d.series.map((s) => (s.p90 === null ? null : +s.p90.toFixed(1))), lineStyle: { type: "dashed", width: 1.5, color: t.muted }, itemStyle: { color: t.muted } },
                ],
              }} />
            )}</Loader>
            {monthly.data && (
              <div className="flex flex-wrap gap-2 px-2 pb-2">
                {Object.entries(monthly.data.season_mean).map(([k, v]) => (
                  <Badge key={k}>{k.replace("_", "-")}: <span className="font-semibold text-fg tabular">{fmt.num(v, 1)}</span></Badge>
                ))}
              </div>
            )}
          </div>
        </Card>

        {/* ---------- diurnal ---------- */}
        <Card>
          <CardHeader title="Time-of-day profile" subtitle="Mean concentration by hour (IST); bold line is the network average" icon={<Clock className="size-4" />} />
          <div className="px-3 pb-3">
            <Loader q={diurnal}>{(d) => (
              <EChart ariaLabel="Diurnal profile line chart" option={{
                ...baseOption(t),
                legend: { ...baseOption(t).legend, type: "scroll", left: 0, right: 0 },
                grid: { left: 8, right: 16, top: 40, bottom: 8, containLabel: true },
                xAxis: axis(t, { type: "category", data: d.hours.map((h) => `${String(h).padStart(2, "0")}:00`), splitLine: { show: false } }),
                yAxis: axis(t, { type: "value", name: unit, nameTextStyle: { color: t.text, align: "left" } }),
                series: [
                  ...d.stations.map((s) => ({ name: shortStation(s.name), type: "line", smooth: true, showSymbol: false, lineStyle: { width: 1, opacity: 0.55 }, data: s.values.map((v) => (v === null ? null : +v.toFixed(1))) })),
                  { name: "Network mean", type: "line", smooth: true, showSymbol: false, lineStyle: { width: 3.5, color: t.textStrong }, itemStyle: { color: t.textStrong }, z: 10, data: d.city.map((v) => (v === null ? null : +v.toFixed(1))) },
                ],
              }} />
            )}</Loader>
          </div>
        </Card>

        {/* ---------- heatmap ---------- */}
        <Card>
          <CardHeader title="Weekly rhythm" subtitle="Mean by weekday × hour of day (IST)" icon={<Grid3x3 className="size-4" />} />
          <div className="px-3 pb-3">
            <Loader q={heat}>{(d) => {
              const data = d.values.flatMap((row, y) => row.map((v, x) => [x, y, v === null ? "-" : +v.toFixed(1)]));
              const vals = d.values.flat().filter((v): v is number => v !== null);
              return (
                <EChart ariaLabel="Weekday by hour heatmap" height={300} option={{
                  ...baseOption(t),
                  tooltip: { ...baseOption(t).tooltip, trigger: "item", formatter: (p: { value: [number, number, number] }) => `${d.days[p.value[1]]} ${String(p.value[0]).padStart(2, "0")}:00 - <b>${p.value[2]}</b> ${d.unit}` },
                  grid: { left: 8, right: 8, top: 8, bottom: 52, containLabel: true },
                  xAxis: axis(t, { type: "category", data: d.hours.map((h) => String(h).padStart(2, "0")), splitArea: { show: false }, splitLine: { show: false } }),
                  yAxis: axis(t, { type: "category", data: d.days, inverse: true, splitLine: { show: false } }),
                  visualMap: { min: Math.min(...vals), max: Math.max(...vals), calculable: true, orient: "horizontal", left: "center", bottom: 0, itemHeight: 220, itemWidth: 12,
                    textStyle: { color: t.text }, inRange: { color: t.dark ? ["#0b2a3a", "#0f766e", "#e5b53a", "#ee8a3c", "#e04f4f"] : ["#e8f6f3", "#7fd1c0", "#e5b53a", "#ee8a3c", "#e04f4f"] } },
                  series: [{ type: "heatmap", data, itemStyle: { borderColor: t.dark ? "#0d1622" : "#ffffff", borderWidth: 2, borderRadius: 3 }, emphasis: { itemStyle: { borderColor: t.textStrong } } }],
                }} />
              );
            }}</Loader>
          </div>
        </Card>

        {/* ---------- correlation ---------- */}
        <Card>
          <CardHeader title="Correlation matrix" subtitle="Spearman rank correlation between pollutants and weather (robust to outliers)" icon={<Sigma className="size-4" />} />
          <div className="px-3 pb-3">
            <Loader q={corr}>{(d) => {
              const data = d.matrix.flatMap((row, y) => row.map((v, x) => [x, y, v ?? "-"]));
              return (
                <EChart ariaLabel="Correlation matrix heatmap" height={340} option={{
                  ...baseOption(t),
                  tooltip: { ...baseOption(t).tooltip, trigger: "item", formatter: (p: { value: [number, number, number] }) => `${d.labels[p.value[1]]} × ${d.labels[p.value[0]]}: <b>${p.value[2]}</b>` },
                  grid: { left: 8, right: 8, top: 8, bottom: 8, containLabel: true },
                  xAxis: axis(t, { type: "category", data: d.labels, axisLabel: { color: t.text, fontSize: 10.5, rotate: 40, interval: 0 }, splitLine: { show: false } }),
                  yAxis: axis(t, { type: "category", data: d.labels, inverse: true, axisLabel: { color: t.text, fontSize: 10.5, interval: 0 }, splitLine: { show: false } }),
                  visualMap: { show: false, min: -1, max: 1, inRange: { color: ["#3b82f6", t.dark ? "#162334" : "#f1f5f9", "#e04f4f"] } },
                  series: [{ type: "heatmap", data, label: { show: true, fontSize: 9.5, color: t.textStrong, formatter: (p: { value: [number, number, number] }) => (typeof p.value[2] === "number" ? p.value[2].toFixed(2) : "") },
                    itemStyle: { borderColor: t.dark ? "#0d1622" : "#fff", borderWidth: 1.5 } }],
                }} />
              );
            }}</Loader>
          </div>
        </Card>

        {/* ---------- distribution ---------- */}
        <Card>
          <CardHeader title="Distribution by station" subtitle="Box = interquartile range, whiskers = 1.5×IQR; outliers are kept in the data and counted" icon={<Table2 className="size-4" />} />
          <div className="px-3 pb-3">
            <Loader q={dist}>{(d) => (
              <EChart ariaLabel="Box plot of concentrations by station" height={340} option={{
                ...baseOption(t),
                tooltip: { ...baseOption(t).tooltip, trigger: "item", formatter: (p: { dataIndex: number }) => { const g = d.groups[p.dataIndex]; return `<b>${g.label}</b><br/>median ${g.median.toFixed(1)} · IQR ${g.q1.toFixed(1)}–${g.q3.toFixed(1)}<br/>mean ${g.mean.toFixed(1)} · n=${g.n.toLocaleString()} · ${g.outliers} outliers`; } },
                grid: { left: 8, right: 16, top: 16, bottom: 8, containLabel: true },
                yAxis: axis(t, { type: "category", data: d.groups.map((g) => shortStation(g.label)), splitLine: { show: false } }),
                xAxis: axis(t, { type: "value", name: d.unit }),
                series: [{ type: "boxplot", data: d.groups.map((g) => [g.min, g.q1, g.median, g.q3, g.max]),
                  itemStyle: { color: t.brandSoft, borderColor: t.brand, borderWidth: 1.5 }, boxWidth: [8, 18] }],
              }} />
            )}</Loader>
          </div>
        </Card>

        {/* ---------- station comparison ---------- */}
        <Card>
          <CardHeader title="Station comparison" subtitle="Mean concentration and number of days above the 60 µg/m³ daily NAAQS standard" icon={<GitCompareArrows className="size-4" />} />
          <div className="px-3 pb-3">
            <Loader q={comp}>{(d) => (
              <EChart ariaLabel="Bar chart comparing stations" height={340} option={{
                ...baseOption(t),
                grid: { left: 8, right: 16, top: 36, bottom: 8, containLabel: true },
                yAxis: axis(t, { type: "category", inverse: true, data: d.stations.map((s) => shortStation(s.name)), splitLine: { show: false } }),
                xAxis: [axis(t, { type: "value", name: d.unit, position: "bottom" }), axis(t, { type: "value", name: "days", position: "top", splitLine: { show: false } })],
                series: [
                  { name: "Mean", type: "bar", barMaxWidth: 14, data: d.stations.map((s) => (s.mean === null ? null : +s.mean.toFixed(1))), itemStyle: { borderRadius: [0, 6, 6, 0], color: t.brand } },
                  ...(param === "pm25" ? [{ name: "Days > 60 µg/m³", type: "scatter", xAxisIndex: 1, symbolSize: 10, data: d.stations.map((s) => s.days_above_threshold), itemStyle: { color: t.danger } }] : []),
                ],
              }} />
            )}</Loader>
          </div>
        </Card>
      </div>

      {/* ---------- weather ---------- */}
      <Card className="mt-4">
        <CardHeader title="PM2.5 versus weather" icon={<CloudRain className="size-4" />}
          subtitle={wx.data ? <>Spearman ρ = <span className="font-semibold text-fg">{fmt.num(wx.data.spearman, 2)}</span> · {wx.data.resolution} values · line = decile-binned mean</> : "Relationship between meteorology and PM2.5"}
          action={<Select aria-label="Weather variable" value={wxVar} onChange={(e) => setWxVar(e.target.value)} className="h-8 text-[13px]">
            <option value="wind_speed_10m">Wind speed</option>
            <option value="boundary_layer_height">Mixing height</option>
            <option value="relative_humidity_2m">Humidity</option>
            <option value="temperature_2m">Temperature</option>
            <option value="precipitation">Rainfall (daily)</option>
            <option value="surface_pressure">Pressure</option>
          </Select>} />
        <div className="px-3 pb-3">
          <Loader q={wx} height={360}>{(d) => {
            const seasons = ["winter", "summer", "monsoon", "post_monsoon"];
            const colors = ["#3b82f6", "#f59e0b", "#14b8a6", "#a855f7"];
            return (
              <EChart ariaLabel="Scatter plot of PM2.5 against a weather variable" height={360} option={{
                ...baseOption(t),
                tooltip: { ...baseOption(t).tooltip, trigger: "item" },
                xAxis: axis(t, { type: "value", name: d.label, nameLocation: "middle", nameGap: 26, nameTextStyle: { color: t.text }, scale: true }),
                yAxis: axis(t, { type: "value", name: "PM2.5 µg/m³", nameTextStyle: { color: t.text, align: "left" } }),
                grid: { left: 8, right: 16, top: 36, bottom: 30, containLabel: true },
                series: [
                  ...seasons.map((s, i) => ({ name: s.replace("_", "-"), type: "scatter", symbolSize: 4, itemStyle: { color: colors[i], opacity: 0.45 },
                    data: d.points.filter((p) => p.season === s).map((p) => [p.x, p.y]) })),
                  { name: "Binned mean", type: "line", smooth: true, symbolSize: 6, lineStyle: { width: 3, color: t.textStrong }, itemStyle: { color: t.textStrong }, data: d.binned.map((b) => [b.x, +b.mean.toFixed(1)]), z: 10 },
                ],
              }} />
            );
          }}</Loader>
        </div>
      </Card>
    </div>
  );
}
