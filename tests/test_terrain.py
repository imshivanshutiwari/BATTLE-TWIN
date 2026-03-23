"""Tests for terrain modules."""

import numpy as np
from terrain.dem_processor import DEMProcessor
from terrain.slope_calculator import SlopeCalculator
from terrain.los_calculator import LOSCalculator
from terrain.cover_analyzer import CoverAnalyzer


def test_slope_calculation_flat():
    calc = SlopeCalculator()
    dem = np.ones((50, 50), dtype=np.float32) * 500
    slope = calc.compute_slope(dem)
    assert float(np.mean(slope)) < 1.0  # should be ~0


def test_los_blocked_by_hill():
    calc = LOSCalculator()
    dem = np.ones((100, 100), dtype=np.float32) * 500
    dem[50, 50] = 1500  # big hill
    los = calc.compute_los(dem, (30, 30), (70, 70))
    assert los is False


def test_viewshed_local_visibility():
    calc = LOSCalculator()
    dem = np.ones((50, 50), dtype=np.float32) * 500
    vs = calc.compute_viewshed(dem, (25, 25), max_range_m=1500)
    assert vs[25, 25]  # observer sees self
    assert vs[26, 26]  # adjacent visible on flat


def test_trafficability_steep():
    calc = SlopeCalculator()
    slope = np.array([[5, 20, 50]], dtype=np.float32)
    traff = calc.compute_trafficability(slope)
    assert traff[0, 0] == 0  # GO
    assert traff[0, 1] == 1  # SLOW_GO
    assert traff[0, 2] == 2  # NO_GO


def test_dem_hillshade():
    proc = DEMProcessor()
    dem = np.random.uniform(800, 1200, (50, 50)).astype(np.float32)
    hs = proc.compute_hillshade(dem)
    assert hs.shape == dem.shape
    assert hs.min() >= 0 and hs.max() <= 1


def test_cover_scoring():
    analyzer = CoverAnalyzer()
    grid = np.array([[0, 1, 2]], dtype=np.int32)
    labels = {0: "OPEN", 1: "FOREST", 2: "URBAN"}
    cover = analyzer.compute_cover_score(grid, labels)
    assert cover[0, 0] == 0.0  # open = no cover
    assert cover[0, 2] == 0.7  # urban = high cover
