"""S2 Intelligence agent — threat analysis and enemy situation tracking."""

import json
from typing import Any, Dict, List
from utils.logger import get_logger

log = get_logger("AGENT_S2")

try:
    from langchain_openai import ChatOpenAI
    from langchain_core.messages import SystemMessage, HumanMessage

    LLM_AVAILABLE = True
except ImportError:
    LLM_AVAILABLE = False

S2_SYSTEM_PROMPT = """You are the S2 Intelligence Officer for a US Army battalion-level digital twin.
Your responsibilities:
1. Analyze enemy contact reports and maintain the enemy situation
2. Assess threat levels using available intelligence
3. Predict enemy courses of action
4. Update the enemy Order of Battle
5. Generate SALUTE reports and PIRs
Respond with structured JSON containing: threat_level (0-1), analysis, recommendation, enemy_coa_prediction."""


class S2IntelAgent:
    """S2 Intelligence agent for threat analysis."""

    def __init__(self, model_name="gpt-4o", temperature=0.3):
        self.model_name = model_name
        self._llm = None
        if LLM_AVAILABLE:
            try:
                self._llm = ChatOpenAI(model=model_name, temperature=temperature)
            except Exception as e:
                log.warning(f"LLM init failed: {e}")

    def analyze_threats(
        self, contacts: List[Dict], current_situation: Dict = None
    ) -> Dict[str, Any]:
        prompt = f"Analyze these enemy contacts and assess threat:\nContacts: {json.dumps(contacts[:10], default=str)}"
        if current_situation:
            prompt += f"\nCurrent situation: {json.dumps(current_situation, default=str)}"
        if self._llm:
            try:
                response = self._llm.invoke(
                    [
                        SystemMessage(content=S2_SYSTEM_PROMPT),
                        HumanMessage(content=prompt),
                    ]
                )
                try:
                    return json.loads(response.content)
                except json.JSONDecodeError:
                    return {"analysis": response.content, "threat_level": 0.5}
            except Exception as e:
                log.warning(f"LLM call failed: {e}")
        return self._rule_based_analysis(contacts)

    def _rule_based_analysis(self, contacts: List[Dict]) -> Dict[str, Any]:
        n = len(contacts)
        avg_conf = sum(c.get("confidence", 0.5) for c in contacts) / max(n, 1)
        high_conf = sum(1 for c in contacts if c.get("confidence", 0) > 0.7)
        threat = min(1.0, 0.2 + n * 0.1 + avg_conf * 0.3)
        coa = "DEFEND" if n > 3 else "PROBE" if n > 1 else "RECON"
        return {
            "threat_level": round(threat, 3),
            "analysis": f"{n} contacts detected, {high_conf} high-confidence. Average confidence: {avg_conf:.2f}",
            "recommendation": f"Recommend {'increased vigilance' if threat > 0.6 else 'normal operations'}",
            "enemy_coa_prediction": coa,
            "priority_intel_requirements": [
                "Confirm enemy strength",
                "Identify unit type",
                "Determine intent",
            ],
        }

    def generate_intsum(self, contacts: List[Dict], weather: Dict = None) -> str:
        analysis = self.analyze_threats(contacts)
        return (
            f"INTELLIGENCE SUMMARY\n"
            f"Threat Level: {analysis['threat_level']}\n"
            f"Analysis: {analysis['analysis']}\n"
            f"Enemy COA: {analysis['enemy_coa_prediction']}\n"
            f"Recommendation: {analysis['recommendation']}"
        )


if __name__ == "__main__":
    agent = S2IntelAgent()
    contacts = [
        {"uid": "RED-01", "confidence": 0.85, "lat": 34.3},
        {"uid": "RED-02", "confidence": 0.6, "lat": 34.25},
    ]
    result = agent.analyze_threats(contacts)
    print(f"Threat: {result['threat_level']}, COA: {result['enemy_coa_prediction']}")
    print("s2_intel_agent.py OK")
