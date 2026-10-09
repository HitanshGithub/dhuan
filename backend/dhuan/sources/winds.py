"""Hourly winds and boundary-layer height from Open-Meteo, on a 1-degree grid over the domain.

Open-Meteo (https://open-meteo.com) is free for non-commercial use under CC BY 4.0. One request returns all
247 grid points, two days back and three days ahead, in UTC.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from urllib.request import Request, urlopen

import numpy as np

from .. import geo

LATS = np.arange(geo.LAT0, geo.LAT1 + 0.5, 1.0)  # 22..34
LONS = np.arange(geo.LON0, geo.LON1 + 0.5, 1.0)  # 70..88
URL = "https://api.open-meteo.com/v1/forecast"
HOURLY = ["wind_speed_10m", "wind_direction_10m", "wind_speed_100m", "wind_direction_100m", "boundary_layer_height"]
USER_AGENT = "dhuan/0.1 (+https://github.com/HitanshGithub/dhuan)"


@dataclass
class WindField:
    times: np.ndarray  # datetime64[s], UTC, hourly
    lats: np.ndarray
    lons: np.ndarray
    u100: np.ndarray  # (T, NLAT, NLON) m/s, eastward
    v100: np.ndarray  # northward
    u10: np.ndarray
    v10: np.ndarray
    pbl: np.ndarray  # boundary-layer height, m

    def hour_index(self, when: datetime | np.datetime64) -> float:
        """Fractional position of `when` on the time axis."""
        if isinstance(when, datetime):
            when = np.datetime64(when.astimezone(timezone.utc).replace(tzinfo=None), "s")
        return float((np.datetime64(when, "s") - self.times[0]) / np.timedelta64(3600, "s"))

    def time_at(self, t: float) -> np.datetime64:
        return self.times[0] + np.timedelta64(int(round(t * 3600)), "s")

    def sample(self, t: float, lon: np.ndarray, lat: np.ndarray, level: str = "100m"):
        """Wind (u, v) and boundary-layer height at each point: bilinear in space, linear in time."""
        u, v = (self.u100, self.v100) if level == "100m" else (self.u10, self.v10)
        nt, nlat, nlon = self.pbl.shape
        ti = int(np.clip(np.floor(t), 0, nt - 2))
        wt = float(np.clip(t - ti, 0.0, 1.0))
        fx = (np.asarray(lon) - self.lons[0]) / (self.lons[1] - self.lons[0])
        fy = (np.asarray(lat) - self.lats[0]) / (self.lats[1] - self.lats[0])
        ix = np.clip(np.floor(fx).astype(int), 0, nlon - 2)
        iy = np.clip(np.floor(fy).astype(int), 0, nlat - 2)
        wx = np.clip(fx - ix, 0.0, 1.0)
        wy = np.clip(fy - iy, 0.0, 1.0)

        def bilin(a):
            def at(k):
                return (a[k, iy, ix] * (1 - wx) * (1 - wy) + a[k, iy, ix + 1] * wx * (1 - wy)
                        + a[k, iy + 1, ix] * (1 - wx) * wy + a[k, iy + 1, ix + 1] * wx * wy)
            return at(ti) * (1 - wt) + at(ti + 1) * wt

        return bilin(u), bilin(v), bilin(self.pbl)


def _components(speed, direction):
    """Meteorological direction is where the wind blows FROM; convert to eastward/northward components."""
    rad = np.radians(direction)
    return -speed * np.sin(rad), -speed * np.cos(rad)


def from_json(points: list[dict], lats: np.ndarray = LATS, lons: np.ndarray = LONS) -> WindField:
    """Open-Meteo returns one object per requested point, in request order (latitude-major)."""
    nlat, nlon = len(lats), len(lons)
    assert len(points) == nlat * nlon, f"expected {nlat * nlon} points, got {len(points)}"
    times = np.array([np.datetime64(t, "s") for t in points[0]["hourly"]["time"]])
    nt = len(times)

    def stack(name):
        a = np.array([[float(x) if x is not None else np.nan for x in p["hourly"][name]] for p in points], dtype=np.float32)
        a = a.reshape(nlat, nlon, nt).transpose(2, 0, 1)  # (T, NLAT, NLON)
        fill = float(np.nanmean(a)) if np.isfinite(a).any() else 0.0
        return np.nan_to_num(a, nan=fill)

    s10, d10, s100, d100 = (stack(n) for n in HOURLY[:4])
    pbl = np.clip(stack("boundary_layer_height"), 80.0, 4000.0)
    u10, v10 = _components(s10, d10)
    u100, v100 = _components(s100, d100)
    return WindField(times=times, lats=np.asarray(lats, float), lons=np.asarray(lons, float),
                     u100=u100, v100=v100, u10=u10, v10=v10, pbl=pbl)


def request_url(past_days: int = 2, forecast_days: int = 3) -> str:
    grid_lat = np.repeat(LATS, len(LONS))
    grid_lon = np.tile(LONS, len(LATS))
    lat_list = ",".join(f"{x:g}" for x in grid_lat)
    lon_list = ",".join(f"{x:g}" for x in grid_lon)
    return (f"{URL}?latitude={lat_list}&longitude={lon_list}&hourly={','.join(HOURLY)}"
            f"&past_days={past_days}&forecast_days={forecast_days}&timezone=UTC&wind_speed_unit=ms")


def fetch(past_days: int = 2, forecast_days: int = 3, timeout: int = 60) -> WindField:
    req = Request(request_url(past_days, forecast_days), headers={"User-Agent": USER_AGENT})
    with urlopen(req, timeout=timeout) as resp:
        payload = json.loads(resp.read().decode("utf-8"))
    return from_json(payload)
