"""Benchmark suite — stress testing C2 pipeline at scale."""
import time
import numpy as np
from typing import Dict, List
from evaluation.metrics import C2Metrics
from digital_twin.twin_state import BattlefieldState, UnitState, ContactReport
from simulation.sim_engine import SimulationEngine
from utils.logger import get_logger
log = get_logger("BENCHMARK")


class Benchmark:
    """Stress test the entire C2 pipeline."""

    def __init__(self):
        self.metrics = C2Metrics()

    def benchmark_sim_throughput(self, n_units: int = 100, n_ticks: int = 1000) -> Dict:
        state = BattlefieldState()
        rng = np.random.default_rng(42)
        for i in range(n_units):
            state.add_unit(UnitState(
                uid=f"U{i:04d}", callsign=f"UNIT-{i}", unit_type="infantry",
                lat=34.0+rng.random()*0.5, lon=-117.5+rng.random()*0.5,
                speed_mps=rng.uniform(0, 10), heading_deg=rng.uniform(0, 360)))
        engine = SimulationEngine(dt_s=0.1)
        start = time.time()
        for _ in range(n_ticks):
            engine.step(state)
        elapsed = time.time() - start
        return {"units": n_units, "ticks": n_ticks, "elapsed_s": elapsed,
                "ticks_per_sec": n_ticks/max(elapsed, 0.001),
                "updates_per_sec": n_units*n_ticks/max(elapsed, 0.001)}

    def benchmark_serialization(self, n_units: int = 100, iterations: int = 100) -> Dict:
        state = BattlefieldState()
        rng = np.random.default_rng(42)
        for i in range(n_units):
            state.add_unit(UnitState(uid=f"U{i:04d}", callsign=f"U{i}", unit_type="infantry",
                                     lat=34+rng.random()*0.5, lon=-117.5+rng.random()*0.5))
        start = time.time()
        for _ in range(iterations):
            d = state.to_dict()
            BattlefieldState.from_dict(d)
        elapsed = time.time() - start
        ue5_start = time.time()
        for _ in range(iterations):
            state.serialize_for_ue5()
        ue5_elapsed = time.time() - ue5_start
        return {"units": n_units, "iterations": iterations,
                "dict_roundtrip_s": elapsed, "ue5_serialize_s": ue5_elapsed,
                "dict_per_sec": iterations/max(elapsed, 0.001),
                "ue5_per_sec": iterations/max(ue5_elapsed, 0.001)}

    def benchmark_path_planning(self, grid_sizes: List[int] = None) -> Dict:
        from planning.dstar_lite import DStarLitePlanner
        grid_sizes = grid_sizes or [50, 100, 200]
        results = {}
        planner = DStarLitePlanner()
        for size in grid_sizes:
            grid = np.ones((size, size), dtype=np.float32)
            grid[size//3:2*size//3, size//2] = 999
            start = time.time()
            path = planner.plan((0, 0), (size-1, size-1), grid)
            elapsed = (time.time() - start) * 1000
            results[f"{size}x{size}"] = {"time_ms": elapsed, "path_length": len(path)}
        return results

    def run_all_benchmarks(self) -> Dict:
        log.info("Running benchmarks...")
        return {
            "sim_throughput": self.benchmark_sim_throughput(),
            "serialization": self.benchmark_serialization(),
            "path_planning": self.benchmark_path_planning(),
        }


if __name__ == "__main__":
    bench = Benchmark()
    results = bench.run_all_benchmarks()
    for name, data in results.items():
        print(f"\n{name}: {data}")
    print("\nbenchmark.py OK")
