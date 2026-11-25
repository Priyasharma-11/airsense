"use client";

import { useQuery } from "@tanstack/react-query";
import { motion } from "framer-motion";
import {
  Activity, ArrowRight, BellRing, BrainCircuit, ChartNoAxesCombined, Database, Gauge, MapPinned, ShieldCheck, Sparkles, Workflow,
} from "lucide-react";
import { HistoryForecastChart } from "@/components/charts/history-forecast-chart";
import { Footer, MarketingNav } from "@/components/layout/marketing";
import { AqiBadge, ButtonLink, ChartSkeleton, ErrorState } from "@/components/ui/primitives";
import { api } from "@/lib/api";
import { categoryColor, fmt, shortStation } from "@/lib/format";
import { useCurrent } from "@/lib/hooks";

const CAPABILITIES = [
  { icon: Activity, title: "Live station monitoring", body: "Ten CPCB, MPCB and IITM reference monitors across Pune and Pimpri-Chinchwad, quality-controlled hour by hour." },
  { icon: ChartNoAxesCombined, title: "Exploratory analytics", body: "Seasonal, weekly and diurnal patterns, pollutant correlations and weather relationships - with auto-generated findings." },
  { icon: Sparkles, title: "24-hour PM2.5 forecasts", body: "Direct multi-horizon XGBoost models that beat persistence at every lead time on unseen data." },
  { icon: ShieldCheck, title: "Calibrated uncertainty", body: "Split-conformal 80% intervals and exceedance probabilities, so alerts say how sure they are." },
  { icon: MapPinned, title: "Geospatial hotspots", body: "Statistically defined hotspots and nearest-station lookup, powered by PostGIS in production." },
  { icon: BellRing, title: "Personal alerts", body: "Rules on your stations and thresholds, evaluated against every new forecast and observation." },
];

const STEPS = [
  { icon: Database, title: "Collect", body: "15-minute readings from the OpenAQ archive plus hourly ERA5 weather, with full provenance." },
  { icon: Workflow, title: "Clean", body: "Physical bounds, flat-line detection, robust outlier flags, ≥50% hourly coverage, no long-gap filling." },
  { icon: BrainCircuit, title: "Model", body: "Leakage-safe lag, rolling, weather and calendar features; chronological train / validation / test split." },
  { icon: Gauge, title: "Serve", body: "FastAPI serves versioned models; every number on screen comes from the database or the model." },
];

export function Landing() {
  const current = useCurrent();
  const metrics = useQuery({
    queryKey: ["landing-metrics"],
    queryFn: async () => {
      const m = await api.activeModel();
      return api.modelMetrics(m.version);
    },
  });
  const featured = current.data?.stations.filter((s) => s.pm25 !== null && s.station.used_in_model).sort((a, b) => (b.pm25 ?? 0) - (a.pm25 ?? 0))[0];
  const fc = useQuery({ queryKey: ["forecast", featured?.station.id, 60], queryFn: () => api.forecast(featured!.station.id, { threshold: 60 }), enabled: !!featured });
  const issued = fc.data?.issued_at;
  const hist = useQuery({ queryKey: ["history-landing", featured?.station.id, issued], enabled: !!issued,
    queryFn: () => api.history(featured!.station.id, "pm25", "hour", new Date(new Date(issued!).getTime() - 72 * 3600_000).toISOString(), issued) });

  const m = metrics.data?.metrics ?? [];
  const xgb24 = m.find((r) => r.model === "XGBoost" && r.horizon === 24);
  const avgSkill = m.filter((r) => r.model === "XGBoost").reduce((a, r, _, arr) => a + (r.skill_vs_persistence ?? 0) / arr.length, 0);
  const s = current.data?.summary;

  return (
    <div className="min-h-dvh">
      {/* ---------------- hero ---------------- */}
      <div className="relative overflow-hidden bg-[#050b14] text-white">
        <MarketingNav dark />
        <div className="bg-grid pointer-events-none absolute inset-0 opacity-70 [mask-image:radial-gradient(ellipse_at_top,black_30%,transparent_75%)]" />
        <div className="pointer-events-none absolute left-1/2 top-[-260px] size-[760px] -translate-x-1/2 rounded-full bg-brand-500/20 blur-[140px]" />
        <section className="relative mx-auto grid max-w-6xl gap-12 px-4 pb-20 pt-16 md:px-6 lg:grid-cols-[1.05fr_1fr] lg:pt-24">
          <motion.div initial={{ opacity: 0, y: 14 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.5 }}>
            <span className="inline-flex items-center gap-2 rounded-full border border-white/15 bg-white/5 px-3 py-1 text-[12.5px] text-slate-300">
              <span className="relative flex size-2"><span className="absolute inline-flex size-full animate-ping rounded-full bg-brand-400 opacity-70" /><span className="relative size-2 rounded-full bg-brand-400" /></span>
              {s ? <>Live from {s.stations_reporting} Pune monitors · {fmt.dateTime(s.observed_at)}</> : "Connecting to the monitoring network…"}
            </span>
            <h1 className="mt-6 font-display text-[40px] font-semibold leading-[1.05] tracking-tight md:text-[56px]">
              Know Pune&apos;s air <span className="bg-gradient-to-r from-brand-400 to-sky-400 bg-clip-text text-transparent">a day ahead.</span>
            </h1>
            <p className="mt-5 max-w-xl text-[16.5px] leading-relaxed text-slate-300">
              AirSense turns official monitoring-station data into understanding and foresight: where pollution concentrates, why it moves,
              and what PM2.5 will do over the next 24 hours - with honest uncertainty.
            </p>
            <div className="mt-8 flex flex-wrap gap-3">
              <ButtonLink href="/register" size="lg" icon={<ArrowRight className="size-4" />}>Start monitoring</ButtonLink>
              <ButtonLink href="/methodology" size="lg" variant="outline" className="border-white/20 text-white hover:bg-white/10">Read the methodology</ButtonLink>
            </div>
            <dl className="mt-12 grid max-w-lg grid-cols-3 gap-6">
              {[
                ["City PM2.5 now", s ? `${fmt.num(s.pm25_mean)}` : "—", "µg/m³"],
                ["Forecast MAE +24 h", xgb24 ? fmt.num(xgb24.mae, 1) : "—", "µg/m³"],
                ["Skill vs persistence", m.length ? `+${Math.round(avgSkill * 100)}%` : "—", "avg."],
              ].map(([k, v, u]) => (
                <div key={k}>
                  <dt className="text-[12px] text-slate-400">{k}</dt>
                  <dd className="mt-1 font-display text-[26px] font-semibold tabular">{v}<span className="ml-1 text-[12px] font-normal text-slate-400">{u}</span></dd>
                </div>
              ))}
            </dl>
          </motion.div>

          <motion.div id="forecast" initial={{ opacity: 0, y: 18 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.55, delay: 0.1 }}
            className="relative rounded-[24px] border border-white/10 bg-white/[0.035] p-2 shadow-2xl backdrop-blur-xl">
            <div className="rounded-[18px] border border-white/5 bg-[#0b1522]/90 p-5 dark">
              <div className="flex items-start justify-between gap-4">
                <div>
                  <p className="text-[12px] text-slate-400">Live forecast preview</p>
                  <p className="mt-0.5 font-display text-lg font-semibold">{featured ? shortStation(featured.station.name) : "Loading…"}</p>
                </div>
                {featured && <AqiBadge category={featured.category} size="md" />}
              </div>
              <div className="mt-4 grid grid-cols-3 gap-3">
                {[
                  ["Now", fc.data ? fmt.num(fc.data.latest_pm25) : "—"],
                  ["Peak 24 h", fc.data ? fmt.num(fc.data.peak.pm25) : "—"],
                  ["Hours > 60", fc.data ? String(fc.data.hours_above_threshold) : "—"],
                ].map(([k, v]) => (
                  <div key={k} className="rounded-[12px] bg-white/5 px-3 py-2.5"><p className="text-[11px] text-slate-400">{k}</p><p className="font-display text-xl font-semibold tabular">{v}</p></div>
                ))}
              </div>
              <div className="mt-3">
                {fc.error ? <ErrorState compact error={fc.error} /> : fc.isLoading || hist.isLoading || !fc.data ? <ChartSkeleton height={230} /> :
                  <HistoryForecastChart height={230} history={hist.data} forecast={fc.data} forceDark />}
              </div>
              <p className="mt-2 text-[11.5px] text-slate-500">Generated by model {fc.data?.model_version ?? "…"} from the latest observation. Shaded band = 80% prediction interval.</p>
            </div>
          </motion.div>
        </section>

        {/* station ticker */}
        <div className="relative border-t border-white/10 bg-white/[0.02]">
          <div className="mx-auto flex max-w-6xl gap-6 overflow-x-auto px-4 py-4 md:px-6 [scrollbar-width:none]">
            {(current.data?.stations ?? []).filter((x) => x.pm25 !== null).map((x) => (
              <div key={x.station.id} className="flex shrink-0 items-center gap-2 text-[13px]">
                <span className="size-2 rounded-full" style={{ background: categoryColor(x.category) }} />
                <span className="text-slate-300">{shortStation(x.station.name)}</span>
                <span className="font-semibold tabular">{fmt.num(x.pm25)}</span>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* ---------------- capabilities ---------------- */}
      <section id="capabilities" className="mx-auto max-w-6xl px-4 py-20 md:px-6">
        <p className="text-[12.5px] font-semibold uppercase tracking-[0.16em] text-brand-600">Platform</p>
        <h2 className="mt-3 max-w-2xl font-display text-[32px] font-semibold leading-tight tracking-tight">Everything between a sensor reading and a decision.</h2>
        <div className="mt-10 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {CAPABILITIES.map((c, i) => (
            <motion.div key={c.title} initial={{ opacity: 0, y: 12 }} whileInView={{ opacity: 1, y: 0 }} viewport={{ once: true }} transition={{ delay: i * 0.05 }}
              className="group rounded-[18px] border border-line bg-elevated p-6 shadow-card transition hover:-translate-y-0.5 hover:shadow-pop">
              <div className="grid size-10 place-items-center rounded-[12px] bg-brand-50 text-brand-600 transition group-hover:bg-brand-600 group-hover:text-white"><c.icon className="size-5" /></div>
              <h3 className="mt-4 font-display text-[16px] font-semibold">{c.title}</h3>
              <p className="mt-1.5 text-[14px] leading-relaxed text-muted">{c.body}</p>
            </motion.div>
          ))}
        </div>
      </section>

      {/* ---------------- how it works ---------------- */}
      <section id="how" className="border-y border-line bg-subtle/50">
        <div className="mx-auto max-w-6xl px-4 py-20 md:px-6">
          <p className="text-[12.5px] font-semibold uppercase tracking-[0.16em] text-brand-600">How it works</p>
          <h2 className="mt-3 max-w-2xl font-display text-[32px] font-semibold leading-tight tracking-tight">A reproducible pipeline - from raw archive to calibrated forecast.</h2>
          <ol className="mt-10 grid gap-6 md:grid-cols-4">
            {STEPS.map((st, i) => (
              <li key={st.title} className="relative">
                <div className="flex items-center gap-3">
                  <span className="grid size-9 place-items-center rounded-full border border-line-strong bg-elevated font-display text-[13px] font-semibold">{i + 1}</span>
                  <st.icon className="size-5 text-brand-600" />
                </div>
                <h3 className="mt-4 font-display text-[16px] font-semibold">{st.title}</h3>
                <p className="mt-1.5 text-[14px] leading-relaxed text-muted">{st.body}</p>
              </li>
            ))}
          </ol>
          {metrics.data && (
            <div className="mt-12 grid gap-4 rounded-[20px] border border-line bg-elevated p-6 shadow-card md:grid-cols-4">
              {[1, 6, 12, 24].map((h) => {
                const x = m.find((r) => r.model === "XGBoost" && r.horizon === h);
                const p = m.find((r) => r.model === "Persistence" && r.horizon === h);
                return (
                  <div key={h}>
                    <p className="text-[12px] text-muted">+{h} h forecast MAE</p>
                    <p className="mt-1 font-display text-[26px] font-semibold tabular">{fmt.num(x?.mae, 1)} <span className="text-[12px] font-normal text-faint">µg/m³</span></p>
                    <p className="text-[12.5px] text-green-600 dark:text-green-400">{x?.skill_vs_persistence ? `${Math.round(x.skill_vs_persistence * 100)}% better` : ""} than persistence ({fmt.num(p?.mae, 1)})</p>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      </section>

      {/* ---------------- CTA ---------------- */}
      <section className="mx-auto max-w-6xl px-4 py-20 md:px-6">
        <div className="relative overflow-hidden rounded-[28px] bg-[#050b14] px-8 py-14 text-white md:px-14">
          <div className="bg-grid absolute inset-0 opacity-50" />
          <div className="absolute -right-24 -top-24 size-96 rounded-full bg-brand-500/30 blur-[100px]" />
          <div className="relative flex flex-col items-start justify-between gap-8 md:flex-row md:items-center">
            <div>
              <h2 className="font-display text-[30px] font-semibold leading-tight tracking-tight">Plan your day around cleaner air.</h2>
              <p className="mt-2 max-w-lg text-slate-300">Create a free account to set station alerts, personal thresholds and see the cleanest window in tomorrow&apos;s forecast.</p>
            </div>
            <ButtonLink href="/register" size="lg" icon={<ArrowRight className="size-4" />}>Create free account</ButtonLink>
          </div>
        </div>
      </section>
      <Footer />
    </div>
  );
}
