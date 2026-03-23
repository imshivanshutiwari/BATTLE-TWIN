"""S4 Logistics agent — supply management and convoy planning."""
import json
from typing import Any, Dict, List
from utils.logger import get_logger
log = get_logger("AGENT_S4")

try:
    from langchain_openai import ChatOpenAI
    from langchain_core.messages import SystemMessage, HumanMessage
    LLM_AVAILABLE = True
except ImportError:
    LLM_AVAILABLE = False

S4_PROMPT = """You are the S4 Logistics Officer for a US Army battalion digital twin.
Responsibilities: Monitor supply levels (ammo/fuel/water), plan resupply convoys,
manage MSRs/ASRs, coordinate with VRP optimizer, prioritize units needing resupply.
Respond JSON: resupply_priority, convoy_plan, supply_status, critical_shortages."""


class S4LogisticsAgent:
    def __init__(self, model_name="gpt-4o", temperature=0.2):
        self._llm = None
        if LLM_AVAILABLE:
            try: self._llm = ChatOpenAI(model=model_name, temperature=temperature)
            except: pass

    def assess_logistics(self, units: List[Dict]) -> Dict:
        if self._llm:
            try:
                resp = self._llm.invoke([SystemMessage(content=S4_PROMPT),
                    HumanMessage(content=f"Assess logistics: {json.dumps(units[:10], default=str)}")])
                try: return json.loads(resp.content)
                except: return {"assessment": resp.content}
            except: pass
        return self._rule_based_assessment(units)

    def _rule_based_assessment(self, units: List[Dict]) -> Dict:
        critical = []
        priority_list = []
        for u in units:
            uid = u.get("uid", "UNKNOWN")
            ammo = u.get("ammo_pct", 100)
            fuel = u.get("fuel_pct", 100)
            water = u.get("water_pct", 100)
            min_supply = min(ammo, fuel, water)
            if min_supply < 30:
                critical.append({"uid": uid, "critical_type": "ammo" if ammo == min_supply else "fuel" if fuel == min_supply else "water", "level": min_supply})
            priority_score = (100 - ammo) * 0.4 + (100 - fuel) * 0.35 + (100 - water) * 0.25
            priority_list.append({"uid": uid, "priority_score": round(priority_score, 1), "ammo": ammo, "fuel": fuel, "water": water})
        priority_list.sort(key=lambda x: x["priority_score"], reverse=True)
        return {
            "resupply_priority": priority_list[:5],
            "critical_shortages": critical,
            "convoy_plan": {"n_convoys_needed": max(1, len(critical)), "route": "MSR TAMPA"},
            "supply_status": "RED" if critical else "AMBER" if priority_list and priority_list[0]["priority_score"] > 30 else "GREEN",
        }

    def plan_convoy(self, units: List[Dict], depot: Dict = None) -> Dict:
        assessment = self.assess_logistics(units)
        needy = assessment["resupply_priority"][:5]
        return {
            "convoy_units": [u["uid"] for u in needy],
            "route": "MSR TAMPA → ASP → Units → MSR TAMPA",
            "estimated_time_h": 2 + len(needy) * 0.5,
            "cargo_manifest": {"ammo": "Class V", "fuel": "Class III", "water": "Class I"},
        }


if __name__ == "__main__":
    agent = S4LogisticsAgent()
    units = [{"uid": "B01", "ammo_pct": 25, "fuel_pct": 40, "water_pct": 60},
             {"uid": "B02", "ammo_pct": 80, "fuel_pct": 90, "water_pct": 85}]
    result = agent.assess_logistics(units)
    print(f"Status: {result['supply_status']}, Critical: {len(result['critical_shortages'])}")
    print("s4_logistics_agent.py OK")
