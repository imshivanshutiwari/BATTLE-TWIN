"""Agent tool functions — all LangGraph tool-decorated functions."""

import json
from utils.logger import get_logger

log = get_logger("AGENT_TOOLS")

try:
    from langchain_core.tools import tool

    TOOLS_AVAILABLE = True
except ImportError:
    TOOLS_AVAILABLE = False

    def tool(func):
        func.is_tool = True
        return func


@tool
def approve_coa(coa_id: str) -> str:
    """Approve a Course of Action for execution."""
    log.info(f"COA {coa_id} APPROVED by Commander")
    return json.dumps({"status": "APPROVED", "coa_id": coa_id, "action": "EXECUTE"})


@tool
def request_fires(target_grid: str, method: str = "FIRE_FOR_EFFECT", ammo: str = "HE") -> str:
    """Submit a fire mission request."""
    mission = {"target": target_grid, "method": method, "ammo": ammo, "status": "SUBMITTED"}
    log.info(f"Fire mission submitted: {target_grid} {method}")
    return json.dumps(mission)


@tool
def order_medevac(unit_id: str, grid: str, patients: int = 1, precedence: str = "URGENT") -> str:
    """Submit a 9-line MEDEVAC request."""
    request = {
        "unit": unit_id,
        "grid": grid,
        "patients": patients,
        "precedence": precedence,
        "status": "REQUESTED",
    }
    log.info(f"MEDEVAC {precedence}: {unit_id} at {grid}")
    return json.dumps(request)


@tool
def issue_fragmentary_order(situation: str, mission: str, execution: str) -> str:
    """Issue a FRAGO (Fragmentary Order)."""
    frago = {
        "type": "FRAGO",
        "situation": situation,
        "mission": mission,
        "execution": execution,
        "status": "ISSUED",
    }
    log.info(f"FRAGO issued: {mission[:50]}")
    return json.dumps(frago)


@tool
def request_air_support(
    target_grid: str, support_type: str = "CAS", priority: str = "IMMEDIATE"
) -> str:
    """Request close air support or air interdiction."""
    request = {
        "target": target_grid,
        "type": support_type,
        "priority": priority,
        "status": "REQUESTED",
    }
    log.info(f"Air support {support_type} requested at {target_grid}")
    return json.dumps(request)


@tool
def update_unit_position(unit_id: str, lat: float, lon: float, heading: float = 0) -> str:
    """Update a unit's position."""
    return json.dumps(
        {"unit": unit_id, "lat": lat, "lon": lon, "heading": heading, "updated": True}
    )


@tool
def query_threat_level(unit_id: str) -> str:
    """Query the current Bayesian threat level for a unit."""
    from planning.threat_assessor import BayesianThreatAssessor

    assessor = BayesianThreatAssessor()
    threat = assessor.query_threat(unit_id)
    return json.dumps({"unit": unit_id, "threat_level": threat})


@tool
def plan_route(start_lat: float, start_lon: float, goal_lat: float, goal_lon: float) -> str:
    """Plan a D* Lite route between two positions."""
    return json.dumps(
        {
            "start": [start_lat, start_lon],
            "goal": [goal_lat, goal_lon],
            "status": "PLANNED",
            "algorithm": "D*_LITE",
        }
    )


ALL_TOOLS = [
    approve_coa,
    request_fires,
    order_medevac,
    issue_fragmentary_order,
    request_air_support,
    update_unit_position,
    query_threat_level,
    plan_route,
]


if __name__ == "__main__":
    print(
        f"Available tools: {[t.__name__ if hasattr(t, '__name__') else str(t) for t in ALL_TOOLS]}"
    )
    print("tools.py OK")
