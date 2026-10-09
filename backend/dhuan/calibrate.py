"""From the model's raw smoke index to an estimated PM2.5 contribution, and from that to plain words.

The parcel model's units are arbitrary (fire radiative power carried per metre of mixing depth). UG_PER_UNIT
scales them to micrograms per cubic metre. It is a working estimate, not a measurement; when station readings
are available the run compares against them (see stations.py) so the number can be checked, not trusted blindly.
"""

UG_PER_UNIT = 1.5  # first-run working value (9 Oct 2026); revisited against station readings, see docs/model.md

BANDS = [
    # (lower bound, key, label, colour, one-line meaning)
    (0, "clear", "Clear", "#9ad0a0", "Little or no farm-fire smoke expected."),
    (8, "light", "Light", "#f3d98b", "A thin haze of smoke. Noticeable for sensitive people."),
    (25, "moderate", "Moderate", "#f3a35a", "Smoke adds clearly to pollution. Limit long outdoor exertion."),
    (50, "heavy", "Heavy", "#e05a3a", "Heavy smoke. Keep children, elders and asthma patients indoors."),
    (100, "severe", "Severe", "#8b1e4b", "Severe smoke. Avoid going out; seal windows; run purifiers."),
]


def band_for(ug: float) -> dict:
    chosen = BANDS[0]
    for b in BANDS:
        if ug >= b[0]:
            chosen = b
    return {"key": chosen[1], "label": chosen[2], "color": chosen[3], "meaning": chosen[4]}


def bands() -> list[dict]:
    return [{"from_ug": b[0], "key": b[1], "label": b[2], "color": b[3], "meaning": b[4]} for b in BANDS]
