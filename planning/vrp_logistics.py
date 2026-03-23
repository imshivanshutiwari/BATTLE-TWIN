"""VRP logistics optimizer using OR-Tools."""
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple
import numpy as np
from utils.logger import get_logger
log = get_logger("VRP")

try:
    from ortools.constraint_solver import routing_enums_pb2, pywrapcp
    ORTOOLS_AVAILABLE = True
except ImportError:
    ORTOOLS_AVAILABLE = False


@dataclass
class VRPSolution:
    routes: Dict[int, List[int]] = None
    total_distance_m: float = 0.0
    total_time_s: float = 0.0
    units_served: List[str] = None
    def __post_init__(self):
        self.routes = self.routes or {}
        self.units_served = self.units_served or []
    def to_dict(self):
        return {"routes": self.routes, "total_distance_m": self.total_distance_m,
                "total_time_s": self.total_time_s, "units_served": self.units_served}


class VRPLogistics:
    """Vehicle Routing Problem solver for supply convoy planning."""

    def __init__(self, max_vehicles: int = 8, vehicle_capacity_kg: int = 5000,
                 depot_lat: float = 34.0, depot_lon: float = -117.5):
        self.max_vehicles = max_vehicles
        self.vehicle_capacity = vehicle_capacity_kg
        self.depot = (depot_lat, depot_lon)

    def _haversine(self, lat1, lon1, lat2, lon2):
        R = 6371000
        p1, p2 = np.radians(lat1), np.radians(lat2)
        dp, dl = np.radians(lat2 - lat1), np.radians(lon2 - lon1)
        a = np.sin(dp/2)**2 + np.cos(p1) * np.cos(p2) * np.sin(dl/2)**2
        return R * 2 * np.arctan2(np.sqrt(a), np.sqrt(1 - a))

    def _build_distance_matrix(self, locations: List[Tuple[float, float]]) -> np.ndarray:
        n = len(locations)
        matrix = np.zeros((n, n))
        for i in range(n):
            for j in range(n):
                matrix[i][j] = self._haversine(locations[i][0], locations[i][1],
                                                locations[j][0], locations[j][1])
        return matrix

    def solve(self, unit_locations: List[Tuple[float, float]],
              demands_kg: List[float] = None,
              unit_ids: List[str] = None) -> VRPSolution:
        locations = [self.depot] + unit_locations
        n_units = len(unit_locations)
        demands = demands_kg or [500.0] * n_units
        unit_ids = unit_ids or [f"UNIT-{i}" for i in range(n_units)]
        dist_matrix = self._build_distance_matrix(locations)

        if not ORTOOLS_AVAILABLE:
            log.warning("OR-Tools unavailable, using greedy solution")
            return self._greedy_solve(locations, demands, unit_ids, dist_matrix)

        manager = pywrapcp.RoutingIndexManager(len(locations), self.max_vehicles, 0)
        routing = pywrapcp.RoutingModel(manager)

        def distance_callback(from_idx, to_idx):
            from_node = manager.IndexToNode(from_idx)
            to_node = manager.IndexToNode(to_idx)
            return int(dist_matrix[from_node][to_node])

        transit_idx = routing.RegisterTransitCallback(distance_callback)
        routing.SetArcCostEvaluatorOfAllVehicles(transit_idx)

        full_demands = [0] + [int(d) for d in demands]
        def demand_callback(idx):
            return full_demands[manager.IndexToNode(idx)]
        demand_idx = routing.RegisterUnaryTransitCallback(demand_callback)
        routing.AddDimensionWithVehicleCapacity(
            demand_idx, 0, [self.vehicle_capacity] * self.max_vehicles, True, "Capacity")

        params = pywrapcp.DefaultRoutingSearchParameters()
        params.first_solution_strategy = routing_enums_pb2.FirstSolutionStrategy.PATH_CHEAPEST_ARC
        params.local_search_metaheuristic = routing_enums_pb2.LocalSearchMetaheuristic.GUIDED_LOCAL_SEARCH
        params.time_limit.seconds = 10

        solution = routing.SolveWithParameters(params)
        if not solution:
            log.warning("No VRP solution, falling back to greedy")
            return self._greedy_solve(locations, demands, unit_ids, dist_matrix)

        vrp_sol = VRPSolution()
        total_dist = 0
        for v in range(self.max_vehicles):
            idx = routing.Start(v)
            route = []
            while not routing.IsEnd(idx):
                node = manager.IndexToNode(idx)
                route.append(node)
                idx = solution.Value(routing.NextVar(idx))
            route.append(manager.IndexToNode(idx))
            if len(route) > 2:
                vrp_sol.routes[v] = route
                for i in range(len(route) - 1):
                    total_dist += dist_matrix[route[i]][route[i+1]]
        vrp_sol.total_distance_m = total_dist
        vrp_sol.total_time_s = total_dist / 15.0  # ~15 m/s convoy speed
        vrp_sol.units_served = unit_ids
        return vrp_sol

    def _greedy_solve(self, locations, demands, unit_ids, dist_matrix):
        sol = VRPSolution()
        remaining = list(range(1, len(locations)))
        vehicle = 0
        total_dist = 0
        while remaining and vehicle < self.max_vehicles:
            route = [0]
            capacity = self.vehicle_capacity
            current = 0
            while remaining:
                nearest = min(remaining, key=lambda j: dist_matrix[current][j])
                d = demands[nearest - 1] if nearest - 1 < len(demands) else 500
                if d > capacity:
                    break
                route.append(nearest)
                capacity -= d
                current = nearest
                remaining.remove(nearest)
            route.append(0)
            if len(route) > 2:
                sol.routes[vehicle] = route
                for i in range(len(route) - 1):
                    total_dist += dist_matrix[route[i]][route[i+1]]
            vehicle += 1
        sol.total_distance_m = total_dist
        sol.total_time_s = total_dist / 15.0
        sol.units_served = unit_ids
        return sol


if __name__ == "__main__":
    vrp = VRPLogistics(max_vehicles=3)
    locs = [(34.05, -117.45), (34.10, -117.38), (34.15, -117.30),
            (34.20, -117.25), (34.08, -117.40)]
    sol = vrp.solve(locs, unit_ids=["B01","B02","B03","B04","B05"])
    print(f"Routes: {sol.routes}")
    print(f"Distance: {sol.total_distance_m/1000:.1f} km")
    print(f"Units served: {sol.units_served}")
    print("vrp_logistics.py OK")
