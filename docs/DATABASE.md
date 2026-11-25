# Database Schema

Normalised (3NF) relational model managed by SQLAlchemy 2 + Alembic (`backend/alembic/versions/0001_initial_schema.py`).
On PostgreSQL the migration also enables **PostGIS**. It adds a generated `stations.geom geography(Point,4326)` column with a GiST
index, and a BRIN index on `measurements.ts` (small and well suited to append-only time series).

## ER diagram
```mermaid
erDiagram
  data_sources ||--o{ stations : provides
  data_sources ||--o{ ingestion_runs : "source of"
  stations ||--o{ measurements : records
  stations ||--o{ weather_observations : "weather at"
  stations ||--o{ forecasts : "forecast for"
  model_versions ||--o{ forecasts : produced
  forecasts ||--|{ forecast_points : contains
  ingestion_runs ||--o{ measurements : loaded
  users ||--|| user_preferences : has
  users ||--o{ alert_rules : owns
  users ||--o{ alerts : receives
  users ||--o{ password_reset_tokens : requests
  alert_rules ||--o{ alerts : triggers
  stations ||--o{ alert_rules : watched_by
  stations ||--o{ alerts : about

  stations { int id PK  string external_id  int source_id FK  string name  string city  string provider  float latitude  float longitude  bool used_in_model  float pm25_coverage_pct }
  measurements { bigint id PK  int station_id FK  timestamptz ts  string parameter  float value  string unit  bool is_imputed  bool is_outlier  int ingestion_run_id FK }
  weather_observations { bigint id PK  int station_id FK  timestamptz ts  float temperature_2m  float relative_humidity_2m  float precipitation  float wind_speed_10m  float wind_direction_10m  float surface_pressure  float boundary_layer_height  string source_tag }
  model_versions { int id PK  string version UK  string algorithm  string artifact_path  string data_hash  bool is_active  json metrics }
  forecasts { int id PK  int station_id FK  int model_version_id FK  timestamptz issued_at  float latest_pm25  float interval_scale  json explanations }
  forecast_points { int id PK  int forecast_id FK  int horizon  timestamptz target_time  float pm25  float lower  float upper  float p_exceed  string category }
  users { int id PK  string email UK  string full_name  string hashed_password  string role  bool is_active }
  user_preferences { int user_id PK,FK  int default_station_id FK  float pm25_threshold  bool sensitive_group  bool notify_in_app  bool notify_email  string theme }
  alert_rules { int id PK  int user_id FK  int station_id FK  string name  float threshold  int lookahead_hours  float min_probability  bool is_active }
  alerts { int id PK  int user_id FK  int rule_id FK  int station_id FK  string kind  string severity  string title  text message  float value  float threshold  float probability  timestamptz target_time  bool is_read }
  password_reset_tokens { int id PK  int user_id FK  string token_hash UK  timestamptz expires_at  timestamptz used_at }
  ingestion_runs { int id PK  int source_id FK  string kind  string status  int rows_upserted  json details  int triggered_by_id FK }
  data_sources { int id PK  string slug UK  string name  string url  string license  string kind }
```

## Constraints and indexes
| Table | Integrity | Indexes |
|---|---|---|
| measurements | `UNIQUE(station_id, parameter, ts)` (idempotent upserts) · `CHECK value >= 0` · `CHECK parameter IN (pm25…o3)` · FK cascade | `ix_measurement_param_ts`, BRIN(ts) on PG |
| stations | `UNIQUE(source_id, external_id)` · lat/lon range checks | GiST(geom) on PG |
| forecasts | `UNIQUE(station_id, model_version_id, issued_at)` (forecast cache) | |
| forecast_points | `UNIQUE(forecast_id, horizon)` · `CHECK horizon 1–72` · `CHECK p_exceed 0–1` | forecast_id |
| alerts | `UNIQUE(user_id, station_id, kind, target_time)` · kind check | (user_id, created_at) |
| alert_rules | threshold 0–500 · look-ahead 1–24 · probability 0–1 | user_id |
| users / prefs | unique email · role check · threshold & theme checks | email |

## Notes
* **Long format** for measurements (`parameter` column) keeps the schema stable when pollutants are added. Analytics pivot it in pandas.
* All timestamps are UTC. `UTCDateTime` restores tzinfo on SQLite, which drops it. The UI renders IST.
* Raw 15-minute files are not stored in the DB. They live in `data/raw` with a provenance manifest. The DB holds quality-controlled hourly data plus flags.
* Volumes after seed: ~750 k measurement + weather rows (≈100 MB in SQLite).
