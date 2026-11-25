import type { AqiCategory, Pollutant } from "./types";

export const IST = "Asia/Kolkata";

export const AQI_BANDS: { name: AqiCategory; min: number; max: number | null; color: string; advice: string }[] = [
  { name: "Good", min: 0, max: 30, color: "var(--aqi-good)", advice: "Air quality is ideal for outdoor activity." },
  { name: "Satisfactory", min: 30, max: 60, color: "var(--aqi-satisfactory)", advice: "Minor discomfort possible for very sensitive people." },
  { name: "Moderate", min: 60, max: 90, color: "var(--aqi-moderate)", advice: "Sensitive groups should reduce prolonged outdoor exertion." },
  { name: "Poor", min: 90, max: 120, color: "var(--aqi-poor)", advice: "Breathing discomfort for most on prolonged exposure." },
  { name: "Very Poor", min: 120, max: 250, color: "var(--aqi-very-poor)", advice: "Respiratory illness risk on prolonged exposure. Limit outdoor time." },
  { name: "Severe", min: 250, max: null, color: "var(--aqi-severe)", advice: "Affects healthy people; serious risk for those with conditions. Stay indoors." },
];

export const AQI_HEX: Record<AqiCategory, string> = {
  Good: "#2e9e5b", Satisfactory: "#8fbf3f", Moderate: "#e5b53a", Poor: "#ee8a3c", "Very Poor": "#e04f4f", Severe: "#8e2c48",
};

export function categoryOf(pm25: number | null | undefined): AqiCategory | null {
  if (pm25 === null || pm25 === undefined || Number.isNaN(pm25)) return null;
  for (const b of AQI_BANDS) if (b.max === null || pm25 <= b.max) return b.name;
  return "Severe";
}

export function categoryColor(cat: string | null | undefined): string {
  return (cat && AQI_HEX[cat as AqiCategory]) || "#94a3b8";
}

export const POLLUTANT_LABEL: Record<Pollutant, string> = { pm25: "PM2.5", pm10: "PM10", no2: "NO₂", so2: "SO₂", co: "CO", o3: "O₃" };
export const POLLUTANTS: Pollutant[] = ["pm25", "pm10", "no2", "so2", "co", "o3"];

const dtf = (opts: Intl.DateTimeFormatOptions) => new Intl.DateTimeFormat("en-IN", { timeZone: IST, ...opts });
const F = {
  dateTime: dtf({ day: "numeric", month: "short", hour: "2-digit", minute: "2-digit", hour12: false }),
  date: dtf({ day: "numeric", month: "short", year: "numeric" }),
  time: dtf({ hour: "2-digit", minute: "2-digit", hour12: false }),
  monthYear: dtf({ month: "short", year: "numeric" }),
  dayShort: dtf({ weekday: "short", day: "numeric", month: "short" }),
};

export const fmt = {
  dateTime: (s?: string | null) => (s ? `${F.dateTime.format(new Date(s))} IST` : "—"),
  date: (s?: string | null) => (s ? F.date.format(new Date(s)) : "—"),
  time: (s?: string | null) => (s ? F.time.format(new Date(s)) : "—"),
  monthYear: (s?: string | null) => (s ? F.monthYear.format(new Date(s)) : "—"),
  dayShort: (s?: string | null) => (s ? F.dayShort.format(new Date(s)) : "—"),
  num: (v?: number | null, d = 0) => (v === null || v === undefined || Number.isNaN(v) ? "—" : v.toLocaleString("en-IN", { maximumFractionDigits: d, minimumFractionDigits: d })),
  pct: (v?: number | null, d = 0) => (v === null || v === undefined ? "—" : `${(v * 100).toFixed(d)}%`),
  relative: (s?: string | null) => {
    if (!s) return "—";
    const h = (Date.now() - new Date(s).getTime()) / 3_600_000;
    if (h < 1) return `${Math.max(1, Math.round(h * 60))} min ago`;
    if (h < 48) return `${Math.round(h)} h ago`;
    return `${Math.round(h / 24)} days ago`;
  },
};

export function shortStation(name: string): string {
  return name.split(",")[0].replace("_", " ");
}

export function cn(...c: (string | false | null | undefined)[]) {
  return c.filter(Boolean).join(" ");
}
