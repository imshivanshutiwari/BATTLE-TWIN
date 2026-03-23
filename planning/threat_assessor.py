"""
Bayesian threat assessment using pgmpy Bayesian network.
Nodes: EnemyIntention, EnemyCapability, TerrainAdvantage, AirThreat, IntelQuality → ThreatLevel.
"""

import numpy as np
from typing import Any, Dict, List
from utils.logger import get_logger

log = get_logger("THREAT")

try:
    from pgmpy.models import DiscreteBayesianNetwork
    from pgmpy.factors.discrete import TabularCPD
    from pgmpy.inference import VariableElimination

    PGMPY_AVAILABLE = True
except ImportError:
    try:
        from pgmpy.models import BayesianNetwork as DiscreteBayesianNetwork
        from pgmpy.factors.discrete import TabularCPD
        from pgmpy.inference import VariableElimination

        PGMPY_AVAILABLE = True
    except ImportError:
        PGMPY_AVAILABLE = False


class BayesianThreatAssessor:
    """Bayesian network for threat probability estimation per unit."""

    def __init__(self):
        self._model = None
        self._inference = None
        self._evidence: Dict[str, int] = {}
        self._unit_threats: Dict[str, float] = {}
        self.build_network()

    def build_network(self):
        if not PGMPY_AVAILABLE:
            log.warning("pgmpy not available, using simplified threat model")
            return
        model = DiscreteBayesianNetwork(
            [
                ("EnemyIntention", "ThreatLevel"),
                ("EnemyCapability", "ThreatLevel"),
                ("TerrainAdvantage", "ThreatLevel"),
                ("AirThreat", "ThreatLevel"),
                ("IntelQuality", "ThreatLevel"),
            ]
        )
        # CPDs: 0=LOW, 1=HIGH for parent nodes; 0=LOW,1=MED,2=HIGH for ThreatLevel
        cpd_intent = TabularCPD("EnemyIntention", 2, [[0.6], [0.4]])
        cpd_cap = TabularCPD("EnemyCapability", 2, [[0.5], [0.5]])
        cpd_terrain = TabularCPD("TerrainAdvantage", 2, [[0.5], [0.5]])
        cpd_air = TabularCPD("AirThreat", 2, [[0.7], [0.3]])
        cpd_intel = TabularCPD("IntelQuality", 2, [[0.4], [0.6]])
        # ThreatLevel CPD: conditioned on all 5 parents (2^5=32 columns)
        n_cols = 32
        threat_cpd_values = np.zeros((3, n_cols))
        for i in range(n_cols):
            bits = [(i >> b) & 1 for b in range(5)]
            high_count = sum(bits)
            if high_count <= 1:
                threat_cpd_values[:, i] = [0.7, 0.2, 0.1]
            elif high_count <= 2:
                threat_cpd_values[:, i] = [0.3, 0.5, 0.2]
            elif high_count <= 3:
                threat_cpd_values[:, i] = [0.1, 0.4, 0.5]
            else:
                threat_cpd_values[:, i] = [0.05, 0.2, 0.75]
        cpd_threat = TabularCPD(
            "ThreatLevel",
            3,
            threat_cpd_values.tolist(),
            evidence=[
                "EnemyIntention",
                "EnemyCapability",
                "TerrainAdvantage",
                "AirThreat",
                "IntelQuality",
            ],
            evidence_card=[2, 2, 2, 2, 2],
        )
        model.add_cpds(cpd_intent, cpd_cap, cpd_terrain, cpd_air, cpd_intel, cpd_threat)
        assert model.check_model()
        self._model = model
        self._inference = VariableElimination(model)
        log.info("Bayesian threat network built")

    def update_evidence(self, obs: Dict[str, int]) -> None:
        self._evidence.update(obs)

    def query_threat(self, unit_id: str = "") -> float:
        if not PGMPY_AVAILABLE or self._inference is None:
            score = 0.3 + sum(self._evidence.values()) * 0.1
            return min(1.0, max(0.0, score))
        try:
            result = self._inference.query(["ThreatLevel"], evidence=self._evidence)
            values = result.values
            # Weighted: LOW=0, MED=0.5, HIGH=1.0
            threat_score = values[0] * 0.0 + values[1] * 0.5 + values[2] * 1.0
            self._unit_threats[unit_id] = float(threat_score)
            return float(threat_score)
        except Exception as e:
            log.warning(f"Threat query error: {e}")
            return 0.3

    def update_from_contact(self, contact_dict: Dict[str, Any]) -> None:
        confidence = contact_dict.get("confidence", 0.5)
        self.update_evidence(
            {
                "EnemyIntention": 1 if confidence > 0.6 else 0,
                "EnemyCapability": (
                    1
                    if contact_dict.get("strength_estimate", "") in ("company", "battalion")
                    else 0
                ),
            }
        )

    def get_threat_map(self, grid_shape: tuple, contacts: List[Dict] = None) -> np.ndarray:
        base_threat = self.query_threat()
        threat_map = np.full(grid_shape, base_threat * 0.3, dtype=np.float32)
        if contacts:
            for c in contacts:
                r = int((c.get("lat", 0) % 1) * grid_shape[0]) % grid_shape[0]
                col = int((c.get("lon", 0) % 1) * grid_shape[1]) % grid_shape[1]
                conf = c.get("confidence", 0.5)
                for dr in range(-5, 6):
                    for dc in range(-5, 6):
                        rr, cc = r + dr, col + dc
                        if 0 <= rr < grid_shape[0] and 0 <= cc < grid_shape[1]:
                            dist = max(1, abs(dr) + abs(dc))
                            threat_map[rr, cc] = min(1.0, threat_map[rr, cc] + conf / dist)
        return threat_map

    def get_all_threats(self) -> Dict[str, float]:
        return dict(self._unit_threats)


if __name__ == "__main__":
    assessor = BayesianThreatAssessor()
    print(f"Base threat: {assessor.query_threat('BLUE-01'):.3f}")
    assessor.update_evidence({"EnemyIntention": 1, "EnemyCapability": 1})
    print(f"After contact: {assessor.query_threat('BLUE-01'):.3f}")
    threat_map = assessor.get_threat_map((50, 50))
    print(f"Threat map range: [{threat_map.min():.3f}, {threat_map.max():.3f}]")
    print("threat_assessor.py OK")
