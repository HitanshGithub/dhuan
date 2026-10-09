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
    return {"run_id": run_id, "fires": len(fires), "seconds": round(time.time() - t0, 1)}


def load_inputs(run_id: str, store=None):
    store = store or storage()
    raw = get_json(store, f"runs/{run_id}/inputs/fires.json")
    fires = [fire_src.Fire(lat=r["lat"], lon=r["lon"], frp=r["frp"], time=datetime.fromisoformat(r["time"]),
                           daynight=r["daynight"], satellites=r["satellites"], detections=r["detections"]) for r in raw]
    wind = wind_src.from_json(get_json(store, f"runs/{run_id}/inputs/winds.json"))
    return fires, wind


def step_simulate(run_id: str, store=None, now: datetime | None = None) -> dict:
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
        "bands": bands(),
        "ug_per_unit": UG_PER_UNIT,
        "seconds": round(time.time() - t0, 1),
        "sources": {
            "fires": "NASA FIRMS, VIIRS 375 m (Suomi NPP, NOAA-20, NOAA-21)",
            "winds": "Open-Meteo (CC BY 4.0)",
            "districts": "Census 2011 boundaries via udit-001/india-maps-data",
        },
    }
    put_json(store, f"runs/{run_id}/meta.json", meta)
    put_json(store, "latest.json", {"run_id": run_id, "generated_at": meta["generated_at"], "fires": len(fires), "times": meta["times"],
                                    "now_frame": sim.now_frame, "frame_max_ug": meta["frame_max_ug"]})
    return {"run_id": run_id, "fires": len(fires), "parcels": sim.n_parcels, "frames": len(sim.times), "seconds": meta["seconds"]}


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
