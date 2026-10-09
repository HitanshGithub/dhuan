"""The simulation domain: North India from Pakistan's Punjab to Bihar, on a 0.05-degree (about 5 km) grid."""

import json
from functools import lru_cache

import numpy as np

from .config import settings

LON0, LON1, LAT0, LAT1 = 70.0, 88.0, 22.0, 34.0
RES = 0.05
NX, NY = round((LON1 - LON0) / RES), round((LAT1 - LAT0) / RES)  # 360 x 240 cells
ATTR_RES = 0.25  # coarser grid for "where did this smoke come from"
ANX, ANY = round((LON1 - LON0) / ATTR_RES), round((LAT1 - LAT0) / ATTR_RES)  # 72 x 48
M_PER_DEG_LAT = 110_540.0
BOUNDS = [[LON0, LAT1], [LON1, LAT1], [LON1, LAT0], [LON0, LAT0]]  # image corners for the map: NW, NE, SE, SW


def m_per_deg_lon(lat):
    return 111_320.0 * np.cos(np.radians(lat))


def in_domain(lon, lat):
    return (lon >= LON0) & (lon < LON1) & (lat >= LAT0) & (lat < LAT1)


def to_cell(lon, lat, res: float = RES):
    """Column and row (row 0 is the southern edge) of the cell containing each point."""
    ix = np.floor((np.asarray(lon) - LON0) / res).astype(np.int64)
    iy = np.floor((np.asarray(lat) - LAT0) / res).astype(np.int64)
    return ix, iy


def cell_center(ix, iy, res: float = RES):
    return LON0 + (np.asarray(ix) + 0.5) * res, LAT0 + (np.asarray(iy) + 0.5) * res


class Districts:
    """District ids for every grid cell, rasterised once by scripts/build_districts.py from open boundary data."""

    def __init__(self, names: list[dict], grid: np.ndarray):
        self.names = names  # [{"district", "state"}], the list index is the id
        self.grid = grid  # int16 (NY, NX); -1 where no district is known

    def lookup(self, lon, lat) -> np.ndarray:
        ix, iy = to_cell(lon, lat)
        inside = (ix >= 0) & (ix < NX) & (iy >= 0) & (iy < NY)
        out = np.full(np.shape(ix), -1, dtype=np.int16)
        out[inside] = self.grid[iy[inside], ix[inside]]
        return out

    def label(self, district_id: int) -> str:
        if district_id < 0 or district_id >= len(self.names):
            return "outside India (likely Pakistan's Punjab)"
        d = self.names[district_id]
        return f"{d['district']}, {d['state']}"


@lru_cache(maxsize=1)
def districts() -> Districts:
    names = json.loads((settings.data_dir / "districts.json").read_text(encoding="utf-8"))
    grid = np.load(settings.data_dir / "districts_grid.npy")
    return Districts(names, grid)
