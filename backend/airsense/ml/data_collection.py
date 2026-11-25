"""Data acquisition for AirSense.

Sources (all genuine, documented in docs/DATASET.md):

1. OpenAQ open data archive (AWS Open Data, CC BY 4.0)
   https://openaq-data-archive.s3.amazonaws.com/records/csv.gz/locationid=<id>/year=<y>/month=<m>/
   One gzipped CSV per location per day; no API key required.
   If ``OPENAQ_API_KEY`` is set, the v3 REST API is used for station discovery instead.
2. Open-Meteo Historical Weather API (ERA5 reanalysis, CC BY 4.0) - hourly weather per station.
3. Open-Meteo Air-Quality API (Copernicus CAMS global model, CC BY 4.0) - used ONLY as an
   external benchmark forecast, never as observations.

Raw files are cached byte-for-byte under ``data/raw`` and every run appends to a JSONL manifest
(``data/raw/manifest.jsonl``) recording URL, retrieval time, size and status (data provenance).
"""
from __future__ import annotations

import concurrent.futures as cf
import gzip
import io
import json
import logging
import os
import random
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import asdict, dataclass
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import pandas as pd

from airsense.ml.paths import EXTERNAL_DIR, RAW_DIR

log = logging.getLogger(__name__)

S3_BASE = "https://openaq-data-archive.s3.amazonaws.com"
OPENAQ_API = "https://api.openaq.org/v3"
OPEN_METEO_ARCHIVE = "https://archive-api.open-meteo.com/v1/archive"
OPEN_METEO_FORECAST = "https://api.open-meteo.com/v1/forecast"
OPEN_METEO_AQ = "https://air-quality-api.open-meteo.com/v1/air-quality"
USER_AGENT = "AirSense-research-pipeline/1.0 (+https://github.com/)"

# Pune + Pimpri-Chinchwad bounding box (lon_min, lat_min, lon_max, lat_max)
PUNE_BBOX = (73.70, 18.40, 74.05, 18.70)

WEATHER_VARS = [
    "temperature_2m",
    "relative_humidity_2m",
    "precipitation",
    "wind_speed_10m",
    "wind_direction_10m",
    "surface_pressure",
    "boundary_layer_height",
]


@dataclass
class Station:
    location_id: int
    name: str
    latitude: float
    longitude: float
    provider: str
    city: str
    first_seen: str | None = None


# --------------------------------------------------------------------------------------
# HTTP helpers with retry, exponential backoff + jitter, and rate-limit awareness
# --------------------------------------------------------------------------------------
class FetchError(RuntimeError):
    pass


def http_get(url: str, *, headers: dict | None = None, retries: int = 5, timeout: int = 60) -> bytes:
    if not url.startswith("https://"):
        raise FetchError(f"Refusing non-HTTPS URL: {url}")
    hdrs = {"User-Agent": USER_AGENT, **(headers or {})}
    delay = 1.0
    for attempt in range(1, retries + 1):
        try:
            req = urllib.request.Request(url, headers=hdrs)  # noqa: S310 - scheme checked above
            with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310
                return resp.read()
        except urllib.error.HTTPError as e:
            if e.code == 404:
                raise FetchError(f"404 Not Found: {url}") from e
            if e.code in (429, 500, 502, 503, 504) and attempt < retries:
                retry_after = e.headers.get("Retry-After") if e.headers else None
                wait = float(retry_after) if retry_after and retry_after.isdigit() else delay
                log.warning("HTTP %s on %s; retrying in %.1fs", e.code, url, wait)
                time.sleep(wait + random.uniform(0, 0.5))
                delay = min(delay * 2, 60)
                continue
            raise FetchError(f"HTTP {e.code}: {url}") from e
        except (urllib.error.URLError, TimeoutError, ConnectionError) as e:
            if attempt < retries:
                time.sleep(delay + random.uniform(0, 0.5))
                delay = min(delay * 2, 60)
                continue
            raise FetchError(f"Network error after {retries} attempts: {url}: {e}") from e
    raise FetchError(url)


def _manifest(entry: dict) -> None:
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    entry = {"retrieved_at": datetime.now(UTC).isoformat(), **entry}
    with open(RAW_DIR / "manifest.jsonl", "a", encoding="utf-8") as f:
        f.write(json.dumps(entry) + "\n")


# --------------------------------------------------------------------------------------
# OpenAQ: station discovery
# --------------------------------------------------------------------------------------
def _s3_list(prefix: str, delimiter: str | None = None, start_after: str | None = None, max_keys: int = 1000) -> str:
    q = {"list-type": "2", "prefix": prefix, "max-keys": str(max_keys)}
    if delimiter:
        q["delimiter"] = delimiter
    if start_after:
        q["start-after"] = start_after
    return http_get(f"{S3_BASE}/?{urllib.parse.urlencode(q)}").decode()


def list_archive_keys(location_id: int) -> list[str]:
    """All daily CSV keys for a location in the OpenAQ archive (paginated)."""
    keys: list[str] = []
    token = None
    prefix = f"records/csv.gz/locationid={location_id}/"
    while True:
        q = {"list-type": "2", "prefix": prefix, "max-keys": "1000"}
        if token:
            q["continuation-token"] = token
        xml = http_get(f"{S3_BASE}/?{urllib.parse.urlencode(q)}").decode()
        keys += re.findall(r"<Key>([^<]*)</Key>", xml)
        m = re.search(r"<NextContinuationToken>([^<]*)</NextContinuationToken>", xml)
        if not m:
            break
        token = m.group(1)
    return keys


def discover_stations_via_api(bbox=PUNE_BBOX) -> list[Station]:
    key = os.environ.get("OPENAQ_API_KEY")
    if not key:
        raise FetchError("OPENAQ_API_KEY not set")
    url = f"{OPENAQ_API}/locations?bbox={','.join(map(str, bbox))}&limit=1000"
    data = json.loads(http_get(url, headers={"X-API-Key": key}))
    out = []
    for loc in data.get("results", []):
        c = loc.get("coordinates") or {}
        out.append(Station(loc["id"], loc["name"], c.get("latitude"), c.get("longitude"),
                           (loc.get("provider") or {}).get("name", "unknown"), "Pune"))
    return out


def discover_stations_via_archive(id_ranges: list[tuple[int, int]], bbox=PUNE_BBOX, workers: int = 32) -> list[Station]:
    """Key-less discovery: enumerate archive location prefixes in ID ranges and keep those whose
    first record falls inside ``bbox``. Used because the v3 API requires a key."""
    ids: list[int] = []
    for lo, hi in id_ranges:
        after = f"records/csv.gz/locationid={lo}"
        done = False
        while not done:
            xml = _s3_list("records/csv.gz/locationid=", delimiter="/", start_after=after)
            found = [int(x) for x in re.findall(r"<Prefix>records/csv.gz/locationid=(\d+)/</Prefix>", xml)]
            if not found:
                break
            for i in found:
                if i > hi:
                    done = True
                    break
                if i >= lo:
                    ids.append(i)
            after = f"records/csv.gz/locationid={found[-1]}/~"

    def probe(i: int) -> Station | None:
        try:
            xml = _s3_list(f"records/csv.gz/locationid={i}/", max_keys=1)
            k = re.findall(r"<Key>([^<]*)</Key>", xml)
            if not k:
                return None
            df = pd.read_csv(io.BytesIO(gzip.decompress(http_get(f"{S3_BASE}/{k[0]}"))), nrows=1)
            lat, lon = float(df.lat.iloc[0]), float(df.lon.iloc[0])
            if not (bbox[1] <= lat <= bbox[3] and bbox[0] <= lon <= bbox[2]):
                return None
            raw_name = str(df.location.iloc[0])
            name = re.sub(r"-\d+$", "", raw_name).strip()
            provider = "MPCB" if "MPCB" in name else ("IITM" if "IITM" in name else "CPCB")
            city = "Pimpri-Chinchwad" if "Pimpri" in name else "Pune"
            first = re.search(r"(\d{8})", k[0]).group(1)
            return Station(i, name, lat, lon, provider, city, first_seen=first)
        except FetchError:
            return None

    with cf.ThreadPoolExecutor(workers) as ex:
        stations = [s for s in ex.map(probe, ids) if s]
    return stations


def load_station_catalog() -> list[Station]:
    path = EXTERNAL_DIR / "stations_pune.json"
    return [Station(**s) for s in json.loads(path.read_text(encoding="utf-8"))["stations"]]


def save_station_catalog(stations: list[Station], method: str) -> Path:
    EXTERNAL_DIR.mkdir(parents=True, exist_ok=True)
    path = EXTERNAL_DIR / "stations_pune.json"
    payload = {
        "generated_at": datetime.now(UTC).isoformat(),
        "method": method,
        "source": "OpenAQ (https://openaq.org) - data originally reported by CPCB/MPCB/IITM",
        "license": "CC BY 4.0",
        "bbox": PUNE_BBOX,
        "stations": [asdict(s) for s in sorted(stations, key=lambda s: s.location_id)],
    }
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return path


# --------------------------------------------------------------------------------------
# OpenAQ: measurement download (raw files cached, idempotent)
# --------------------------------------------------------------------------------------
def download_openaq_archive(location_id: int, start: date | None = None, end: date | None = None,
                            workers: int = 16) -> dict:
    keys = list_archive_keys(location_id)
    sel = []
    for k in keys:
        m = re.search(r"(\d{8})\.csv\.gz$", k)
        if not m:
            continue
        d = datetime.strptime(m.group(1), "%Y%m%d").date()
        if (start and d < start) or (end and d > end):
            continue
        sel.append(k)

    dest_root = RAW_DIR / "openaq"
    stats = {"location_id": location_id, "available": len(keys), "selected": len(sel), "downloaded": 0,
             "cached": 0, "failed": 0}

    def fetch(k: str) -> str:
        dest = dest_root / k.replace("records/csv.gz/", "")
        if dest.exists() and dest.stat().st_size > 0:
            return "cached"
        dest.parent.mkdir(parents=True, exist_ok=True)
        try:
            blob = http_get(f"{S3_BASE}/{k}")
            tmp = dest.with_suffix(".part")
            tmp.write_bytes(blob)
            tmp.replace(dest)
            return "downloaded"
        except FetchError as e:
            log.error("failed %s: %s", k, e)
            return "failed"

    with cf.ThreadPoolExecutor(workers) as ex:
        for status in ex.map(fetch, sel):
            stats[status] += 1
    _manifest({"source": "openaq-archive", "location_id": location_id, **stats,
               "url": f"{S3_BASE}/records/csv.gz/locationid={location_id}/"})
    return stats


def read_openaq_raw(location_id: int, since: date | None = None) -> pd.DataFrame:
    root = RAW_DIR / "openaq" / f"locationid={location_id}"
    files = sorted(root.rglob("*.csv.gz"))
    if since is not None:
        files = [f for f in files if (m := re.search(r"(\d{8})\.csv\.gz$", f.name))
                 and datetime.strptime(m.group(1), "%Y%m%d").date() >= since]
    if not files:
        return pd.DataFrame()
    frames = []
    for f in files:
        try:
            frames.append(pd.read_csv(f, compression="gzip", encoding="utf-8", encoding_errors="replace"))
        except Exception as e:  # corrupted file -> skip but record
            log.error("unreadable raw file %s: %s", f, e)
    df = pd.concat(frames, ignore_index=True)
    df["source_file"] = "openaq-archive"
    return df


# --------------------------------------------------------------------------------------
# Open-Meteo weather (ERA5) and CAMS benchmark
# --------------------------------------------------------------------------------------
def _month_chunks(start: date, end: date, months: int = 6):
    cur = start
    while cur <= end:
        nxt = (pd.Timestamp(cur) + pd.DateOffset(months=months)).date() - timedelta(days=1)
        yield cur, min(nxt, end)
        cur = nxt + timedelta(days=1)


def download_weather(station: Station, start: date, end: date) -> pd.DataFrame:
    """Hourly ERA5 weather at the station coordinate. Times are returned in UTC.
    The archive lags real time by ~5 days, so the most recent days come from the forecast API's
    ``past_days`` (analysis) and are flagged in ``weather_source``."""
    frames = []
    archive_end = min(end, date.today() - timedelta(days=6))
    for a, b in _month_chunks(start, archive_end):
        q = {"latitude": station.latitude, "longitude": station.longitude, "start_date": a.isoformat(),
             "end_date": b.isoformat(), "hourly": ",".join(WEATHER_VARS), "timezone": "UTC"}
        url = f"{OPEN_METEO_ARCHIVE}?{urllib.parse.urlencode(q)}"
        raw = http_get(url)
        dest = RAW_DIR / "weather" / f"station={station.location_id}" / f"era5_{a}_{b}.json"
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(raw)
        _manifest({"source": "open-meteo-archive", "location_id": station.location_id, "url": url, "bytes": len(raw)})
        frames.append(_om_frame(json.loads(raw), "era5"))
    if end > archive_end:
        q = {"latitude": station.latitude, "longitude": station.longitude, "past_days": 10, "forecast_days": 2,
             "hourly": ",".join(WEATHER_VARS), "timezone": "UTC"}
        url = f"{OPEN_METEO_FORECAST}?{urllib.parse.urlencode(q)}"
        raw = http_get(url)
        dest = RAW_DIR / "weather" / f"station={station.location_id}" / f"recent_{date.today()}.json"
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(raw)
        _manifest({"source": "open-meteo-forecast", "location_id": station.location_id, "url": url, "bytes": len(raw)})
        frames.append(_om_frame(json.loads(raw), "analysis"))
    df = pd.concat(frames, ignore_index=True)
    df = df.drop_duplicates("datetime_utc", keep="first")  # prefer ERA5 where overlapping
    df["location_id"] = station.location_id
    return df


def _om_frame(payload: dict, tag: str) -> pd.DataFrame:
    h = payload["hourly"]
    df = pd.DataFrame(h).rename(columns={"time": "datetime_utc"})
    df["datetime_utc"] = pd.to_datetime(df["datetime_utc"], utc=True)
    df["weather_source"] = tag
    return df


def download_cams_benchmark(station: Station, start: date, end: date) -> pd.DataFrame:
    """CAMS global PM2.5 (~0.4 deg grid) at the station coordinate via Open-Meteo.
    Used as an external *model* benchmark. Never mixed with observations."""
    frames = []
    for a, b in _month_chunks(start, end, months=3):
        q = {"latitude": station.latitude, "longitude": station.longitude, "start_date": a.isoformat(),
             "end_date": b.isoformat(), "hourly": "pm2_5,pm10", "timezone": "UTC", "domains": "cams_global"}
        url = f"{OPEN_METEO_AQ}?{urllib.parse.urlencode(q)}"
        try:
            raw = http_get(url)
        except FetchError as e:
            log.warning("CAMS chunk failed %s: %s", url, e)
            continue
        dest = RAW_DIR / "cams" / f"station={station.location_id}" / f"cams_{a}_{b}.json"
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(raw)
        _manifest({"source": "open-meteo-cams", "location_id": station.location_id, "url": url, "bytes": len(raw)})
        frames.append(_om_frame(json.loads(raw), "cams_global"))
    if not frames:
        return pd.DataFrame()
    df = pd.concat(frames, ignore_index=True).drop_duplicates("datetime_utc")
    df["location_id"] = station.location_id
    return df.rename(columns={"pm2_5": "cams_pm25", "pm10": "cams_pm10"})


# --------------------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------------------
def main(argv: list[str] | None = None) -> None:
    import argparse

    from airsense.ml.paths import INTERIM_DIR

    p = argparse.ArgumentParser(description="AirSense data collection")
    p.add_argument("--discover", action="store_true", help="re-discover Pune stations")
    p.add_argument("--id-range", nargs=2, type=int, action="append", default=None)
    p.add_argument("--start", type=date.fromisoformat, default=None)
    p.add_argument("--end", type=date.fromisoformat, default=None)
    p.add_argument("--skip-weather", action="store_true")
    p.add_argument("--skip-cams", action="store_true")
    a = p.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

    if a.discover:
        if os.environ.get("OPENAQ_API_KEY"):
            stations, method = discover_stations_via_api(), "openaq-v3-api bbox query"
        else:
            ranges = [tuple(r) for r in (a.id_range or [(3409000, 3410500)])]
            stations, method = discover_stations_via_archive(ranges), f"openaq-archive id-range scan {ranges}"
        path = save_station_catalog(stations, method)
        log.info("discovered %d stations -> %s", len(stations), path)

    stations = load_station_catalog()
    for s in stations:
        stats = download_openaq_archive(s.location_id, a.start, a.end)
        log.info("openaq %s %s", s.name, stats)

    INTERIM_DIR.mkdir(parents=True, exist_ok=True)
    start = a.start or date(2025, 2, 1)
    end = a.end or date.today()
    if not a.skip_weather:
        w = pd.concat([download_weather(s, start, end) for s in stations], ignore_index=True)
        w.to_parquet(INTERIM_DIR / "weather_hourly.parquet", index=False)
        log.info("weather rows: %d", len(w))
    if not a.skip_cams:
        c = pd.concat([download_cams_benchmark(s, start, end) for s in stations], ignore_index=True)
        if len(c):
            c.to_parquet(INTERIM_DIR / "cams_hourly.parquet", index=False)
        log.info("cams rows: %d", len(c))


if __name__ == "__main__":
    main()
