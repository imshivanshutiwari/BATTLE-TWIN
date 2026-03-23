"""Tests for simulation engine."""
from simulation.sim_engine import SimulationEngine
from digital_twin.twin_state import BattlefieldState, UnitState, ContactReport


def test_sim_engine_init():
    engine = SimulationEngine(dt_s=1.0)
    assert engine.tick == 0


def test_sim_step():
    engine = SimulationEngine(dt_s=1.0)
    state = BattlefieldState()
    state.add_unit(UnitState(uid="B01", callsign="W1", unit_type="infantry",
                             lat=34.05, lon=-117.45, speed_mps=5.0, heading_deg=90))
    engine.step(state)
    assert engine.tick == 1
    assert state.units["B01"].lon != -117.45  # should have moved east


def test_sim_supply_consumption():
    engine = SimulationEngine(dt_s=60.0)  # 1 minute steps
    state = BattlefieldState()
    state.add_unit(UnitState(uid="B01", callsign="W1", unit_type="infantry",
                             lat=34.0, lon=-117.0, fuel_pct=100.0))
    initial_fuel = state.units["B01"].fuel_pct
    for _ in range(10):
        engine.step(state)
    assert state.units["B01"].fuel_pct < initial_fuel


def test_sim_proximity_alert():
    engine = SimulationEngine(dt_s=1.0)
    state = BattlefieldState()
    state.add_unit(UnitState(uid="B01", callsign="W1", unit_type="infantry",
                             lat=34.05, lon=-117.45))
    state.add_contact(ContactReport(uid="R01", callsign="H1",
                                     lat=34.051, lon=-117.45))  # very close
    engine.step(state)
    has_prox = any(a.get("type") == "PROXIMITY" for a in state.alerts)
    assert has_prox
