"use client";

import { useQuery } from "@tanstack/react-query";
import { motion } from "framer-motion";
import { ArrowDownRight, ArrowUpRight, Bell, CloudRain, Droplets, Gauge, Layers, MapPin, Sparkles, Thermometer, Wind } from "lucide-react";
import Link from "next/link";
import { useMemo, useState } from "react";
import { HistoryForecastChart } from "@/components/charts/history-forecast-chart";
import { AqiGauge, AqiScaleBar, Sparkline, StationSelect } from "@/components/aq/widgets";
import { AqiBadge, Badge, Card, CardHeader, ChartSkeleton, EmptyState, ErrorState, PageHeader, Skeleton, Stat } from "@/components/ui/primitives";
import { api } from "@/lib/api";
import { AQI_BANDS, categoryColor, cn, fmt, POLLUTANT_LABEL, shortStation } from "@/lib/format";
import { useCurrent, usePreferences, useStations } from "@/lib/hooks";

const fade = { initial: { opacity: 0, y: 8 }, animate: { opacity: 1, y: 0 } };

export default function DashboardPage() {
  const current = useCurrent();
  const stations = useStations();
  const prefs = usePreferences();
  const [chosen, setFocus] = useState<number>();
  // Default focus (derived, not stored): the user's preferred station, else the most polluted model station
  const defaultFocus = useMemo(() => {
    if (prefs.data?.default_station_id) return prefs.data.default_station_id;
    const reporting = (current.data?.stations ?? []).filter((s) => s.pm25 !== null && s.station.used_in_model);
    return [...reporting].sort((a, b) => (b.pm25 ?? 0) - (a.pm25 ?? 0))[0]?.station.id;
  }, [current.data, prefs.data]);
  const focus = chosen ?? defaultFocus;

  const focusLatest = current.data?.stations.find((s) => s.station.id === focus);
  const threshold = prefs.data?.pm25_threshold ?? 60;
  const end = focusLatest?.observed_at ?? undefined;
  const start = end ? new Date(new Date(end).getTime() - 7 * 86400_000).toISOString() : undefined;

  const history = useQuery({ queryKey: ["history", focus, "pm25", "hour", start], queryFn: () => api.history(focus!, "pm25", "hour", start, end), enabled: !!focus && !!end });
  const forecast = useQuery({ queryKey: ["forecast", focus, threshold], queryFn: () => api.forecast(focus!, { threshold }), enabled: !!focus, retry: false });
  const weather = useQuery({ queryKey: ["weather", focus], queryFn: () => api.weatherNow(focus!), enabled: !!focus });
  const overview = useQuery({ queryKey: ["forecast-overview"], queryFn: api.forecastOverview });
  const alerts = useQuery({ queryKey: ["alerts", "recent"], queryFn: () => api.alerts({ page_size: 4 }) });

  const s = current.data?.summary;
  const band = AQI_BANDS.find((b) => b.name === s?.category);
  const ranked = useMemo(() => [...(current.data?.stations ?? [])].sort((a, b) => (b.pm25 ?? -1) - (a.pm25 ?? -1)), [current.data]);
  const spark = new Map(overview.data?.stations.map((o) => [o.station_id, o]) ?? []);

  return (
    <div>
      <PageHeader title="Pune air quality" eyebrow={<Badge tone="brand"><MapPin className="size-3" /> Pune · Pimpri-Chinchwad</Badge>}
        description={s ? <>Latest network observation <span className="font-medium text-fg">{fmt.dateTime(s.observed_at)}</span>
          {s.data_lag_hours !== null && s.data_lag_hours > 6 && <> · source archive lags real time by ~{Math.round(s.data_lag_hours / 24)} days</>}</> : "Loading the latest observations…"}
        actions={<StationSelect stations={stations.data} value={focus} onChange={setFocus} id="focus-station" />} />

      {current.error ? <Card><ErrorState error={current.error} onRetry={() => current.refetch()} /></Card> : (
        <>
          {/* ---------- top row ---------- */}
          <div className="grid gap-4 xl:grid-cols-[1.15fr_1fr]">
            <motion.div {...fade}>
              <Card className="h-full p-5">
                <div className="flex items-start justify-between">
                  <div>
                    <p className="text-[12.5px] font-medium text-muted">City air quality index</p>
                    <p className="text-[12px] text-faint">Mean of 24 h PM2.5 across reporting stations</p>
                  </div>
                  {s && <AqiBadge category={s.category} size="md" />}
                </div>
                <div className="mt-2 flex flex-col items-center gap-4 sm:flex-row sm:items-end">
                  {s ? <AqiGauge aqi={s.aqi} category={s.category} /> : <Skeleton className="h-[132px] w-[220px]" />}
                  <div className="flex-1 space-y-3 pb-2">
                    <p className="text-[13.5px] leading-relaxed text-muted">{band?.advice ?? "—"}</p>
                    <AqiScaleBar value={s?.pm25_mean} />
                  </div>
                </div>
              </Card>
            </motion.div>
            <motion.div {...fade} transition={{ delay: 0.05 }} className="grid grid-cols-2 gap-4">
              <Stat label="City PM2.5 (24 h)" value={fmt.num(s?.pm25_mean, 1)} unit="µg/m³" accent={categoryColor(s?.category)} icon={<Gauge className="size-4" />}
                hint={<span>WHO guideline 15 · NAAQS 60</span>} />
              <Stat label="Highest now" value={fmt.num(s?.pm25_max)} unit="µg/m³" icon={<ArrowUpRight className="size-4" />}
                hint={s?.worst_station ? <span className="truncate">{shortStation(s.worst_station.name)}</span> : "—"} />
              <Stat label="Stations reporting" value={s ? `${s.stations_reporting}/${s.stations_total}` : "—"} icon={<Layers className="size-4" />} hint="CPCB · MPCB · IITM" />
              <Stat label="Forecast peak (24 h)" value={forecast.data ? fmt.num(forecast.data.peak.pm25) : "—"} unit="µg/m³" icon={<Sparkles className="size-4" />}
                accent={categoryColor(forecast.data?.peak.category)} hint={forecast.data ? <span>{fmt.dateTime(forecast.data.peak.target_time)}</span> : forecast.error ? "Unavailable" : "…"} />
            </motion.div>
          </div>

          {/* ---------- chart + pollutants ---------- */}
          <div className="mt-4 grid gap-4 xl:grid-cols-[1fr_340px]">
            <Card>
              <CardHeader title="PM2.5 - last 7 days and next 24 hours" icon={<Sparkles className="size-4" />}
                subtitle={forecast.data ? <>Forecast issued {fmt.dateTime(forecast.data.issued_at)} · model <span className="font-mono text-[12px]">{forecast.data.model_version}</span></> : "Observed hourly concentrations with the XGBoost forecast"}
                action={<Link href={`/forecast?station=${focus ?? ""}`} className="text-[13px] font-medium text-brand-600 hover:underline">Details →</Link>} />
              {history.isLoading || forecast.isLoading ? <ChartSkeleton height={320} /> :
                history.error ? <ErrorState error={history.error} onRetry={() => history.refetch()} /> :
                  <div className="px-3 pb-3"><HistoryForecastChart history={history.data} forecast={forecast.data} threshold={threshold} /></div>}
              {forecast.error && <p className="px-5 pb-4 text-[12.5px] text-warning">Forecast unavailable for this station: {(forecast.error as Error).message}</p>}
            </Card>
            <div className="grid content-start gap-4 sm:grid-cols-2 xl:grid-cols-1">
            <Card>
              <CardHeader title="Pollutants" subtitle="Latest hourly values" icon={<Layers className="size-4" />} />
              <ul className="divide-y divide-line px-5 pb-3">
                {!focusLatest && [0, 1, 2, 3, 4, 5].map((i) => <li key={i} className="py-2.5"><Skeleton className="h-6" /></li>)}
                {focusLatest?.readings.map((r) => (
                  <li key={r.parameter} className="flex items-center justify-between py-2.5">
                    <span className="text-[13.5px] font-medium text-fg">{POLLUTANT_LABEL[r.parameter]}</span>
                    <span className="text-right">
                      <span className="font-display text-[15px] font-semibold text-fg tabular">{fmt.num(r.value, r.parameter === "co" ? 2 : 1)}</span>
                      <span className="ml-1 text-[11.5px] text-faint">{r.unit}</span>
                    </span>
                  </li>
                ))}
              </ul>
              {focusLatest?.pm25_change_24h !== null && focusLatest?.pm25_change_24h !== undefined && (
                <p className={cn("mx-5 mb-5 flex items-center gap-1.5 rounded-[10px] px-3 py-2 text-[12.5px]", focusLatest.pm25_change_24h > 0 ? "bg-red-50 text-red-700 dark:bg-red-950/30 dark:text-red-400" : "bg-green-50 text-green-700 dark:bg-green-950/30 dark:text-green-400")}>
                  {focusLatest.pm25_change_24h > 0 ? <ArrowUpRight className="size-3.5" /> : <ArrowDownRight className="size-3.5" />}
                  PM2.5 {focusLatest.pm25_change_24h > 0 ? "up" : "down"} {fmt.num(Math.abs(focusLatest.pm25_change_24h))} µg/m³ vs same hour yesterday
                </p>
              )}
            </Card>
              <Card>
                <CardHeader title="Conditions" subtitle={focusLatest ? shortStation(focusLatest.station.name) : "—"} icon={<Thermometer className="size-4" />}
                  action={weather.data && <Badge>{weather.data.source_tag === "era5" ? "ERA5" : "Analysis"}</Badge>} />
                <div className="grid grid-cols-2 gap-x-4 gap-y-3 px-5 pb-5">
                  {weather.isLoading && [0, 1, 2, 3].map((i) => <Skeleton key={i} className="h-11" />)}
                  {weather.data && ([
                    [Thermometer, "Temperature", fmt.num(weather.data.temperature_2m, 1), "°C"],
                    [Droplets, "Humidity", fmt.num(weather.data.relative_humidity_2m), "%"],
                    [Wind, "Wind", fmt.num(weather.data.wind_speed_10m, 1), "km/h"],
                    [CloudRain, "Mixing height", fmt.num(weather.data.boundary_layer_height), "m"],
                  ] as const).map(([Icon, l, v, u]) => (
                    <div key={l} className="rounded-[12px] bg-subtle px-3 py-2.5">
                      <p className="flex items-center gap-1.5 text-[11.5px] text-muted"><Icon className="size-3.5" />{l}</p>
                      <p className="mt-0.5 font-display text-lg font-semibold text-fg tabular">{v}<span className="ml-0.5 text-[11px] font-normal text-faint">{u}</span></p>
                    </div>
                  ))}
                  {weather.error && <div className="col-span-2"><ErrorState compact error={weather.error} /></div>}
                </div>
              </Card>
            </div>
          </div>

          {/* ---------- stations + alerts ---------- */}
          <div className="mt-4 grid gap-4 xl:grid-cols-[1fr_380px]">
            <Card>
              <CardHeader title="Monitoring network" subtitle="Latest PM2.5 and the model's 24-hour outlook per station" icon={<MapPin className="size-4" />}
                action={<Link href="/map" className="text-[13px] font-medium text-brand-600 hover:underline">Open map →</Link>} />
              <div className="overflow-x-auto px-2 pb-2">
                <table className="w-full min-w-[640px] text-left text-[13.5px]">
                  <thead>
                    <tr className="text-[11.5px] uppercase tracking-wide text-faint">
                      <th className="px-3 py-2 font-semibold">Station</th>
                      <th className="px-3 py-2 text-right font-semibold">PM2.5</th>
                      <th className="px-3 py-2 font-semibold">Category</th>
                      <th className="px-3 py-2 font-semibold">Next 24 h</th>
                      <th className="px-3 py-2 text-right font-semibold">Peak</th>
                    </tr>
                  </thead>
                  <tbody>
                    {current.isLoading && [0, 1, 2, 3, 4].map((i) => <tr key={i}><td colSpan={5} className="px-3 py-2"><Skeleton className="h-7" /></td></tr>)}
                    {ranked.map((r) => {
                      const o = spark.get(r.station.id);
                      return (
                        <tr key={r.station.id} onClick={() => setFocus(r.station.id)} aria-selected={focus === r.station.id}
                          className={cn("cursor-pointer border-t border-line transition hover:bg-subtle", focus === r.station.id && "bg-brand-50/60 dark:bg-brand-50")}>
                          <td className="px-3 py-2.5">
                            <button className="text-left font-medium text-fg" onClick={() => setFocus(r.station.id)}>{shortStation(r.station.name)}</button>
                            <p className="text-[11.5px] text-faint">{r.station.provider} · {r.station.city}</p>
                          </td>
                          <td className="px-3 py-2.5 text-right font-display font-semibold tabular">{fmt.num(r.pm25)}</td>
                          <td className="px-3 py-2.5"><AqiBadge category={r.category} /></td>
                          <td className="px-3 py-2.5">{o ? <Sparkline values={o.sparkline} color={categoryColor(o.peak_category)} /> : <span className="text-[12px] text-faint">{r.pm25 === null ? "No data" : overview.isLoading ? "…" : "n/a"}</span>}</td>
                          <td className="px-3 py-2.5 text-right tabular">{o ? <span className="font-medium">{fmt.num(o.peak_pm25)}</span> : "—"}</td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            </Card>
            <Card>
              <CardHeader title="Recent alerts" icon={<Bell className="size-4" />} action={<Link href="/alerts" className="text-[13px] font-medium text-brand-600 hover:underline">Manage →</Link>} />
              {alerts.isLoading ? <div className="space-y-2 px-5 pb-5">{[0, 1, 2].map((i) => <Skeleton key={i} className="h-14" />)}</div> :
                alerts.error ? <ErrorState compact error={alerts.error} /> :
                  alerts.data && alerts.data.items.length ? (
                    <ul className="space-y-2 px-5 pb-5">
                      {alerts.data.items.map((a) => (
                        <li key={a.id} className="rounded-[12px] border border-line p-3">
                          <div className="flex items-center gap-2"><span className="size-2 rounded-full" style={{ background: categoryColor(a.severity) }} /><p className="truncate text-[13px] font-medium text-fg">{a.title}</p></div>
                          <p className="mt-1 text-[12px] text-muted">{fmt.dateTime(a.target_time)}{a.probability !== null && ` · ${fmt.pct(a.probability)} likely`}</p>
                        </li>
                      ))}
                    </ul>
                  ) : <EmptyState title="No alerts yet" description="Create a rule to be warned before PM2.5 crosses your threshold." icon={<Bell className="size-5" />}
                    action={<Link href="/alerts" className="text-[13px] font-medium text-brand-600 hover:underline">Create an alert rule</Link>} />}
            </Card>
          </div>
        </>
      )}
    </div>
  );
}
