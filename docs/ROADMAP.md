# Development Roadmap (2–3 months, solo)

| Phase | Weeks | Deliverables | Status |
|---|---|---|---|
| 0. Research and architecture | 1 | PS analysis, source audit (OpenAQ key-free archive, ERA5, CAMS), stack choice, ADRs | ✅ |
| 1. Data engineering | 1–2 | Station discovery, resilient downloader with manifest, weather/CAMS fetch | ✅ |
| 2. Cleaning and EDA | 2–3 | QC rules + quality log, coverage audit, 8 EDA figures, insights | ✅ |
| 3. Modelling | 3–5 | Leakage-safe features, purged splits, 6 models × 24 horizons, conformal intervals, SHAP, SARIMA track, registry | ✅ |
| 4. Backend | 5–7 | Schema + migrations, auth, 56 endpoints, services, ingestion, alerting | ✅ |
| 5. Frontend | 7–9 | Design system, 14 routes, charts, map, auth flows | ✅ |
| 6. QA | 9–10 | 74 automated tests, visual QA, performance fixes | ✅ |
| 7. DevOps | 10 | Dockerfiles, Compose with PostGIS, CI, Render/Vercel config | ✅ config · 🔐 deploy pending |
| 8. Portfolio | 11 | README, docs, notebooks, presentation outline, resume bullets | ✅ |

## Next iterations
1. **Deploy** (Render + Vercel) and run 2 weeks of scheduled ingestion. Track live forecast error against the hold-out error.
2. **NWP features**: add Open-Meteo forecast weather for t + h (expected to help most at 12–24 h).
3. **Drift monitoring**: rolling 7-day MAE per station on `/models`, with automatic retraining when skill drops below 10%.
4. **Probabilistic models**: quantile XGBoost or NGBoost, compared on CRPS.
5. **More cities**: Mumbai and Delhi through a new bbox and station catalog.
6. **Notifications**: web push and WhatsApp Business API.
