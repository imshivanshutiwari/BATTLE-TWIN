"""Tests for agent modules and graph runner."""

from agents.s2_intel_agent import S2IntelAgent
from agents.s3_maneuver_agent import S3ManeuverAgent
from agents.fso_fires_agent import FSOFiresAgent
from agents.s4_logistics_agent import S4LogisticsAgent
from agents.css_medevac_agent import CSSMedevacAgent
from agents.graph_runner import GraphRunner


def test_s2_rule_based():
    agent = S2IntelAgent()
    contacts = [{"uid": "R01", "confidence": 0.85, "lat": 34.3}]
    result = agent.analyze_threats(contacts)
    assert "threat_level" in result
    assert 0 <= result["threat_level"] <= 1


def test_s3_rule_based():
    agent = S3ManeuverAgent()
    units = [{"callsign": "W1", "type": "infantry"}]
    objs = [{"name": "OBJ ALPHA"}]
    plan = agent.plan_maneuver(units, objs)
    assert "orders" in plan


def test_fso_rule_based():
    agent = FSOFiresAgent()
    targets = [{"lat": 34.3, "lon": -117.15, "confidence": 0.8}]
    friendlies = [{"lat": 34.05, "lon": -117.45}]
    plan = agent.plan_fires(targets, friendlies)
    assert "fire_missions" in plan


def test_s4_rule_based():
    agent = S4LogisticsAgent()
    units = [{"uid": "B01", "ammo_pct": 20, "fuel_pct": 30, "water_pct": 50}]
    result = agent.assess_logistics(units)
    assert result["supply_status"] in ("RED", "AMBER", "GREEN")


def test_css_medevac_9line():
    agent = CSSMedevacAgent()
    req = agent.generate_9line("B01", 34.05, -117.45, n_patients=2, precedence="URGENT")
    assert req["precedence"] == "URGENT"
    assert "line1_location" in req


def test_graph_runner_sequential():
    runner = GraphRunner()
    state = {
        "units": {
            "B01": {
                "uid": "B01",
                "callsign": "W1",
                "lat": 34.05,
                "lon": -117.45,
                "ammo_pct": 60,
                "fuel_pct": 70,
                "water_pct": 80,
            }
        },
        "contacts": {"R01": {"uid": "R01", "lat": 34.3, "lon": -117.15, "confidence": 0.8}},
        "objectives": [{"name": "OBJ ALPHA"}],
    }
    result = runner.run_all(state)
    assert "s2_result" in result
    assert "s3_result" in result
    assert "s4_result" in result
