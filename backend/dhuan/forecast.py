"""Answer the one question people have: when does the smoke reach *my* place, how bad, and from where."""

from __future__ import annotations

import io
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

import numpy as np

from . import geo
from .calibrate import band_for
from .storage import get_json, storage

IST = timezone(timedelta(hours=5, minutes=30))
_cache: dict[str, "Run"] = {}


@dataclass
class Run:
    meta: dict
    ug: np.ndarray  # (F, NY, NX) float32
    attr_ids: np.ndarray
    attr_pct: np.ndarray
    times: list[datetime]


def latest_run(store=None) -> Run | None:
    store = store or storage()
    latest = get_json(store, "latest.json")
    if not latest:
        return None
    run_id = latest["run_id"]
    if run_id in _cache:
        return _cache[run_id]
    meta = get_json(store, f"runs/{run_id}/meta.json")
    ug = np.load(io.BytesIO(store.get(f"runs/{run_id}/ug.npy"))).astype(np.float32)
    attr = np.load(io.BytesIO(store.get(f"runs/{run_id}/attr.npz")))
    times = [datetime.fromisoformat(t.replace("Z", "+00:00")) for t in meta["times"]]
    run = Run(meta=meta, ug=ug, attr_ids=attr["ids"], attr_pct=attr["pct"], times=times)
    _cache.clear()
    _cache[run_id] = run
    return run


def _ist(t: datetime) -> str:
    """'Saturday 10 Oct, 6 AM': full weekday names, because the advisory model mistranslated abbreviations."""
    return t.astimezone(IST).strftime("%A %d %b, %I %p").replace(" 0", " ").lstrip("0")


def point_forecast(lat: float, lon: float, run: Run | None = None) -> dict | None:
    run = run or latest_run()
    if run is None or not geo.in_domain(lon, lat):
        return None
    ix, iy = geo.to_cell(lon, lat)
    ix, iy = int(ix), int(iy)
    y0, y1, x0, x1 = max(iy - 1, 0), min(iy + 2, geo.NY), max(ix - 1, 0), min(ix + 2, geo.NX)
    series = run.ug[:, y0:y1, x0:x1].mean(axis=(1, 2))  # 3x3 cells, about 15 km, smooths parcel noise
    now_i = run.meta["now_frame"]
    frames = [
        {"time": run.times[i].isoformat(timespec="minutes"), "ist": _ist(run.times[i]), "ug": round(float(series[i]), 1),
         "band": band_for(float(series[i]))["key"], "is_now": i == now_i}
        for i in range(len(series))
    ]
    future = series[now_i:]
    peak_rel = int(np.argmax(future))
    peak_i = now_i + peak_rel
    now_band = band_for(float(series[now_i]))
    light_from = 8.0
    arrival_i = next((now_i + k for k, v in enumerate(future) if v >= light_from), None)
    clear_i = next((peak_i + k for k, v in enumerate(series[peak_i:]) if v < light_from), None)

    # where the smoke over this place in the next 24 hours came from
    aix, aiy = geo.to_cell(lon, lat, geo.ATTR_RES)
    aix, aiy = int(np.clip(aix, 0, geo.ANX - 1)), int(np.clip(aiy, 0, geo.ANY - 1))
    weight: dict[int, float] = {}
    for i in range(now_i, min(now_i + 25, len(series))):
        ids, pct = run.attr_ids[i, aiy, aix], run.attr_pct[i, aiy, aix]
        for d, p in zip(ids.tolist(), pct.tolist()):
            if p > 0:
                weight[d] = weight.get(d, 0.0) + p / 100.0 * float(series[i])
    total = sum(weight.values()) or 1.0
    districts = geo.districts()
    sources = [{"district": districts.label(d), "share": round(w / total, 2)} for d, w in sorted(weight.items(), key=lambda kv: -kv[1])[:4]]

    return {
        "lat": round(lat, 4), "lon": round(lon, 4), "run_id": run.meta["run_id"], "generated_at": run.meta["generated_at"],
        "now": {"time": frames[now_i]["time"], "ist": frames[now_i]["ist"], "ug": frames[now_i]["ug"], **now_band},
        "arrival": None if arrival_i is None or arrival_i == now_i else {"frame": arrival_i, "time": frames[arrival_i]["time"], "ist": frames[arrival_i]["ist"]},
        "peak": {"frame": peak_i, "time": frames[peak_i]["time"], "ist": frames[peak_i]["ist"], "ug": frames[peak_i]["ug"], **band_for(float(series[peak_i]))},
        "clears": None if clear_i is None or clear_i == peak_i else {"frame": clear_i, "time": frames[clear_i]["time"], "ist": frames[clear_i]["ist"]},
        "sources": sources,
        "frames": frames,
        "fires": run.meta["fires"],
        "disclaimer": "Indicative estimate from a smoke-transport model driven by satellite fire detections and forecast winds. Not an official air-quality forecast.",
    }
