"""
MCTS Course of Action generator.
Generates and evaluates multiple COAs via Monte Carlo Tree Search.
"""
import math
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
import numpy as np
from utils.logger import get_logger
log = get_logger("MCTS_COA")

ACTIONS = ["ATTACK", "DEFEND", "DELAY", "WITHDRAW", "CONSOLIDATE", "BYPASS", "ENVELOP"]


@dataclass
class COA:
    coa_id: str
    name: str
    actions: List[str]
    score: float = 0.0
    feasibility: float = 0.0
    acceptability: float = 0.0
    suitability: float = 0.0
    risk: float = 0.0
    time_factor: float = 0.0
    resource_cost: float = 0.0
    brief: str = ""
    def to_dict(self):
        return {"id": self.coa_id, "name": self.name, "actions": self.actions,
                "score": self.score, "feasibility": self.feasibility,
                "acceptability": self.acceptability, "suitability": self.suitability,
                "risk": self.risk, "time": self.time_factor, "resource_cost": self.resource_cost,
                "brief": self.brief}


class MCTSNode:
    def __init__(self, action=None, parent=None):
        self.action = action
        self.parent = parent
        self.children: List["MCTSNode"] = []
        self.visits = 0
        self.total_reward = 0.0
    @property
    def avg_reward(self):
        return self.total_reward / max(self.visits, 1)
    def ucb1(self, c=1.414):
        if self.visits == 0:
            return float('inf')
        parent_visits = self.parent.visits if self.parent else 1
        return self.avg_reward + c * math.sqrt(math.log(parent_visits) / self.visits)


class MCTSCourseOfAction:
    """MCTS for COA generation. Generates and ranks multiple courses of action."""

    def __init__(self, exploration_c=1.414, max_depth=10, reward_weights=None):
        self.exploration_c = exploration_c
        self.max_depth = max_depth
        self.reward_weights = reward_weights or {
            "terrain_advantage": 0.25, "force_ratio": 0.30,
            "logistics_sustainability": 0.20, "time_factor": 0.15, "risk": 0.10,
        }
        self._rng = np.random.default_rng(42)

    def _compute_reward(self, actions: List[str], state: Dict) -> float:
        force_ratio = state.get("force_ratio", 1.0)
        terrain_score = state.get("terrain_score", 0.5)
        logistics = state.get("logistics_sustainability", 0.7)
        # Action-specific modifiers
        attack_count = actions.count("ATTACK") + actions.count("ENVELOP")
        defend_count = actions.count("DEFEND") + actions.count("CONSOLIDATE")
        if force_ratio > 2.0:
            attack_bonus = 0.3
        elif force_ratio < 0.5:
            attack_bonus = -0.3
        else:
            attack_bonus = 0.0
        risk = 0.3 + 0.1 * attack_count - 0.05 * defend_count
        time_score = 1.0 / (1.0 + len(actions) * 0.1)
        reward = (
            self.reward_weights["terrain_advantage"] * terrain_score
            + self.reward_weights["force_ratio"] * min(force_ratio / 3.0, 1.0)
            + self.reward_weights["logistics_sustainability"] * logistics
            + self.reward_weights["time_factor"] * time_score
            + self.reward_weights["risk"] * (1.0 - risk)
            + attack_bonus * 0.2
        )
        return float(np.clip(reward + self._rng.normal(0, 0.05), 0, 1))

    def _select(self, node: MCTSNode) -> MCTSNode:
        while node.children:
            node = max(node.children, key=lambda c: c.ucb1(self.exploration_c))
        return node

    def _expand(self, node: MCTSNode, depth: int) -> MCTSNode:
        if depth >= self.max_depth:
            return node
        for action in ACTIONS:
            child = MCTSNode(action=action, parent=node)
            node.children.append(child)
        return self._rng.choice(node.children) if node.children else node

    def _simulate(self, node: MCTSNode, state: Dict, depth: int) -> float:
        actions = []
        current = node
        while current.parent:
            if current.action:
                actions.append(current.action)
            current = current.parent
        actions.reverse()
        for _ in range(self.max_depth - depth):
            actions.append(self._rng.choice(ACTIONS))
        return self._compute_reward(actions, state)

    def _backpropagate(self, node: MCTSNode, reward: float):
        while node:
            node.visits += 1
            node.total_reward += reward
            node = node.parent

    def generate_coas(self, state: Dict, n_coas: int = 5,
                      n_simulations: int = 1000) -> List[COA]:
        root = MCTSNode()
        for _ in range(n_simulations):
            leaf = self._select(root)
            depth = 0
            n = leaf
            while n.parent:
                depth += 1
                n = n.parent
            child = self._expand(leaf, depth)
            reward = self._simulate(child, state, depth)
            self._backpropagate(child, reward)

        # Extract top COAs from tree
        coas = []
        sorted_children = sorted(root.children, key=lambda c: c.avg_reward, reverse=True)
        for i, child in enumerate(sorted_children[:n_coas]):
            actions = [child.action]
            best = child
            for _ in range(self.max_depth - 1):
                if best.children:
                    best = max(best.children, key=lambda c: c.avg_reward)
                    actions.append(best.action)
                else:
                    actions.append(self._rng.choice(ACTIONS))
            coa = COA(
                coa_id=f"COA-{i+1}", name=f"COA {actions[0]}-{actions[1]}",
                actions=actions, score=child.avg_reward,
                feasibility=0.5 + child.avg_reward * 0.5,
                acceptability=0.6 + child.avg_reward * 0.3,
                suitability=child.avg_reward,
                risk=1.0 - child.avg_reward,
                time_factor=1.0 / (1 + len(actions) * 0.1),
                resource_cost=actions.count("ATTACK") * 0.2,
            )
            coa.brief = self.brief_coa(coa)
            coas.append(coa)
        log.info(f"Generated {len(coas)} COAs from {n_simulations} simulations")
        return coas

    def evaluate_coa(self, coa: COA, state: Dict) -> float:
        return self._compute_reward(coa.actions, state)

    def compare_coas(self, coas: List[COA]) -> List[COA]:
        return sorted(coas, key=lambda c: c.score, reverse=True)

    def brief_coa(self, coa: COA) -> str:
        phase_strs = [f"Phase {i+1}: {a}" for i, a in enumerate(coa.actions[:5])]
        return (f"{coa.name}\n" + "\n".join(phase_strs) +
                f"\nOverall Score: {coa.score:.2f}, Risk: {coa.risk:.2f}")

    def get_mcts_tree_data(self, root: MCTSNode = None, max_depth: int = 3) -> Dict:
        """Export partial tree for visualization."""
        if root is None:
            return {}
        def _export(node, depth):
            if depth > max_depth:
                return None
            return {
                "action": node.action, "visits": node.visits,
                "reward": node.avg_reward,
                "children": [_export(c, depth+1) for c in node.children[:5] if c.visits > 0],
            }
        return _export(root, 0)


if __name__ == "__main__":
    mcts = MCTSCourseOfAction()
    state = {"force_ratio": 2.4, "terrain_score": 0.6, "logistics_sustainability": 0.8}
    coas = mcts.generate_coas(state, n_coas=5, n_simulations=500)
    for coa in coas:
        print(f"{coa.coa_id}: {coa.actions[:3]} score={coa.score:.3f}")
    print("mcts_coa.py OK")
