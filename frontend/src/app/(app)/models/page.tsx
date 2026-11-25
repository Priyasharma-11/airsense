"use client";

import { useQuery } from "@tanstack/react-query";
import { Award, BarChart3, BellRing, Crosshair, FlaskConical, Layers, LineChart, Scale } from "lucide-react";
import { useMemo, useState } from "react";
import { axis, baseOption, EChart, useChartTokens } from "@/components/charts/echart";
import { StationSelect } from "@/components/aq/widgets";
import { Badge, Card, CardHeader, ChartSkeleton, ErrorState, PageHeader, Segmented, Skeleton, Stat } from "@/components/ui/primitives";
import { api } from "@/lib/api";
import { cn, fmt } from "@/lib/format";
import { useActiveModel, useStations } from "@/lib/hooks";
import type { MetricRow } from "@/lib/types";

const MODEL_ORDER = ["Persistence", "Seasonal naive (24h)", "Linear Regression", "Random Forest", "XGBoost", "CAMS global (Copernicus)"];
const MODEL_COLORS: Record<string, string> = {
  Persistence: "#94a3b8", "Seasonal naive (24h)": "#cbd5e1", "Linear Regression": "#3b82f6", "Random Forest": "#a855f7",
  XGBoost: "#12b89a", "CAMS global (Copernicus)": "#f59e0b",
};
const KEY_H = [1, 3, 6, 12, 24];

export default function ModelsPage() {
  const t = useChartTokens();
  const stations = useStations();
  const active = useActiveModel();
  const version = active.data?.version;
  const metrics = useQuery({ queryKey: ["metrics", version], queryFn: () => api.modelMetrics(version!), enabled: !!version });
  const [h, setH] = useState(24);
  const [station, setStation] = useState<number>();
  const [metric, setMetric] = useState<"mae" | "rmse" | "r2">("mae");
  const evalQ = useQuery({ queryKey: ["eval", version, h, station], queryFn: () => api.evaluation(version!, { horizon: h, station_id: station, days: 30 }), enabled: !!version });

  const rows = metrics.data?.metrics ?? [];
  const by = (model: string, hz: number) => rows.find((r) => r.model === model && r.horizon === hz);
  const models = MODEL_ORDER.filter((m) => rows.some((r) => r.model === m));
  const xgb = rows.filter((r) => r.model === "XGBoost");
  const avgSkill = xgb.length ? xgb.reduce((a, r) => a + (r.skill_vs_persistence ?? 0), 0) / xgb.length : null;
  const winsAll = xgb.length > 0 && xgb.every((r) => (r.skill_vs_persistence ?? 0) > 0);
  const imp = useMemo(() => Object.entries(metrics.data?.importance ?? {}).slice(0, 12).reverse(), [metrics.data]);

  return (
    <div>
      <PageHeader title="Model Lab" description="Chronological hold-out evaluation of every candidate model on data the models never saw. The test window covers post-monsoon, Diwali 2026 and early winter."
        eyebrow={version && <Badge tone="brand"><FlaskConical className="size-3" /> Active model {version}</Badge>} />

      {metrics.error ? <Card><ErrorState error={metrics.error} onRetry={() => metrics.refetch()} /></Card> : (
        <>
          <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
            {!metrics.data ? [0, 1, 2, 3].map((i) => <Skeleton key={i} className="h-[118px] rounded-[16px]" />) : <>
              <Stat label="XGBoost MAE · +1 h" value={fmt.num(by("XGBoost", 1)?.mae, 2)} unit="µg/m³" accent="#12b89a" icon={<Crosshair className="size-4" />}
                hint={<>Persistence {fmt.num(by("Persistence", 1)?.mae, 2)} · R² {fmt.num(by("XGBoost", 1)?.r2, 2)}</>} />
              <Stat label="XGBoost MAE · +24 h" value={fmt.num(by("XGBoost", 24)?.mae, 2)} unit="µg/m³" accent="#12b89a" icon={<Crosshair className="size-4" />}
                hint={<>Persistence {fmt.num(by("Persistence", 24)?.mae, 2)} · R² {fmt.num(by("XGBoost", 24)?.r2, 2)}</>} />
              <Stat label="Mean skill vs persistence" value={avgSkill === null ? "—" : `${(avgSkill * 100).toFixed(0)}%`} icon={<Award className="size-4" />}
                hint={winsAll ? "Beats the baseline at all 24 horizons" : "Does not beat the baseline at every horizon"} accent={winsAll ? "#16a34a" : "#d97706"} />
              <Stat label="80% interval coverage (+24 h)" value={fmt.pct(by("XGBoost", 24)?.interval_coverage_80)} icon={<Scale className="size-4" />}
                hint="Target 80% - split-conformal calibration" />
            </>}
          </div>

          <div className="mt-4 grid gap-4 xl:grid-cols-[1.3fr_1fr]">
            <Card>
              <CardHeader title="Error by forecast horizon" subtitle="Test-set error for every model and lead time (lower is better, except R²)" icon={<LineChart className="size-4" />}
                action={<Segmented size="sm" label="Metric" value={metric} onChange={setMetric} options={[{ value: "mae", label: "MAE" }, { value: "rmse", label: "RMSE" }, { value: "r2", label: "R²" }]} />} />
              <div className="px-3 pb-3">
                {!metrics.data ? <ChartSkeleton /> : (
                  <EChart ariaLabel="Line chart of model error by horizon" height={320} option={{
                    ...baseOption(t),
                    legend: { ...baseOption(t).legend, type: "scroll", left: 0 },
                    grid: { left: 8, right: 16, top: 40, bottom: 24, containLabel: true },
                    xAxis: axis(t, { type: "value", min: 1, max: 24, interval: 1, name: "hours ahead", nameLocation: "middle", nameGap: 22, nameTextStyle: { color: t.text }, splitLine: { show: false } }),
                    yAxis: axis(t, { type: "value", name: metric === "r2" ? "R²" : "µg/m³", nameTextStyle: { color: t.text, align: "left" }, ...(metric === "r2" ? { min: -0.5, max: 1 } : {}) }),
                    tooltip: { ...baseOption(t).tooltip, valueFormatter: (v: number) => (v === null || v === undefined ? "—" : v.toFixed(2)) },
                    series: models.map((m) => ({ name: m, type: "line", symbolSize: m === "XGBoost" ? 6 : 4, smooth: 0.2,
                      lineStyle: { width: m === "XGBoost" ? 3 : 1.6, type: m === "CAMS global (Copernicus)" ? "dashed" : "solid", color: MODEL_COLORS[m] }, itemStyle: { color: MODEL_COLORS[m] },
                      data: rows.filter((r) => r.model === m).sort((a, b) => a.horizon - b.horizon).map((r) => [r.horizon, r[metric]]) })),
                  }} />
                )}
              </div>
            </Card>
            <Card>
              <CardHeader title="Global feature importance" subtitle="Mean |SHAP| on the test set, +24 h model" icon={<Layers className="size-4" />} />
              <div className="px-3 pb-3">
                {!metrics.data ? <ChartSkeleton /> : (
                  <EChart ariaLabel="Feature importance bar chart" height={320} option={{
                    ...baseOption(t),
                    tooltip: { ...baseOption(t).tooltip, trigger: "item", valueFormatter: (v: number) => `${v.toFixed(2)} µg/m³` },
                    grid: { left: 8, right: 24, top: 8, bottom: 8, containLabel: true },
                    yAxis: axis(t, { type: "category", data: imp.map(([k]) => k), splitLine: { show: false }, axisLabel: { color: t.text, fontSize: 10.5, fontFamily: "ui-monospace, monospace" } }),
                    xAxis: axis(t, { type: "value" }),
                    series: [{ type: "bar", barMaxWidth: 12, data: imp.map(([, v]) => v), itemStyle: { color: t.brand, borderRadius: [0, 5, 5, 0] } }],
                  }} />
                )}
              </div>
            </Card>
          </div>

          <Card className="mt-4">
            <CardHeader title="Actual vs predicted (hold-out test window)" icon={<BarChart3 className="size-4" />}
              subtitle={evalQ.data ? <>{evalQ.data.station_name} · last 30 test days · MAE in window {fmt.num(evalQ.data.mae_window, 2)} µg/m³</> : "Predictions stored with the model version at training time"}
              action={<div className="flex flex-wrap items-center gap-2">
                <StationSelect stations={stations.data} value={station ?? evalQ.data?.station_id} onChange={setStation} onlyModel className="h-8 min-w-[200px] text-[13px]" />
                <Segmented size="sm" label="Horizon" value={h} onChange={setH} options={KEY_H.map((x) => ({ value: x, label: `+${x}h` }))} />
              </div>} />
            <div className="px-3 pb-3">
              {evalQ.isLoading ? <ChartSkeleton height={320} /> : evalQ.error ? <ErrorState error={evalQ.error} onRetry={() => evalQ.refetch()} /> : evalQ.data && (
                <EChart ariaLabel="Actual versus predicted line chart" height={320} option={{
                  ...baseOption(t),
                  dataZoom: [{ type: "inside" }],
                  xAxis: axis(t, { type: "time", splitLine: { show: false } }),
                  yAxis: axis(t, { type: "value", name: "µg/m³", nameTextStyle: { color: t.text, align: "left" } }),
                  tooltip: { ...baseOption(t).tooltip, valueFormatter: (v: number) => (v === null || v === undefined ? "—" : v.toFixed(1)) },
                  series: [
                    { name: "lower", type: "line", stack: "pi", showSymbol: false, lineStyle: { opacity: 0 }, data: evalQ.data.points.map((p) => [p.ts, p.lower]), tooltip: { show: false }, silent: true },
                    { name: "80% interval", type: "line", stack: "pi", showSymbol: false, lineStyle: { opacity: 0 }, areaStyle: { color: t.brandSoft }, data: evalQ.data.points.map((p) => [p.ts, p.upper - p.lower]), tooltip: { show: false }, silent: true },
                    { name: "Actual", type: "line", showSymbol: false, lineStyle: { width: 1.5, color: t.textStrong }, itemStyle: { color: t.textStrong }, data: evalQ.data.points.map((p) => [p.ts, p.actual]) },
                    { name: "XGBoost", type: "line", showSymbol: false, lineStyle: { width: 1.8, color: "#12b89a" }, itemStyle: { color: "#12b89a" }, data: evalQ.data.points.map((p) => [p.ts, p.xgboost]) },
                    { name: "Persistence", type: "line", showSymbol: false, lineStyle: { width: 1, type: "dashed", color: "#94a3b8" }, itemStyle: { color: "#94a3b8" }, data: evalQ.data.points.map((p) => [p.ts, p.persistence]) },
                  ],
                  legend: { ...baseOption(t).legend, data: ["Actual", "XGBoost", "Persistence", "80% interval"] },
                }} />
              )}
            </div>
          </Card>

          <div className="mt-4 grid gap-4 xl:grid-cols-[1fr_1fr]">
            <Card>
              <CardHeader title="Residual analysis" subtitle={`Distribution of forecast errors (predicted − actual) at +${h} h`} icon={<BarChart3 className="size-4" />} />
              <div className="px-3 pb-3">
                {evalQ.data ? (
                  <EChart ariaLabel="Residual histogram" height={260} option={{
                    ...baseOption(t),
                    xAxis: axis(t, { type: "category", data: evalQ.data.residual_histogram.map((b) => b.bin.toFixed(0)), name: "µg/m³", splitLine: { show: false } }),
                    yAxis: axis(t, { type: "value", name: "hours" }),
                    series: [{ type: "bar", barCategoryGap: "8%", data: evalQ.data.residual_histogram.map((b) => ({ value: b.count, itemStyle: { color: b.bin < 0 ? "#3b82f6" : "#ee8a3c", borderRadius: [3, 3, 0, 0] } })) }],
                  }} />
                ) : <ChartSkeleton height={260} />}
              </div>
            </Card>
            <Card>
              <CardHeader title="Alerting skill (PM2.5 > 60 µg/m³)" subtitle="Forecast treated as a classifier of exceedance hours on the test set" icon={<BellRing className="size-4" />} />
              <div className="overflow-x-auto px-2 pb-3">
                <table className="w-full min-w-[460px] text-[13px]">
                  <thead><tr className="text-left text-[11.5px] uppercase tracking-wide text-faint"><th className="px-3 py-2">Model</th>{[1, 6, 24].map((x) => <th key={x} className="px-3 py-2 text-right">+{x} h P / R</th>)}</tr></thead>
                  <tbody>
                    {models.filter((m) => m !== "Seasonal naive (24h)").map((m) => (
                      <tr key={m} className="border-t border-line">
                        <td className="px-3 py-2 font-medium"><span className="mr-2 inline-block size-2 rounded-full" style={{ background: MODEL_COLORS[m] }} />{m}</td>
                        {[1, 6, 24].map((x) => {
                          const a = by(m, x)?.alert;
                          return <td key={x} className="px-3 py-2 text-right tabular">{a ? `${fmt.pct(a.precision)} / ${fmt.pct(a.recall)}` : "—"}</td>;
                        })}
                      </tr>
                    ))}
                  </tbody>
                </table>
                <p className="px-3 pt-3 text-[12px] text-faint">P = precision (alerts that were right), R = recall (exceedances that were caught).</p>
              </div>
            </Card>
          </div>

          <Card className="mt-4">
            <CardHeader title="Full comparison at key horizons" subtitle="Skill = 1 − MAE(model) / MAE(persistence). Bold marks the best model per horizon." icon={<Award className="size-4" />} />
            <div className="overflow-x-auto px-2 pb-3">
              <table className="w-full min-w-[760px] text-[13px]">
                <thead><tr className="text-left text-[11.5px] uppercase tracking-wide text-faint"><th className="px-3 py-2">Model</th>{KEY_H.map((x) => <th key={x} className="px-3 py-2 text-right">+{x} h MAE</th>)}<th className="px-3 py-2 text-right">+24 h RMSE</th><th className="px-3 py-2 text-right">+24 h R²</th><th className="px-3 py-2 text-right">Skill +24 h</th></tr></thead>
                <tbody>
                  {models.map((m) => (
                    <tr key={m} className={cn("border-t border-line", m === "XGBoost" && "bg-brand-50/50 dark:bg-brand-50")}>
                      <td className="px-3 py-2 font-medium">{m}{m === "XGBoost" && <Badge tone="brand" className="ml-2">deployed</Badge>}</td>
                      {KEY_H.map((x) => {
                        const r = by(m, x);
                        const best = Math.min(...models.map((mm) => by(mm, x)?.mae ?? Infinity));
                        return <td key={x} className={cn("px-3 py-2 text-right tabular", r?.mae === best && "font-bold text-brand-700 dark:text-brand-400")}>{fmt.num(r?.mae, 2)}</td>;
                      })}
                      <td className="px-3 py-2 text-right tabular">{fmt.num(by(m, 24)?.rmse, 2)}</td>
                      <td className="px-3 py-2 text-right tabular">{fmt.num(by(m, 24)?.r2, 3)}</td>
                      <td className="px-3 py-2 text-right tabular">{skillCell(by(m, 24))}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            {metrics.data?.sarima_daily && (
              <div className="mx-5 mb-5 rounded-[12px] border border-line bg-subtle/60 p-4 text-[13px] text-muted">
                <span className="font-semibold text-fg">Daily SARIMA track.</span> {metrics.data.sarima_daily.spec}, one-day-ahead over the test window:
                mean MAE <span className="font-semibold text-fg tabular">{fmt.num(metrics.data.sarima_daily.mean.sarima?.mean_mae, 2)}</span> vs daily persistence{" "}
                <span className="font-semibold text-fg tabular">{fmt.num(metrics.data.sarima_daily.mean.persistence?.mean_mae, 2)}</span> µg/m³ - the classical model does not beat the naive baseline on this data, which is why it was not deployed.
              </div>
            )}
          </Card>
        </>
      )}
    </div>
  );
}

function skillCell(r?: MetricRow) {
  if (!r || r.skill_vs_persistence === null) return "—";
  const v = r.skill_vs_persistence * 100;
  return <span className={v > 0 ? "text-green-600 dark:text-green-400" : v < 0 ? "text-red-600 dark:text-red-400" : ""}>{v > 0 ? "+" : ""}{v.toFixed(0)}%</span>;
}
