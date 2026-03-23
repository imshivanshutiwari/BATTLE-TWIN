"""Tests for data fetcher modules."""
from data.osm_terrain_fetcher import OSMTerrainFetcher
from data.weather_fetcher import WeatherFetcher
from data.adsb_fetcher import ADSBFetcher, Aircraft
from data.usgs_dem_fetcher import USGSDEMFetcher
from data.cot_parser import CoTParser


def test_osm_fetcher_init():
    fetcher = OSMTerrainFetcher()
    assert fetcher is not None


def test_weather_fetcher_init():
    fetcher = WeatherFetcher()
    assert fetcher is not None


def test_adsb_fetcher_init():
    fetcher = ADSBFetcher()
    assert fetcher is not None


def test_aircraft_military_callsign():
    ac = Aircraft(icao24="abc123", callsign="EVAC01", latitude=34.0, longitude=-117.0)
    assert ac.is_military_callsign()


def test_aircraft_civilian_callsign():
    ac = Aircraft(icao24="abc456", callsign="UAL123", latitude=34.0, longitude=-117.0)
    assert not ac.is_military_callsign()


def test_dem_fetcher_realistic():
    fetcher = USGSDEMFetcher()
    dem = fetcher._generate_realistic_dem((34.0, -117.5, 34.5, -117.0), 100, 100)
    assert dem.shape == (100, 100)
    assert dem.min() > 600
    assert dem.max() < 2000


def test_dem_slope():
    import numpy as np
    fetcher = USGSDEMFetcher()
    dem = np.random.uniform(800, 1200, (50, 50)).astype(np.float32)
    slope = fetcher.compute_slope(dem)
    assert slope.shape == dem.shape
    assert slope.min() >= 0


def test_dem_trafficability():
    import numpy as np
    fetcher = USGSDEMFetcher()
    slope = np.array([[5.0, 20.0, 40.0]])
    traff = fetcher.compute_trafficability(slope)
    assert traff[0, 0] == 0  # GO
    assert traff[0, 1] == 1  # SLOW_GO
    assert traff[0, 2] == 2  # NO_GO


def test_cot_parser_sample():
    parser = CoTParser()
    xml = CoTParser.generate_sample_cot("U01", "BLUE-1", "a-f-G", 34.0, -117.0)
    event = parser.parse_event(xml)
    assert event.uid == "U01"
    assert event.is_friendly


def test_cot_hostile():
    parser = CoTParser()
    xml = CoTParser.generate_sample_cot("R01", "RED-1", "a-h-G", 34.3, -117.1)
    event = parser.parse_event(xml)
    assert event.is_hostile
    assert event.affiliation == "HOSTILE"


def test_cot_batch():
    parser = CoTParser()
    xmls = [CoTParser.generate_sample_cot(f"U{i}", f"C{i}", "a-f-G", 34+i*0.01, -117) for i in range(5)]
    events = parser.parse_batch(xmls)
    assert len(events) == 5
