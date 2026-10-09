"""Active-fire detections from NASA FIRMS (VIIRS, 375 m), read from the keyless regional CSV files.

Three satellites carry VIIRS: Suomi NPP, NOAA-20 and NOAA-21. FIRMS publishes each one's last 24 h, 48 h and
7 days of detections over South Asia as a CSV, no API key needed. We merge the three and collapse repeated
detections of the same field on the same day (two satellites pass within an hour of each other).

Attribution, as NASA asks: "We acknowledge the use of data from NASA's Fire Information for Resource Management
System (FIRMS), part of NASA's Earth Science Data and Information System (ESDIS)."
"""

from __future__ import annotations

import csv
import io
from dataclasses import dataclass, field
from datetime import datetime, timezone
from urllib.request import Request, urlopen

import numpy as np

from .. import geo

BASE = "https://firms.modaps.eosdis.nasa.gov/data/active_fire"
FILES = {
    "Suomi NPP": "suomi-npp-viirs-c2/csv/SUOMI_VIIRS_C2_South_Asia_{window}.csv",
    "NOAA-20": "noaa-20-viirs-c2/csv/J1_VIIRS_C2_South_Asia_{window}.csv",
    "NOAA-21": "noaa-21-viirs-c2/csv/J2_VIIRS_C2_South_Asia_{window}.csv",
}
MERGE_CELL_DEG = 0.01  # about 1 km: detections closer than this on the same day are one fire
USER_AGENT = "dhuan/0.1 (+https://github.com/HitanshGithub/dhuan)"


@dataclass
class Fire:
    lat: float
    lon: float
    frp: float  # fire radiative power, MW: how hard it is burning
    time: datetime  # UTC, when the satellite saw it
    daynight: str  # "D" or "N"
    satellites: list[str] = field(default_factory=list)
    detections: int = 1
    district: int = -1


def parse_csv(text: str, satellite: str) -> list[Fire]:
    """Rows inside the domain with nominal or high confidence. Low-confidence pixels are mostly not fires."""
    fires = []
    for row in csv.DictReader(io.StringIO(text)):
        try:
            lat, lon, frp = float(row["latitude"]), float(row["longitude"]), float(row["frp"] or 0)
        except (KeyError, ValueError):
            continue
        if not geo.in_domain(lon, lat) or str(row.get("confidence", "n")).lower()[:1] == "l":
            continue
        hhmm = str(row["acq_time"]).zfill(4)
        when = datetime.strptime(f"{row['acq_date']} {hhmm}", "%Y-%m-%d %H%M").replace(tzinfo=timezone.utc)
        fires.append(Fire(lat=lat, lon=lon, frp=max(frp, 0.5), time=when, daynight=row.get("daynight", "D"), satellites=[satellite]))
    return fires


def merge(fires: list[Fire], cell_deg: float = MERGE_CELL_DEG) -> list[Fire]:
    """One Fire per field per day: keep the strongest detection, remember who else saw it."""
    merged: dict[tuple, Fire] = {}
    for f in fires:
        key = (f.time.date(), round(f.lat / cell_deg), round(f.lon / cell_deg))
        kept = merged.get(key)
        if kept is None:
            merged[key] = Fire(**{**f.__dict__, "satellites": list(f.satellites)})
            continue
        kept.detections += 1
        for s in f.satellites:
            if s not in kept.satellites:
                kept.satellites.append(s)
        if f.frp > kept.frp:
            kept.frp, kept.time, kept.daynight = f.frp, f.time, f.daynight
    return sorted(merged.values(), key=lambda f: f.time)


def fetch(window: str = "48h", timeout: int = 30) -> list[Fire]:
    fires: list[Fire] = []
    for satellite, path in FILES.items():
        req = Request(f"{BASE}/{path.format(window=window)}", headers={"User-Agent": USER_AGENT})
        with urlopen(req, timeout=timeout) as resp:
            fires += parse_csv(resp.read().decode("utf-8"), satellite)
    return merge(fires)


def to_geojson(fires: list[Fire], districts: geo.Districts | None = None) -> dict:
    return {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [round(f.lon, 4), round(f.lat, 4)]},
                "properties": {
                    "frp": round(f.frp, 1),
                    "time": f.time.strftime("%Y-%m-%dT%H:%MZ"),
                    "daynight": f.daynight,
                    "satellites": ", ".join(f.satellites),
                    "detections": f.detections,
                    "district": districts.label(f.district) if districts else None,
                },
            }
            for f in fires
        ],
    }


def arrays(fires: list[Fire]) -> dict[str, np.ndarray]:
    return {
        "lon": np.array([f.lon for f in fires], dtype=np.float64),
        "lat": np.array([f.lat for f in fires], dtype=np.float64),
        "frp": np.array([f.frp for f in fires], dtype=np.float64),
        "time": np.array([np.datetime64(f.time.replace(tzinfo=None), "s") for f in fires]),
        "district": np.array([f.district for f in fires], dtype=np.int16),
    }
