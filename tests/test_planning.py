"""Tests for planning modules: D* Lite, MCTS COA, threat, VRP, MANET."""

import numpy as np
from planning.dstar_lite import DStarLitePlanner
from planning.mcts_coa import MCTSCourseOfAction
from planning.threat_assessor import BayesianThreatAssessor
from planning.vrp_logistics import VRPLogistics
from planning.manet_router import MANETRouter


def test_dstar_simple_path():
    planner = DStarLitePlanner()
    grid = np.ones((30, 30), dtype=np.float32)
    path = planner.plan((0, 0), (29, 29), grid)
    assert path.valid
    assert len(path) > 2


def test_dstar_with_obstacle():
    planner = DStarLitePlanner()
    grid = np.ones((30, 30), dtype=np.float32)
    grid[10:20, 15] = 999  # wall
    path = planner.plan((5, 5), (25, 25), grid)
    assert path.valid


def test_dstar_replan():
    planner = DStarLitePlanner()
    grid = np.ones((30, 30), dtype=np.float32)
    planner.plan((0, 0), (29, 29), grid)
    path2 = planner.replan((15, 15))
    assert path2 is not None


def test_mcts_generates_coas():
    mcts = MCTSCourseOfAction()
    state = {"force_ratio": 2.0, "terrain_score": 0.5, "logistics_sustainability": 0.7}
    coas = mcts.generate_coas(state, n_coas=3, n_simulations=100)
    assert len(coas) == 3
    assert all(c.score >= 0 for c in coas)


def test_mcts_coa_scored():
    mcts = MCTSCourseOfAction()
    state = {"force_ratio": 3.0, "terrain_score": 0.8, "logistics_sustainability": 0.9}
    coas = mcts.generate_coas(state, n_coas=5, n_simulations=200)
    ranked = mcts.compare_coas(coas)
    assert ranked[0].score >= ranked[-1].score


def test_threat_assessor():
    assessor = BayesianThreatAssessor()
    threat = assessor.query_threat("B01")
    assert 0 <= threat <= 1


def test_threat_with_evidence():
    assessor = BayesianThreatAssessor()
    assessor.update_evidence({"EnemyIntention": 1, "EnemyCapability": 1})
    threat = assessor.query_threat("B01")
    assert threat > 0.2  # Should be elevated


def test_vrp_greedy():
    vrp = VRPLogistics(max_vehicles=2)
    locs = [(34.05, -117.45), (34.10, -117.38), (34.15, -117.30)]
    sol = vrp.solve(locs)
    assert sol.total_distance_m > 0
    assert len(sol.routes) >= 1


def test_manet_routing():
    router = MANETRouter()
    router.add_node("N1", 34.05, -117.45, 8000)
    router.add_node("N2", 34.07, -117.42, 8000)
    router.add_node("N3", 34.10, -117.38, 8000)
    router.compute_routing_tables()
    route = router.get_route("N1", "N3")
    assert len(route) >= 2


def test_manet_stats():
    router = MANETRouter()
    router.add_node("N1", 34.0, -117.0, 8000)
    router.add_node("N2", 34.01, -117.0, 8000)
    router.compute_routing_tables()
    stats = router.get_network_stats()
    assert stats["total_nodes"] == 2
    assert stats["up_nodes"] == 2
