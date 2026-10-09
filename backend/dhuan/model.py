"""Smoke transport: a Lagrangian parcel model driven by the wind field.

Every fire releases parcels of smoke over the hours it burns. Each parcel is carried by the wind at 100 m,
spread by turbulence (a random walk, plus a per-parcel speed and direction offset standing in for wind shear
between heights), and slowly loses mass to deposition. Every hour the parcels are binned onto the grid and
divided by the depth of air they are mixed through: the same smoke trapped in a shallow night-time layer means
dirtier air at the surface, which is why the worst hours are late night and early morning.

Three deliberate simplifications, all stated in the app:
  * Tomorrow's fires are unknown, so fields seen burning in the last 24 hours are assumed to burn again at the
    same hours for the next two days, with less weight each day (a persistence forecast, as operational smoke
    models do).
  * When the boundary layer collapses at dusk, smoke that was mixed through a deep daytime layer does not all
    drop to the ground at once; each parcel's mixing depth relaxes towards the new, shallower layer over hours.
  * This is an indicative transport model, not a chemical-transport forecast. Its output is a relative smoke
    index that is scaled to an estimated PM2.5 contribution (see calibrate.py) and labelled as an estimate.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from . import geo
from .sources.winds import WindField

PARCELS_PER_HOUR = 8  # parcels released per fire per burning hour
BURN_HOURS_BEFORE, BURN_HOURS_AFTER = 3, 4  # a field seen burning at 13:30 IST burns roughly 10:30 to 18:00
DIFFUSION_M2_S = 800.0  # horizontal eddy diffusivity
DECAY_HOURS = 72.0  # e-folding time for deposition and loss out of the mixed layer
SUBSTEPS = 2  # advection sub-steps per hour
PAST_HOURS, AHEAD_HOURS = 12, 48  # frames kept: half a day back, two days ahead
FRP_CAP = 80.0  # MW; VIIRS pixels hotter than this are mostly industrial or merged pixels
TOP_SOURCES = 5
SPEED_JITTER, DIRECTION_JITTER_DEG = 0.25, 15.0
DEPTH_RELAX_HOURS = 6.0  # how quickly smoke aloft is treated as mixing back down when the layer gets shallower
PERSIST_WEIGHTS = (1.0, 0.7)  # assumed repeat of the last 24 h of fires on day +1 and day +2
SMOOTH_SIGMA_CELLS = 1.5  # sub-grid dispersion, about 7 km
UNIT_SCALE = 1000.0  # keeps the raw index in a readable range


@dataclass
class Simulation:
    times: np.ndarray  # datetime64[s] per frame, hourly, UTC
    conc: np.ndarray  # (F, NY, NX) float32, raw smoke index
    attr_ids: np.ndarray  # (F, ANY, ANX, TOP_SOURCES) int16 source ids, -1 = none
    attr_pct: np.ndarray  # (F, ANY, ANX, TOP_SOURCES) uint8 share of the smoke in that cell
    n_fires: int
    n_assumed: int  # fires repeated under the persistence assumption
    n_parcels: int
    now_frame: int  # index of the frame for the run hour


def gaussian_blur(grid: np.ndarray, sigma: float) -> np.ndarray:
    r = int(np.ceil(3 * sigma))
    x = np.arange(-r, r + 1)
    k = np.exp(-0.5 * (x / sigma) ** 2)
    k /= k.sum()
    rows = np.apply_along_axis(lambda m: np.convolve(m, k, mode="same"), 1, grid)
    return np.apply_along_axis(lambda m: np.convolve(m, k, mode="same"), 0, rows)


def release_schedule(fires: dict[str, np.ndarray], wind: WindField, now: np.datetime64, rng: np.random.Generator):
    """One row per parcel: where and when it is released, how much it carries, and which district it came from."""
    empty = np.zeros(0)
    if len(fires["lon"]) == 0:
        return empty, empty, empty, np.zeros(0, dtype=np.int16), np.zeros(0, dtype=np.int64), 0
    detect = np.array([wind.hour_index(t) for t in fires["time"]])
    frp_w = np.minimum(fires["frp"], FRP_CAP)
    now_h = wind.hour_index(now)
    recent = detect >= now_h - 24
    lon_l, lat_l, det_l, w_l, src_l = [fires["lon"]], [fires["lat"]], [detect], [frp_w], [fires["district"]]
    for day, weight in enumerate(PERSIST_WEIGHTS, start=1):
        lon_l.append(fires["lon"][recent])
        lat_l.append(fires["lat"][recent])
        det_l.append(detect[recent] + 24 * day)
        w_l.append(frp_w[recent] * weight)
        src_l.append(fires["district"][recent])
    lon0, lat0, det0, w0, src0 = (np.concatenate(a) for a in (lon_l, lat_l, det_l, w_l, src_l))

    hours = np.arange(-BURN_HOURS_BEFORE, BURN_HOURS_AFTER + 1)
    per_fire = len(hours) * PARCELS_PER_HOUR
    step = (np.floor(det0)[:, None] + hours[None, :]).astype(np.int64)  # (fire, hour)
    step = np.repeat(step[:, :, None], PARCELS_PER_HOUR, axis=2).reshape(-1)
    w = np.repeat(w0 / PARCELS_PER_HOUR, per_fire)
    src = np.repeat(src0, per_fire).astype(np.int16)
    n = len(lon0) * per_fire
    # scatter the release point by about a kilometre so parcels from one fire do not all share a cell
    lon = np.repeat(lon0, per_fire) + rng.normal(0, 0.01, n)
    lat = np.repeat(lat0, per_fire) + rng.normal(0, 0.01, n)
    keep = step >= 0
    return lon[keep], lat[keep], w[keep], src[keep], step[keep], int(recent.sum())


def simulate(fires: dict[str, np.ndarray], wind: WindField, now: np.datetime64, n_sources: int, seed: int = 42) -> Simulation:
    rng = np.random.default_rng(seed)
    r_lon, r_lat, r_w, r_src, r_step, n_assumed = release_schedule(fires, wind, now, rng)
    now_hour = int(np.floor(wind.hour_index(now)))
    frame_steps = np.arange(now_hour - PAST_HOURS, now_hour + AHEAD_HOURS + 1)
    frames = len(frame_steps)
    n_sources = n_sources + 1  # the last bucket is "outside India's mapped districts"
    conc = np.zeros((frames, geo.NY, geo.NX), dtype=np.float32)
    attr_ids = np.full((frames, geo.ANY, geo.ANX, TOP_SOURCES), -1, dtype=np.int16)
    attr_pct = np.zeros((frames, geo.ANY, geo.ANX, TOP_SOURCES), dtype=np.uint8)

    lon = np.zeros(0)
    lat = np.zeros(0)
    w = np.zeros(0)
    src = np.zeros(0, dtype=np.int16)
    speed = np.zeros(0)
    turn = np.zeros(0)
    depth = np.zeros(0)
    dt = 3600.0 / SUBSTEPS
    sigma_m = np.sqrt(2 * DIFFUSION_M2_S * dt)
    decay = np.exp(-1.0 / (DECAY_HOURS * SUBSTEPS))
    relax = 1.0 - np.exp(-1.0 / DEPTH_RELAX_HOURS)
    first_step = int(min(r_step.min(), frame_steps[0])) if len(r_step) else int(frame_steps[0])
    max_step = int(min(frame_steps[-1], len(wind.times) - 2))

    for k in range(first_step, max_step + 1):
        new = r_step == k
        if new.any():
            n = int(new.sum())
            _, _, pbl_new = wind.sample(k + 0.5, r_lon[new], r_lat[new])
            lon = np.concatenate([lon, r_lon[new]])
            lat = np.concatenate([lat, r_lat[new]])
            w = np.concatenate([w, r_w[new]])
            src = np.concatenate([src, r_src[new]])
            speed = np.concatenate([speed, np.clip(1.0 + rng.normal(0, SPEED_JITTER, n), 0.3, 1.7)])
            turn = np.concatenate([turn, np.radians(rng.normal(0, DIRECTION_JITTER_DEG, n))])
            depth = np.concatenate([depth, pbl_new])
        if len(lon) == 0:
            continue
        cos_t, sin_t = np.cos(turn), np.sin(turn)
        for sub in range(SUBSTEPS):
            t = k + (sub + 0.5) / SUBSTEPS
            u, v, _ = wind.sample(t, lon, lat)
            ur = (u * cos_t - v * sin_t) * speed
            vr = (u * sin_t + v * cos_t) * speed
            lon = lon + (ur * dt + rng.normal(0, sigma_m, len(lon))) / geo.m_per_deg_lon(lat)
            lat = lat + (vr * dt + rng.normal(0, sigma_m, len(lat))) / geo.M_PER_DEG_LAT
            w = w * decay
        alive = geo.in_domain(lon, lat) & (w > 1e-3)
        lon, lat, w, src, speed, turn, depth = (a[alive] for a in (lon, lat, w, src, speed, turn, depth))
        _, _, pbl = wind.sample(k + 1.0, lon, lat)
        depth = np.where(pbl > depth, pbl, depth + (pbl - depth) * relax)

        frame = k + 1 - frame_steps[0]
        if 0 <= frame < frames and len(lon):
            load = w / depth * UNIT_SCALE
            ix, iy = geo.to_cell(lon, lat)
            raw = np.bincount(iy * geo.NX + ix, weights=load, minlength=geo.NY * geo.NX).reshape(geo.NY, geo.NX)
            conc[frame] = gaussian_blur(raw, SMOOTH_SIGMA_CELLS)
            aix, aiy = geo.to_cell(lon, lat, geo.ATTR_RES)
            s = np.where(src < 0, n_sources - 1, src).astype(np.int64)
            key = (aiy * geo.ANX + aix) * n_sources + s
            by_src = np.bincount(key, weights=load, minlength=geo.ANY * geo.ANX * n_sources).reshape(geo.ANY, geo.ANX, n_sources)
            total = by_src.sum(axis=2)
            top = np.argsort(-by_src, axis=2)[:, :, :TOP_SOURCES]
            share = np.take_along_axis(by_src, top, axis=2) / np.maximum(total, 1e-9)[:, :, None]
            has = total > 0
            ids = np.where(top == n_sources - 1, -1, top).astype(np.int16)
            attr_ids[frame][has] = ids[has]
            attr_pct[frame][has] = np.clip(np.round(share[has] * 100), 0, 100).astype(np.uint8)

    times = wind.times[0] + (frame_steps * 3600).astype("timedelta64[s]")
    return Simulation(times=times, conc=conc, attr_ids=attr_ids, attr_pct=attr_pct, n_fires=len(fires["lon"]),
                      n_assumed=n_assumed, n_parcels=len(r_w), now_frame=PAST_HOURS)
