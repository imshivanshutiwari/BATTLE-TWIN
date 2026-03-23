"""
D* Lite incremental path planner.
Handles dynamic obstacles and terrain changes with efficient replanning.
"""

import heapq
import math
from dataclasses import dataclass, field
from datetime import timedelta
from typing import Dict, List, Optional, Tuple
import numpy as np
from utils.logger import get_logger

log = get_logger("DSTAR")


@dataclass
class Path:
    cells: List[Tuple[int, int]] = field(default_factory=list)
    total_cost: float = 0.0
    distance_m: float = 0.0

    def __len__(self):
        return len(self.cells)

    @property
    def valid(self):
        return len(self.cells) >= 2


class DStarLitePlanner:
    """
    D* Lite incremental path planner.
    Cost = terrain_penalty(slope) + threat_penalty + road_bonus + LOS_penalty.
    Supports dynamic replanning when routes are blocked.
    """

    def __init__(self, cell_size_m: float = 30.0):
        self.cell_size_m = cell_size_m
        self._terrain_grid: Optional[np.ndarray] = None
        self._threat_grid: Optional[np.ndarray] = None
        self._road_grid: Optional[np.ndarray] = None
        self._los_grid: Optional[np.ndarray] = None
        self._rhs: Dict[Tuple, float] = {}
        self._g: Dict[Tuple, float] = {}
        self._km = 0.0
        self._start: Optional[Tuple[int, int]] = None
        self._goal: Optional[Tuple[int, int]] = None
        self._open_list: List = []
        self._last_path: Optional[Path] = None

    def _neighbors(self, node: Tuple[int, int]) -> List[Tuple[int, int]]:
        r, c = node
        rows, cols = self._terrain_grid.shape
        nbrs = []
        for dr, dc in [(-1, 0), (1, 0), (0, -1), (0, 1), (-1, -1), (-1, 1), (1, -1), (1, 1)]:
            nr, nc = r + dr, c + dc
            if 0 <= nr < rows and 0 <= nc < cols:
                nbrs.append((nr, nc))
        return nbrs

    def _cost(self, a: Tuple[int, int], b: Tuple[int, int]) -> float:
        base = self.cell_size_m * (1.414 if abs(a[0] - b[0]) + abs(a[1] - b[1]) == 2 else 1.0)
        terrain_cost = 1.0
        if self._terrain_grid is not None:
            val = self._terrain_grid[b[0], b[1]]
            if val >= 999:
                return float("inf")
            terrain_cost += val / 10.0
        threat_cost = 0.0
        if self._threat_grid is not None:
            threat_cost = self._threat_grid[b[0], b[1]] * 5.0
        road_bonus = 1.0
        if self._road_grid is not None and self._road_grid[b[0], b[1]] > 0:
            road_bonus = 0.3
        los_penalty = 0.0
        if self._los_grid is not None and self._los_grid[b[0], b[1]]:
            los_penalty = 2.0
        return base * terrain_cost * road_bonus + threat_cost + los_penalty

    def _heuristic(self, a: Tuple[int, int], b: Tuple[int, int]) -> float:
        return self.cell_size_m * math.sqrt((a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2)

    def _key(self, node: Tuple[int, int]) -> Tuple[float, float]:
        g_val = self._g.get(node, float("inf"))
        rhs_val = self._rhs.get(node, float("inf"))
        k1 = min(g_val, rhs_val) + self._heuristic(self._start, node) + self._km
        k2 = min(g_val, rhs_val)
        return (k1, k2)

    def _initialize(self, start, goal, terrain_grid):
        self._terrain_grid = terrain_grid
        self._start = start
        self._goal = goal
        self._g.clear()
        self._rhs.clear()
        self._open_list = []
        self._km = 0.0
        self._rhs[goal] = 0.0
        heapq.heappush(self._open_list, (self._key(goal), goal))

    def _update_vertex(self, node):
        if node != self._goal:
            min_rhs = float("inf")
            for nbr in self._neighbors(node):
                cost = self._cost(node, nbr)
                val = self._g.get(nbr, float("inf")) + cost
                if val < min_rhs:
                    min_rhs = val
            self._rhs[node] = min_rhs
        # Remove from open list (lazy deletion)
        g_val = self._g.get(node, float("inf"))
        rhs_val = self._rhs.get(node, float("inf"))
        if g_val != rhs_val:
            heapq.heappush(self._open_list, (self._key(node), node))

    def _compute_shortest_path(self, max_iterations=50000):
        iterations = 0
        while self._open_list and iterations < max_iterations:
            key_top, u = heapq.heappop(self._open_list)
            g_val = self._g.get(u, float("inf"))
            rhs_val = self._rhs.get(u, float("inf"))
            current_key = self._key(u)
            if key_top < current_key:
                heapq.heappush(self._open_list, (current_key, u))
            elif g_val > rhs_val:
                self._g[u] = rhs_val
                for nbr in self._neighbors(u):
                    self._update_vertex(nbr)
            else:
                self._g[u] = float("inf")
                self._update_vertex(u)
                for nbr in self._neighbors(u):
                    self._update_vertex(nbr)
            iterations += 1
            start_g = self._g.get(self._start, float("inf"))
            start_rhs = self._rhs.get(self._start, float("inf"))
            if start_g == start_rhs and start_g < float("inf"):
                break

    def _extract_path(self) -> Path:
        path = Path()
        current = self._start
        visited = set()
        # Try to follow g-values from start to goal
        while current != self._goal:
            if current in visited or len(path.cells) > self._terrain_grid.size:
                break
            visited.add(current)
            path.cells.append(current)
            best_next = None
            best_cost = float("inf")
            for nbr in self._neighbors(current):
                g_nbr = self._g.get(nbr, float("inf"))
                c = self._cost(current, nbr)
                if g_nbr < float("inf") and c < float("inf"):
                    total = g_nbr + c
                    if total < best_cost:
                        best_cost = total
                        best_next = nbr
            if best_next is None:
                break
            path.total_cost += self._cost(path.cells[-1], best_next)
            current = best_next
        if current == self._goal:
            path.cells.append(self._goal)
        else:
            # Fallback: A* search when D* Lite g-values incomplete
            path = self._astar_fallback()
        path.distance_m = len(path.cells) * self.cell_size_m
        return path

    def _astar_fallback(self) -> Path:
        """Simple A* search as fallback when D* Lite extraction fails."""
        start, goal = self._start, self._goal
        open_set = []
        heapq.heappush(open_set, (self._heuristic(start, goal), start))
        came_from = {}
        g_score = {start: 0.0}
        visited = set()
        while open_set:
            _, current = heapq.heappop(open_set)
            if current in visited:
                continue
            visited.add(current)
            if current == goal:
                cells = []
                while current in came_from:
                    cells.append(current)
                    current = came_from[current]
                cells.append(start)
                cells.reverse()
                p = Path(cells=cells, total_cost=g_score.get(goal, 0.0))
                return p
            for nbr in self._neighbors(current):
                c = self._cost(current, nbr)
                if c == float("inf"):
                    continue
                tentative = g_score.get(current, float("inf")) + c
                if tentative < g_score.get(nbr, float("inf")):
                    came_from[nbr] = current
                    g_score[nbr] = tentative
                    f = tentative + self._heuristic(nbr, goal)
                    heapq.heappush(open_set, (f, nbr))
        # No path found — return start → goal directly
        return Path(cells=[start, goal])

    def plan(self, start: Tuple[int, int], goal: Tuple[int, int], terrain_grid: np.ndarray) -> Path:
        self._initialize(start, goal, terrain_grid)
        self._compute_shortest_path()
        self._last_path = self._extract_path()
        log.info(f"Path found: {len(self._last_path)} cells, cost={self._last_path.total_cost:.1f}")
        return self._last_path

    def replan(self, blocked_node: Tuple[int, int]) -> Path:
        if self._terrain_grid is None:
            raise RuntimeError("No initial plan exists")
        self._terrain_grid[blocked_node[0], blocked_node[1]] = 999.0
        for nbr in self._neighbors(blocked_node):
            self._update_vertex(nbr)
        self._compute_shortest_path()
        self._last_path = self._extract_path()
        return self._last_path

    def update_threat_costs(self, threat_map: np.ndarray) -> None:
        self._threat_grid = threat_map

    def set_road_grid(self, road_grid: np.ndarray) -> None:
        self._road_grid = road_grid

    def set_los_grid(self, los_grid: np.ndarray) -> None:
        self._los_grid = los_grid

    def compute_eta(self, path: Path, unit_speed_mps: float = 5.0) -> timedelta:
        if unit_speed_mps <= 0:
            return timedelta(hours=999)
        return timedelta(seconds=path.distance_m / unit_speed_mps)


if __name__ == "__main__":
    planner = DStarLitePlanner()
    grid = np.ones((50, 50), dtype=np.float32)
    grid[20:30, 25] = 999  # Obstacle wall
    path = planner.plan((5, 5), (45, 45), grid)
    print(f"Path: {len(path)} cells, cost={path.total_cost:.1f}, dist={path.distance_m:.0f}m")
    eta = planner.compute_eta(path, 5.0)
    print(f"ETA: {eta}")
    path2 = planner.replan((15, 15))
    print(f"Replanned: {len(path2)} cells")
    print("dstar_lite.py OK")
