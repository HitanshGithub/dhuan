"""Rasterise India's district boundaries onto the simulation grid, once, at build time.

Input: data/raw/states/*.geojson from https://github.com/udit-001/india-maps-data (Census 2011 districts, MIT).
Output: data/districts.json (id -> district, state) and data/districts_grid.npy (int16 NY x NX, -1 = none).

The runtime then needs no geometry library: looking up a fire's district is an array index.
"""

import json
import sys
from pathlib import Path

import numpy as np
from shapely import STRtree, points
from shapely.geometry import shape

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from dhuan import geo  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / "data" / "raw" / "states"


def main() -> None:
    names, polys = [], []
    for path in sorted(RAW.glob("*.geojson")):
        for feature in json.loads(path.read_text(encoding="utf-8"))["features"]:
            p = feature["properties"]
            names.append({"district": p["district"], "state": p["st_nm"]})
            polys.append(shape(feature["geometry"]))
    tree = STRtree(polys)
    ix, iy = np.meshgrid(np.arange(geo.NX), np.arange(geo.NY))
    lon, lat = geo.cell_center(ix.ravel(), iy.ravel())
    cells = points(lon, lat)
    cell_idx, poly_idx = tree.query(cells, predicate="within")
    grid = np.full(geo.NY * geo.NX, -1, dtype=np.int16)
    grid[cell_idx] = poly_idx  # a cell centre is within at most one district
    grid = grid.reshape(geo.NY, geo.NX)
    out = ROOT / "data"
    (out / "districts.json").write_text(json.dumps(names, ensure_ascii=False, indent=0), encoding="utf-8")
    np.save(out / "districts_grid.npy", grid)
    covered = int((grid >= 0).sum())
    print(f"{len(names)} districts from {len(list(RAW.glob('*.geojson')))} states; {covered}/{grid.size} cells covered")


if __name__ == "__main__":
    main()
