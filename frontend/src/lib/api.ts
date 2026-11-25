/**
 * Typed API client. All requests go to the same origin (/api/v1/...) and are proxied by Next.js
 * rewrites to the FastAPI backend, so the httpOnly session cookie is first-party.
 * Errors surface as ApiError - the UI never substitutes fake data.
 */
import type {
  Alert, AlertRule, CurrentResponse, EvaluationSeries, Forecast, ForecastOverview, Hotspot, Insight, ModelMetrics,
  ModelVersion, Page, Pollutant, Preferences, Series, Station, User, WeatherNow,
} from "./types";

export class ApiError extends Error {
  status: number;
  code: string;
  details: unknown;
  requestId?: string;
  constructor(status: number, code: string, message: string, details?: unknown, requestId?: string) {
    super(message);
    this.status = status;
    this.code = code;
    this.details = details;
    this.requestId = requestId;
  }
  /** First field-level validation message, if any */
  get fieldMessage(): string | undefined {
    const d = this.details as { field: string; message: string }[] | undefined;
    return Array.isArray(d) && d.length ? d[0].message.replace(/^Value error, /, "") : undefined;
  }
}

type Query = Record<string, string | number | boolean | undefined | null | (string | number)[]>;

function qs(params?: Query): string {
  if (!params) return "";
  const sp = new URLSearchParams();
  for (const [k, v] of Object.entries(params)) {
    if (v === undefined || v === null || v === "") continue;
    if (Array.isArray(v)) v.forEach((x) => sp.append(k, String(x)));
    else sp.set(k, String(v));
  }
  const s = sp.toString();
  return s ? `?${s}` : "";
}

const BASE = "/api/v1";

export async function request<T>(path: string, init: RequestInit & { query?: Query } = {}): Promise<T> {
  const { query, ...rest } = init;
  let res: Response;
  try {
    res = await fetch(`${BASE}${path}${qs(query)}`, {
      credentials: "same-origin",
      ...rest,
      headers: { Accept: "application/json", ...(rest.body ? { "Content-Type": "application/json" } : {}), ...rest.headers },
    });
  } catch {
    throw new ApiError(0, "network_error", "Cannot reach the AirSense API. Check your connection and try again.");
  }
  if (res.status === 204) return undefined as T;
  const text = await res.text();
  let body: unknown = null;
  try {
    body = text ? JSON.parse(text) : null;
  } catch {
    body = null;
  }
  if (!res.ok) {
    const err = (body as { error?: { code: string; message: string; details?: unknown }; request_id?: string } | null)?.error;
    if (res.status === 429) throw new ApiError(429, "rate_limited", "Too many requests - please wait a moment and retry.");
    throw new ApiError(res.status, err?.code ?? "http_error", err?.message ?? `Request failed (${res.status})`,
      err?.details, (body as { request_id?: string } | null)?.request_id);
  }
  return body as T;
}

const json = (b: unknown) => JSON.stringify(b);

export const api = {
  // auth
  me: () => request<User>("/auth/me"),
  login: (email: string, password: string) => request<{ access_token: string }>("/auth/login", { method: "POST", body: json({ email, password }) }),
  register: (email: string, full_name: string, password: string) =>
    request<User>("/auth/register", { method: "POST", body: json({ email, full_name, password }) }),
  logout: () => request<{ message: string }>("/auth/logout", { method: "POST" }),
  forgotPassword: (email: string) =>
    request<{ message: string; dev_reset_token: string | null }>("/auth/forgot-password", { method: "POST", body: json({ email }) }),
  resetPassword: (token: string, new_password: string) =>
    request<{ message: string }>("/auth/reset-password", { method: "POST", body: json({ token, new_password }) }),
  updateMe: (full_name: string) => request<User>("/users/me", { method: "PATCH", body: json({ full_name }) }),
  changePassword: (current_password: string, new_password: string) =>
    request<{ message: string }>("/users/me/password", { method: "POST", body: json({ current_password, new_password }) }),
  deleteAccount: () => request<void>("/users/me", { method: "DELETE" }),
  preferences: () => request<Preferences>("/users/me/preferences"),
  savePreferences: (p: Preferences) => request<Preferences>("/users/me/preferences", { method: "PUT", body: json(p) }),

  // data
  stations: (q?: string) => request<Station[]>("/stations", { query: { q } }),
  current: () => request<CurrentResponse>("/air-quality/current"),
  history: (station_id: number, parameter: Pollutant, resolution: string, start?: string, end?: string) =>
    request<Series>("/air-quality/history", { query: { station_id, parameter, resolution, start, end } }),
  compare: (station_ids: number[], parameter: Pollutant, resolution: string, start?: string, end?: string) =>
    request<Series[]>("/air-quality/compare", { query: { station_ids, parameter, resolution, start, end } }),
  records: (q: Query) => request<Page<{ ts: string; station_id: number; station_name: string; parameter: Pollutant; value: number; unit: string; is_imputed: boolean; is_outlier: boolean }>>("/air-quality/records", { query: q }),
  weatherNow: (station_id: number) => request<WeatherNow>("/weather/current", { query: { station_id } }),

  // analytics
  summary: () => request<{ period_start: string; period_end: string; hourly_records: number; stations: number; pm25_mean: number; pm25_median: number; pm25_p95: number; pct_hours_above_threshold: number }>("/analytics/summary"),
  insights: () => request<{ insights: Insight[]; generated_from_records: number }>("/analytics/insights"),
  diurnal: (q: Query) => request<{ unit: string; hours: number[]; city: (number | null)[]; stations: { station_id: number; name: string; values: (number | null)[] }[] }>("/analytics/diurnal", { query: q }),
  monthly: (q: Query) => request<{ unit: string; series: { month: string; mean: number | null; p90: number | null; n: number }[]; season_mean: Record<string, number | null> }>("/analytics/monthly", { query: q }),
  heatmap: (q: Query) => request<{ unit: string; days: string[]; hours: number[]; values: (number | null)[][] }>("/analytics/heatmap", { query: q }),
  correlation: (q: Query) => request<{ variables: string[]; labels: string[]; matrix: (number | null)[][]; method: string; n: number }>("/analytics/correlation", { query: q }),
  distribution: (q: Query) => request<{ unit: string; groups: { key: number; label: string; min: number; q1: number; median: number; q3: number; max: number; mean: number; n: number; outliers: number }[]; histogram: { counts: number[]; edges: number[] } }>("/analytics/distribution", { query: q }),
  stationComparison: (q: Query) => request<{ unit: string; threshold: number; stations: { station_id: number; name: string; mean: number | null; median: number | null; p95: number | null; hours: number; pct_hours_above_threshold: number | null; days_above_threshold: number; valid_days: number }[] }>("/analytics/station-comparison", { query: q }),
  weatherRelationship: (q: Query) => request<{ variable: string; label: string; spearman: number | null; resolution: string; points: { x: number; y: number; season: string }[]; binned: { x: number; mean: number; median: number; n: number }[] }>("/analytics/weather-relationship", { query: q }),

  // geo
  geoStations: () => request<GeoJSON.FeatureCollection<GeoJSON.Point, { id: number; name: string; city: string; provider: string; pm25: number | null; aqi: number | null; category: string | null; color: string; observed_at: string | null; used_in_model: boolean }>>("/geo/stations"),
  hotspots: (q?: Query) => request<{ city_mean: number | null; stations: Hotspot[]; method: string }>("/geo/hotspots", { query: q }),
  nearest: (lat: number, lon: number) => request<{ station: Station; distance_km: number }[]>("/stations/nearest", { query: { lat, lon, limit: 3 } }),

  // forecasts / models
  forecast: (station_id: number, q?: Query) => request<Forecast>(`/forecasts/${station_id}`, { query: q }),
  forecastOverview: () => request<ForecastOverview>("/forecasts"),
  models: () => request<ModelVersion[]>("/models"),
  activeModel: () => request<ModelVersion>("/models/active"),
  modelMetrics: (v: string) => request<ModelMetrics>(`/models/${v}/metrics`),
  evaluation: (v: string, q: Query) => request<EvaluationSeries>(`/models/${v}/evaluation`, { query: q }),

  // alerts
  alerts: (q: Query) => request<Page<Alert>>("/alerts", { query: q }),
  unreadCount: () => request<{ unread: number }>("/alerts/unread-count"),
  markRead: (id: number) => request<Alert>(`/alerts/${id}/read`, { method: "POST" }),
  readAll: () => request<{ message: string }>("/alerts/read-all", { method: "POST" }),
  deleteAlert: (id: number) => request<void>(`/alerts/${id}`, { method: "DELETE" }),
  rules: () => request<AlertRule[]>("/alerts/rules"),
  createRule: (b: Omit<AlertRule, "id" | "created_at" | "station">) => request<AlertRule>("/alerts/rules", { method: "POST", body: json(b) }),
  updateRule: (id: number, b: Partial<AlertRule>) => request<AlertRule>(`/alerts/rules/${id}`, { method: "PATCH", body: json(b) }),
  deleteRule: (id: number) => request<void>(`/alerts/rules/${id}`, { method: "DELETE" }),
  evaluate: () => request<{ rules_evaluated: number; alerts_created: number; alerts: Alert[] }>("/alerts/evaluate", { method: "POST" }),

  sources: () => request<{ sources: { slug: string; name: string; url: string; license: string; kind: string; description: string }[]; last_ingestion: { kind: string; finished_at: string; rows: number } | null }>("/meta/sources"),
};
