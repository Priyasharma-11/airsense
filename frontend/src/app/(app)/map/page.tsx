"use client";

import { useQuery } from "@tanstack/react-query";
import { Crosshair, Flame, LocateFixed, MapPinned, Navigation } from "lucide-react";
import dynamic from "next/dynamic";
import { useMemo, useState } from "react";
import { toast } from "sonner";
import { AqiBadge, Badge, Button, Card, CardHeader, ErrorState, PageHeader, Segmented, Skeleton } from "@/components/ui/primitives";
import type { MapPoint } from "@/components/map/station-map";
import { api } from "@/lib/api";
import { categoryColor, cn, fmt, shortStation } from "@/lib/format";
import type { Station } from "@/lib/types";

const StationMap = dynamic(() => import("@/components/map/station-map"), { ssr: false, loading: () => <Skeleton className="h-[520px] rounded-[14px]" /> });

const LEVEL_TONE = { hotspot: "danger", elevated: "warning", typical: "success" } as const;

export default function MapPage() {
  const [layer, setLayer] = useState<"current" | "hotspots">("current");
  const [period, setPeriod] = useState("all");
  const [selected, setSelected] = useState<number>();
  const [nearest, setNearest] = useState<{ station: Station; distance_km: number }[]>();
  const [locating, setLocating] = useState(false);
  const geo = useQuery({ queryKey: ["geo-stations"], queryFn: api.geoStations });
  const summary = useQuery({ queryKey: ["summary"], queryFn: api.summary });
  const start = period === "all" || !summary.data ? undefined : new Date(new Date(summary.data.period_end).getTime() - Number(period) * 86400_000).toISOString();
  const hot = useQuery({ queryKey: ["hotspots", start], queryFn: () => api.hotspots({ start }) });

  const points: MapPoint[] = useMemo(() => {
    if (layer === "current") {
      return (geo.data?.features ?? []).map((f) => ({
        id: f.properties.id, name: f.properties.name, lat: f.geometry.coordinates[1], lon: f.geometry.coordinates[0],
        value: f.properties.pm25, color: f.properties.color, radius: 9 + Math.min(14, (f.properties.pm25 ?? 0) / 10),
        label: f.properties.pm25 === null ? "no data" : `${fmt.num(f.properties.pm25)} µg/m³`,
        detail: `${f.properties.category ?? "No data"} · ${fmt.dateTime(f.properties.observed_at)}`,
      }));
    }
    return (hot.data?.stations ?? []).map((s) => ({
      id: s.station_id, name: s.name, lat: s.latitude, lon: s.longitude, value: s.mean_pm25,
      color: s.level === "hotspot" ? "#e04f4f" : s.level === "elevated" ? "#ee8a3c" : "#2e9e5b",
      radius: 8 + Math.max(0, s.score + 2) * 5, ring: true,
      label: `${s.level} · mean ${fmt.num(s.mean_pm25)} µg/m³`,
      detail: `${s.pct_days_above_threshold}% of days above 60 µg/m³ · rank #${s.rank}`,
    }));
  }, [layer, geo.data, hot.data]);

  function locate() {
    if (!("geolocation" in navigator)) return toast.error("Geolocation is not available in this browser.");
    setLocating(true);
    navigator.geolocation.getCurrentPosition(async (pos) => {
      try {
        const r = await api.nearest(pos.coords.latitude, pos.coords.longitude);
        setNearest(r);
        setSelected(r[0]?.station.id);
      } catch (e) {
        toast.error((e as Error).message);
      } finally {
        setLocating(false);
      }
    }, () => { setLocating(false); toast.error("Location permission was denied."); }, { timeout: 10_000 });
  }

  const err = layer === "current" ? geo.error : hot.error;

  return (
    <div>
      <PageHeader title="Geospatial intelligence" description="Station locations, current concentrations and statistically defined pollution hotspots across Pune and Pimpri-Chinchwad."
        actions={<>
          <Segmented label="Map layer" value={layer} onChange={setLayer} options={[{ value: "current", label: "Current PM2.5" }, { value: "hotspots", label: "Hotspots" }]} />
          <Button variant="secondary" onClick={locate} loading={locating} icon={<LocateFixed className="size-4" />}>Nearest to me</Button>
        </>} />

      <div className="grid gap-4 xl:grid-cols-[1fr_380px]">
        <Card className="p-2">
          {err ? <ErrorState error={err} /> : <StationMap points={points} selected={selected} onSelect={setSelected} />}
          <div className="flex flex-wrap items-center gap-3 px-3 py-3 text-[12px] text-muted">
            {layer === "current" ? (
              <>{["Good", "Satisfactory", "Moderate", "Poor", "Very Poor", "Severe"].map((c) => (
                <span key={c} className="inline-flex items-center gap-1.5"><span className="size-2.5 rounded-full" style={{ background: categoryColor(c) }} />{c}</span>
              ))}<span className="ml-auto">Marker size ∝ PM2.5</span></>
            ) : (
              <><span className="inline-flex items-center gap-1.5"><span className="size-2.5 rounded-full bg-[#e04f4f]" />Hotspot</span>
                <span className="inline-flex items-center gap-1.5"><span className="size-2.5 rounded-full bg-[#ee8a3c]" />Elevated</span>
                <span className="inline-flex items-center gap-1.5"><span className="size-2.5 rounded-full bg-[#2e9e5b]" />Typical</span>
                <span className="ml-auto">Marker size ∝ hotspot score</span></>
            )}
          </div>
        </Card>

        <div className="space-y-4">
          {nearest && (
            <Card>
              <CardHeader title="Nearest stations" icon={<Navigation className="size-4" />} subtitle="Great-circle distance from your location (PostGIS in production)" />
              <ul className="space-y-1 px-5 pb-4">
                {nearest.map((n) => (
                  <li key={n.station.id}><button onClick={() => setSelected(n.station.id)} className="flex w-full items-center justify-between rounded-[10px] px-2 py-2 text-left text-[13.5px] hover:bg-subtle">
                    <span className="font-medium">{shortStation(n.station.name)}</span><span className="text-muted tabular">{n.distance_km.toFixed(1)} km</span>
                  </button></li>
                ))}
              </ul>
            </Card>
          )}
          <Card>
            <CardHeader title="Hotspot ranking" icon={<Flame className="size-4" />}
              subtitle={hot.data ? <>City mean {fmt.num(hot.data.city_mean, 1)} µg/m³</> : "Ranking stations by persistent pollution"}
              action={<Segmented size="sm" label="Hotspot period" value={period} onChange={setPeriod} options={[{ value: "all", label: "All" }, { value: "90", label: "90 d" }, { value: "30", label: "30 d" }]} />} />
            {hot.isLoading ? <div className="space-y-2 px-5 pb-5">{[0, 1, 2, 3, 4].map((i) => <Skeleton key={i} className="h-12" />)}</div> : hot.error ? <ErrorState compact error={hot.error} /> : (
              <ol className="space-y-1 px-3 pb-3">
                {hot.data?.stations.map((s) => (
                  <li key={s.station_id}>
                    <button onClick={() => { setSelected(s.station_id); setLayer("hotspots"); }}
                      className={cn("flex w-full items-center gap-3 rounded-[12px] px-2.5 py-2 text-left transition hover:bg-subtle", selected === s.station_id && "bg-subtle ring-1 ring-line")}>
                      <span className="w-5 text-center font-display text-[13px] font-semibold text-faint tabular">{s.rank}</span>
                      <span className="min-w-0 flex-1">
                        <span className="block truncate text-[13.5px] font-medium text-fg">{shortStation(s.name)}</span>
                        <span className="text-[11.5px] text-muted">{s.pct_days_above_threshold}% days &gt; 60 · p95 {fmt.num(s.p95_pm25)}</span>
                      </span>
                      <span className="text-right">
                        <span className="block font-display text-[15px] font-semibold tabular">{fmt.num(s.mean_pm25)}</span>
                        <Badge tone={LEVEL_TONE[s.level]}>{s.level}</Badge>
                      </span>
                    </button>
                  </li>
                ))}
              </ol>
            )}
          </Card>
          <Card className="p-4 text-[12.5px] leading-relaxed text-muted">
            <p className="flex items-center gap-1.5 font-semibold text-fg"><Crosshair className="size-3.5" /> How hotspots are defined</p>
            <p className="mt-1">{hot.data?.method ?? "…"} With only ten monitors we rank stations statistically rather than interpolating a continuous surface, which would imply precision the network can&apos;t support.</p>
          </Card>
          {selected && geo.data && (() => {
            const f = geo.data.features.find((x) => x.properties.id === selected);
            if (!f) return null;
            return (
              <Card className="p-4">
                <div className="flex items-start justify-between"><div><p className="text-[12px] text-muted">Selected</p><p className="font-display font-semibold">{f.properties.name}</p></div><MapPinned className="size-4 text-faint" /></div>
                <div className="mt-3 flex items-center gap-3"><span className="font-display text-2xl font-semibold tabular">{fmt.num(f.properties.pm25, 1)}</span><span className="text-[12px] text-faint">µg/m³</span><AqiBadge category={f.properties.category} /></div>
                <p className="mt-1 text-[12px] text-muted">{fmt.dateTime(f.properties.observed_at)} · {f.geometry.coordinates[1].toFixed(4)}°N, {f.geometry.coordinates[0].toFixed(4)}°E</p>
              </Card>
            );
          })()}
        </div>
      </div>
    </div>
  );
}
