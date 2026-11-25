# Portfolio Pack

## Portfolio description (≈80 words)
**AirSense** is a full-stack air-quality intelligence platform for Pune. It ingests 4 million real 15-minute readings from 10 government
monitors and runs them through a quality-controlled pipeline. Leakage-safe XGBoost models then forecast PM2.5 up to 24 hours ahead with calibrated uncertainty.
They beat persistence at every lead time and the Copernicus CAMS model by 38%. A FastAPI + PostGIS backend serves forecasts, explanations,
hotspots and personal alerts to a Next.js analytics app. The project has 74 automated tests, Docker and CI.

## Resume bullets
- Built **AirSense**, an end-to-end PM2.5 forecasting platform (Python, FastAPI, PostgreSQL/PostGIS, Next.js/TypeScript) on 4 M real readings from 10 CPCB/MPCB/IITM monitors.
- Engineered a **leakage-safe, purged chronological** pipeline with 24 direct-horizon XGBoost models. The models beat persistence at all horizons (mean MAE skill +29.5%) and were **38% more accurate than the Copernicus CAMS** physics model at +24 h.
- Added **split-conformal prediction intervals** (77–82% empirical coverage at the 80% target) that drive probabilistic threshold alerts, plus **SHAP** explanations for every forecast.
- Designed a normalised schema (13 tables, Alembic, PostGIS GiST/BRIN indexes) and **56 REST endpoints** with JWT httpOnly-cookie auth, rate limiting, a structured error envelope and a single-flight analytics cache.
- Shipped a responsive SaaS UI (14 routes, ECharts, Leaflet, dark mode, WCAG-minded controls) verified by **74 automated tests**: pytest, Vitest/RTL and Playwright E2E on desktop and mobile.

## 10-slide presentation outline
1. **Problem:** Pune's air data is measured but not understood or anticipated. Research question.
2. **Data:** OpenAQ archive (key-free), 10 stations, ERA5 weather, CAMS benchmark. Provenance manifest.
3. **Data quality:** 47k impossible values, 124k stuck-sensor readings, the Diwali reality. Flag, don't delete.
4. **EDA:** December peak (84 µg/m³, 5.2× August); 08:00 IST morning peak; winter ≈ 4× monsoon; the Pimpri-Chinchwad hotspot belt.
5. **Method:** issue-time features, purged chronological splits, direct multi-horizon, level vs delta target.
6. **Results:** horizon-error chart. Wins at 24/24 horizons; RF ties; SARIMA loses; CAMS loses badly.
7. **Uncertainty and alerts:** conformal intervals, exceedance probability, precision/recall vs CAMS.
8. **Product demo:** dashboard → forecast "why" → map hotspots → create alert → evaluate.
9. **Engineering:** architecture diagram, security, tests, CI/Docker.
10. **Limitations and next steps:** archive lag, one winter, NWP features, drift monitoring.

## Technical interview walkthrough (5 minutes)
1. *"I started with the data, not the model."* The OpenAQ API needs a key, so I found the public S3 archive. I wrote a resilient downloader with retries, backoff and a provenance manifest, and discovered stations by scanning archive IDs against a bbox.
2. *"The data was dirty in instructive ways."* PM2.5 values like 36,000 µg/m³, flat-lined sensors and inconsistent unit labels. I removed physically impossible values, flagged statistical outliers and kept them. Diwali spikes near 1,000 µg/m³ appeared at four stations at once, so they were real.
3. *"Leakage was the main risk."* Every feature is computed at issue time *t*. The training rows whose targets cross a split boundary are purged. A unit test perturbs the future and asserts the features don't change.
4. *"Persistence is a strong baseline at 1 hour."* My first XGBoost lost to it on RMSE because trees can't extrapolate to unprecedented spikes. Predicting the delta from the current value fixed that. I then let validation choose level or delta per horizon.
5. *"Point forecasts aren't enough for alerts."* Normalised split-conformal intervals give calibrated bands and exceedance probabilities, so alert rules use probability thresholds. I evaluated alerting as classification and compared it against CAMS.
6. *"Then I productised it."* FastAPI services, PostGIS, versioned model registry with train/serve parity, a same-origin cookie auth design, and a Next.js UI where every number comes from the API.

## Key technical decisions
See [ARCHITECTURE.md §4](ARCHITECTURE.md#4-key-decisions-adr-summary): archive vs API, direct vs recursive, level/delta, conformal, XGBoost vs RF,
SQLite/PostGIS duality, same-origin auth, Cache Components off, statistical hotspots, station-agnostic features.

## Challenges and solutions
| Challenge | Solution |
|---|---|
| OpenAQ v3 requires an API key | Used the public AWS archive; ID-range scan + bbox filter for discovery |
| Windows MAX_PATH broke pyarrow DLL loading | Moved the virtualenv to a short path; documented in the README |
| Trees under-predicted Diwali spikes (RMSE worse than persistence at 1 h) | Delta target + per-horizon target-mode selection on validation |
| Intervals too narrow in volatile periods | Normalised conformal scores (scaled by 24 h σ) |
| SQLite's 32,766 bound-variable limit during seeding | Chunk size derived from column count |
| Cold-start latency under concurrent dashboard requests | Single-flight cache locks + startup warm-up (0.2 s warm) |
| CARTO basemaps started requiring a key | OSM tiles with a CSS dark filter; provider configurable through env |
| Next 16 Cache Components validation on a client dashboard | Disabled it and documented why; still prerendered static shells |
| E2E suite tripped the login rate limiter | Rate limit relaxed only in the E2E environment; 429 covered by a backend test |

## Acceptance checklist
| Criterion | Evidence |
|---|---|
| Professional landing page | `/`: hero with live forecast preview, capabilities, pipeline, CTA, footer |
| All application pages | 14 routes incl. auth (4), dashboard, analytics, forecast, model lab, map, alerts, settings, methodology, 404 |
| Polished, responsive UI | Design system (UI_UX.md); E2E mobile overflow test; light and dark |
| Frontend ↔ backend connected | Same-origin rewrites; E2E full journey |
| Database operational | Alembic migrations; 750k rows seeded; DB tests |
| Real data acquisition | 5,658 OpenAQ files, manifest; ERA5; CAMS |
| Preprocessing pipeline | `preprocessing.py` + quality log + tests |
| Models trained and evaluated | 6 models × horizons; `reports/model_results`; Model Lab |
| Predictions via backend | `/forecasts/{id}` runs `predict.py` on DB data; cached in `forecasts` |
| Interactive visualisations | 15+ ECharts views with filters |
| Geospatial maps | Leaflet, hotspots, nearest (PostGIS on PG) |
| Authentication | Cookie + bearer JWT, reset flow, tests |
| Critical journeys pass | 7/7 Playwright, 45/45 pytest, 22/22 Vitest |
| Security fundamentals | bcrypt, JWT httpOnly, CORS, validation, rate limits, ownership checks, security headers, prod secret guard |
| Deployment configuration | Dockerfiles, Compose, CI, render.yaml |
| Deployed and verified | **Pending:** needs the owner's Render/Vercel accounts (DEPLOYMENT.md) |
| Organised repository and documentation | README + 11 docs + 5 executed notebooks |
