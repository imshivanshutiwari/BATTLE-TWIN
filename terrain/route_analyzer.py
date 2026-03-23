"""Route terrain scoring for path planning."""
import numpy as np
from typing import Dict, List, Tuple
from utils.logger import get_logger
log = get_logger("ROUTE")


class RouteAnalyzer:
    """Scores route segments based on terrain properties."""

    def __init__(self, cell_size_m: float = 30.0):
        self.cell_size_m = cell_size_m

    def compute_route_cost_grid(self, slope: np.ndarray, trafficability: np.ndarray,
                                 threat_map: np.ndarray = None,
                                 road_mask: np.ndarray = None) -> np.ndarray:
        cost = np.ones_like(slope, dtype=np.float32)
        cost += slope / 10.0
        cost[trafficability == 1] += 2.0
        cost[trafficability == 2] = 999.0
        if threat_map is not None:
            cost += threat_map * 5.0
        if road_mask is not None:
            cost[road_mask > 0] *= 0.3
        return cost

    def score_route(self, cost_grid: np.ndarray, path: List[Tuple[int, int]]) -> Dict:
        if not path:
            return {"total_cost": 0, "avg_cost": 0, "max_cost": 0, "length_m": 0}
        costs = [float(cost_grid[r, c]) for r, c in path if 0 <= r < cost_grid.shape[0] and 0 <= c < cost_grid.shape[1]]
        return {
            "total_cost": sum(costs),
            "avg_cost": np.mean(costs) if costs else 0,
            "max_cost": max(costs) if costs else 0,
            "length_m": len(path) * self.cell_size_m,
            "n_cells": len(path),
        }

    def find_chokepoints(self, cost_grid: np.ndarray, threshold: float = 0.8) -> List[Tuple[int, int]]:
        from scipy.ndimage import minimum_filter
        local_min = minimum_filter(cost_grid, size=5)
        is_narrow = (cost_grid - local_min) < (cost_grid.max() * (1 - threshold))
        narrow_cells = np.argwhere(is_narrow & (cost_grid < np.percentile(cost_grid, 20)))
        return [(int(r), int(c)) for r, c in narrow_cells[:50]]

    def compare_routes(self, cost_grid: np.ndarray,
                       routes: Dict[str, List[Tuple[int, int]]]) -> Dict[str, Dict]:
        return {name: self.score_route(cost_grid, path) for name, path in routes.items()}


if __name__ == "__main__":
    analyzer = RouteAnalyzer()
    slope = np.random.uniform(0, 20, (100, 100)).astype(np.float32)
    traff = np.zeros((100, 100), dtype=np.int32)
    traff[slope > 15] = 1
    traff[slope > 30] = 2
    cost = analyzer.compute_route_cost_grid(slope, traff)
    path = [(i, i) for i in range(50)]
    score = analyzer.score_route(cost, path)
    print(f"Route score: {score}")
    print("route_analyzer.py OK")
