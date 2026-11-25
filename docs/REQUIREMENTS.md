# Project Requirement Specification: AirSense

## 1. Purpose
Turn Pune's official air-quality monitoring data into **understanding** (patterns, hotspots, drivers) and
**foresight** (24-hour PM2.5 forecasts with honest uncertainty and personal alerts).

## 2. Stakeholders
| Stakeholder | Need |
|---|---|
| Citizens, especially sensitive groups | Advance warning; best time to be outdoors |
| Civic bodies (PMC, PCMC, MPCB) | Evidence of persistent hotspots and seasonal episodes |
| Researchers and students | Reproducible pipeline and baselines |
| Recruiters and interviewers | A demonstrable, honest, end-to-end ML product |

## 3. Scope
* **Geography:** Pune + Pimpri-Chinchwad, 10 CAAQMS stations. The architecture is bbox/catalog-driven so more cities can be added.
* **Primary ML task:** PM2.5 forecasting at 1–24 h lead times (hourly). Other pollutants are used as inputs and for analysis.
* **Out of scope:** official advisories, source apportionment, street-level exposure.

## 4. Functional requirements
| ID | Requirement | Status |
|---|---|---|
| F1 | Collect genuine station data (OpenAQ) and compatible weather (ERA5) with provenance | ✅ `ml/data_collection.py`, `data/raw/manifest.jsonl` |
| F2 | Clean data: duplicates, timezones, impossible values, flat-lines, outlier flags, hourly resampling, short-gap-only interpolation, quality log | ✅ `ml/preprocessing.py`, `reports/data_quality/` |
| F3 | EDA with the 8 required visualisations, answering the 6 EDA questions | ✅ `ml/eda.py`, Analytics page, notebook 03 |
| F4 | Leakage-safe features: time, lags (1, 3, 24…), rolling mean/std, weather | ✅ `ml/feature_engineering.py` + leakage test |
| F5 | Compare persistence, linear regression, RF, XGBoost (plus SARIMA and CAMS) on a chronological split with MAE, RMSE, R², actual vs predicted, residuals | ✅ `ml/train.py`, Model Lab |
| F6 | Versioned model artefacts used by the API (no hard-coded predictions) | ✅ `models/registry.json`, `ml/predict.py` |
| F7 | Auth: register, login, logout, password reset, profile, preferences, delete account | ✅ |
| F8 | REST API: current, history, records (paginated), comparisons, stations, analytics, geo/hotspots, forecasts, model evaluation, alerts, ingestion | ✅ 40+ endpoints, OpenAPI at `/docs` |
| F9 | Threshold alerts: user rules, probabilistic evaluation, history, read state | ✅ |
| F10 | Professional responsive UI: landing, auth, dashboard, analytics, forecast, model lab, map, alerts, settings, methodology | ✅ |
| F11 | Incremental ingestion (admin trigger + optional scheduler) | ✅ code path built and unit-tested; live run depends on archive availability |

## 5. Non-functional requirements
| Category | Requirement | Implementation |
|---|---|---|
| Security | Hashed passwords, signed tokens, no secrets in client/repo, CORS, input validation, rate limits, authorisation checks | bcrypt(12), HS256 JWT in httpOnly SameSite=Lax cookie, Pydantic, slowapi, per-user ownership checks, prod secret guard |
| Reliability | Clear errors, health probes, idempotent ingestion | Error envelope with request id, `/health`, `/health/ready`, upserts |
| Performance | p95 < 500 ms for warm dashboard calls | single-flight TTL cache, cache warm-up, GZip, indexed queries (measured warm: 0.2–0.45 s) |
| Accessibility | Keyboard navigable, labelled controls, focus rings, reduced-motion | ARIA radiogroups/switches, skip link, `role=img` charts with labels |
| Reproducibility | Pinned dependencies, deterministic seeds, data hash in model version | `requirements.txt`, `SEED=42`, `vYYYYMMDD-<datahash>` |
| Honesty | Never fabricate data; label lags and limitations | Gaps shown as gaps; Methodology page |

## 6. Acceptance criteria → evidence
See the checklist in [PORTFOLIO.md](PORTFOLIO.md#acceptance-checklist).
