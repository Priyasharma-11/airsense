"use client";

import "leaflet/dist/leaflet.css";
import { CircleMarker, MapContainer, Popup, TileLayer, Tooltip, useMap } from "react-leaflet";
import { useEffect } from "react";
import { useTheme } from "@/components/providers";
import { fmt } from "@/lib/format";

export interface MapPoint {
  id: number;
  name: string;
  lat: number;
  lon: number;
  value: number | null;
  color: string;
  radius: number;
  label: string;
  detail: string;
  ring?: boolean;
}

function FitBounds({ points }: { points: MapPoint[] }) {
  const map = useMap();
  useEffect(() => {
    if (points.length) map.fitBounds(points.map((p) => [p.lat, p.lon] as [number, number]), { padding: [48, 48], maxZoom: 13 });
  }, [map, points]);
  return null;
}

export default function StationMap({ points, selected, onSelect, height = 520 }: {
  points: MapPoint[]; selected?: number; onSelect?: (id: number) => void; height?: number;
}) {
  const { resolved } = useTheme();
  // OpenStreetMap standard tiles (fair-use policy; set NEXT_PUBLIC_TILE_URL for a keyed provider in production).
  // Dark mode re-colours the same tiles with a CSS filter (see .dark .as-map in globals.css).
  const tiles = process.env.NEXT_PUBLIC_TILE_URL ?? "https://tile.openstreetmap.org/{z}/{x}/{y}.png";
  return (
    <div style={{ height }} className="as-map overflow-hidden rounded-[14px]">
      <MapContainer center={[18.55, 73.83]} zoom={11} scrollWheelZoom style={{ height: "100%", width: "100%" }} attributionControl>
        <TileLayer url={tiles} maxZoom={18}
          attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors' />
        <FitBounds points={points} />
        {points.map((p) => (
          <CircleMarker key={p.id} center={[p.lat, p.lon]} radius={p.radius}
            pathOptions={{ color: p.id === selected ? (resolved === "dark" ? "#fff" : "#0b1726") : p.ring ? p.color : "#ffffff",
              weight: p.id === selected ? 3 : 2, fillColor: p.color, fillOpacity: 0.85 }}
            eventHandlers={{ click: () => onSelect?.(p.id) }}>
            <Tooltip direction="top" offset={[0, -p.radius]}>{p.name.split(",")[0]} · {p.label}</Tooltip>
            <Popup>
              <div className="min-w-[180px]">
                <p className="text-[13px] font-semibold">{p.name}</p>
                <p className="mt-1 text-[20px] font-semibold" style={{ color: p.color }}>{p.value === null ? "—" : fmt.num(p.value, 1)} <span className="text-[11px] font-normal opacity-70">µg/m³</span></p>
                <p className="mt-1 text-[12px] opacity-80">{p.detail}</p>
              </div>
            </Popup>
          </CircleMarker>
        ))}
      </MapContainer>
    </div>
  );
}
