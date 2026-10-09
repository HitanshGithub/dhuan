"""The whole pipeline on synthetic inputs, then the API on top of it."""

import json

import numpy as np
import pytest
from fastapi.testclient import TestClient

from dhuan import run
from dhuan.api import app
from dhuan.sources import winds
from dhuan.storage import storage

RUN_ID = "20261009T1200Z"


@pytest.fixture(scope="module")
def forecast_run():
    """One strong fire cluster in Sangrur with a steady north-westerly, saved as a run's inputs, then simulated."""
    store = storage()
    base = np.datetime64("2026-10-08T00:00")
    hours = 96
    times = [str(base + np.timedelta64(h, "h")) for h in range(hours)]
    n = len(winds.LATS) * len(winds.LONS)
    payload = [{"hourly": {"time": times, "wind_speed_10m": [4.0] * hours, "wind_direction_10m": [315.0] * hours,
                           "wind_speed_100m": [6.0] * hours, "wind_direction_100m": [315.0] * hours,
                           "boundary_layer_height": [300.0 if (h % 24) < 3 or (h % 24) > 13 else 1500.0 for h in range(hours)]}}
               for _ in range(n)]
    store.put(f"runs/{RUN_ID}/inputs/winds.json", json.dumps(payload).encode())
    rng = np.random.default_rng(1)
    fires = [{"lat": float(30.2 + rng.normal(0, 0.1)), "lon": float(75.8 + rng.normal(0, 0.1)), "frp": float(rng.uniform(5, 40)),
              "time": "2026-10-09T08:00:00+00:00", "daynight": "D", "satellites": ["Suomi NPP"], "detections": 1} for _ in range(120)]
    store.put(f"runs/{RUN_ID}/inputs/fires.json", json.dumps(fires).encode())
    return run.step_simulate(RUN_ID, store)


def test_simulate_writes_everything_the_map_needs(forecast_run):
    assert forecast_run["fires"] == 120 and forecast_run["frames"] == 61
    store = storage()
    meta = json.loads(store.get(f"runs/{RUN_ID}/meta.json"))
    assert meta["now_frame"] == 12 and len(meta["times"]) == 61 and meta["fires"]["by_state"].get("Punjab", 0) > 100
    assert store.get(f"runs/{RUN_ID}/img/12.png")[:8] == b"\x89PNG\r\n\x1a\n"
    assert json.loads(store.get("latest.json"))["run_id"] == RUN_ID


def test_api_forecast_downwind_of_the_fires(forecast_run):
    client = TestClient(app)
    assert client.get("/api/health").json()["ok"] is True
    latest = client.get("/api/latest").json()
    assert latest["run_id"] == RUN_ID and latest["data_url"].endswith(f"/runs/{RUN_ID}")

    delhi = client.get("/api/forecast", params={"lat": 28.64, "lon": 77.22}).json()
    assert delhi["peak"]["ug"] > delhi["now"]["ug"]  # the smoke has not arrived yet at the run hour, but it will
    assert delhi["arrival"] is not None and delhi["peak"]["key"] in ("light", "moderate", "heavy", "severe")
    assert delhi["sources"][0]["district"].startswith(("Sangrur", "Barnala", "Patiala", "Ludhiana", "Malerkotla"))
    assert len(delhi["frames"]) == 61 and sum(f["is_now"] for f in delhi["frames"]) == 1

    upwind = client.get("/api/forecast", params={"lat": 32.5, "lon": 74.5}).json()
    assert upwind["peak"]["ug"] < 1.0

    assert client.get("/api/forecast", params={"lat": 12.9, "lon": 77.6}).status_code == 404  # Bengaluru is outside the domain


def test_api_advisory_and_local_subscription(forecast_run):
    client = TestClient(app)
    hi = client.get("/api/advisory", params={"lat": 28.64, "lon": 77.22, "lang": "hi", "label": "Delhi"}).json()
    assert hi["language"] == "hi" and "Delhi" in hi["body"] and "क्या करें" in hi["body"] and hi["generated_by"] == "template"
    pa = client.get("/api/advisory", params={"lat": 28.64, "lon": 77.22, "lang": "pa"}).json()
    assert pa["language"] == "en"  # no model in this build: falls back to the English template

    sub = client.post("/api/subscribe", json={"email": "someone@example.com", "lat": 28.64, "lon": 77.22, "label": "Delhi", "language": "en"})
    assert sub.status_code == 201 and sub.json()["status"] == "subscribed"
    sent = client.post(f"/api/subscribe/{sub.json()['id']}/preview").json()
    assert sent["sent"] is True and sent["subject"].startswith("Dhuan:") and storage().get(sent["ref"]) is not None
    again = client.post("/api/subscribe", json={"email": "Someone@example.com", "lat": 28.645, "lon": 77.215, "label": "Delhi", "language": "hi"})
    assert again.status_code == 201 and again.json()["id"] == sub.json()["id"]  # same person, same place: reused, not duplicated
    assert client.post("/api/subscribe/nope/preview").status_code == 404
    assert client.post("/api/subscribe", json={"email": "not-an-email", "lat": 28.6, "lon": 77.2}).status_code == 422
