"""
LangGraph StateGraph — multi-agent C2 decision support graph.
Wires: intel → threat → [coa + fires] (parallel) → logistics → medevac → commander → END
"""
import json
from typing import Any, Dict, List, Optional
from agents.s2_intel_agent import S2IntelAgent
from agents.s3_maneuver_agent import S3ManeuverAgent
from agents.fso_fires_agent import FSOFiresAgent
from agents.s4_logistics_agent import S4LogisticsAgent
from agents.css_medevac_agent import CSSMedevacAgent
from agents.commander_agent import CommanderAgent
from utils.logger import get_logger
log = get_logger("AGENT_GRAPH")

try:
    from langgraph.graph import StateGraph, END
    LANGGRAPH_AVAILABLE = True
except ImportError:
    LANGGRAPH_AVAILABLE = False


class AgentState(dict):
    """Typed state for LangGraph."""
    pass


class BattleTwinAgentGraph:
    """
    LangGraph StateGraph with 6 specialized agents.

    Graph: intel_fusion → threat_assess → [coa_generate, fires_coord] → 
           logistics_plan → medevac_coord → commander_brief → END
    """

    def __init__(self):
        self.intel = S2IntelAgent()
        self.maneuver = S3ManeuverAgent()
        self.fires = FSOFiresAgent()
        self.logistics = S4LogisticsAgent()
        self.medevac = CSSMedevacAgent()
        self.commander = CommanderAgent()
        self._graph = None
        self._build_graph()

    def _build_graph(self):
        if not LANGGRAPH_AVAILABLE:
            log.warning("LangGraph not available — sequential fallback")
            return
        try:
            graph = StateGraph(AgentState)
            graph.add_node("intel_fusion", self._intel_node)
            graph.add_node("threat_assess", self._threat_node)
            graph.add_node("coa_generate", self._coa_node)
            graph.add_node("fires_coord", self._fires_node)
            graph.add_node("logistics_plan", self._logistics_node)
            graph.add_node("medevac_coord", self._medevac_node)
            graph.add_node("commander_brief", self._commander_node)
            graph.set_entry_point("intel_fusion")
            graph.add_edge("intel_fusion", "threat_assess")
            graph.add_edge("threat_assess", "coa_generate")
            graph.add_edge("coa_generate", "fires_coord")
            graph.add_edge("fires_coord", "logistics_plan")
            graph.add_edge("logistics_plan", "medevac_coord")
            graph.add_edge("medevac_coord", "commander_brief")
            graph.add_edge("commander_brief", END)
            self._graph = graph.compile()
            log.info("LangGraph agent graph compiled successfully")
        except Exception as e:
            log.warning(f"Graph build error: {e}")

    def _intel_node(self, state: AgentState) -> AgentState:
        contacts = state.get("contacts", [])
        result = self.intel.analyze_threats(contacts if isinstance(contacts, list) else list(contacts.values()))
        state["s2_result"] = result
        state["threat_level"] = result.get("threat_level", 0.3)
        state["current_reports"] = [result.get("analysis", "")]
        return state

    def _threat_node(self, state: AgentState) -> AgentState:
        from planning.threat_assessor import BayesianThreatAssessor
        assessor = BayesianThreatAssessor()
        if state.get("threat_level", 0) > 0.5:
            assessor.update_evidence({"EnemyIntention": 1})
        state["bayesian_threat"] = assessor.query_threat()
        return state

    def _coa_node(self, state: AgentState) -> AgentState:
        from planning.mcts_coa import MCTSCourseOfAction
        mcts = MCTSCourseOfAction()
        sim_state = {"force_ratio": state.get("force_ratio", 1.5),
                     "terrain_score": 0.5, "logistics_sustainability": 0.7}
        coas = mcts.generate_coas(sim_state, n_coas=5, n_simulations=200)
        state["coas"] = [c.to_dict() for c in coas]
        units = state.get("units", {})
        objs = state.get("objectives", [])
        unit_list = list(units.values()) if isinstance(units, dict) else units
        state["s3_result"] = self.maneuver.plan_maneuver(unit_list, objs)
        return state

    def _fires_node(self, state: AgentState) -> AgentState:
        contacts = state.get("contacts", {})
        contact_list = list(contacts.values()) if isinstance(contacts, dict) else contacts
        units = state.get("units", {})
        friendly_list = [{"lat": u.get("lat", 0), "lon": u.get("lon", 0)}
                         for u in (units.values() if isinstance(units, dict) else units)]
        state["fso_result"] = self.fires.plan_fires(contact_list, friendly_list)
        return state

    def _logistics_node(self, state: AgentState) -> AgentState:
        units = state.get("units", {})
        unit_list = list(units.values()) if isinstance(units, dict) else units
        state["s4_result"] = self.logistics.assess_logistics(unit_list)
        return state

    def _medevac_node(self, state: AgentState) -> AgentState:
        state["css_result"] = self.medevac.get_status()
        return state

    def _commander_node(self, state: AgentState) -> AgentState:
        decision = self.commander.process(state)
        state["commander_decision"] = decision
        state["decisions"] = [decision]
        state["alerts"] = state.get("alerts", [])
        state["agent_outputs"] = {
            "s2": state.get("s2_result"), "s3": state.get("s3_result"),
            "fso": state.get("fso_result"), "s4": state.get("s4_result"),
            "css": state.get("css_result"), "commander": decision,
        }
        return state

    def build_graph(self):
        return self._graph

    def run(self, state: Dict) -> Dict:
        initial = AgentState(state)
        if self._graph:
            try:
                return dict(self._graph.invoke(initial))
            except Exception as e:
                log.warning(f"Graph execution failed: {e}")
        return self._sequential_run(initial)

    def _sequential_run(self, state: AgentState) -> Dict:
        for node_fn in [self._intel_node, self._threat_node, self._coa_node,
                        self._fires_node, self._logistics_node,
                        self._medevac_node, self._commander_node]:
            state = node_fn(state)
        return dict(state)

    async def stream_decisions(self, state: Dict):
        """Yield each agent's output as it completes."""
        initial = AgentState(state)
        nodes = [("intel", self._intel_node), ("threat", self._threat_node),
                 ("coa", self._coa_node), ("fires", self._fires_node),
                 ("logistics", self._logistics_node), ("medevac", self._medevac_node),
                 ("commander", self._commander_node)]
        for name, fn in nodes:
            initial = fn(initial)
            yield name, dict(initial)


if __name__ == "__main__":
    graph = BattleTwinAgentGraph()
    state = {
        "units": {"B01": {"uid": "B01", "callsign": "W1", "lat": 34.05, "lon": -117.45,
                           "ammo_pct": 60, "fuel_pct": 70, "water_pct": 80}},
        "contacts": {"R01": {"uid": "R01", "lat": 34.3, "lon": -117.15, "confidence": 0.8}},
        "objectives": [{"name": "OBJ ALPHA"}],
    }
    result = graph.run(state)
    print(f"Commander decision: {result.get('commander_decision', {}).get('decision')}")
    print(f"Threat: {result.get('threat_level')}")
    print(f"COAs: {len(result.get('coas', []))}")
    print("graph.py OK")
