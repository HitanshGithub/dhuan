import numpy as np

from dhuan import geo, model
from dhuan.sources import winds


def _uniform_wind(hours=96, speed=5.0, direction=315.0, pbl=600.0):
    """A steady north-westerly over the whole domain, from 2026-10-08T00:00 UTC."""
    base = np.datetime64("2026-10-08T00:00")
    times = [str(base + np.timedelta64(h, "h")) for h in range(hours)]
    n = len(winds.LATS) * len(winds.LONS)
    payload = [{"hourly": {"time": times, "wind_speed_10m": [speed] * hours, "wind_direction_10m": [direction] * hours,
                           "wind_speed_100m": [speed] * hours, "wind_direction_100m": [direction] * hours,
                           "boundary_layer_height": [pbl] * hours}} for _ in range(n)]
    return winds.from_json(payload)


def _coarse(grid: np.ndarray) -> np.ndarray:
    f = int(geo.ATTR_RES / geo.RES)
    return grid.reshape(geo.ANY, f, geo.ANX, f).sum(axis=(1, 3))


def test_smoke_travels_downwind_and_is_attributed_to_its_source():
    wind = _uniform_wind()
    fires = {"lon": np.array([75.0]), "lat": np.array([30.5]), "frp": np.array([20.0]),
             "time": np.array([np.datetime64("2026-10-08T08:00:00")]),  # seen at 13:30 IST
             "district": np.array([7], dtype=np.int16)}
    now = np.datetime64("2026-10-08T12:00:00")
    sim = model.simulate(fires, wind, now, n_sources=10)

    assert sim.conc.shape == (model.PAST_HOURS + model.AHEAD_HOURS + 1, geo.NY, geo.NX)
    assert sim.n_fires == 1 and sim.n_assumed == 1 and sim.n_parcels > 0
    now_i = sim.now_frame

    def centre(frame):
        g = sim.conc[frame]
        iy, ix = np.indices(g.shape)
        return float((g * ix).sum() / g.sum()), float((g * iy).sum() / g.sum())

    # at the run hour the smoke is near the fire; 12 hours later it has moved south-east
    x0, y0 = centre(now_i)
    x1, y1 = centre(now_i + 12)
    assert x1 > x0 + 5 and y1 < y0 - 5, (x0, y0, x1, y1)
    # wherever the smoke is thickest, the source lookup names the fire's district, and only it
    aiy, aix = np.unravel_index(np.argmax(_coarse(sim.conc[now_i + 12])), (geo.ANY, geo.ANX))
    assert sim.attr_ids[now_i + 12, aiy, aix, 0] == 7
    assert sim.attr_pct[now_i + 12, aiy, aix, 0] == 100


def test_persistence_repeats_recent_fires_only():
    wind = _uniform_wind()
    rng = np.random.default_rng(0)
    fires = {"lon": np.array([75.0, 75.0]), "lat": np.array([30.5, 30.5]), "frp": np.array([10.0, 10.0]),
             "time": np.array([np.datetime64("2026-10-09T08:00:00"), np.datetime64("2026-10-08T08:00:00")]),
             "district": np.array([1, 2], dtype=np.int16)}
    *_, step, n_assumed = model.release_schedule(fires, wind, np.datetime64("2026-10-09T12:00:00"), rng)
    assert n_assumed == 1  # only the fire from the last 24 hours is assumed to burn again
    per_fire = (model.BURN_HOURS_BEFORE + model.BURN_HOURS_AFTER + 1) * model.PARCELS_PER_HOUR
    assert len(step) == per_fire * (2 + len(model.PERSIST_WEIGHTS))


def test_gaussian_blur_conserves_mass_in_the_interior():
    grid = np.zeros((40, 40))
    grid[20, 20] = 100.0
    out = model.gaussian_blur(grid, 1.5)
    assert abs(out.sum() - 100.0) < 1e-6 and out.max() < 20.0
