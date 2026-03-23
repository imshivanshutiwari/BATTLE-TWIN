"""Commander decision agent — synthesizes all agent outputs into actionable decisions."""
import json
from typing import Any, Dict, List
from utils.logger import get_logger
log = get_logger("AGENT_CDR")

try:
    from langchain_openai import ChatOpenAI
    from langchain_core.messages import SystemMessage, HumanMessage
    LLM_AVAILABLE = True
except ImportError:
    LLM_AVAILABLE = False

CDR_PROMPT = """You are the Battalion Commander for a US Army digital twin.
You synthesize all staff outputs (S2 Intel, S3 Maneuver, FSO Fires, S4 Logistics, CSS MEDEVAC)
into actionable decisions. Issue FRAGOs, approve COAs, prioritize actions.
Respond JSON: decision, priority_actions, sitrep, frago."""


class CommanderAgent:
    """Commander decision agent — top of the C2 chain."""

    def __init__(self, model_name="gpt-4o", temperature=0.2):
        self._llm = None
        if LLM_AVAILABLE:
            try:
                self._llm = ChatOpenAI(model=model_name, temperature=temperature)
            except Exception:
                pass

    def process(self, state: Dict) -> Dict:
        s2 = state.get("s2_result", {})
        s3 = state.get("s3_result", {})
        fso = state.get("fso_result", {})
        s4 = state.get("s4_result", {})
        css = state.get("css_result", {})
        if self._llm:
            try:
                prompt = (f"Synthesize staff outputs:\nS2: {json.dumps(s2, default=str)[:500]}\n"
                          f"S3: {json.dumps(s3, default=str)[:500]}\nS4: {json.dumps(s4, default=str)[:500]}")
                resp = self._llm.invoke([SystemMessage(content=CDR_PROMPT), HumanMessage(content=prompt)])
                try:
                    return json.loads(resp.content)
                except:
                    return {"decision": resp.content}
            except Exception as e:
                log.warning(f"LLM failed: {e}")
        return self._rule_based_decision(s2, s3, s4, fso, css)

    def _rule_based_decision(self, s2, s3, s4, fso, css) -> Dict:
        threat = s2.get("threat_level", 0.3)
        supply = s4.get("supply_status", "GREEN")
        priority_actions = []
        if threat > 0.7:
            priority_actions.append("INCREASE FORCE PROTECTION")
        if supply == "RED":
            priority_actions.append("EMERGENCY RESUPPLY")
        if threat > 0.5:
            priority_actions.append("REQUEST CAS ON STANDBY")
        priority_actions.append("CONTINUE MISSION")
        posture = "DEFEND" if threat > 0.7 else "ATTACK" if threat < 0.3 else "MOVEMENT_TO_CONTACT"
        return {
            "decision": posture,
            "priority_actions": priority_actions,
            "threat_level": threat,
            "supply_status": supply,
            "frago": f"FRAGO: {posture} posture, priority={priority_actions[0]}",
        }

    def generate_sitrep(self, state: Dict = None) -> str:
        threat = state.get("threat_level", 0.3) if state else 0.3
        n_units = len(state.get("units", {})) if state else 0
        n_contacts = len(state.get("contacts", {})) if state else 0
        return (f"SITREP\n"
                f"DTG: NOW\n"
                f"1. ENEMY: {n_contacts} contacts, threat level {threat:.0%}\n"
                f"2. FRIENDLY: {n_units} units operational\n"
                f"3. OPERATIONS: Continuing assigned mission\n"
                f"4. LOGISTICS: Supply status assessed\n"
                f"5. COMMS: Primary nets operational\n"
                f"6. GENERAL: No change to OPORD")

    def assess_mission_accomplishment(self, state: Dict = None) -> float:
        if not state:
            return 0.5
        threat = state.get("threat_level", 0.5)
        n_units = len(state.get("units", {}))
        score = 0.5 + (1.0 - threat) * 0.3 + min(n_units / 12, 1.0) * 0.2
        return min(1.0, max(0.0, score))


if __name__ == "__main__":
    cdr = CommanderAgent()
    state = {"s2_result": {"threat_level": 0.6}, "s4_result": {"supply_status": "AMBER"},
             "units": {"B01": {}}, "contacts": {"R01": {}}, "threat_level": 0.6}
    decision = cdr.process(state)
    print(f"Decision: {decision['decision']}")
    print(cdr.generate_sitrep(state))
    print(f"Mission: {cdr.assess_mission_accomplishment(state):.2f}")
    print("commander_agent.py OK")
