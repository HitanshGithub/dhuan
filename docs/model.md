# The smoke model, and what it does not know

Dhuan's forecast is a Lagrangian parcel model: a few hundred thousand "parcels" of smoke released from satellite
fire detections and carried hourly by the forecast wind. It was built in a weekend to answer one question
("when does the smoke reach me, how heavy, from where?"), and this page says exactly how, so the numbers can be
checked rather than trusted.

## Inputs

| Input | Source | Resolution | Refresh |
|---|---|---|---|
| Active fires | NASA FIRMS, VIIRS 375 m on Suomi NPP, NOAA-20 and NOAA-21, regional CSV for South Asia | per pixel, two overpasses a day per satellite | hourly fetch, 48 h window |
| Winds at 100 m, boundary-layer height | Open-Meteo forecast API (best-match model blend) | 1° grid, 13 × 19 points over 70–88 °E, 22–34 °N | hourly fetch, 2 days back, 3 ahead |
| District boundaries | Census 2011 via udit-001/india-maps-data | rasterised once to the 0.05° grid | build time |

Detections with low confidence are dropped. Detections of the same field by two satellites on the same day are
merged (1 km cell), keeping the strongest fire radiative power (FRP).

## Release

A field seen burning at the afternoon overpass (about 13:30 IST) is assumed to burn from 3 hours before to
4 hours after the detection. Each burning hour releases 8 parcels, each carrying FRP / 8 (FRP capped at 80 MW,
which removes merged pixels and industrial sources). Release points are scattered by about 1 km.

**Persistence.** Tomorrow's fires cannot be seen today. Fields seen burning in the last 24 hours are assumed to
burn again at the same hours on day +1 (weight 1.0) and day +2 (weight 0.7). Operational smoke models (for
example NOAA's HRRR-Smoke) make the same assumption. The app says so on the timeline whenever a frame depends
on it, and `meta.json` carries the count as `fires.assumed_repeat`.

## Transport

Every hour, in two half-hour sub-steps:

* position += wind at 100 m, interpolated bilinearly in space and linearly in time;
* each parcel has a persistent speed factor (normal, σ = 0.25) and heading offset (normal, σ = 15°), standing in
  for wind shear between heights;
* a random walk with σ = √(2 K Δt), K = 800 m²/s (about 2.4 km per hour);
* mass decays with an e-folding time of 72 hours (deposition and loss out of the mixed layer);
* parcels leaving the domain are dropped.

## Surface concentration

At each output hour the parcels are binned onto the 0.05° grid (about 5 km) and each parcel's mass is divided
by its **mixing depth**. The depth starts as the boundary-layer height at release. When the boundary layer grows
(morning), the depth follows it at once. When it collapses (dusk), the depth relaxes towards the new value with
a 6-hour time constant: smoke that was mixed through a 2 km layer during the day does not all drop to the
ground at sunset. Without this the index jumped six-fold in one hour at dusk, which is an artefact.

The grid is then smoothed with a Gaussian of σ = 1.5 cells to represent dispersion below the grid scale.

Attribution: on a coarser 0.25° grid, the same binning is done per source district, and the top five sources
per cell per hour are stored (`attr.npz`). The point forecast sums these over the next 24 hours, weighted by
the smoke level, to say where the smoke over a place came from.

## From index to micrograms

The raw index is FRP-hours per metre of mixing depth per cell. `calibrate.UG_PER_UNIT` (1.5 on 9 Oct 2026)
turns it into an **estimated extra PM2.5** in µg/m³, and the bands are:

| Band | from µg/m³ |
|---|---|
| Clear | 0 |
| Light | 8 |
| Moderate | 25 |
| Heavy | 50 |
| Severe | 100 |

How the first value was chosen: on 9 Oct 2026, early in the season, the run had 74 fires in Punjab over 48 hours
and the index at Delhi was 0.5–3 units. The published estimates of the farm-fire share of Delhi's PM2.5 on peak
days (late October to mid November, 3,000–5,000 fires a day) are 100–200 µg/m³. Scaling the fire count by 40–60×
and the unit by 1.5 lands in that range, so 1.5 is a defensible order of magnitude, not a fitted value.

What it is not: a chemical-transport model, a measurement, or the total air quality. Traffic, dust, industry
and secondary aerosol are on top of it. The next step is obvious and planned: fit `UG_PER_UNIT` every hour by
regressing CPCB station PM2.5 (minus a background) on the index at the station locations, and show the fit on
the map so users can see when the model is wrong.

## Known limitations

* Night-time overpasses see fewer fires; small or short fires are missed entirely, so the index is biased low.
* Winds at 100 m stand in for transport through the whole mixed layer.
* No plume rise: strong fires can inject smoke above the boundary layer, where it travels further and arrives
  later than modelled.
* The persistence assumption is wrong on the day burning stops (rain, enforcement, end of harvest).
* Pakistan's Punjab is inside the domain but outside the district raster, so its fires are attributed as
  "outside India".

## Reproducing a run

```bash
cd backend
uv run python -m dhuan.run            # fetch live inputs, simulate, render to backend/out
uv run python -m dhuan.run --reuse    # simulate again on the inputs already saved for this hour
```

Every run keeps its inputs under `runs/<id>/inputs/`, so a forecast can be re-run with changed parameters.
