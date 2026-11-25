"use client";

import { AQI_BANDS, categoryColor, cn } from "@/lib/format";
import type { Station } from "@/lib/types";
import { Select } from "@/components/ui/primitives";

/** Semi-circular AQI gauge (SVG). 0-500 index mapped onto CPCB bands. */
export function AqiGauge({ aqi, category, size = 220 }: { aqi: number | null; category: string | null; size?: number }) {
  const r = 80, cx = 100, cy = 96, sw = 14;
  const arc = (from: number, to: number) => {
    const a0 = Math.PI * (1 - from), a1 = Math.PI * (1 - to);
    const p = (a: number) => [cx + r * Math.cos(a), cy - r * Math.sin(a)];
    const [x0, y0] = p(a0), [x1, y1] = p(a1);
    return `M ${x0} ${y0} A ${r} ${r} 0 0 1 ${x1} ${y1}`;
  };
  const stops = [0, 50, 100, 200, 300, 400, 500];
  const v = Math.min(500, Math.max(0, aqi ?? 0)) / 500;
  const needle = Math.PI * (1 - v);
  return (
    <svg viewBox="0 0 200 120" width={size} height={(size * 120) / 200} role="img" aria-label={`AQI ${aqi ?? "unavailable"}, ${category ?? "no data"}`}>
      {AQI_BANDS.map((b, i) => (
        <path key={b.name} d={arc(stops[i] / 500 + 0.004, stops[i + 1] / 500 - 0.004)} stroke={categoryColor(b.name)} strokeWidth={sw}
          fill="none" strokeLinecap="butt" opacity={category === b.name ? 1 : 0.28} />
      ))}
      {aqi !== null && (
        <g style={{ transition: "transform .6s" }}>
          <circle cx={cx + (r) * Math.cos(needle)} cy={cy - r * Math.sin(needle)} r={9} fill="var(--bg-elevated)" stroke={categoryColor(category)} strokeWidth={4} />
        </g>
      )}
      <text x={cx} y={cy - 18} textAnchor="middle" className="fill-[var(--fg)] font-display" style={{ fontSize: 38, fontWeight: 600 }}>{aqi ?? "—"}</text>
      <text x={cx} y={cy + 2} textAnchor="middle" style={{ fontSize: 10.5, fill: "var(--fg-subtle)", letterSpacing: 1 }}>CPCB AQI · PM2.5</text>
    </svg>
  );
}

export function AqiScaleBar({ value }: { value?: number | null }) {
  const max = 300;
  return (
    <div>
      <div className="flex h-2 overflow-hidden rounded-full">
        {AQI_BANDS.map((b) => {
          const w = ((Math.min(b.max ?? max, max) - b.min) / max) * 100;
          return <div key={b.name} style={{ width: `${w}%`, background: categoryColor(b.name) }} title={`${b.name}: ${b.min}–${b.max ?? "+"} µg/m³`} />;
        })}
      </div>
      {value !== undefined && value !== null && (
        <div className="relative h-3">
          <div className="absolute -top-0.5 h-3 w-0.5 rounded bg-fg" style={{ left: `${Math.min(99.5, (value / max) * 100)}%` }} />
        </div>
      )}
      <div className="mt-1 flex justify-between text-[10.5px] text-faint tabular"><span>0</span><span>30</span><span>60</span><span>90</span><span>120</span><span>250+</span></div>
    </div>
  );
}

export function StationSelect({ stations, value, onChange, onlyModel, id = "station", className }: {
  stations: Station[] | undefined; value: number | undefined; onChange: (id: number) => void; onlyModel?: boolean; id?: string; className?: string;
}) {
  const list = (stations ?? []).filter((s) => !onlyModel || s.used_in_model);
  return (
    <Select id={id} aria-label="Monitoring station" value={value ?? ""} onChange={(e) => onChange(Number(e.target.value))} className={cn("min-w-[220px]", className)} disabled={!stations}>
      {!stations && <option>Loading stations…</option>}
      {list.map((s) => <option key={s.id} value={s.id}>{s.name.replace(" - ", " · ")}</option>)}
    </Select>
  );
}

export function Sparkline({ values, color = "var(--brand-500)", width = 96, height = 28 }: { values: number[]; color?: string; width?: number; height?: number }) {
  if (values.length < 2) return null;
  const min = Math.min(...values), max = Math.max(...values), rng = max - min || 1;
  const pts = values.map((v, i) => `${(i / (values.length - 1)) * width},${height - 2 - ((v - min) / rng) * (height - 4)}`).join(" ");
  return (
    <svg width={width} height={height} aria-hidden className="overflow-visible">
      <polyline points={pts} fill="none" stroke={color} strokeWidth={1.75} strokeLinejoin="round" strokeLinecap="round" />
    </svg>
  );
}
