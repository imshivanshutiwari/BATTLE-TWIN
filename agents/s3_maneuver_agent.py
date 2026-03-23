"""S3 Maneuver agent — movement orders and COA execution."""
import json
from typing import Any, Dict, List, Optional
from utils.logger import get_logger
log = get_logger("AGENT_S3")

try:
    from langchain_openai import ChatOpenAI
    from langchain_core.messages import SystemMessage, HumanMessage
    LLM_AVAILABLE = True
except ImportError:
    LLM_AVAILABLE = False

S3_SYSTEM_PROMPT = """You are the S3 Operations Officer for a US Army battalion digital twin.
Your responsibilities:
1. Plan and execute tactical maneuvers
2. Issue OPORD fragments (FRAGOs)
3. Coordinate movement with fire support
4. Manage control measures (phase lines, objectives)
5. Synchronize combined arms operations
Respond in structured JSON: orders, movement_plan, synchronization_matrix, risk_assessment."""


class S3ManeuverAgent:
    def __init__(self, model_name="gpt-4o", temperature=0.3):
        self._llm = None
        if LLM_AVAILABLE:
            try:
                self._llm = ChatOpenAI(model=model_name, temperature=temperature)
            except Exception:
                pass

    def plan_maneuver(self, units: List[Dict], objectives: List[Dict],
                      terrain: Dict = None, threats: Dict = None) -> Dict[str, Any]:
        prompt = (f"Plan maneuver for units:\n{json.dumps(units[:10], default=str)}\n"
                  f"Objectives: {json.dumps(objectives, default=str)}")
        if self._llm:
            try:
                resp = self._llm.invoke([SystemMessage(content=S3_SYSTEM_PROMPT), HumanMessage(content=prompt)])
                try: return json.loads(resp.content)
                except: return {"plan": resp.content}
            except Exception as e:
                log.warning(f"LLM failed: {e}")
        return self._rule_based_plan(units, objectives)

    def _rule_based_plan(self, units, objectives) -> Dict:
        n_units = len(units)
        n_obj = len(objectives)
        assignments = {}
        for i, obj in enumerate(objectives):
            assigned = units[i % n_units] if units else {}
            assignments[obj.get("name", f"OBJ-{i}")] = assigned.get("callsign", f"UNIT-{i}")
        return {
            "orders": [{"unit": a, "objective": o, "action": "ATTACK"} for o, a in assignments.items()],
            "movement_plan": {"formation": "WEDGE", "speed": "DELIBERATE", "route": "COVERED_CONCEALED"},
            "synchronization_matrix": {"H_hour": "0600Z", "phase_1": "MOVEMENT_TO_CONTACT"},
            "risk_assessment": {"overall": "MODERATE", "mitigation": "MAINTAIN_DISPERSION"},
        }

    def issue_frago(self, situation_update: Dict) -> str:
        return (f"FRAGO\n1. SITUATION: {situation_update.get('situation', 'UNCHANGED')}\n"
                f"2. MISSION: Continue attack to seize objectives\n"
                f"3. EXECUTION: Adjust movement per threat update\n"
                f"4. SUSTAINMENT: LOG resupply at PL TIGER\n"
                f"5. COMMAND: CDR at CP1")


if __name__ == "__main__":
    agent = S3ManeuverAgent()
    units = [{"callsign": "WARHORSE-1", "type": "infantry"}, {"callsign": "WARHORSE-2", "type": "armor"}]
    objs = [{"name": "OBJ ALPHA"}, {"name": "OBJ BRAVO"}]
    plan = agent.plan_maneuver(units, objs)
    print(f"Orders: {plan['orders']}")
    print("s3_maneuver_agent.py OK")
