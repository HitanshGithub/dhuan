"""Observed air quality from CPCB and other monitoring stations, via the World Air Quality Index project (aqicn.org).

The bounds endpoint returns only the stations it would draw at one zoom level, so the domain is tiled into 3-degree
boxes and the results merged. Values are the US EPA AQI of the dominant pollutant (PM2.5 almost always, in North India
in winter); `aqi_to_pm25` inverts the PM2.5 breakpoints WAQI uses so the number can sit next to the model's µg/m³.
Attribution: World Air Quality Index project and the originating agencies (CPCB, state boards).
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from urllib.request import Request, urlopen

from .. import geo

URL = "https://api.waqi.info/map/bounds?latlng={s},{w},{n},{e}&networks=all&token={token}"
TILE_DEG = 3.0
USER_AGENT = "dhuan/0.1 (+https://github.com/HitanshGithub/dhuan)"
# US EPA PM2.5 breakpoints as used by WAQI: (aqi_lo, aqi_hi, pm_lo, pm_hi)
PM25_BREAKPOINTS = [(0, 50, 0.0, 12.0), (51, 100, 12.1, 35.4), (101, 150, 35.5, 55.4), (151, 200, 55.5, 150.4),
                    (201, 300, 150.5, 250.4), (301, 400, 250.5, 350.4), (401, 500, 350.5, 500.4)]
CATEGORIES = [(0, "good", "Good", "#4caf50"), (51, "moderate", "Moderate", "#e0c341"), (101, "usg", "Unhealthy for sensitive groups", "#f18a2b"),
              (151, "unhealthy", "Unhealthy", "#e0433d"), (201, "very_unhealthy", "Very unhealthy", "#8f3f97"), (301, "hazardous", "Hazardous", "#7e0023")]


@dataclass
class Station:
    uid: int
    name: str
    lat: float
    lon: float
    aqi: int
    time: str  # as reported by the station, ISO with offset


def aqi_to_pm25(aqi: float) -> float | None:
    for lo, hi, plo, phi in PM25_BREAKPOINTS:
        if lo <= aqi <= hi:
            return round(plo + (aqi - lo) * (phi - plo) / (hi - lo), 1)
    return None


def category(aqi: float) -> dict:
    chosen = CATEGORIES[0]
    for c in CATEGORIES:
        if aqi >= c[0]:
            chosen = c
    return {"key": chosen[1], "label": chosen[2], "color": chosen[3]}


def parse(payload: dict) -> list[Station]:
    out = []
    for item in payload.get("data", []) or []:
        try:
            aqi = int(str(item.get("aqi", "-")).strip())
        except ValueError:
            continue  # "-" means no current data
        lat, lon = float(item["lat"]), float(item["lon"])
        if not geo.in_domain(lon, lat):
            continue
        out.append(Station(uid=int(item["uid"]), name=item.get("station", {}).get("name", "Station"), lat=lat, lon=lon, aqi=aqi,
                           time=item.get("station", {}).get("time", "")))
    return out


def fetch(token: str, timeout: int = 20) -> list[Station]:
    seen: dict[int, Station] = {}
    lat = geo.LAT0
    while lat < geo.LAT1:
        lon = geo.LON0
        while lon < geo.LON1:
            url = URL.format(s=lat, w=lon, n=min(lat + TILE_DEG, geo.LAT1), e=min(lon + TILE_DEG, geo.LON1), token=token)
            with urlopen(Request(url, headers={"User-Agent": USER_AGENT}), timeout=timeout) as resp:
                payload = json.loads(resp.read().decode("utf-8"))
            if payload.get("status") != "ok":
                raise RuntimeError(f"WAQI: {payload.get('data')}")
            for s in parse(payload):
                seen[s.uid] = s
            lon += TILE_DEG
        lat += TILE_DEG
    return sorted(seen.values(), key=lambda s: s.uid)


def to_geojson(stations: list[Station]) -> dict:
    return {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [round(s.lon, 4), round(s.lat, 4)]},
                "properties": {"uid": s.uid, "name": s.name, "aqi": s.aqi, "pm25": aqi_to_pm25(s.aqi), "time": s.time, **category(s.aqi)},
            }
            for s in stations
        ],
    }
