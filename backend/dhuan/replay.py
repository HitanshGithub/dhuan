"""Build a replay of a past day, so the forecast can be seen in peak stubble season with thousands of fires.

    uv run python -m dhuan.replay --date 2025-11-09 --title "Peak season, 9 November 2025"

Reads FIRMS_MAP_KEY from the environment or the repository's .env. Fires come from the FIRMS area API (standard-
processing VIIRS products, which cover dates older than about two months), winds from Open-Meteo's ERA5 archive.
The run is written to the configured storage as runs/replay-<date>/ and listed in replays.json; it never becomes
`latest`. Set DHUAN_STORAGE=s3 and DHUAN_BUCKET to publish straight to the deployed bucket.
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from datetime import date, datetime, timedelta, timezone
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import numpy as np

from . import run as run_mod
from .config import settings
from .sources import fires as fire_src
from .sources import winds as wind_src
from .storage import get_json, put_json, storage

log = logging.getLogger(__name__)
SOURCES = {"Suomi NPP": "VIIRS_SNPP_SP", "NOAA-20": "VIIRS_NOAA20_SP", "NOAA-21": "VIIRS_NOAA21_SP"}
AREA = "70,22,88,34"  # west,south,east,north
ARCHIVE_URL = "https://archive-api.open-meteo.com/v1/archive"


def fetch_fires(key: str, day: date) -> list[fire_src.Fire]:
    """The 48 hours ending on `day`: FIRMS counts DAY_RANGE days forward from DATE."""
    start = day - timedelta(days=1)
    fires: list[fire_src.Fire] = []
    for satellite, product in SOURCES.items():
        url = f"https://firms.modaps.eosdis.nasa.gov/api/area/csv/{key}/{product}/{AREA}/2/{start:%Y-%m-%d}"
        text = _download(url)
        if text is None:  # a product may not exist for that date (NOAA-21 started in 2023, SP lags NRT)
            log.warning("%s unavailable for %s", product, start)
            continue
        if text.lower().startswith("invalid") or "latitude" not in text[:200].lower():
            log.warning("%s returned no table for %s: %s", product, start, text[:120])
            continue
        fires += fire_src.parse_csv(text, satellite)
    return fire_src.merge(fires)


def _download(url: str, attempts: int = 3) -> str | None:
    """FIRMS serves multi-megabyte CSVs and sometimes cuts the connection; retry a few times, give up on a 4xx."""
    import http.client
    import time
    from urllib.error import URLError

    for attempt in range(attempts):
        try:
            with urlopen(Request(url, headers={"User-Agent": fire_src.USER_AGENT}), timeout=180) as resp:
                return resp.read().decode("utf-8")
        except HTTPError as exc:
            if 400 <= exc.code < 500:
                return None
            log.warning("attempt %d failed: %s", attempt + 1, exc)
        except (http.client.IncompleteRead, URLError, TimeoutError) as exc:
            log.warning("attempt %d failed: %s", attempt + 1, exc)
        time.sleep(5 * (attempt + 1))
    return None


def fetch_winds_payload(day: date) -> list[dict]:
    grid_lat = np.repeat(wind_src.LATS, len(wind_src.LONS))
    grid_lon = np.tile(wind_src.LONS, len(wind_src.LATS))
    query = (f"latitude={','.join(f'{x:g}' for x in grid_lat)}&longitude={','.join(f'{x:g}' for x in grid_lon)}"
             f"&start_date={day - timedelta(days=2):%Y-%m-%d}&end_date={day + timedelta(days=3):%Y-%m-%d}"
             f"&hourly={','.join(wind_src.HOURLY)}&timezone=UTC&wind_speed_unit=ms")
    with urlopen(Request(f"{ARCHIVE_URL}?{query}", headers={"User-Agent": wind_src.USER_AGENT}), timeout=120) as resp:
        return json.loads(resp.read().decode("utf-8"))


def build(day: date, title: str, store=None) -> dict:
    key = settings.firms_map_key
    if not key:
        raise SystemExit("FIRMS_MAP_KEY is not set (put it in .env); get one at https://firms.modaps.eosdis.nasa.gov/api/map_key/")
    store = store or storage()
    run_id = f"replay-{day:%Y-%m-%d}"
    fires = fetch_fires(key, day)
    print(f"{len(fires)} fires in the 48 h to {day}")
    put_json(store, f"runs/{run_id}/inputs/fires.json", [
        {"lat": f.lat, "lon": f.lon, "frp": f.frp, "time": f.time.isoformat(), "daynight": f.daynight, "satellites": f.satellites,
         "detections": f.detections} for f in fires])
    put_json(store, f"runs/{run_id}/inputs/winds.json", fetch_winds_payload(day))
    now = datetime(day.year, day.month, day.day, 12, tzinfo=timezone.utc)  # 17:30 IST, after the afternoon overpasses
    result = run_mod.step_simulate(run_id, store, now=now, set_latest=False,
                                   extra_meta={"replay": {"date": day.isoformat(), "title": title}})
    replays = [r for r in (get_json(store, "replays.json") or []) if r["run_id"] != run_id]
    replays.append({"run_id": run_id, "date": day.isoformat(), "title": title, "fires": len(fires)})
    put_json(store, "replays.json", sorted(replays, key=lambda r: r["date"], reverse=True))
    return result


def main(argv: list[str]) -> None:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--date", required=True, help="YYYY-MM-DD, the day the replay is centred on")
    parser.add_argument("--title", default=None)
    args = parser.parse_args(argv)
    day = date.fromisoformat(args.date)
    title = args.title or f"Peak season replay, {day.day} {day:%B %Y}"
    print("replay:", build(day, title))


if __name__ == "__main__":
    main(sys.argv[1:])
