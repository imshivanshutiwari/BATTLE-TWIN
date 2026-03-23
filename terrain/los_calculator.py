"""Line-of-sight computation from DEM data."""
import numpy as np
from typing import List, Optional, Tuple
from utils.logger import get_logger
log = get_logger("LOS")


class LOSCalculator:
    """True Line-of-Sight computation using Bresenham + terrain profile."""

    def __init__(self, cell_size_m: float = 30.0):
        self.cell_size_m = cell_size_m

    def _bresenham(self, r0, c0, r1, c1) -> List[Tuple[int, int]]:
        cells = []
        dr, dc = abs(r1 - r0), abs(c1 - c0)
        sr = 1 if r0 < r1 else -1
        sc = 1 if c0 < c1 else -1
        err = dr - dc
        while True:
            cells.append((r0, c0))
            if r0 == r1 and c0 == c1:
                break
            e2 = 2 * err
            if e2 > -dc:
                err -= dc
                r0 += sr
            if e2 < dr:
                err += dr
                c0 += sc
        return cells

    def compute_los(self, dem: np.ndarray, observer: Tuple[int, int],
                    target: Tuple[int, int], obs_height: float = 2.0,
                    tgt_height: float = 2.0) -> bool:
        cells = self._bresenham(observer[0], observer[1], target[0], target[1])
        if len(cells) < 2:
            return True
        obs_elev = dem[observer[0], observer[1]] + obs_height
        tgt_elev = dem[target[0], target[1]] + tgt_height
        total_dist = len(cells) - 1
        for i, (r, c) in enumerate(cells[1:-1], 1):
            t = i / total_dist
            los_elev = obs_elev + t * (tgt_elev - obs_elev)
            if dem[r, c] > los_elev:
                return False
        return True

    def compute_viewshed(self, dem: np.ndarray, observer_pos: Tuple[int, int],
                         max_range_m: float = 5000, obs_height: float = 2.0) -> np.ndarray:
        rows, cols = dem.shape
        max_cells = int(max_range_m / self.cell_size_m)
        viewshed = np.zeros((rows, cols), dtype=bool)
        viewshed[observer_pos[0], observer_pos[1]] = True
        obs_elev = dem[observer_pos[0], observer_pos[1]] + obs_height
        for angle_deg in range(360):
            angle_rad = np.radians(angle_deg)
            dr, dc = np.cos(angle_rad), np.sin(angle_rad)
            max_slope = -np.inf
            for step in range(1, max_cells):
                r, c = int(observer_pos[0] + dr * step), int(observer_pos[1] + dc * step)
                if r < 0 or r >= rows or c < 0 or c >= cols:
                    break
                slope_to = (dem[r, c] - obs_elev) / (step * self.cell_size_m)
                if slope_to >= max_slope:
                    viewshed[r, c] = True
                    max_slope = slope_to
        return viewshed

    def compute_mutual_los(self, dem: np.ndarray, positions: List[Tuple[int, int]]) -> np.ndarray:
        n = len(positions)
        matrix = np.zeros((n, n), dtype=bool)
        for i in range(n):
            for j in range(i + 1, n):
                los = self.compute_los(dem, positions[i], positions[j])
                matrix[i, j] = matrix[j, i] = los
            matrix[i, i] = True
        return matrix

    def find_defilade(self, dem: np.ndarray, observer: Tuple[int, int],
                      search_radius: int = 50) -> List[Tuple[int, int]]:
        viewshed = self.compute_viewshed(dem, observer,
                                         max_range_m=search_radius * self.cell_size_m)
        rows, cols = dem.shape
        defilade = []
        or_, oc = observer
        for r in range(max(0, or_ - search_radius), min(rows, or_ + search_radius)):
            for c in range(max(0, oc - search_radius), min(cols, oc + search_radius)):
                if not viewshed[r, c]:
                    defilade.append((r, c))
        return defilade


if __name__ == "__main__":
    calc = LOSCalculator()
    dem = np.random.uniform(800, 1200, (100, 100)).astype(np.float32)
    dem[50, 50] = 1500  # Hill
    los = calc.compute_los(dem, (40, 40), (60, 60))
    print(f"LOS through hill: {los}")
    vs = calc.compute_viewshed(dem, (50, 50), max_range_m=1500)
    print(f"Viewshed visible: {vs.sum()}/{vs.size} cells")
    print("los_calculator.py OK")
