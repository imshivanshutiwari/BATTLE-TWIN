"""
State reconciler for merging conflicting digital twin updates.

Implements last-writer-wins with conflict detection for concurrent
updates from multiple sources (sensors, agents, manual inputs).
"""

import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from utils.logger import get_logger

log = get_logger("STATE_RECONCILER")


class ConflictRecord:
    """Record of a state conflict."""

    def __init__(
        self,
        field: str,
        value_a: Any,
        value_b: Any,
        source_a: str,
        source_b: str,
        resolved_value: Any,
        strategy: str,
    ):
        self.field = field
        self.value_a = value_a
        self.value_b = value_b
        self.source_a = source_a
        self.source_b = source_b
        self.resolved_value = resolved_value
        self.strategy = strategy
        self.timestamp = datetime.now(tz=timezone.utc)


class StateReconciler:
    """
    Merges conflicting state updates from multiple sources.

    Strategies:
    - LAST_WRITER_WINS: Most recent timestamp wins (default)
    - HIGHEST_CONFIDENCE: Highest confidence source wins
    - WEIGHTED_AVERAGE: Weighted average for numeric fields
    - PRIORITY_SOURCE: Named source always wins
    """

    def __init__(
        self,
        strategy: str = "LAST_WRITER_WINS",
        priority_sources: Optional[List[str]] = None,
    ):
        self.strategy = strategy
        self.priority_sources = priority_sources or ["COMMANDER", "SIGINT", "IMINT"]
        self._conflict_log: List[ConflictRecord] = []
        self._source_weights: Dict[str, float] = {
            "SIGINT": 0.9,
            "IMINT": 0.85,
            "HUMINT": 0.6,
            "SENSOR": 0.75,
            "GPS": 0.95,
            "IMU": 0.7,
            "MANUAL": 0.5,
            "COMMANDER": 1.0,
        }

    def reconcile(
        self,
        current_state: Dict[str, Any],
        update_a: Dict[str, Any],
        update_b: Dict[str, Any],
        source_a: str = "SOURCE_A",
        source_b: str = "SOURCE_B",
        timestamp_a: Optional[float] = None,
        timestamp_b: Optional[float] = None,
    ) -> Dict[str, Any]:
        """
        Reconcile two conflicting updates into a single state.

        Args:
            current_state: Current canonical state.
            update_a: First update dict.
            update_b: Second update dict.
            source_a: Source of update A.
            source_b: Source of update B.
            timestamp_a: Timestamp of update A.
            timestamp_b: Timestamp of update B.

        Returns:
            Reconciled state dictionary.
        """
        ts_a = timestamp_a or time.time()
        ts_b = timestamp_b or time.time()

        result = dict(current_state)

        # Find conflicting fields
        all_fields = set(update_a.keys()) | set(update_b.keys())

        for field in all_fields:
            in_a = field in update_a
            in_b = field in update_b

            if in_a and in_b:
                # Both updates modify this field — conflict!
                val_a = update_a[field]
                val_b = update_b[field]

                if val_a == val_b:
                    result[field] = val_a
                    continue

                resolved = self._resolve_conflict(
                    field, val_a, val_b, source_a, source_b, ts_a, ts_b
                )
                result[field] = resolved

                self._conflict_log.append(
                    ConflictRecord(
                        field=field,
                        value_a=val_a,
                        value_b=val_b,
                        source_a=source_a,
                        source_b=source_b,
                        resolved_value=resolved,
                        strategy=self.strategy,
                    )
                )

            elif in_a:
                result[field] = update_a[field]
            elif in_b:
                result[field] = update_b[field]

        return result

    def _resolve_conflict(
        self,
        field: str,
        val_a: Any,
        val_b: Any,
        source_a: str,
        source_b: str,
        ts_a: float,
        ts_b: float,
    ) -> Any:
        """Resolve a single field conflict using configured strategy."""
        if self.strategy == "LAST_WRITER_WINS":
            return val_b if ts_b >= ts_a else val_a

        elif self.strategy == "PRIORITY_SOURCE":
            idx_a = (
                self.priority_sources.index(source_a) if source_a in self.priority_sources else 999
            )
            idx_b = (
                self.priority_sources.index(source_b) if source_b in self.priority_sources else 999
            )
            return val_a if idx_a <= idx_b else val_b

        elif self.strategy == "HIGHEST_CONFIDENCE":
            weight_a = self._source_weights.get(source_a, 0.5)
            weight_b = self._source_weights.get(source_b, 0.5)
            return val_a if weight_a >= weight_b else val_b

        elif self.strategy == "WEIGHTED_AVERAGE":
            if isinstance(val_a, (int, float)) and isinstance(val_b, (int, float)):
                weight_a = self._source_weights.get(source_a, 0.5)
                weight_b = self._source_weights.get(source_b, 0.5)
                total = weight_a + weight_b
                return (val_a * weight_a + val_b * weight_b) / total
            # Fall back to last writer for non-numeric
            return val_b if ts_b >= ts_a else val_a

        # Default
        return val_b if ts_b >= ts_a else val_a

    def merge_unit_updates(
        self,
        current: Dict[str, Any],
        updates: List[Tuple[Dict[str, Any], str, float]],
    ) -> Dict[str, Any]:
        """
        Merge multiple updates for a single unit sequentially.

        Args:
            current: Current unit state dict.
            updates: List of (delta, source, timestamp) tuples.

        Returns:
            Merged state dictionary.
        """
        result = dict(current)
        if not updates:
            return result

        # Sort by timestamp — earlier updates applied first
        sorted_updates = sorted(updates, key=lambda x: x[2])

        # Fold each delta into the accumulated result using the configured strategy.
        # For every update, reconcile the current values of affected fields (prev)
        # against the incoming delta (next), accumulating into result.
        prev_source = "CURRENT"
        prev_ts = sorted_updates[0][2] - 1.0  # just before the first update

        for delta, source, ts in sorted_updates:
            # Build a "current-state slice" containing only fields touched by this delta
            current_slice = {k: result[k] for k in delta if k in result}
            result = self.reconcile(
                result,
                current_slice,
                delta,
                prev_source,
                source,
                prev_ts,
                ts,
            )
            prev_source = source
            prev_ts = ts

        return result

    def get_conflict_log(self, last_n: int = 50) -> List[Dict[str, Any]]:
        """Get recent conflict records."""
        return [
            {
                "field": r.field,
                "value_a": str(r.value_a),
                "value_b": str(r.value_b),
                "source_a": r.source_a,
                "source_b": r.source_b,
                "resolved": str(r.resolved_value),
                "strategy": r.strategy,
                "timestamp": r.timestamp.isoformat(),
            }
            for r in self._conflict_log[-last_n:]
        ]

    def clear_log(self) -> None:
        """Clear the conflict log."""
        self._conflict_log.clear()


if __name__ == "__main__":
    reconciler = StateReconciler(strategy="LAST_WRITER_WINS")

    current = {"lat": 34.05, "lon": -117.45, "speed_mps": 0.0}
    update_a = {"lat": 34.06, "speed_mps": 2.5}
    update_b = {"lat": 34.07, "speed_mps": 3.0}

    result = reconciler.reconcile(current, update_a, update_b, "GPS", "IMU", 1000.0, 1001.0)
    print(f"Reconciled: {result}")
    print(f"Conflicts: {len(reconciler.get_conflict_log())}")

    print("state_reconciler.py OK")
