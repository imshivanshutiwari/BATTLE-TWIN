"""LangGraph multi-agent graph runner — orchestrates all agents."""

from typing import Any, Dict
from agents.s2_intel_agent import S2IntelAgent
from agents.s3_maneuver_agent import S3ManeuverAgent
from agents.fso_fires_agent import FSOFiresAgent
from agents.s4_logistics_agent import S4LogisticsAgent
from agents.css_medevac_agent import CSSMedevacAgent
from utils.logger import get_logger

log = get_logger("GRAPH_RUNNER")

try:
    from langgraph.graph import StateGraph, END

    LANGGRAPH_AVAILABLE = True
except ImportError:
    LANGGRAPH_AVAILABLE = False


class AgentState(dict):
    """Typed state dictionary for the multi-agent graph."""

    pass


class GraphRunner:
    """
    LangGraph multi-agent orchestrator.
    Runs S2→S3→FSO→S4→CSS pipeline or individual agents.
    Falls back to sequential execution if LangGraph unavailable.
    """

    def __init__(self):
        self.s2 = S2IntelAgent()
        self.s3 = S3ManeuverAgent()
        self.fso = FSOFiresAgent()
        self.s4 = S4LogisticsAgent()
        self.css = CSSMedevacAgent()
        self._graph = None
        self._build_graph()

    def _build_graph(self):
        if not LANGGRAPH_AVAILABLE:
            log.warning("LangGraph unavailable, using sequential runner")
            return
        try:
            graph = StateGraph(AgentState)
            graph.add_node("s2_intel", self._s2_node)
            graph.add_node("s3_maneuver", self._s3_node)
            graph.add_node("fso_fires", self._fso_node)
            graph.add_node("s4_logistics", self._s4_node)
            graph.add_node("css_medevac", self._css_node)
            graph.set_entry_point("s2_intel")
            graph.add_edge("s2_intel", "s3_maneuver")
            graph.add_edge("s3_maneuver", "fso_fires")
            graph.add_edge("fso_fires", "s4_logistics")
            graph.add_edge("s4_logistics", "css_medevac")
            graph.add_edge("css_medevac", END)
            self._graph = graph.compile()
            log.info("LangGraph multi-agent graph compiled")
        except Exception as e:
            log.warning(f"Graph build failed: {e}")

    def _s2_node(self, state: AgentState) -> AgentState:
        contacts = state.get("contacts", [])
        result = self.s2.analyze_threats(contacts)
        state["s2_result"] = result
        state["threat_level"] = result.get("threat_level", 0.3)
        return state

    def _s3_node(self, state: AgentState) -> AgentState:
        units = state.get("units", [])
        objectives = state.get("objectives", [])
        result = self.s3.plan_maneuver(units, objectives)
        state["s3_result"] = result
        return state

    def _fso_node(self, state: AgentState) -> AgentState:
        targets = state.get("contacts", [])
        friendlies = [
            {"lat": u.get("lat", 0), "lon": u.get("lon", 0)} for u in state.get("units", [])
        ]
        result = self.fso.plan_fires(targets, friendlies)
        state["fso_result"] = result
        return state

    def _s4_node(self, state: AgentState) -> AgentState:
        units = state.get("units", [])
        result = self.s4.assess_logistics(units)
        state["s4_result"] = result
        return state

    def _css_node(self, state: AgentState) -> AgentState:
        state["css_result"] = self.css.get_status()
        return state

    def run_all(self, battlefield_state: Dict) -> Dict[str, Any]:
        initial_state = AgentState(
            {
                "units": list(battlefield_state.get("units", {}).values()),
                "contacts": list(battlefield_state.get("contacts", {}).values()),
                "objectives": battlefield_state.get("objectives", []),
            }
        )
        if self._graph:
            try:
                result = self._graph.invoke(initial_state)
                return dict(result)
            except Exception as e:
                log.warning(f"Graph run failed: {e}")
        return self._sequential_run(initial_state)

    def _sequential_run(self, state: AgentState) -> Dict:
        state = self._s2_node(state)
        state = self._s3_node(state)
        state = self._fso_node(state)
        state = self._s4_node(state)
        state = self._css_node(state)
        return dict(state)

    def run_single(self, agent_name: str, state: Dict) -> Dict:
        agent_state = AgentState(state)
        nodes = {
            "s2": self._s2_node,
            "s3": self._s3_node,
            "fso": self._fso_node,
            "s4": self._s4_node,
            "css": self._css_node,
        }
        if agent_name in nodes:
            return dict(nodes[agent_name](agent_state))
        raise ValueError(f"Unknown agent: {agent_name}")


if __name__ == "__main__":
    runner = GraphRunner()
    state = {
        "units": {
            "B01": {
                "uid": "B01",
                "callsign": "WARHORSE-1",
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
    print(f"S2 threat: {result.get('threat_level', 'N/A')}")
    print(f"S4 status: {result.get('s4_result', {}).get('supply_status', 'N/A')}")
    print(f"LangGraph: {LANGGRAPH_AVAILABLE}")
    print("graph_runner.py OK")
