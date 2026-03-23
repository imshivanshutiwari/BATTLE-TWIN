"""Terrain slope + trafficability calculator."""
import numpy as np
from typing import Dict, Tuple
from utils.logger import get_logger
log = get_logger("SLOPE")


class SlopeCalculator:
    """Computes slope, aspect, and NATO trafficability from DEM."""

    def __init__(self, cell_size_m: float = 30.0, go_max=15.0, slow_go_max=30.0):
        self.cell_size_m = cell_size_m
        self.go_max = go_max
        self.slow_go_max = slow_go_max

    def compute_slope(self, dem: np.ndarray) -> np.ndarray:
        dy, dx = np.gradient(dem, self.cell_size_m)
        return np.degrees(np.arctan(np.sqrt(dx**2 + dy**2))).astype(np.float32)

    def compute_aspect(self, dem: np.ndarray) -> np.ndarray:
        dy, dx = np.gradient(dem, self.cell_size_m)
        return (np.degrees(np.arctan2(-dx, dy)) % 360).astype(np.float32)

    def compute_trafficability(self, slope: np.ndarray) -> np.ndarray:
        traff = np.zeros_like(slope, dtype=np.int32)
        traff[slope >= self.go_max] = 1
        traff[slope >= self.slow_go_max] = 2
        return traff

    def trafficability_label(self, value: int) -> str:
        return {0: "GO", 1: "SLOW_GO", 2: "NO_GO"}.get(value, "UNKNOWN")

    def compute_speed_factor(self, slope: np.ndarray) -> np.ndarray:
        factor = np.ones_like(slope)
        factor[slope > 5] = 0.8
        factor[slope > 15] = 0.5
        factor[slope > 25] = 0.2
        factor[slope > 35] = 0.05
        factor[slope > 45] = 0.0
        return factor.astype(np.float32)

    def get_statistics(self, slope: np.ndarray) -> Dict:
        traff = self.compute_trafficability(slope)
        total = traff.size
        return {
            "mean_slope_deg": float(np.mean(slope)),
            "max_slope_deg": float(np.max(slope)),
            "go_pct": float((traff == 0).sum() / total * 100),
            "slow_go_pct": float((traff == 1).sum() / total * 100),
            "no_go_pct": float((traff == 2).sum() / total * 100),
        }


if __name__ == "__main__":
    calc = SlopeCalculator()
    dem = np.random.uniform(800, 1200, (100, 100)).astype(np.float32)
    slope = calc.compute_slope(dem)
    stats = calc.get_statistics(slope)
    print(f"Slope stats: {stats}")
    print("slope_calculator.py OK")
