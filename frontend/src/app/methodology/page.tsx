"use client";

import { useQuery } from "@tanstack/react-query";
import { AlertTriangle, BookOpen, Database, ExternalLink, FlaskConical, Scale, ShieldCheck, Workflow } from "lucide-react";
import type { ReactNode } from "react";
import { Footer, MarketingNav } from "@/components/layout/marketing";
import { Badge, Card, Skeleton } from "@/components/ui/primitives";
import { api } from "@/lib/api";
import { fmt } from "@/lib/format";

function Section({ id, icon, title, children }: { id: string; icon: ReactNode; title: string; children: ReactNode }) {
  return (
    <section id={id} className="scroll-mt-24">
      <div className="flex items-center gap-3">
        <div className="grid size-9 place-items-center rounded-[10px] bg-brand-50 text-brand-600">{icon}</div>
        <h2 className="font-display text-xl font-semibold tracking-tight">{title}</h2>
      </div>
      <div className="mt-4 space-y-3 text-[14.5px] leading-relaxed text-muted [&_strong]:text-fg">{children}</div>
    </section>
  );
}

const TOC = [["data", "Data sources"], ["cleaning", "Cleaning & validation"], ["features", "Feature engineering"], ["models", "Models & evaluation"],
  ["uncertainty", "Uncertainty & alerts"], ["hotspots", "Hotspots"], ["limitations", "Limitations"]];

export default function MethodologyPage() {
  const sources = useQuery({ queryKey: ["sources"], queryFn: api.sources });
  const summary = useQuery({ queryKey: ["summary"], queryFn: api.summary });
  const model = useQuery({ queryKey: ["model", "active"], queryFn: api.activeModel });
  return (
    <div className="min-h-dvh">
      <MarketingNav />
      <header className="border-b border-line bg-subtle/50">
        <div className="mx-auto max-w-6xl px-4 py-14 md:px-6">
          <Badge tone="brand"><BookOpen className="size-3" /> Methodology & documentation</Badge>
          <h1 className="mt-4 max-w-3xl font-display text-[36px] font-semibold leading-tight tracking-tight">How AirSense turns raw monitoring data into forecasts you can trust.</h1>
          <p className="mt-3 max-w-2xl text-muted">Research question: <em>can historical air-quality measurements, temporal patterns and meteorological information forecast short-term PM2.5 accurately and identify pollution hotspots?</em></p>
          <div className="mt-6 flex flex-wrap gap-2 text-[12.5px]">
            {summary.data ? <>
              <Badge>{fmt.num(summary.data.hourly_records)} hourly PM2.5 records</Badge>
              <Badge>{summary.data.stations} stations</Badge>
              <Badge>{fmt.date(summary.data.period_start)} – {fmt.date(summary.data.period_end)}</Badge>
            </> : <Skeleton className="h-6 w-80" />}
            {model.data && <Badge tone="brand">Model {model.data.version}</Badge>}
          </div>
        </div>
      </header>
      <div className="mx-auto grid max-w-6xl gap-10 px-4 py-12 md:px-6 lg:grid-cols-[200px_1fr]">
        <nav aria-label="On this page" className="hidden lg:block">
          <ul className="sticky top-24 space-y-1 text-[13.5px]">
            {TOC.map(([id, l]) => <li key={id}><a href={`#${id}`} className="block rounded-lg px-3 py-1.5 text-muted hover:bg-subtle hover:text-fg">{l}</a></li>)}
          </ul>
        </nav>
        <article className="max-w-3xl space-y-12">
          <Section id="data" icon={<Database className="size-4" />} title="Data sources">
            <p>All data is genuine and openly licensed. Nothing is simulated; where data is missing it is shown as missing.</p>
            <div className="grid gap-3">
              {sources.isLoading && <Skeleton className="h-32" />}
              {sources.data?.sources.map((s) => (
                <Card key={s.slug} className="p-4">
                  <div className="flex flex-wrap items-center gap-2"><p className="font-semibold text-fg">{s.name}</p><Badge>{s.kind.replace("_", " ")}</Badge><Badge>{s.license}</Badge></div>
                  <p className="mt-1 text-[13.5px]">{s.description}</p>
                  <a href={s.url} target="_blank" rel="noreferrer" className="mt-1 inline-flex items-center gap-1 text-[13px] text-brand-600 hover:underline">{s.url} <ExternalLink className="size-3" /></a>
                </Card>
              ))}
            </div>
            <p>The OpenAQ v3 REST API requires a key, so stations were discovered and downloaded key-free from OpenAQ&apos;s public AWS archive (one gzipped CSV per station per day, 15-minute resolution). Each download is logged with URL, time and size in a provenance manifest.
              {sources.data?.last_ingestion && <> Last ingestion: <strong>{sources.data.last_ingestion.kind}</strong>, {fmt.dateTime(sources.data.last_ingestion.finished_at)}.</>}</p>
            <p>The archive lags real time by a few days, so the &quot;latest&quot; observation in the app is the latest one published. Forecasts are always issued from that observation and labelled with its timestamp.</p>
          </Section>

          <Section id="cleaning" icon={<Workflow className="size-4" />} title="Cleaning & validation">
            <ul className="list-disc space-y-1.5 pl-5">
              <li><strong>Timestamps</strong> are parsed with their +05:30 offsets and stored in UTC; everything is displayed in IST.</li>
              <li><strong>Duplicates</strong> (same parameter and timestamp) are removed.</li>
              <li><strong>Impossible values</strong> outside physical bounds (e.g. PM2.5 &lt; 0 or &gt; 1000 µg/m³) are removed. The raw archive contained PM2.5 values as high as 36,216 µg/m³.</li>
              <li><strong>Flat-lines</strong> - a sensor repeating the same value for ≥ 6 hours - are removed as instrument faults.</li>
              <li><strong>Statistical outliers</strong> (robust z-score &gt; 6 on a 24-hour window) are <em>flagged but kept</em>: Diwali night 2026 pushed PM2.5 near 1,000 µg/m³ at several stations simultaneously. That is real signal.</li>
              <li><strong>Hourly averages</strong> require at least 2 of 4 valid 15-minute readings.</li>
              <li><strong>Gaps</strong> of ≤ 2 hours are linearly interpolated and marked; longer gaps are never filled. Interpolated hours are excluded as forecast targets.</li>
              <li><strong>Station selection</strong>: 8 of 10 stations had ≥ 70% hourly PM2.5 coverage and were used for training; all 10 are shown in the app.</li>
            </ul>
          </Section>

          <Section id="features" icon={<FlaskConical className="size-4" />} title="Feature engineering">
            <p>For each issue hour <em>t</em> the model only sees information available at <em>t</em>: PM2.5 lags (1–168 h), rolling means/std/min/max (3–168 h), 1 h and 24 h trends, other pollutants&apos; current and 24 h means, ERA5 weather (temperature, humidity, wind vector, pressure, rainfall, boundary-layer/mixing height), calendar features of both the issue time and the target time (hour, weekday, month, IMD season, Diwali window). An automated test changes all values after <em>t</em> and asserts that no feature at <em>t</em> changes.</p>
          </Section>

          <Section id="models" icon={<Scale className="size-4" />} title="Models & evaluation">
            <p>Strategy: <strong>direct multi-horizon</strong> - one model per lead time (1–24 h) to avoid recursive error accumulation. Splits are strictly chronological with purging (training rows whose target falls in the next split are dropped): train Feb 2025 – Mar 2026, validation Apr – Jul 2026, test Aug – Nov 2026.</p>
            <p>Candidates: persistence, seasonal-naive (same hour yesterday), linear regression, random forest, XGBoost, SARIMA on daily means, and the Copernicus CAMS physics-based model as an external benchmark. XGBoost predicts either the level or the change from the latest observation; the choice is made per horizon on validation MAE. Metrics: MAE, RMSE, R², skill vs persistence, and precision/recall for exceedance alerts.</p>
            <p>Result: XGBoost beats persistence at every horizon on the hold-out test set, and the station-level ML models are far more accurate than the ~40 km CAMS grid. Random forest performs similarly; XGBoost was deployed for its small artefact size, native missing-value handling and exact SHAP explanations. See the <a className="text-brand-600 hover:underline" href="/models">Model Lab</a> for every number.</p>
          </Section>

          <Section id="uncertainty" icon={<ShieldCheck className="size-4" />} title="Uncertainty & alerts">
            <p>Intervals use <strong>normalised split-conformal prediction</strong>: residuals on the validation window are scaled by recent volatility (24 h standard deviation + 5 µg/m³), so intervals widen in turbulent periods. Empirical 80% coverage on the test set is 77–82% across horizons.</p>
            <p>The same residual distribution gives the probability of exceeding any threshold. Alert rules fire when that probability passes the user&apos;s confidence level; alerts are de-duplicated per pollution episode (± 6 h).</p>
            <p>AQI categories follow the CPCB National AQI breakpoints for PM2.5. Officially the AQI uses 24-hour averages; hourly category labels are indicative.</p>
          </Section>

          <Section id="hotspots" icon={<Database className="size-4" />} title="Hotspots">
            <p>Each station gets a score of 0.5·z(mean PM2.5) + 0.5·z(share of days with a daily mean above 60 µg/m³). Score &gt; 0.75 = hotspot, &gt; 0 = elevated. With ten monitors we deliberately avoid kriging or IDW surfaces, which would suggest spatial precision the network cannot support.</p>
          </Section>

          <Section id="limitations" icon={<AlertTriangle className="size-4" />} title="Limitations">
            <ul className="list-disc space-y-1.5 pl-5">
              <li>~21 months of history - only one complete winter in training; the test window contains a stronger Diwali episode than training did.</li>
              <li>Weather features are ERA5 reanalysis at ~25 km rather than on-site observations; the model uses weather only up to issue time (no NWP forecasts yet).</li>
              <li>OpenAQ unit labels for gaseous pollutants are inconsistent between stations; values are kept in CPCB reporting units and gases are secondary features.</li>
              <li>The data archive lags real time by several days, so the app is a near-real-time demonstrator, not an official advisory.</li>
              <li>Ten monitors cannot resolve street-level variation; hotspots describe monitoring sites, not neighbourhoods.</li>
            </ul>
          </Section>
        </article>
      </div>
      <Footer />
    </div>
  );
}
