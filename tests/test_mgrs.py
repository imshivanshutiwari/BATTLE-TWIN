"""Tests for utils/mgrs_converter.py."""
from utils.mgrs_converter import MGRSConverter, MGRSCoord


def test_latlon_to_mgrs():
    conv = MGRSConverter()
    mgrs = conv.latlon_to_mgrs(34.0, -117.0)
    assert isinstance(mgrs, MGRSCoord)
    assert mgrs.zone_number > 0


def test_mgrs_roundtrip():
    conv = MGRSConverter()
    mgrs = conv.latlon_to_mgrs(34.25, -117.25)
    lat, lon = conv.mgrs_to_latlon(mgrs)
    assert abs(lat - 34.25) < 0.01
    assert abs(lon - (-117.25)) < 0.01


def test_mgrs_string():
    conv = MGRSConverter()
    s = conv.latlon_to_mgrs_string(34.0, -117.0)
    assert isinstance(s, str)
    assert len(s) > 5


def test_distance():
    conv = MGRSConverter()
    d = conv.distance_m(34.0, -117.0, 34.1, -117.0)
    assert 10000 < d < 12000  # ~11.1 km


def test_bearing():
    conv = MGRSConverter()
    b = conv.bearing_deg(34.0, -117.0, 35.0, -117.0)
    assert abs(b - 0.0) < 5  # Due north
