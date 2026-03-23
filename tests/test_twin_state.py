"""Tests for digital_twin/twin_state.py."""

from digital_twin.twin_state import BattlefieldState, UnitState, ContactReport


def test_unit_state_creation():
    u = UnitState(uid="B01", callsign="WARHORSE-1", unit_type="infantry", lat=34.05, lon=-117.45)
    assert u.uid == "B01"
    assert u.position is not None


def test_unit_state_update():
    u = UnitState(uid="B01", callsign="WARHORSE-1", unit_type="infantry", lat=34.05, lon=-117.45)
    u.update({"lat": 34.06, "speed_mps": 5.0})
    assert u.lat == 34.06
    assert u.speed_mps == 5.0


def test_unit_serialization_roundtrip():
    u = UnitState(uid="B01", callsign="WARHORSE-1", unit_type="infantry", lat=34.05, lon=-117.45)
    d = u.to_dict()
    u2 = UnitState.from_dict(d)
    assert u2.uid == u.uid
    assert u2.lat == u.lat


def test_contact_report():
    c = ContactReport(uid="R01", callsign="HOSTILE-1", lat=34.3, lon=-117.15, confidence=0.85)
    assert c.affiliation == "HOSTILE"
    assert c.mgrs != ""


def test_battlefield_state():
    state = BattlefieldState()
    state.add_unit(
        UnitState(uid="B01", callsign="W1", unit_type="infantry", lat=34.05, lon=-117.45)
    )
    state.add_contact(ContactReport(uid="R01", callsign="H1", lat=34.3, lon=-117.15))
    assert len(state.units) == 1
    assert len(state.contacts) == 1
    assert state.compute_force_ratio() == 1.0


def test_battlefield_serialization():
    state = BattlefieldState()
    state.add_unit(UnitState(uid="B01", callsign="W1", unit_type="infantry", lat=34.0, lon=-117.0))
    d = state.to_dict()
    state2 = BattlefieldState.from_dict(d)
    assert len(state2.units) == 1
    assert "B01" in state2.units


def test_ue5_serialization():
    state = BattlefieldState()
    state.add_unit(UnitState(uid="B01", callsign="W1", unit_type="infantry", lat=34.0, lon=-117.0))
    ue5_bytes = state.serialize_for_ue5()
    assert len(ue5_bytes) > 10
    import json

    data = json.loads(ue5_bytes)
    assert data["seq"] == state.nats_sequence


def test_alert_log():
    state = BattlefieldState()
    state.add_alert("FLASH", "B01", "PROXIMITY", "Enemy within 2km")
    assert len(state.alerts) == 1
    assert state.alerts[0]["level"] == "FLASH"


def test_state_reconciler_merge_unit_updates():
    """Ensure merge_unit_updates folds ALL updates, not just the first pair."""
    from digital_twin.state_reconciler import StateReconciler

    reconciler = StateReconciler(strategy="LAST_WRITER_WINS")
    current = {"lat": 34.00, "lon": -117.00, "speed_mps": 0.0, "fuel_pct": 100}

    updates = [
        ({"lat": 34.01, "speed_mps": 2.0}, "GPS", 1000.0),
        ({"lat": 34.02, "fuel_pct": 80}, "SENSOR", 1001.0),
        ({"lat": 34.03, "speed_mps": 5.0}, "GPS", 1002.0),
    ]

    result = reconciler.merge_unit_updates(current, updates)

    # All three updates must have been applied (lat from last GPS update wins)
    assert result["lat"] == 34.03, f"Expected 34.03, got {result['lat']}"
    assert result["speed_mps"] == 5.0
    assert result["fuel_pct"] == 80  # from second update
    assert result["lon"] == -117.00  # unchanged field preserved


def test_state_reconciler_single_update():
    """Single update must still be applied correctly."""
    from digital_twin.state_reconciler import StateReconciler

    reconciler = StateReconciler()
    current = {"lat": 34.00, "lon": -117.00}
    result = reconciler.merge_unit_updates(current, [({"lat": 34.05}, "GPS", 1000.0)])
    assert result["lat"] == 34.05
    assert result["lon"] == -117.00


def test_state_reconciler_empty_updates():
    """Empty update list must return current state unchanged."""
    from digital_twin.state_reconciler import StateReconciler

    reconciler = StateReconciler()
    current = {"lat": 34.00, "lon": -117.00}
    result = reconciler.merge_unit_updates(current, [])
    assert result == current
