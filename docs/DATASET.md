# Dataset Card

| Field | Value |
|---|---|
| Name | AirSense Pune hourly air quality (processed) |
| Files | `data/processed/hourly_measurements.parquet`, `data/interim/weather_hourly.parquet`, `data/interim/cams_hourly.parquet`, `data/external/stations_pune.json` |
| Period | 18 Feb 2025 – 19 Nov 2026 (UTC) |
| Stations | 10 CAAQMS monitors in Pune and Pimpri-Chinchwad (5 MPCB, 5 IITM/SAFAR) |
| Collected | 22–23 Nov 2026 (see `data/raw/manifest.jsonl` for every URL and timestamp) |
| Licence | Measurements CC BY 4.0 (OpenAQ; originating agencies CPCB/MPCB/IITM). Weather and CAMS CC BY 4.0 (Open-Meteo; ECMWF ERA5 and Copernicus CAMS) |

## Sources
1. **OpenAQ open-data archive**: `https://openaq-data-archive.s3.amazonaws.com/records/csv.gz/locationid=<id>/year=YYYY/month=MM/`.
   One CSV per location per day with columns `location_id, sensors_id, location, datetime (+05:30), lat, lon, parameter, units, value`.
   Station discovery scanned archive IDs 3409000–3410500 and kept locations inside the Pune bbox (73.70–74.05 E, 18.40–18.70 N).
   With an `OPENAQ_API_KEY`, discovery can use the v3 `/locations?bbox=` endpoint instead. That path is implemented but untested, because no key was available.
2. **Open-Meteo Historical Weather API** (ERA5 / ERA5-Land): hourly variables at each station coordinate. The last ~6 days come from the forecast API's `past_days` analysis and are tagged `analysis`.
3. **Open-Meteo Air-Quality API** (`cams_global`): PM2.5/PM10 at the station coordinate. Used only for benchmarking.

## Stations
| OpenAQ ID | Station | Operator | Lat, Lon | PM2.5 hourly coverage | In model |
|---|---|---|---|---|---|
| 3409526 | Panchawati, Pashan | IITM | 18.5365, 73.8055 | 90.5% | ✓ |
| 3409437 | Thergaon, PCMC | MPCB | 18.6163, 73.7658 | 85.4% | ✓ |
| 3409528 | Savta Mali Nagar, PCMC | IITM | 18.6148, 73.7995 | 81.9% | ✓ |
| 3409436 | Park Street Wakad, PCMC | MPCB | 18.5905, 73.7795 | 79.2% | ✓ |
| 3409523 | Bhumkar Nagar | IITM | 18.6058, 73.7500 | 76.5% | ✓ |
| 3409435 | Gavalinagar, PCMC | MPCB | 18.6367, 73.8249 | 76.0% | ✓ |
| 3409438 | Katraj Dairy | MPCB | 18.4545, 73.8542 | 73.8% | ✓ |
| 3409331 | Bhosari | IITM | 18.6401, 73.8490 | 70.9% | ✓ |
| 3410005 | Dhankawadi | IITM | 18.4599, 73.8522 | 61.8% | — |
| 3409439 | Savitribai Phule Pune University | MPCB | 18.5471, 73.8269 | 47.7% | — |

## Processing summary
Timestamps → UTC; duplicates removed; physical bounds; flat-line ≥ 6 h removed; robust-z outliers flagged; hourly mean requires ≥ 2/4 slots;
PM2.5 gaps ≤ 2 h interpolated and marked. Full counts are in `reports/data_quality/`. Nothing is simulated.

## Known issues
* **Units:** OpenAQ labels gases inconsistently (e.g. CO "ppb" with values around 0.8, which match CPCB's mg/m³). Values are kept as reported in CPCB units. Gases are secondary features.
* **Latency:** the archive publishes with a ~3–4 day lag.
* **Station meteorology** (temperature, RH, wind from the CAAQMS) is often stuck or out of range, so ERA5 is used instead.
* The test window contains **Diwali 2026** (8 Nov), with simultaneous PM2.5 near 1,000 µg/m³. These values are kept as genuine.
