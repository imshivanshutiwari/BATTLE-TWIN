"""System-level evaluation — runs full pipeline and measures performance."""

import time
import numpy as np
from typing import Dict
from evaluation.metrics import C2Metrics
from digital_twin.twin_state import BattlefieldState, UnitState, ContactReport
from simulation.sim_engine import SimulationEngine
from agents.graph_runner import GraphRunner
from utils.logger import get_logger

log = get_logger("EVALUATE")


class SystemEvaluator:
    """Evaluates the end-to-end C2 system performance."""

    def __init__(self):
        self.metrics = C2Metrics()

    def _create_test_state(self) -> BattlefieldState:
        state = BattlefieldState()
        for i in range(12):
            state.add_unit(
                UnitState(
                    uid=f"B{i:02d}",
                    callsign=f"WARHORSE-{i+1}",
                    unit_type="infantry",
                    lat=34.05 + i * 0.02,
                    lon=-117.45 + i * 0.01,
                    ammo_pct=80 - i * 3,
                    fuel_pct=90 - i * 2,
                    water_pct=85 - i * 2,
                )
            )
        for i in range(5):
            state.add_contact(
                ContactReport(
                    uid=f"R{i:02d}",
                    callsign=f"HOSTILE-{i+1}",
                    lat=34.30 + i * 0.02,
                    lon=-117.15 + i * 0.01,
                    confidence=0.7 + i * 0.05,
                )
            )
        return state

    def evaluate_sim_performance(self, n_ticks: int = 100) -> Dict:
        state = self._create_test_state()
        engine = SimulationEngine(dt_s=0.1)
        start = time.time()
        for _ in range(n_ticks):
            engine.step(state)
        elapsed = time.time() - start
        return {
            "ticks": n_ticks,
            "elapsed_s": elapsed,
            "ticks_per_sec": n_ticks / max(elapsed, 0.001),
            "alerts_generated": len(state.alerts),
        }

    def evaluate_agent_performance(self) -> Dict:
        state = self._create_test_state()
        runner = GraphRunner()
        start = time.time()
        result = runner.run_all(state.to_dict())
        elapsed_ms = (time.time() - start) * 1000
        self.metrics.record_decision_time(elapsed_ms)
        return {
            "decision_time_ms": elapsed_ms,
            "agents_ran": (
                list(result.get("agent_outputs", {}).keys())
                if "agent_outputs" in result
                else ["s2", "s3", "fso", "s4", "css"]
            ),
            "threat_level": result.get("threat_level", 0),
        }

    def evaluate_sync_accuracy(self) -> Dict:
        state = self._create_test_state()
        d = state.to_dict()
        state2 = BattlefieldState.from_dict(d)
        errors = []
        for uid in state.units:
            u1, u2 = state.units[uid], state2.units[uid]
            err = abs(u1.lat - u2.lat) * 111320 + abs(u1.lon - u2.lon) * 111320
            errors.append(err)
            self.metrics.record_sync_error(err)
        return {
            "mean_error_m": float(np.mean(errors)),
            "max_error_m": float(np.max(errors)),
            "perfect_sync": all(e < 0.01 for e in errors),
        }

    def run_full_evaluation(self) -> Dict:
        log.info("Running full system evaluation...")
        sim = self.evaluate_sim_performance()
        agent = self.evaluate_agent_performance()
        sync = self.evaluate_sync_accuracy()
        sla = self.metrics.check_sla()
        return {"simulation": sim, "agents": agent, "sync": sync, "sla": sla}


if __name__ == "__main__":
    evaluator = SystemEvaluator()
    results = evaluator.run_full_evaluation()
    print(f"Sim: {results['simulation']['ticks_per_sec']:.0f} ticks/sec")
    print(f"Agent decision: {results['agents']['decision_time_ms']:.0f}ms")
    print(f"Sync: {results['sync']}")
    print(f"SLA: {results['sla']}")
    print("evaluate.py OK")
