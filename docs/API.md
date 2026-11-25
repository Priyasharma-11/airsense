# API Specification

Base URL: `/api/v1` · Interactive docs: **`/docs`** (Swagger UI) and `/redoc` · Schema: `/openapi.json` (this file is generated from it).

**Auth:** `POST /auth/login` sets an httpOnly `airsense_token` cookie and returns a JWT. Send it as `Authorization: Bearer <token>` or rely on the cookie. Swagger's *Authorize* button uses `POST /auth/token` (OAuth2 password flow).

**Errors:** every error returns `{"error": {"code", "message", "details"}, "request_id"}` with the matching status: 401 unauthenticated, 403 forbidden, 404 not found, 409 conflict, 422 validation, 429 rate-limited, 503 model unavailable. Every response carries `X-Request-ID`.

**Rate limits:** 120 req/min per IP by default · 10/min on login/register · 5/min on forgot-password · 30/min per-station forecasts.

## Air quality

| Method | Path | Summary | Query params | Access |
|---|---|---|---|---|
| `GET` | `/api/v1/air-quality/current` | Current | — | public |
| `GET` | `/api/v1/air-quality/history` | History | station_id, parameter, start, end, resolution | public |
| `GET` | `/api/v1/air-quality/compare` | Compare | station_ids, parameter, start, end, resolution | public |
| `GET` | `/api/v1/air-quality/records` | Records | station_id, parameter, start, end, page, page_size, sort | public |

## Alerts

| Method | Path | Summary | Query params | Access |
|---|---|---|---|---|
| `GET` | `/api/v1/alerts` | List Alerts | unread_only, page, page_size | user |
| `GET` | `/api/v1/alerts/unread-count` | Unread Count | — | user |
| `POST` | `/api/v1/alerts/{alert_id}/read` | Mark Read | — | user |
| `POST` | `/api/v1/alerts/read-all` | Read All | — | user |
| `DELETE` | `/api/v1/alerts/{alert_id}` | Delete Alert | — | user |
| `GET` | `/api/v1/alerts/rules` | List Rules | — | user |
| `POST` | `/api/v1/alerts/rules` | Create Rule | — | user |
| `PATCH` | `/api/v1/alerts/rules/{rule_id}` | Update Rule | — | user |
| `DELETE` | `/api/v1/alerts/rules/{rule_id}` | Delete Rule | — | user |
| `POST` | `/api/v1/alerts/evaluate` | Evaluate | — | user |

## Analytics

| Method | Path | Summary | Query params | Access |
|---|---|---|---|---|
| `GET` | `/api/v1/analytics/summary` | A Summary | — | public |
| `GET` | `/api/v1/analytics/insights` | A Insights | — | public |
| `GET` | `/api/v1/analytics/diurnal` | A Diurnal | parameter, station_ids, start, end | public |
| `GET` | `/api/v1/analytics/monthly` | A Monthly | parameter, station_ids, start, end | public |
| `GET` | `/api/v1/analytics/heatmap` | A Heatmap | parameter, station_ids, start, end | public |
| `GET` | `/api/v1/analytics/correlation` | A Corr | station_ids, start, end, method | public |
| `GET` | `/api/v1/analytics/distribution` | A Dist | parameter, station_ids, start, end, by | public |
| `GET` | `/api/v1/analytics/station-comparison` | A Compare | parameter, start, end | public |
| `GET` | `/api/v1/analytics/weather-relationship` | A Weather | variable, station_ids, start, end, sample | public |

## Authentication

| Method | Path | Summary | Query params | Access |
|---|---|---|---|---|
| `POST` | `/api/v1/auth/register` | Register | — | public |
| `POST` | `/api/v1/auth/login` | Login | — | public |
| `POST` | `/api/v1/auth/token` | OAuth2 password flow (used by the Swagger 'Authorize' button) | — | public |
| `POST` | `/api/v1/auth/logout` | Logout | — | public |
| `GET` | `/api/v1/auth/me` | Me | — | user |
| `POST` | `/api/v1/auth/forgot-password` | Forgot Password | — | public |
| `POST` | `/api/v1/auth/reset-password` | Reset Password | — | public |

## Data ingestion (admin)

| Method | Path | Summary | Query params | Access |
|---|---|---|---|---|
| `POST` | `/api/v1/ingestion/runs` | Trigger | days | admin |
| `GET` | `/api/v1/ingestion/runs` | Runs | limit | admin |

## Forecasting

| Method | Path | Summary | Query params | Access |
|---|---|---|---|---|
| `GET` | `/api/v1/forecasts/{station_id}` | Forecast | horizon, threshold, refresh | public |
| `GET` | `/api/v1/forecasts` | Next-24 h outlook for every station | — | public |

## Geospatial

| Method | Path | Summary | Query params | Access |
|---|---|---|---|---|
| `GET` | `/api/v1/geo/stations` | GeoJSON FeatureCollection of stations with latest PM2.5 | — | public |
| `GET` | `/api/v1/geo/hotspots` | Geo Hotspots | start, end | public |

## Health

| Method | Path | Summary | Query params | Access |
|---|---|---|---|---|
| `GET` | `/health` | Liveness probe | — | public |
| `GET` | `/health/ready` | Readiness probe: database + model | — | public |

## Metadata

| Method | Path | Summary | Query params | Access |
|---|---|---|---|---|
| `GET` | `/api/v1/meta/aqi-scale` | Aqi Scale | — | public |
| `GET` | `/api/v1/meta/sources` | Sources | — | public |

## Model evaluation

| Method | Path | Summary | Query params | Access |
|---|---|---|---|---|
| `GET` | `/api/v1/models` | List Models | — | public |
| `GET` | `/api/v1/models/active` | Active | — | public |
| `GET` | `/api/v1/models/{version}/metrics` | Metrics | — | public |
| `GET` | `/api/v1/models/{version}/evaluation` | Evaluation | horizon, station_id, days | public |
| `POST` | `/api/v1/models/{version}/activate` | Activate | — | admin |

## Monitoring stations

| Method | Path | Summary | Query params | Access |
|---|---|---|---|---|
| `GET` | `/api/v1/stations` | List Stations | q, city, provider | public |
| `GET` | `/api/v1/stations/nearest` | Nearest | lat, lon, limit | public |
| `GET` | `/api/v1/stations/{station_id}` | Station Detail | — | public |
| `GET` | `/api/v1/stations/{station_id}/latest` | Station Latest | — | public |

## Users

| Method | Path | Summary | Query params | Access |
|---|---|---|---|---|
| `DELETE` | `/api/v1/users/me` | Delete Me | — | user |
| `PATCH` | `/api/v1/users/me` | Update Me | — | user |
| `POST` | `/api/v1/users/me/password` | Change Password | — | user |
| `GET` | `/api/v1/users/me/preferences` | Get Preferences | — | user |
| `PUT` | `/api/v1/users/me/preferences` | Put Preferences | — | user |

## Weather

| Method | Path | Summary | Query params | Access |
|---|---|---|---|---|
| `GET` | `/api/v1/weather/current` | Weather Current | station_id | public |
| `GET` | `/api/v1/weather/history` | Weather History | station_id, start, end | public |

## Example
```bash
curl -s -X POST localhost:8000/api/v1/auth/login -H 'Content-Type: application/json' \
     -d '{"email":"you@example.com","password":"<your password>"}'
curl -s 'localhost:8000/api/v1/forecasts/5?horizon=6&threshold=60' | jq '.points[] | {target_time, pm25, lower, upper, p_exceed}'
```