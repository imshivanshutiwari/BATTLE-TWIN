"""
Core simulation engine — advances battlefield state each tick.
Applies physics, movement, combat, logistics, and sensor updates.
"""

import math
import numpy as np
from digital_twin.twin_state import BattlefieldState, UnitState, ContactReport
from utils.logger import get_logger

log = get_logger("SIM_ENGINE")


class SimulationEngine:
    """Discrete-event simulation engine for the digital twin."""

    def __init__(self, dt_s: float = 1.0, speed_multiplier: float = 1.0):
        self.dt = dt_s
        self.speed = speed_multiplier
        self.tick = 0
        self.elapsed_s = 0.0
        self._running = False

    def step(self, state: BattlefieldState) -> BattlefieldState:
        """Advance simulation by one time step."""
        self.tick += 1
        self.elapsed_s += self.dt * self.speed

        self._move_units(state)
        self._update_contacts(state)
        self._consume_supplies(state)
        self._check_proximity_alerts(state)
        self._update_comms(state)

        return state

    def _move_units(self, state: BattlefieldState):
        for uid, unit in state.units.items():
            if unit.speed_mps > 0:
                hdg_rad = math.radians(unit.heading_deg)
                dlat = unit.speed_mps * math.cos(hdg_rad) * self.dt / 111320
                dlon = (
                    unit.speed_mps
                    * math.sin(hdg_rad)
                    * self.dt
                    / (111320 * math.cos(math.radians(unit.lat)))
                )
                unit.lat += dlat
                unit.lon += dlon

    def _update_contacts(self, state: BattlefieldState):
        for cid, contact in state.contacts.items():
            if contact.speed_mps > 0:
                hdg_rad = math.radians(contact.heading_deg)
                contact.lat += contact.speed_mps * math.cos(hdg_rad) * self.dt / 111320
                contact.lon += (
                    contact.speed_mps
                    * math.sin(hdg_rad)
                    * self.dt
                    / (111320 * max(0.01, math.cos(math.radians(contact.lat))))
                )
            # Decay confidence over time
            contact.confidence = max(0.1, contact.confidence - 0.001 * self.dt)

    def _consume_supplies(self, state: BattlefieldState):
        for uid, unit in state.units.items():
            consumed = 0.01 * self.dt / 60  # per minute
            if unit.speed_mps > 0:
                consumed *= 2
            unit.fuel_pct = max(0, unit.fuel_pct - consumed)
            unit.water_pct = max(0, unit.water_pct - consumed * 0.5)
            unit.ammo_pct = max(0, unit.ammo_pct - consumed * 0.1)
            # Generate alert if critical
            if unit.fuel_pct < 20 or unit.ammo_pct < 20 or unit.water_pct < 20:
                supply_type = (
                    "FUEL" if unit.fuel_pct < 20 else "AMMO" if unit.ammo_pct < 20 else "WATER"
                )
                state.add_alert(
                    "PRIORITY", uid, "SUPPLY_LOW", f"{unit.callsign} {supply_type} critical"
                )

    def _check_proximity_alerts(self, state: BattlefieldState):
        for uid, unit in state.units.items():
            for cid, contact in state.contacts.items():
                dist = self._distance_m(unit.lat, unit.lon, contact.lat, contact.lon)
                if dist < 2000:
                    state.add_alert(
                        "FLASH",
                        uid,
                        "PROXIMITY",
                        f"{unit.callsign} within 2km of {contact.callsign}",
                    )

    def _update_comms(self, state: BattlefieldState):
        for uid, unit in state.units.items():
            if np.random.random() < 0.001:
                unit.comms_status = "DEGRADED"
            elif np.random.random() < 0.05:
                unit.comms_status = "UP"

    @staticmethod
    def _distance_m(lat1, lon1, lat2, lon2):
        R = 6371000
        p1, p2 = math.radians(lat1), math.radians(lat2)
        dp, dl = math.radians(lat2 - lat1), math.radians(lon2 - lon1)
        a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
        return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


if __name__ == "__main__":
    from utils.config_loader import load_config

    try:
        config = load_config("battlefield_config")
        state = BattlefieldState.from_config(config)
    except Exception:
        state = BattlefieldState()
        state.add_unit(
            UnitState(
                uid="B01",
                callsign="WARHORSE-1",
                unit_type="infantry",
                lat=34.05,
                lon=-117.45,
                speed_mps=2.0,
                heading_deg=45,
            )
        )
        state.add_contact(ContactReport(uid="R01", callsign="HOSTILE-1", lat=34.30, lon=-117.15))
    engine = SimulationEngine(dt_s=1.0)
    for i in range(60):
        engine.step(state)
    print(f"After 60 ticks: {len(state.alerts)} alerts generated")
    for u in state.units.values():
        print(f"  {u.callsign}: fuel={u.fuel_pct:.1f}% ammo={u.ammo_pct:.1f}%")
    print("sim_engine.py OK")
