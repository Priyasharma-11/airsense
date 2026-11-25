"""API integration tests: real FastAPI app + database + trained model."""
from __future__ import annotations

import uuid

from tests.conftest import register_and_login

API = "/api/v1"


# ------------------------------------------------------------------ health / errors
def test_health(client):
    assert client.get("/health").json() == {"status": "ok"}
    r = client.get("/health/ready")
    assert r.status_code == 200 and r.json()["checks"]["database"] == "ok"
    assert r.json()["checks"]["model"].startswith("v")


def test_error_envelope_and_request_id(client):
    r = client.get(f"{API}/stations/99999")
    assert r.status_code == 404
    body = r.json()
    assert body["error"]["code"] == "not_found" and body["request_id"] == r.headers["X-Request-ID"]
    assert r.headers["X-Content-Type-Options"] == "nosniff"


# ------------------------------------------------------------------ authentication
def test_register_login_me_logout(client):
    email = f"a-{uuid.uuid4().hex[:6]}@example.com"
    r = client.post(f"{API}/auth/register", json={"email": email, "full_name": "  Ada   Lovelace ", "password": "Secur3pass"})
    assert r.status_code == 201
    assert r.json()["full_name"] == "Ada Lovelace" and "hashed_password" not in r.json()
    r = client.post(f"{API}/auth/login", json={"email": email.upper(), "password": "Secur3pass"})
    assert r.status_code == 200 and "airsense_token" in r.cookies
    me = client.get(f"{API}/auth/me")                      # authenticated via httpOnly cookie
    assert me.status_code == 200 and me.json()["email"] == email
    client.post(f"{API}/auth/logout")
    client.cookies.clear()
    assert client.get(f"{API}/auth/me").status_code == 401


def test_duplicate_registration_conflict(client):
    email = f"d-{uuid.uuid4().hex[:6]}@example.com"
    body = {"email": email, "full_name": "Dup", "password": "Secur3pass"}
    assert client.post(f"{API}/auth/register", json=body).status_code == 201
    assert client.post(f"{API}/auth/register", json=body).status_code == 409


def test_input_validation_rejects_bad_payloads(client):
    bad = [{"email": "not-an-email", "full_name": "X Y", "password": "Secur3pass"},
           {"email": "ok@example.com", "full_name": "X Y", "password": "short1"},
           {"email": "ok@example.com", "full_name": "X Y", "password": "lettersonly"},
           {"email": "ok@example.com", "full_name": "<script>", "password": "Secur3pass"}]
    for b in bad:
        r = client.post(f"{API}/auth/register", json=b)
        assert r.status_code == 422, b
        assert r.json()["error"]["code"] == "validation_error"


def test_wrong_password_and_tampered_token(client):
    email = f"w-{uuid.uuid4().hex[:6]}@example.com"
    register_and_login(client, email)
    assert client.post(f"{API}/auth/login", json={"email": email, "password": "Wrong1234"}).status_code == 401
    assert client.post(f"{API}/auth/login", json={"email": "nobody@example.com", "password": "Wrong1234"}).status_code == 401
    r = client.get(f"{API}/auth/me", headers={"Authorization": "Bearer abc.def.ghi"})
    assert r.status_code == 401


def test_oauth2_token_endpoint_for_swagger(client):
    email = f"s-{uuid.uuid4().hex[:6]}@example.com"
    register_and_login(client, email)
    r = client.post(f"{API}/auth/token", data={"username": email, "password": "Str0ngPass!"})
    assert r.status_code == 200 and r.json()["token_type"] == "bearer"


def test_password_reset_flow(client):
    email = f"r-{uuid.uuid4().hex[:6]}@example.com"
    register_and_login(client, email)
    r = client.post(f"{API}/auth/forgot-password", json={"email": email})
    assert r.status_code == 202
    token = r.json()["dev_reset_token"]
    assert token
    # unknown e-mail -> same response, no token, no enumeration
    r2 = client.post(f"{API}/auth/forgot-password", json={"email": "ghost@example.com"})
    assert r2.status_code == 202 and r2.json()["dev_reset_token"] is None
    assert client.post(f"{API}/auth/reset-password", json={"token": token, "new_password": "N3wPassword"}).status_code == 200
    # one-time use
    assert client.post(f"{API}/auth/reset-password", json={"token": token, "new_password": "N3wPassword2"}).status_code == 422
    assert client.post(f"{API}/auth/login", json={"email": email, "password": "N3wPassword"}).status_code == 200
    client.cookies.clear()


def test_change_password_and_preferences(client, auth_headers, seeded):
    r = client.post(f"{API}/users/me/password", headers=auth_headers,
                    json={"current_password": "wrong", "new_password": "Another1pass"})
    assert r.status_code == 401
    p = client.get(f"{API}/users/me/preferences", headers=auth_headers).json()
    assert p["pm25_threshold"] == 60.0
    sid = next(iter(seeded.values()))
    r = client.put(f"{API}/users/me/preferences", headers=auth_headers,
                   json={"default_station_id": sid, "pm25_threshold": 45, "sensitive_group": True, "theme": "dark"})
    assert r.status_code == 200 and r.json()["pm25_threshold"] == 45
    assert client.put(f"{API}/users/me/preferences", headers=auth_headers,
                      json={"pm25_threshold": 9999}).status_code == 422


# ------------------------------------------------------------------ data
def test_stations_and_search(client):
    r = client.get(f"{API}/stations")
    assert r.status_code == 200 and len(r.json()) == 10
    r = client.get(f"{API}/stations", params={"q": "katraj"})
    assert [s["name"] for s in r.json()] == ["Katraj Dairy, Pune - MPCB"]


def test_current_conditions(client, seeded):
    r = client.get(f"{API}/air-quality/current").json()
    assert r["summary"]["stations_reporting"] == len(seeded)
    reporting = [s for s in r["stations"] if s["pm25"] is not None]
    assert {s["station"]["id"] for s in reporting} == set(seeded.values())
    for s in reporting:
        assert s["category"] in {"Good", "Satisfactory", "Moderate", "Poor", "Very Poor", "Severe"}


def test_history_resolutions_and_validation(client, seeded):
    sid = next(iter(seeded.values()))
    hourly = client.get(f"{API}/air-quality/history", params={"station_id": sid, "resolution": "hour"}).json()
    daily = client.get(f"{API}/air-quality/history", params={"station_id": sid, "resolution": "day"}).json()
    assert len(hourly["points"]) > len(daily["points"]) > 5
    assert hourly["unit"] == "µg/m³"
    r = client.get(f"{API}/air-quality/history", params={"station_id": sid, "start": "2026-11-10", "end": "2026-11-01"})
    assert r.status_code == 422


def test_records_pagination(client, seeded):
    sid = next(iter(seeded.values()))
    p1 = client.get(f"{API}/air-quality/records", params={"station_id": sid, "parameter": "pm25", "page_size": 5}).json()
    p2 = client.get(f"{API}/air-quality/records", params={"station_id": sid, "parameter": "pm25", "page_size": 5,
                                                         "page": 2}).json()
    assert p1["total"] == p2["total"] > 10 and len(p1["items"]) == 5
    assert p1["items"][-1]["ts"] > p2["items"][0]["ts"]
    assert client.get(f"{API}/air-quality/records", params={"page_size": 10000}).status_code == 422


def test_analytics_endpoints(client):
    for path in ("summary", "insights", "diurnal", "monthly", "heatmap", "correlation", "distribution",
                 "station-comparison", "weather-relationship"):
        r = client.get(f"{API}/analytics/{path}")
        assert r.status_code == 200, path
    hm = client.get(f"{API}/analytics/heatmap").json()
    assert len(hm["values"]) == 7 and len(hm["values"][0]) == 24
    corr = client.get(f"{API}/analytics/correlation").json()
    i = corr["variables"].index("pm25")
    assert corr["matrix"][i][i] == 1.0


def test_geo(client, seeded):
    g = client.get(f"{API}/geo/stations").json()
    assert g["type"] == "FeatureCollection" and len(g["features"]) == 10
    lon, lat = g["features"][0]["geometry"]["coordinates"]
    assert 73 < lon < 75 and 18 < lat < 19
    hs = client.get(f"{API}/geo/hotspots").json()
    assert {s["level"] for s in hs["stations"]} <= {"hotspot", "elevated", "typical"}
    near = client.get(f"{API}/stations/nearest", params={"lat": 18.4545, "lon": 73.8542, "limit": 1}).json()
    assert near[0]["station"]["name"].startswith("Katraj") and near[0]["distance_km"] < 0.1


# ------------------------------------------------------------------ forecasting / models
def test_forecast_generated_by_model_and_cached(client, seeded):
    sid = next(iter(seeded.values()))
    r = client.get(f"{API}/forecasts/{sid}")
    assert r.status_code == 200, r.text
    f = r.json()
    assert len(f["points"]) == 24 and f["model_version"].startswith("v")
    assert all(p["lower"] <= p["pm25"] <= p["upper"] for p in f["points"])
    assert f["best_window"] is not None
    again = client.get(f"{API}/forecasts/{sid}").json()
    assert again["generated_at"] == f["generated_at"]          # served from the forecasts table
    short = client.get(f"{API}/forecasts/{sid}", params={"horizon": 6, "threshold": 30}).json()
    assert len(short["points"]) == 6 and short["threshold"] == 30


def test_forecast_unavailable_for_station_without_data(client, seeded):
    stations = client.get(f"{API}/stations").json()
    no_data = next(s for s in stations if s["id"] not in seeded.values())
    r = client.get(f"{API}/forecasts/{no_data['id']}")
    assert r.status_code == 422 and "Not enough" in r.json()["error"]["message"]


def test_model_metrics_and_evaluation(client):
    active = client.get(f"{API}/models/active").json()
    m = client.get(f"{API}/models/{active['version']}/metrics").json()
    models = {r["model"] for r in m["metrics"]}
    assert {"Persistence", "Linear Regression", "Random Forest", "XGBoost"} <= models
    xgb24 = next(r for r in m["metrics"] if r["model"] == "XGBoost" and r["horizon"] == 24)
    p24 = next(r for r in m["metrics"] if r["model"] == "Persistence" and r["horizon"] == 24)
    assert xgb24["mae"] < p24["mae"]                       # the core research claim
    ev = client.get(f"{API}/models/{active['version']}/evaluation", params={"horizon": 24}).json()
    assert len(ev["points"]) > 100 and ev["mae_window"] > 0
    assert client.get(f"{API}/models/{active['version']}/evaluation", params={"horizon": 5}).status_code == 422


def test_activate_model_requires_admin(client, auth_headers):
    active = client.get(f"{API}/models/active").json()["version"]
    assert client.post(f"{API}/models/{active}/activate", headers=auth_headers).status_code == 403
    assert client.post(f"{API}/ingestion/runs", headers=auth_headers).status_code == 403


# ------------------------------------------------------------------ alerts
def test_alert_rules_crud_evaluate_and_isolation(client, seeded):
    a = register_and_login(client, f"alice-{uuid.uuid4().hex[:6]}@example.com")
    b = register_and_login(client, f"bob-{uuid.uuid4().hex[:6]}@example.com")
    sid = next(iter(seeded.values()))
    r = client.post(f"{API}/alerts/rules", headers=a,
                    json={"station_id": sid, "name": "Home", "threshold": 5, "lookahead_hours": 24, "min_probability": 0.1})
    assert r.status_code == 201
    rule = r.json()
    # Bob can neither see nor modify Alice's rule
    assert client.get(f"{API}/alerts/rules", headers=b).json() == []
    assert client.patch(f"{API}/alerts/rules/{rule['id']}", headers=b, json={"threshold": 100}).status_code == 404
    assert client.delete(f"{API}/alerts/rules/{rule['id']}", headers=b).status_code == 404
    # A threshold of 5 ug/m3 is exceeded essentially always -> alerts are created and persisted
    ev = client.post(f"{API}/alerts/evaluate", headers=a).json()
    assert ev["rules_evaluated"] == 1 and ev["alerts_created"] >= 1
    # Re-evaluating is idempotent (episode de-duplication)
    assert client.post(f"{API}/alerts/evaluate", headers=a).json()["alerts_created"] == 0
    lst = client.get(f"{API}/alerts", headers=a).json()
    assert lst["total"] >= 1 and lst["items"][0]["station"]["id"] == sid
    assert client.get(f"{API}/alerts/unread-count", headers=a).json()["unread"] >= 1
    alert_id = lst["items"][0]["id"]
    assert client.post(f"{API}/alerts/{alert_id}/read", headers=b).status_code == 404
    assert client.post(f"{API}/alerts/{alert_id}/read", headers=a).json()["is_read"] is True
    client.post(f"{API}/alerts/read-all", headers=a)
    assert client.get(f"{API}/alerts/unread-count", headers=a).json()["unread"] == 0
    assert client.patch(f"{API}/alerts/rules/{rule['id']}", headers=a, json={"lookahead_hours": 48}).status_code == 422
    assert client.patch(f"{API}/alerts/rules/{rule['id']}", headers=a, json={"is_active": False}).json()["is_active"] is False
    assert client.delete(f"{API}/alerts/{alert_id}", headers=a).status_code == 204
    assert client.delete(f"{API}/alerts/rules/{rule['id']}", headers=a).status_code == 204


def test_alert_rule_for_unknown_station(client, auth_headers):
    r = client.post(f"{API}/alerts/rules", headers=auth_headers, json={"station_id": 4242, "name": "x"})
    assert r.status_code == 404


def test_delete_account(client):
    h = register_and_login(client, f"del-{uuid.uuid4().hex[:6]}@example.com")
    assert client.delete(f"{API}/users/me", headers=h).status_code == 204
    assert client.get(f"{API}/auth/me", headers=h).status_code == 401


def test_rate_limiting(client):
    from airsense.app.core.ratelimit import limiter

    limiter.enabled = True
    limiter.reset()
    try:
        codes = [client.post(f"{API}/auth/login", json={"email": "rl@example.com", "password": "x"}).status_code
                 for _ in range(12)]
        assert 429 in codes
    finally:
        limiter.enabled = False
        limiter.reset()
