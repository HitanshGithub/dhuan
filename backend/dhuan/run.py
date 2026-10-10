"""One forecast run, in three steps that map onto the Step Functions state machine.

  fetch     -> runs/<id>/inputs/fires.json, winds.json       (live data, saved so the run is reproducible)
  simulate  -> runs/<id>/meta.json, ug.npy, attr.npz, fires.geojson, img/NN.png, and latest.json
  alerts    -> emails to subscribers whose place is about to get smoky (alerts.py)

Locally `python -m dhuan.run` does all three against the folder in DHUAN_OUT_DIR.
"""

from __future__ import annotations

import io
import json
import logging
import sys
import time
from datetime import datetime, timezone

import numpy as np

from . import geo, model, render
from .calibrate import UG_PER_UNIT, bands
from .config import settings
from .sources import fires as fire_src
from .sources import winds as wind_src
from .storage import get_json, put_json, storage

log = logging.getLogger(__name__)


def run_id_for(now: datetime) -> str:
    return now.strftime("%Y%m%dT%H00Z")


def floor_hour(now: datetime | None = None) -> datetime:
    now = now or datetime.now(timezone.utc)
    return now.astimezone(timezone.utc).replace(minute=0, second=0, microsecond=0)


def step_fetch(run_id: str, store=None) -> dict:
    store = store or storage()
    t0 = time.time()
    fires = fire_src.fetch(settings.firms_window)
    put_json(store, f"runs/{run_id}/inputs/fires.json", [
        {"lat": f.lat, "lon": f.lon, "frp": f.frp, "time": f.time.isoformat(), "daynight": f.daynight,
         "satellites": f.satellites, "detections": f.detections} for f in fires])
    from urllib.request import Request, urlopen

    req = Request(wind_src.request_url(), headers={"User-Agent": wind_src.USER_AGENT})
    with urlopen(req, timeout=60) as resp:
        store.put(f"runs/{run_id}/inputs/winds.json", resp.read())
    n_stations = 0
    if settings.waqi_token:
        try:  # observations are a bonus for the map; never let them stop the forecast
            from .sources import stations as station_src

            observed = station_src.fetch(settings.waqi_token)
            put_json(store, f"runs/{run_id}/stations.geojson", station_src.to_geojson(observed))
            n_stations = len(observed)
        except Exception:
            log.exception("station readings unavailable for run %s", run_id)
    return {"run_id": run_id, "fires": len(fires), "stations": n_stations, "seconds": round(time.time() - t0, 1)}


def load_inputs(run_id: str, store=None):
    store = store or storage()
    raw = get_json(store, f"runs/{run_id}/inputs/fires.json")
    fires = [fire_src.Fire(lat=r["lat"], lon=r["lon"], frp=r["frp"], time=datetime.fromisoformat(r["time"]),
                           daynight=r["daynight"], satellites=r["satellites"], detections=r["detections"]) for r in raw]
    wind = wind_src.from_json(get_json(store, f"runs/{run_id}/inputs/winds.json"))
    return fires, wind


def step_simulate(run_id: str, store=None, now: datetime | None = None, set_latest: bool = True, extra_meta: dict | None = None) -> dict:
    """Simulate a run whose inputs are saved. Replays (dhuan.replay) pass their own `now` and do not become `latest`."""
    store = store or storage()
    t0 = time.time()
    fires, wind = load_inputs(run_id, store)
    now = now or datetime.strptime(run_id, "%Y%m%dT%H00Z").replace(tzinfo=timezone.utc)
    districts = geo.districts()
    if fires:
        ids = districts.lookup(np.array([f.lon for f in fires]), np.array([f.lat for f in fires]))
        for f, d in zip(fires, ids):
            f.district = int(d)
    sim = model.simulate(fire_src.arrays(fires), wind, np.datetime64(now.replace(tzinfo=None), "s"), len(districts.names))
    ug = sim.conc * UG_PER_UNIT

    for i in range(len(sim.times)):
        store.put(f"runs/{run_id}/img/{i:02d}.png", render.to_png(ug[i]))
    buf = io.BytesIO()
    np.save(buf, ug.astype(np.float16))
    store.put(f"runs/{run_id}/ug.npy", buf.getvalue())
    buf = io.BytesIO()
    np.savez_compressed(buf, ids=sim.attr_ids, pct=sim.attr_pct)
    store.put(f"runs/{run_id}/attr.npz", buf.getvalue())
    put_json(store, f"runs/{run_id}/fires.geojson", fire_src.to_geojson(fires, districts))
    # the 100 m wind per frame on the 1-degree grid, so the map can animate the flow that carries the smoke (~100 KB)
    idx = [int(np.clip(round(wind.hour_index(t)), 0, len(wind.times) - 1)) for t in sim.times]
    put_json(store, f"runs/{run_id}/winds.json", {
        "lats": wind.lats.tolist(), "lons": wind.lons.tolist(),
        "u": [np.round(wind.u100[i].astype(float), 1).ravel().tolist() for i in idx],
        "v": [np.round(wind.v100[i].astype(float), 1).ravel().tolist() for i in idx],
    })

    by_state: dict[str, int] = {}
    for f in fires:
        state = districts.names[f.district]["state"] if f.district >= 0 else "Outside India"
        by_state[state] = by_state.get(state, 0) + 1
    exposed = exposure(ug, districts, sim.now_frame)
    meta = {
        "run_id": run_id,
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "times": [str(t) + "Z" for t in sim.times.astype("datetime64[m]")],
        "now_frame": sim.now_frame,
        "bounds": geo.BOUNDS,
        "grid": {"lon0": geo.LON0, "lat0": geo.LAT0, "res": geo.RES, "nx": geo.NX, "ny": geo.NY, "attr_res": geo.ATTR_RES},
        "fires": {"count": len(fires), "assumed_repeat": sim.n_assumed, "by_state": dict(sorted(by_state.items(), key=lambda kv: -kv[1])),
                  "window": settings.firms_window},
        "parcels": sim.n_parcels,
        "frame_max_ug": [round(float(ug[i].max()), 1) for i in range(len(sim.times))],
        "exposure": exposed,
        "bands": bands(),
        "ug_per_unit": UG_PER_UNIT,
        "seconds": round(time.time() - t0, 1),
        "sources": {
            "fires": "NASA FIRMS, VIIRS 375 m (Suomi NPP, NOAA-20, NOAA-21)",
            "winds": "Open-Meteo (CC BY 4.0)",
            "districts": "Census 2011 boundaries via udit-001/india-maps-data",
            "stations": "World Air Quality Index project (CPCB and state boards)" if store.get(f"runs/{run_id}/stations.geojson") else None,
        },
        "has_stations": store.get(f"runs/{run_id}/stations.geojson") is not None,
        **(extra_meta or {}),
    }
    put_json(store, f"runs/{run_id}/meta.json", meta)
    if set_latest:
        put_json(store, "latest.json", {"run_id": run_id, "generated_at": meta["generated_at"], "fires": len(fires), "times": meta["times"],
                                        "now_frame": sim.now_frame, "frame_max_ug": meta["frame_max_ug"]})
        publish_metrics(meta, len(districts.names))
    return {"run_id": run_id, "fires": len(fires), "parcels": sim.n_parcels, "frames": len(sim.times), "seconds": meta["seconds"],
            "heavy_districts_24h": exposed["next_24h"]["heavy"]}


def exposure(ug: np.ndarray, districts: geo.Districts, now_frame: int) -> dict:
    """How many Indian districts sit under moderate (>= 25 ug/m3) or heavy (>= 50) smoke, frame by frame.

    The district raster covers India only, so Pakistan's Punjab is not counted. 'Under smoke' means the district's
    mean estimated farm-fire PM2.5 crosses the band, which understates small hot spots and is deliberately conservative.
    """
    from .calibrate import BANDS

    moderate_from = next(b[0] for b in BANDS if b[1] == "moderate")
    heavy_from = next(b[0] for b in BANDS if b[1] == "heavy")
    mask = districts.grid >= 0
    ids = districts.grid[mask].astype(np.int64)
    n = len(districts.names)
    counts = np.maximum(np.bincount(ids, minlength=n), 1)
    means = np.stack([np.bincount(ids, weights=ug[f][mask].astype(np.float64), minlength=n) / counts for f in range(ug.shape[0])])
    heavy = (means >= heavy_from).sum(axis=1)
    moderate = (means >= moderate_from).sum(axis=1)
    ahead = slice(now_frame, min(now_frame + 25, ug.shape[0]))
    score = heavy[ahead] * 1000 + moderate[ahead]
    peak = now_frame + int(np.argmax(score))
    worst = [int(i) for i in np.argsort(-means[peak]) if means[peak][i] >= moderate_from][:8]
    return {
        "frames": [{"heavy": int(h), "moderate": int(m)} for h, m in zip(heavy, moderate)],
        "next_24h": {"frame": peak, "heavy": int(heavy[peak]), "moderate": int(moderate[peak]),
                     "districts": [{"name": districts.label(i), "ug": round(float(means[peak][i]), 1)} for i in worst]},
        "thresholds": {"moderate": moderate_from, "heavy": heavy_from},
    }


def publish_metrics(meta: dict, n_districts: int) -> None:
    """Operational metrics for the CloudWatch dashboard and alarms; only when deployed, and never fatal."""
    if settings.storage != "s3":
        return
    try:
        import boto3

        now_i = meta["now_frame"]
        data = [
            ("FiresDetected", meta["fires"]["count"], "Count"),
            ("Parcels", meta["parcels"], "Count"),
            ("SimulateSeconds", meta["seconds"], "Seconds"),
            ("MaxUgNow", meta["frame_max_ug"][now_i], "None"),
            ("DistrictsHeavy24h", meta["exposure"]["next_24h"]["heavy"], "Count"),
            ("DistrictsModerate24h", meta["exposure"]["next_24h"]["moderate"], "Count"),
            ("StationsObserved", int(meta.get("has_stations", False)) and len(get_json(storage(), f"runs/{meta['run_id']}/stations.geojson").get("features", [])), "Count"),
        ]
        boto3.client("cloudwatch", region_name=settings.region).put_metric_data(
            Namespace="Dhuan", MetricData=[{"MetricName": name, "Value": float(value), "Unit": unit} for name, value, unit in data])
    except Exception:
        log.exception("could not publish metrics")


def main(argv: list[str]) -> None:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    run_id = run_id_for(floor_hour())
    if "--reuse" in argv:  # simulate again on the most recent saved inputs (handy while tuning the model)
        latest = get_json(storage(), "latest.json")
        if not storage().get(f"runs/{run_id}/inputs/fires.json") and latest:
            run_id = latest["run_id"]
        print("reusing inputs for", run_id)
    else:
        print("fetch:", step_fetch(run_id))
    print("simulate:", step_simulate(run_id))
    print("outputs in", settings.out_dir / "runs" / run_id)


if __name__ == "__main__":
    main(sys.argv[1:])
