"""C2 system performance metrics."""

import numpy as np
from typing import Dict, List
from utils.logger import get_logger

log = get_logger("METRICS")


class C2Metrics:
    """Computes all C2 performance metrics."""

    def __init__(self):
        self._latencies: List[float] = []
        self._sync_errors: List[float] = []
        self._decision_times: List[float] = []
        self._message_counts: Dict[str, int] = {}

    def record_latency(self, latency_ms: float):
        self._latencies.append(latency_ms)

    def record_sync_error(self, error_m: float):
        self._sync_errors.append(error_m)

    def record_decision_time(self, time_ms: float):
        self._decision_times.append(time_ms)

    def record_message(self, topic: str):
        self._message_counts[topic] = self._message_counts.get(topic, 0) + 1

    def c2_latency_stats(self) -> Dict:
        if not self._latencies:
            return {"mean": 0, "p50": 0, "p95": 0, "p99": 0, "max": 0}
        arr = np.array(self._latencies)
        return {
            "mean": float(np.mean(arr)),
            "p50": float(np.percentile(arr, 50)),
            "p95": float(np.percentile(arr, 95)),
            "p99": float(np.percentile(arr, 99)),
            "max": float(np.max(arr)),
            "count": len(arr),
        }

    def sync_accuracy_stats(self) -> Dict:
        if not self._sync_errors:
            return {"mean_error_m": 0, "max_error_m": 0, "within_1m_pct": 100}
        arr = np.array(self._sync_errors)
        return {
            "mean_error_m": float(np.mean(arr)),
            "max_error_m": float(np.max(arr)),
            "within_1m_pct": float((arr < 1.0).sum() / len(arr) * 100),
        }

    def decision_time_stats(self) -> Dict:
        if not self._decision_times:
            return {"mean_ms": 0, "max_ms": 0}
        arr = np.array(self._decision_times)
        return {
            "mean_ms": float(np.mean(arr)),
            "max_ms": float(np.max(arr)),
            "under_500ms_pct": float((arr < 500).sum() / len(arr) * 100),
        }

    def throughput_stats(self) -> Dict:
        return {
            "total_messages": sum(self._message_counts.values()),
            "by_topic": dict(self._message_counts),
        }

    def all_metrics(self) -> Dict:
        return {
            "latency": self.c2_latency_stats(),
            "sync": self.sync_accuracy_stats(),
            "decisions": self.decision_time_stats(),
            "throughput": self.throughput_stats(),
        }

    def check_sla(self) -> Dict:
        lat = self.c2_latency_stats()
        sync = self.sync_accuracy_stats()
        return {
            "latency_p95_under_500ms": lat.get("p95", 0) < 500,
            "sync_within_1m": sync.get("within_1m_pct", 0) > 95,
            "all_pass": lat.get("p95", 0) < 500 and sync.get("within_1m_pct", 0) > 95,
        }


if __name__ == "__main__":
    m = C2Metrics()
    rng = np.random.default_rng(42)
    for _ in range(100):
        m.record_latency(rng.exponential(50))
        m.record_sync_error(rng.exponential(0.3))
        m.record_decision_time(rng.exponential(100))
    print(f"Metrics: {m.all_metrics()}")
    print(f"SLA: {m.check_sla()}")
    print("metrics.py OK")
