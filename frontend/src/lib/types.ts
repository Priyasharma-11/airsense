// Types mirroring the FastAPI response models (backend/airsense/app/schemas.py)

export type Pollutant = "pm25" | "pm10" | "no2" | "so2" | "co" | "o3";
export type AqiCategory = "Good" | "Satisfactory" | "Moderate" | "Poor" | "Very Poor" | "Severe";

export interface Station {
  id: number;
  external_id: string;
  name: string;
  city: string;
  provider: string;
  latitude: number;
  longitude: number;
  is_active: boolean;
  used_in_model: boolean;
  pm25_coverage_pct: number | null;
}

export interface Reading { parameter: Pollutant; value: number | null; unit: string; ts: string | null }

export interface StationLatest {
  station: Station;
  observed_at: string | null;
  pm25: number | null;
  aqi: number | null;
  category: AqiCategory | null;
  readings: Reading[];
  pm25_24h_mean: number | null;
  pm25_change_24h: number | null;
}

export interface CitySummary {
  observed_at: string | null;
  stations_reporting: number;
  stations_total: number;
  pm25_mean: number | null;
  pm25_max: number | null;
  worst_station: Station | null;
  aqi: number | null;
  category: AqiCategory | null;
  data_lag_hours: number | null;
}

export interface CurrentResponse { summary: CitySummary; stations: StationLatest[] }

export interface SeriesPoint { ts: string; value: number | null; n: number | null }
export interface Series {
  station_id: number;
  station_name: string;
  parameter: Pollutant;
  unit: string;
  resolution: "hour" | "day" | "month";
  points: SeriesPoint[];
}

export interface ForecastPoint {
  horizon: number;
  target_time: string;
  pm25: number;
  lower: number;
  upper: number;
  p_exceed: number;
  category: AqiCategory | null;
}

export interface Contribution { feature: string; label: string; value: number | null; contribution: number }

export interface Forecast {
  station: Station;
  model_version: string;
  issued_at: string;
  generated_at: string;
  latest_pm25: number;
  threshold: number;
  interval_level: number;
  points: ForecastPoint[];
  explanations: Record<string, Contribution[]>;
  peak: ForecastPoint;
  hours_above_threshold: number;
  best_window: { start: string; end: string; mean_pm25: number; category: AqiCategory | null } | null;
}

export interface ForecastOverview {
  stations: {
    station_id: number;
    name: string;
    issued_at: string;
    latest_pm25: number;
    peak_pm25: number;
    peak_time: string;
    peak_category: AqiCategory | null;
    max_p_exceed: number;
    sparkline: number[];
  }[];
  unavailable: { station_id: number; name: string; error: string }[];
}

export interface User { id: number; email: string; full_name: string; role: "user" | "admin"; created_at: string; last_login_at: string | null }

export interface Preferences {
  default_station_id: number | null;
  pm25_threshold: number;
  sensitive_group: boolean;
  notify_in_app: boolean;
  notify_email: boolean;
  theme: "light" | "dark" | "system";
}

export interface AlertRule {
  id: number;
  station_id: number;
  name: string;
  threshold: number;
  lookahead_hours: number;
  min_probability: number;
  is_active: boolean;
  created_at: string;
  station: Station;
}

export interface Alert {
  id: number;
  rule_id: number | null;
  station_id: number;
  kind: "forecast_exceedance" | "observed_exceedance";
  severity: string;
  title: string;
  message: string;
  value: number;
  threshold: number;
  probability: number | null;
  target_time: string;
  is_read: boolean;
  created_at: string;
  station: Station;
}

export interface Page<T> { items: T[]; total: number; page: number; page_size: number; pages: number }

export interface MetricRow {
  model: string;
  horizon: number;
  mae: number;
  rmse: number;
  r2: number | null;
  bias: number;
  n: number;
  skill_vs_persistence: number | null;
  interval_coverage_80: number | null;
  alert: { precision: number | null; recall: number | null; f1: number | null; tp: number; fp: number; fn: number; tn: number; threshold: number } | null;
}

export interface ModelMetrics {
  version: string;
  test_window_start: string;
  metrics: MetricRow[];
  target_modes: Record<string, string> | null;
  importance: Record<string, number> | null;
  sarima_daily: {
    mean: Record<string, { mean_mae: number | null }>;
    per_station: Record<string, { n_days: number; sarima: { mae: number }; persistence: { mae: number } }>;
    spec: string;
  } | null;
}

export interface ModelVersion { version: string; algorithm: string; is_active: boolean; trained_at: string; data_hash: string; metrics: Record<string, unknown> | null }

export interface EvaluationSeries {
  version: string;
  horizon: number;
  station_id: number;
  station_name: string;
  available_station_ids: number[];
  mae_window: number | null;
  points: { ts: string; actual: number | null; xgboost: number; lower: number; upper: number; persistence: number; linear: number }[];
  residual_histogram: { bin: number; count: number }[];
}

export interface Insight { id: string; question: string; answer: string; metric: number | null }

export interface Hotspot {
  station_id: number;
  name: string;
  latitude: number;
  longitude: number;
  mean_pm25: number;
  p95_pm25: number | null;
  pct_days_above_threshold: number;
  days_above_threshold: number;
  valid_days: number;
  score: number;
  level: "hotspot" | "elevated" | "typical";
  category: AqiCategory | null;
  rank: number;
}

export interface WeatherNow {
  ts: string;
  temperature_2m: number | null;
  relative_humidity_2m: number | null;
  precipitation: number | null;
  wind_speed_10m: number | null;
  wind_direction_10m: number | null;
  surface_pressure: number | null;
  boundary_layer_height: number | null;
  source_tag: string;
}
