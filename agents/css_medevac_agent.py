"""CSS MEDEVAC agent — 9-line MEDEVAC requests and CASEVAC coordination."""
import json
from typing import Any, Dict, List
from utils.logger import get_logger
log = get_logger("AGENT_CSS")


class CSSMedevacAgent:
    """Combat Service Support MEDEVAC agent."""

    def __init__(self):
        self._pending: List[Dict] = []
        self._completed: List[Dict] = []

    def generate_9line(self, unit_id: str, lat: float, lon: float,
                       n_patients: int = 1, precedence: str = "URGENT",
                       security: str = "NO_ENEMY", marking: str = "PANELS") -> Dict:
        from utils.mgrs_converter import MGRSConverter
        mgrs = MGRSConverter()
        grid = mgrs.latlon_to_mgrs_string(lat, lon)
        request = {
            "line1_location": grid,
            "line2_frequency": f"DUSTOFF-{unit_id}",
            "line3_patients": f"{n_patients}A" if precedence == "URGENT" else f"{n_patients}C",
            "line4_equipment": "NONE",
            "line5_patients_type": f"{n_patients} LITTER",
            "line6_security": security,
            "line7_marking": marking,
            "line8_nationality": "US_MILITARY",
            "line9_terrain": "FLAT_TERRAIN",
            "precedence": precedence,
            "requesting_unit": unit_id,
            "lat": lat, "lon": lon,
            "status": "REQUESTED",
        }
        self._pending.append(request)
        log.info(f"9-LINE MEDEVAC: {precedence} from {unit_id} at {grid}")
        return request

    def process_requests(self, available_assets: List[str] = None) -> List[Dict]:
        assets = available_assets or ["DUSTOFF-1", "DUSTOFF-2"]
        dispatched = []
        sorted_pending = sorted(self._pending,
            key=lambda r: {"URGENT": 0, "PRIORITY": 1, "ROUTINE": 2}.get(r["precedence"], 3))
        for i, req in enumerate(sorted_pending):
            if i < len(assets):
                req["status"] = "DISPATCHED"
                req["assigned_asset"] = assets[i]
                req["eta_minutes"] = 15 + i * 5
                dispatched.append(req)
        self._pending = [r for r in self._pending if r["status"] == "REQUESTED"]
        return dispatched

    def get_status(self) -> Dict:
        return {
            "pending": len(self._pending),
            "dispatched": sum(1 for r in self._pending if r.get("status") == "DISPATCHED"),
            "completed": len(self._completed),
        }


if __name__ == "__main__":
    agent = CSSMedevacAgent()
    agent.generate_9line("B01", 34.05, -117.45, n_patients=2, precedence="URGENT")
    agent.generate_9line("B03", 34.15, -117.30, n_patients=1, precedence="PRIORITY")
    dispatched = agent.process_requests()
    print(f"Dispatched: {len(dispatched)}")
    print(f"Status: {agent.get_status()}")
    print("css_medevac_agent.py OK")
