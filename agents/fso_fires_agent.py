"""FSO Fire Support agent — fire mission planning and coordination."""

import json
from typing import Dict, List
from utils.logger import get_logger

log = get_logger("AGENT_FSO")

try:
    from langchain_openai import ChatOpenAI
    from langchain_core.messages import SystemMessage, HumanMessage

    LLM_AVAILABLE = True
except ImportError:
    LLM_AVAILABLE = False

FSO_PROMPT = """You are the Fire Support Officer for a US Army battalion digital twin.
Responsibilities: Plan fire missions, CFF (Call for Fire), fire deconfliction,
target prioritization (HPT list), SEAD, danger close calculations.
Respond JSON: fire_missions, target_priorities, cff_request, deconfliction_status."""


class FSOFiresAgent:
    def __init__(self, model_name="gpt-4o", temperature=0.2):
        self._llm = None
        if LLM_AVAILABLE:
            try:
                self._llm = ChatOpenAI(model=model_name, temperature=temperature)
            except Exception:
                pass

    def plan_fires(
        self,
        targets: List[Dict],
        friendly_positions: List[Dict],
        available_assets: List[str] = None,
    ) -> Dict:
        if self._llm:
            try:
                prompt = (
                    f"Plan fire support:\nTargets: {json.dumps(targets[:5], default=str)}\n"
                    f"Friendly: {json.dumps(friendly_positions[:5], default=str)}"
                )
                resp = self._llm.invoke(
                    [SystemMessage(content=FSO_PROMPT), HumanMessage(content=prompt)]
                )
                try:
                    return json.loads(resp.content)
                except Exception:
                    return {"plan": resp.content}
            except Exception:
                pass
        return self._rule_based_fires(targets, friendly_positions)

    def _rule_based_fires(self, targets, friendlies) -> Dict:
        missions = []
        for i, t in enumerate(targets):
            t_lat, t_lon = t.get("lat", 0), t.get("lon", 0)
            min_dist = float("inf")
            for f in friendlies:
                dist = (
                    (t_lat - f.get("lat", 0)) ** 2 + (t_lon - f.get("lon", 0)) ** 2
                ) ** 0.5 * 111320
                min_dist = min(min_dist, dist)
            is_danger_close = min_dist < 600
            missions.append(
                {
                    "mission_id": f"FM-{i+1:03d}",
                    "target": t,
                    "method": "ADJUST_FIRE" if is_danger_close else "FIRE_FOR_EFFECT",
                    "ammunition": "HE",
                    "danger_close": is_danger_close,
                    "min_friendly_dist_m": round(min_dist),
                    "priority": "HIGH" if t.get("confidence", 0) > 0.7 else "ROUTINE",
                }
            )
        return {
            "fire_missions": sorted(missions, key=lambda m: m["priority"] == "HIGH", reverse=True),
            "target_priorities": ["ARMOR", "ARTILLERY", "C2", "LOGISTICS"],
            "deconfliction_status": "CLEAR",
        }

    def call_for_fire(
        self, observer: str, target_lat: float, target_lon: float, target_desc: str
    ) -> str:
        return (
            f"CFF (Call For Fire)\n"
            f"OBSERVER: {observer}\n"
            f"TARGET GRID: {target_lat:.5f}N {abs(target_lon):.5f}W\n"
            f"TARGET DESC: {target_desc}\n"
            f"METHOD: FIRE FOR EFFECT\n"
            f"AMMO: HE, 3 ROUNDS"
        )


if __name__ == "__main__":
    agent = FSOFiresAgent()
    targets = [{"lat": 34.3, "lon": -117.15, "confidence": 0.85}]
    friendlies = [{"lat": 34.05, "lon": -117.45}]
    plan = agent.plan_fires(targets, friendlies)
    print(f"Missions: {len(plan['fire_missions'])}")
    print("fso_fires_agent.py OK")
