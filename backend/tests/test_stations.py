from dhuan.sources import stations


def test_aqi_to_pm25_inverts_the_breakpoints():
    assert stations.aqi_to_pm25(0) == 0.0
    assert stations.aqi_to_pm25(50) == 12.0
    assert stations.aqi_to_pm25(100) == 35.4
    assert stations.aqi_to_pm25(152) == 57.4  # just into "unhealthy": 55.5 + (152-151) * (150.4-55.5) / 49
    assert stations.aqi_to_pm25(600) is None


def test_parse_skips_missing_values_and_points_outside_the_domain():
    payload = {"status": "ok", "data": [
        {"lat": 28.63, "lon": 77.20, "uid": 1, "aqi": "152", "station": {"name": "Mandir Marg, Delhi", "time": "2026-10-10T00:00:00+05:30"}},
        {"lat": 28.60, "lon": 77.10, "uid": 2, "aqi": "-", "station": {"name": "Offline"}},
        {"lat": 12.97, "lon": 77.59, "uid": 3, "aqi": "60", "station": {"name": "Bengaluru"}},
    ]}
    parsed = stations.parse(payload)
    assert [s.uid for s in parsed] == [1]
    feature = stations.to_geojson(parsed)["features"][0]["properties"]
    assert feature["pm25"] == 57.4 and feature["key"] == "unhealthy" and feature["name"].startswith("Mandir Marg")
