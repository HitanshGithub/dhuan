from datetime import datetime, timezone
from pathlib import Path

import numpy as np

from dhuan import geo
from dhuan.sources import fires, winds

FIXTURES = Path(__file__).parent / "fixtures"


def test_parse_firms_keeps_domain_rows_with_times():
    text = (FIXTURES / "firms_snpp_2026-10-08.csv").read_text()
    parsed = fires.parse_csv(text, "Suomi NPP")
    assert len(parsed) > 50
    f = parsed[0]
    assert geo.in_domain(f.lon, f.lat)
    assert f.time.tzinfo is timezone.utc and f.time.year == 2026
    assert f.frp >= 0.5 and f.satellites == ["Suomi NPP"]


def test_merge_collapses_same_field_same_day():
    t = datetime(2026, 10, 8, 8, 0, tzinfo=timezone.utc)
    a = fires.Fire(lat=30.1234, lon=75.5678, frp=5.0, time=t, daynight="D", satellites=["Suomi NPP"])
    b = fires.Fire(lat=30.1241, lon=75.5671, frp=9.0, time=t.replace(hour=7), daynight="D", satellites=["NOAA-20"])
    c = fires.Fire(lat=30.1234, lon=75.5678, frp=5.0, time=t.replace(day=9), daynight="D", satellites=["Suomi NPP"])
    merged = fires.merge([a, b, c])
    assert len(merged) == 2
    same_day = next(m for m in merged if m.time.day == 8)
    assert same_day.frp == 9.0 and same_day.detections == 2 and set(same_day.satellites) == {"Suomi NPP", "NOAA-20"}


def _payload(nlat, nlon, hours, speed=5.0, direction=315.0, pbl=500.0):
    times = [f"2026-10-08T{h:02d}:00" for h in range(hours)]
    return [
        {"hourly": {"time": times, "wind_speed_10m": [speed] * hours, "wind_direction_10m": [direction] * hours,
                    "wind_speed_100m": [speed] * hours, "wind_direction_100m": [direction] * hours,
                    "boundary_layer_height": [pbl] * hours}}
        for _ in range(nlat * nlon)
    ]


def test_wind_from_json_converts_direction_to_components():
    field = winds.from_json(_payload(2, 2, 6), lats=np.array([22.0, 23.0]), lons=np.array([70.0, 71.0]))
    assert field.u100.shape == (6, 2, 2)
    u, v, pbl = field.sample(2.5, np.array([70.5]), np.array([22.5]))
    # a north-westerly (from 315 deg) blows towards the south-east: u > 0, v < 0, equal magnitude
    assert u[0] > 0 and v[0] < 0 and abs(abs(u[0]) - abs(v[0])) < 1e-3
    assert abs(np.hypot(u[0], v[0]) - 5.0) < 1e-3 and abs(pbl[0] - 500.0) < 1e-6


def test_wind_hour_index_and_null_handling():
    payload = _payload(1, 2, 4)
    payload[0]["hourly"]["wind_speed_100m"][1] = None
    field = winds.from_json(payload, lats=np.array([22.0]), lons=np.array([70.0, 71.0]))
    assert np.isfinite(field.u100).all()
    assert field.hour_index(datetime(2026, 10, 8, 3, 30, tzinfo=timezone.utc)) == 3.5
    assert field.hour_index(np.datetime64("2026-10-08T02:00")) == 2.0
