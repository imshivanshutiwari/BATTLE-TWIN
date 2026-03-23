"""
Canonical battlefield state for the BATTLE-TWIN digital twin.

Core data structures:
- UnitState: Individual friendly/hostile unit state
- ContactReport: Enemy contact observation
- PhaseLine, Objective: Control measures
- FireMission, MEDEVACRequest: Operational events
- BattlefieldState: Complete battlefield picture
"""

import json
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

from utils.mgrs_converter import MGRSConverter


_mgrs = MGRSConverter()


class UnitType(str, Enum):
    INFANTRY = "infantry"
    ARMOR = "armor"
    ARTILLERY = "artillery"
    AVIATION = "aviation"
    LOGISTICS = "logistics"
    UNKNOWN = "unknown"


class CommsStatus(str, Enum):
    UP = "UP"
    DEGRADED = "DEGRADED"
    DOWN = "DOWN"


class AlertLevel(str, Enum):
    ROUTINE = "ROUTINE"
    PRIORITY = "PRIORITY"
    IMMEDIATE = "IMMEDIATE"
    FLASH = "FLASH"
    OVERRIDE = "OVERRIDE"


class Affiliation(str, Enum):
    FRIENDLY = "FRIENDLY"
    HOSTILE = "HOSTILE"
    UNKNOWN = "UNKNOWN"
    NEUTRAL = "NEUTRAL"


@dataclass
class UnitState:
    """Individual unit state in the digital twin."""

    uid: str
    callsign: str
    unit_type: str
    position: Optional[str] = None  # MGRS string
    lat: float = 0.0
    lon: float = 0.0
    altitude_m: float = 0.0
    heading_deg: float = 0.0
    speed_mps: float = 0.0
    strength_pct: float = 100.0
    ammo_pct: float = 100.0
    fuel_pct: float = 100.0
    water_pct: float = 100.0
    comms_status: str = "UP"
    threat_level: float = 0.0
    last_updated: datetime = field(default_factory=lambda: datetime.now(tz=timezone.utc))
    sensor_data: Dict[str, Any] = field(default_factory=dict)
    affiliation: str = "FRIENDLY"
    designation: str = ""
    status: str = "OPERATIONAL"

    def __post_init__(self):
        """Compute MGRS position from lat/lon if not set."""
        if self.position is None and (self.lat != 0.0 or self.lon != 0.0):
            try:
                self.position = _mgrs.latlon_to_mgrs_string(self.lat, self.lon)
            except Exception:
                self.position = "UNKNOWN"

    def update(self, delta: Dict[str, Any]) -> None:
        """Apply a delta update to this unit's state."""
        for key, value in delta.items():
            if hasattr(self, key):
                setattr(self, key, value)
        self.last_updated = datetime.now(tz=timezone.utc)
        if "lat" in delta or "lon" in delta:
            try:
                self.position = _mgrs.latlon_to_mgrs_string(self.lat, self.lon)
            except Exception:
                pass

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        d = asdict(self)
        d["last_updated"] = self.last_updated.isoformat()
        return d

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "UnitState":
        """Deserialize from dictionary."""
        if isinstance(d.get("last_updated"), str):
            d["last_updated"] = datetime.fromisoformat(d["last_updated"])
        return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})


@dataclass
class ContactReport:
    """Enemy contact observation report."""

    uid: str
    callsign: str
    affiliation: str = "HOSTILE"
    lat: float = 0.0
    lon: float = 0.0
    altitude_m: float = 0.0
    heading_deg: float = 0.0
    speed_mps: float = 0.0
    confidence: float = 0.5
    source: str = "UNKNOWN"
    strength_estimate: str = "unknown"
    timestamp: datetime = field(default_factory=lambda: datetime.now(tz=timezone.utc))
    mgrs: str = ""

    def __post_init__(self):
        if not self.mgrs and (self.lat != 0.0 or self.lon != 0.0):
            try:
                self.mgrs = _mgrs.latlon_to_mgrs_string(self.lat, self.lon)
            except Exception:
                self.mgrs = ""

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["timestamp"] = self.timestamp.isoformat()
        return d

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "ContactReport":
        if isinstance(d.get("timestamp"), str):
            d["timestamp"] = datetime.fromisoformat(d["timestamp"])
        return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})


@dataclass
class PhaseLine:
    """Tactical control measure — phase line."""

    name: str
    line_type: str  # line_of_departure, phase_line, limit_of_advance
    coordinates: List[Tuple[float, float]] = field(default_factory=list)
    color: str = "#00ff00"

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class Objective:
    """Tactical objective."""

    name: str
    obj_type: str  # seize, secure, destroy
    center_lat: float = 0.0
    center_lon: float = 0.0
    radius_m: float = 500.0
    status: str = "NOT_STARTED"

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class FireMission:
    """Fire support mission."""

    mission_id: str
    target_lat: float
    target_lon: float
    target_description: str
    method_of_fire: str = "FIRE_FOR_EFFECT"
    ammunition: str = "HE"
    status: str = "REQUESTED"  # REQUESTED, CLEARED, FIRING, COMPLETE
    firing_unit: str = ""
    observer: str = ""
    timestamp: datetime = field(default_factory=lambda: datetime.now(tz=timezone.utc))

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["timestamp"] = self.timestamp.isoformat()
        return d


@dataclass
class MEDEVACRequest:
    """9-line MEDEVAC request."""

    request_id: str
    line1_location: str  # Grid of pickup site
    line2_frequency: str  # Radio frequency/callsign
    line3_patients: str  # Number of patients by precedence
    line4_equipment: str  # Special equipment required
    line5_patients_type: str  # Number of patients by type (litter/ambulatory)
    line6_security: str  # Security at pickup site
    line7_marking: str  # Method of marking pickup site
    line8_nationality: str  # Patient nationality/status
    line9_terrain: str  # NBC contamination / terrain description
    precedence: str = "ROUTINE"  # URGENT, PRIORITY, ROUTINE
    status: str = "REQUESTED"  # REQUESTED, DISPATCHED, EN_ROUTE, COMPLETE
    lat: float = 0.0
    lon: float = 0.0
    timestamp: datetime = field(default_factory=lambda: datetime.now(tz=timezone.utc))

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["timestamp"] = self.timestamp.isoformat()
        return d


class BattlefieldState:
    """
    Complete battlefield state for the digital twin.

    This is the canonical state object that is:
    - Published to NATS JetStream
    - Consumed by the Dash C2 dashboard
    - Synced to UE5 for 3D visualization
    - Queried by LangGraph agents
    """

    def __init__(self):
        self.units: Dict[str, UnitState] = {}
        self.contacts: Dict[str, ContactReport] = {}
        self.phase_lines: List[PhaseLine] = []
        self.objectives: List[Objective] = []
        self.fire_missions: List[FireMission] = []
        self.medevac_requests: List[MEDEVACRequest] = []
        self.alerts: List[Dict[str, Any]] = []
        self.nats_sequence: int = 0
        self.timestamp: datetime = datetime.now(tz=timezone.utc)

    def update_unit(self, uid: str, delta: Dict[str, Any]) -> None:
        """Update a single unit's state."""
        if uid in self.units:
            self.units[uid].update(delta)
        self.timestamp = datetime.now(tz=timezone.utc)
        self.nats_sequence += 1

    def add_unit(self, unit: UnitState) -> None:
        """Add a new unit to the battlefield."""
        self.units[unit.uid] = unit
        self.nats_sequence += 1

    def add_contact(self, contact: ContactReport) -> None:
        """Add or update a contact report."""
        self.contacts[contact.uid] = contact
        self.nats_sequence += 1

    def add_fire_mission(self, mission: FireMission) -> None:
        """Add a fire mission."""
        self.fire_missions.append(mission)
        self.nats_sequence += 1

    def add_medevac_request(self, request: MEDEVACRequest) -> None:
        """Add a MEDEVAC request."""
        self.medevac_requests.append(request)
        self.nats_sequence += 1

    def add_alert(
        self,
        level: str,
        unit_id: str,
        alert_type: str,
        details: str,
    ) -> None:
        """Add an alert to the log."""
        self.alerts.append(
            {
                "timestamp": datetime.now(tz=timezone.utc).isoformat(),
                "level": level,
                "unit_id": unit_id,
                "type": alert_type,
                "details": details,
                "acknowledged": False,
            }
        )
        # Keep last 100 alerts
        if len(self.alerts) > 100:
            self.alerts = self.alerts[-100:]
        self.nats_sequence += 1

    def get_tactical_picture(self) -> Dict[str, Any]:
        """Get complete tactical picture for dashboard rendering."""
        return {
            "units": {uid: u.to_dict() for uid, u in self.units.items()},
            "contacts": {uid: c.to_dict() for uid, c in self.contacts.items()},
            "phase_lines": [pl.to_dict() for pl in self.phase_lines],
            "objectives": [obj.to_dict() for obj in self.objectives],
            "fire_missions": [fm.to_dict() for fm in self.fire_missions],
            "medevac_requests": [mr.to_dict() for mr in self.medevac_requests],
            "alerts": self.alerts[-20:],
            "nats_sequence": self.nats_sequence,
            "timestamp": self.timestamp.isoformat(),
            "force_ratio": self.compute_force_ratio(),
        }

    def serialize_for_ue5(self) -> bytes:
        """
        Serialize battlefield state for UE5 consumption.

        Uses JSON encoding (compact) for cross-platform compatibility.
        """
        data = {
            "seq": self.nats_sequence,
            "ts": self.timestamp.timestamp(),
            "units": [],
            "contacts": [],
        }
        for u in self.units.values():
            data["units"].append(
                {
                    "uid": u.uid,
                    "type": u.unit_type,
                    "lat": u.lat,
                    "lon": u.lon,
                    "alt": u.altitude_m,
                    "hdg": u.heading_deg,
                    "spd": u.speed_mps,
                    "str": u.strength_pct,
                    "thr": u.threat_level,
                    "aff": u.affiliation,
                }
            )
        for c in self.contacts.values():
            data["contacts"].append(
                {
                    "uid": c.uid,
                    "lat": c.lat,
                    "lon": c.lon,
                    "alt": c.altitude_m,
                    "hdg": c.heading_deg,
                    "conf": c.confidence,
                    "aff": c.affiliation,
                }
            )
        return json.dumps(data, separators=(",", ":")).encode("utf-8")

    def compute_force_ratio(self) -> float:
        """Compute friendly:hostile force ratio."""
        friendly = sum(1 for u in self.units.values() if u.affiliation == "FRIENDLY")
        hostile = max(len(self.contacts), 1)
        return friendly / hostile

    def to_dict(self) -> Dict[str, Any]:
        """Full serialization."""
        return self.get_tactical_picture()

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "BattlefieldState":
        """Deserialize from dictionary."""
        state = cls()
        for uid, u_dict in d.get("units", {}).items():
            state.units[uid] = UnitState.from_dict(u_dict)
        for uid, c_dict in d.get("contacts", {}).items():
            state.contacts[uid] = ContactReport.from_dict(c_dict)
        for pl_dict in d.get("phase_lines", []):
            state.phase_lines.append(PhaseLine(**pl_dict))
        for obj_dict in d.get("objectives", []):
            state.objectives.append(Objective(**obj_dict))
        state.nats_sequence = d.get("nats_sequence", 0)
        state.alerts = d.get("alerts", [])
        ts = d.get("timestamp", "")
        if isinstance(ts, str) and ts:
            state.timestamp = datetime.fromisoformat(ts)
        return state

    @classmethod
    def from_config(cls, config: Dict[str, Any]) -> "BattlefieldState":
        """Initialize from battlefield_config.yaml."""
        state = cls()

        # Add friendly units
        for unit_cfg in config.get("friendly_units", []):
            state.add_unit(
                UnitState(
                    uid=unit_cfg["uid"],
                    callsign=unit_cfg["callsign"],
                    unit_type=unit_cfg.get("unit_type", "infantry"),
                    lat=unit_cfg["initial_lat"],
                    lon=unit_cfg["initial_lon"],
                    strength_pct=unit_cfg.get("strength_pct", 100),
                    ammo_pct=unit_cfg.get("ammo_pct", 100),
                    fuel_pct=unit_cfg.get("fuel_pct", 100),
                    water_pct=unit_cfg.get("water_pct", 100),
                    affiliation="FRIENDLY",
                    designation=unit_cfg.get("designation", ""),
                )
            )

        # Add hostile contacts
        for contact_cfg in config.get("hostile_contacts_initial", []):
            state.add_contact(
                ContactReport(
                    uid=contact_cfg["uid"],
                    callsign=contact_cfg["callsign"],
                    lat=contact_cfg["last_known_lat"],
                    lon=contact_cfg["last_known_lon"],
                    confidence=contact_cfg.get("confidence", 0.5),
                    source=contact_cfg.get("source", "UNKNOWN"),
                    strength_estimate=contact_cfg.get("strength_estimate", "unknown"),
                )
            )

        # Add phase lines
        for pl_cfg in config.get("phase_lines", []):
            coords = [tuple(c) for c in pl_cfg.get("coordinates", [])]
            state.phase_lines.append(
                PhaseLine(
                    name=pl_cfg["name"],
                    line_type=pl_cfg.get("type", "phase_line"),
                    coordinates=coords,
                    color=pl_cfg.get("color", "#00ff00"),
                )
            )

        # Add objectives
        for obj_cfg in config.get("objectives", []):
            state.objectives.append(
                Objective(
                    name=obj_cfg["name"],
                    obj_type=obj_cfg.get("type", "seize"),
                    center_lat=obj_cfg.get("center_lat", 0),
                    center_lon=obj_cfg.get("center_lon", 0),
                    radius_m=obj_cfg.get("radius_m", 500),
                )
            )

        return state


if __name__ == "__main__":
    # Create state from config
    try:
        from utils.config_loader import load_config

        config = load_config("battlefield_config")
        state = BattlefieldState.from_config(config)
    except FileNotFoundError:
        state = BattlefieldState()
        state.add_unit(
            UnitState(
                uid="BLUE-01", callsign="WARHORSE-6", unit_type="infantry", lat=34.05, lon=-117.45
            )
        )
        state.add_contact(
            ContactReport(
                uid="RED-01", callsign="HOSTILE-1", lat=34.30, lon=-117.15, confidence=0.85
            )
        )

    print(f"Units: {len(state.units)}")
    print(f"Contacts: {len(state.contacts)}")
    print(f"Phase Lines: {len(state.phase_lines)}")
    print(f"Objectives: {len(state.objectives)}")
    print(f"Force Ratio: {state.compute_force_ratio():.1f}:1")

    # Test serialization roundtrip
    serialized = state.to_dict()
    restored = BattlefieldState.from_dict(serialized)
    print(f"Serialization roundtrip: {len(restored.units)} units")

    # Test UE5 serialization
    ue5_bytes = state.serialize_for_ue5()
    print(f"UE5 payload: {len(ue5_bytes)} bytes")

    print("twin_state.py OK")
