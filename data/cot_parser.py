"""
Cursor-on-Target (CoT) XML event parser.

CoT is the real military data standard used by ATAK (Android Team
Awareness Kit) for sharing position and situation awareness data.

Parses CoT XML events into structured Python objects:
- Position reports (a-f-G = friendly ground)
- Contact reports (a-h-G = hostile ground)
- Alert events
- Multicast stream listening (239.2.3.1:6969)
"""

import asyncio
import socket
import struct
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, AsyncGenerator, Dict, List, Optional
from xml.etree import ElementTree as ET

from utils.logger import get_logger

log = get_logger("COT_PARSER")

# CoT type codes (APP-6D mapping)
COT_TYPE_MAP = {
    "a-f-G": "FRIENDLY_GROUND",
    "a-f-A": "FRIENDLY_AIR",
    "a-f-S": "FRIENDLY_SEA",
    "a-h-G": "HOSTILE_GROUND",
    "a-h-A": "HOSTILE_AIR",
    "a-h-S": "HOSTILE_SEA",
    "a-u-G": "UNKNOWN_GROUND",
    "a-u-A": "UNKNOWN_AIR",
    "a-n-G": "NEUTRAL_GROUND",
    "b-m-p-s-p-i": "MEDEVAC_REQUEST",
    "b-a-o-tbl": "ALERT",
    "b-m-p-c": "CASEVAC",
    "b-r-f-h-c": "FIRE_MISSION",
}

# Default CoT multicast settings
COT_MULTICAST_HOST = "239.2.3.1"
COT_MULTICAST_PORT = 6969


@dataclass
class CoTEvent:
    """Parsed Cursor-on-Target event."""

    uid: str
    event_type: str
    time: datetime
    start: datetime
    stale: datetime
    latitude: float
    longitude: float
    hae: float  # Height Above Ellipsoid
    ce: float  # Circular Error (meters)
    le: float  # Linear Error (meters)
    detail: Dict[str, Any] = field(default_factory=dict)

    @property
    def type_name(self) -> str:
        """Human-readable event type name."""
        return COT_TYPE_MAP.get(self.event_type, self.event_type)

    @property
    def is_friendly(self) -> bool:
        return self.event_type.startswith("a-f")

    @property
    def is_hostile(self) -> bool:
        return self.event_type.startswith("a-h")

    @property
    def is_unknown(self) -> bool:
        return self.event_type.startswith("a-u")

    @property
    def is_stale(self) -> bool:
        return datetime.now(tz=timezone.utc) > self.stale

    @property
    def affiliation(self) -> str:
        """Military affiliation string."""
        if self.is_friendly:
            return "FRIENDLY"
        if self.is_hostile:
            return "HOSTILE"
        if self.is_unknown:
            return "UNKNOWN"
        return "NEUTRAL"

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "uid": self.uid,
            "event_type": self.event_type,
            "type_name": self.type_name,
            "affiliation": self.affiliation,
            "time": self.time.isoformat(),
            "start": self.start.isoformat(),
            "stale": self.stale.isoformat(),
            "latitude": self.latitude,
            "longitude": self.longitude,
            "hae": self.hae,
            "ce": self.ce,
            "le": self.le,
            "detail": self.detail,
        }


@dataclass
class CoTContactReport:
    """Contact report extracted from CoT events."""

    uid: str
    callsign: str
    affiliation: str
    latitude: float
    longitude: float
    altitude_m: float
    speed_mps: float
    heading_deg: float
    timestamp: datetime
    source: str
    confidence: float

    def to_salute(self) -> str:
        """
        Generate SALUTE report format.

        S - Size
        A - Activity
        L - Location
        U - Unit
        T - Time
        E - Equipment
        """
        return (
            f"SALUTE REPORT\n"
            f"S: {self.affiliation} element\n"
            f"A: Moving {self.heading_deg:.0f}° at {self.speed_mps:.0f} m/s\n"
            f"L: {self.latitude:.5f}N, {self.longitude:.5f}E, "
            f"ALT {self.altitude_m:.0f}m\n"
            f"U: {self.callsign} ({self.uid})\n"
            f"T: {self.timestamp.strftime('%d%H%MZ %b %Y').upper()}\n"
            f"E: Source: {self.source}, Confidence: {self.confidence:.0%}\n"
        )


class CoTParser:
    """
    Parser for real Cursor-on-Target (CoT) XML events.

    CoT is the interoperability standard used by:
    - ATAK (Android Team Awareness Kit)
    - WinTAK
    - iTAK
    - TAK Server
    """

    def __init__(self):
        self._event_cache: Dict[str, CoTEvent] = {}

    def _parse_datetime(self, dt_str: str) -> datetime:
        """Parse CoT datetime string (ISO 8601)."""
        try:
            if dt_str.endswith("Z"):
                dt_str = dt_str[:-1] + "+00:00"
            return datetime.fromisoformat(dt_str)
        except ValueError:
            return datetime.now(tz=timezone.utc)

    def _parse_detail(self, detail_elem: Optional[ET.Element]) -> Dict[str, Any]:
        """Parse CoT detail element into a dictionary."""
        if detail_elem is None:
            return {}

        detail = {}
        for child in detail_elem:
            tag = child.tag
            attrs = dict(child.attrib)

            # Handle nested elements
            sub_children = list(child)
            if sub_children:
                attrs["_children"] = [
                    {"tag": sc.tag, **dict(sc.attrib), "text": sc.text} for sc in sub_children
                ]

            if child.text and child.text.strip():
                attrs["_text"] = child.text.strip()

            detail[tag] = attrs

        return detail

    def parse_event(self, xml_string: str) -> CoTEvent:
        """
        Parse a single CoT XML event string.

        Args:
            xml_string: Raw CoT XML string.

        Returns:
            Parsed CoTEvent object.

        Raises:
            ValueError: If XML is malformed or missing required fields.
        """
        try:
            root = ET.fromstring(xml_string)
        except ET.ParseError as e:
            raise ValueError(f"Malformed CoT XML: {e}")

        uid = root.get("uid", "")
        event_type = root.get("type", "")
        time_str = root.get("time", "")
        start_str = root.get("start", time_str)
        stale_str = root.get("stale", time_str)

        if not uid or not event_type:
            raise ValueError("CoT event missing uid or type")

        # Parse point element
        point = root.find("point")
        if point is None:
            raise ValueError("CoT event missing point element")

        lat = float(point.get("lat", 0))
        lon = float(point.get("lon", 0))
        hae = float(point.get("hae", 0))
        ce = float(point.get("ce", 999999))
        le = float(point.get("le", 999999))

        # Parse detail element
        detail_elem = root.find("detail")
        detail = self._parse_detail(detail_elem)

        event = CoTEvent(
            uid=uid,
            event_type=event_type,
            time=self._parse_datetime(time_str),
            start=self._parse_datetime(start_str),
            stale=self._parse_datetime(stale_str),
            latitude=lat,
            longitude=lon,
            hae=hae,
            ce=ce,
            le=le,
            detail=detail,
        )

        self._event_cache[uid] = event
        return event

    def parse_batch(self, xml_list: List[str]) -> List[CoTEvent]:
        """
        Parse a batch of CoT XML event strings.

        Args:
            xml_list: List of XML strings.

        Returns:
            List of successfully parsed CoTEvent objects.
        """
        events = []
        for xml_str in xml_list:
            try:
                events.append(self.parse_event(xml_str))
            except ValueError as e:
                log.warning(f"Failed to parse CoT event: {e}")
        log.info(f"Parsed {len(events)}/{len(xml_list)} CoT events")
        return events

    def to_contact_report(self, event: CoTEvent) -> CoTContactReport:
        """
        Convert a CoT event to a structured contact report.

        Args:
            event: Parsed CoT event.

        Returns:
            CoTContactReport with extracted fields.
        """
        # Extract callsign from detail
        contact = event.detail.get("contact", {})
        callsign = contact.get("callsign", event.uid)

        # Extract track info
        track = event.detail.get("track", {})
        speed = float(track.get("speed", 0))
        course = float(track.get("course", 0))

        # Determine source type
        remarks = event.detail.get("remarks", {})
        source = remarks.get("source", "UNKNOWN")

        return CoTContactReport(
            uid=event.uid,
            callsign=callsign,
            affiliation=event.affiliation,
            latitude=event.latitude,
            longitude=event.longitude,
            altitude_m=event.hae,
            speed_mps=speed,
            heading_deg=course,
            timestamp=event.time,
            source=source,
            confidence=max(0.0, min(1.0, 1.0 - (event.ce / 10000))),
        )

    async def stream_from_multicast(
        self,
        host: str = COT_MULTICAST_HOST,
        port: int = COT_MULTICAST_PORT,
        timeout_s: float = 5.0,
    ) -> AsyncGenerator[CoTEvent, None]:
        """
        Listen for CoT events on multicast address.

        Real CoT multicast standard: 239.2.3.1:6969

        Args:
            host: Multicast group address.
            port: UDP port.
            timeout_s: Socket timeout in seconds.

        Yields:
            CoTEvent objects as they arrive.
        """
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.settimeout(timeout_s)

        try:
            sock.bind(("", port))
            mreq = struct.pack("4sl", socket.inet_aton(host), socket.INADDR_ANY)
            sock.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, mreq)
            log.info(f"Listening for CoT on {host}:{port}")

            while True:
                try:
                    data, addr = sock.recvfrom(65536)
                    xml_str = data.decode("utf-8", errors="replace")
                    event = self.parse_event(xml_str)
                    yield event
                except socket.timeout:
                    await asyncio.sleep(0.1)
                except ValueError as e:
                    log.warning(f"Invalid CoT from {addr}: {e}")

        finally:
            sock.close()

    def get_cached_events(self) -> Dict[str, CoTEvent]:
        """Return all cached events."""
        return dict(self._event_cache)

    @staticmethod
    def generate_sample_cot(
        uid: str,
        callsign: str,
        event_type: str,
        lat: float,
        lon: float,
        alt: float = 0.0,
        speed: float = 0.0,
        course: float = 0.0,
    ) -> str:
        """
        Generate a valid CoT XML event string for testing.

        This creates a properly formatted CoT event matching
        the real ATAK specification.

        Args:
            uid: Unique identifier.
            callsign: Unit callsign.
            event_type: CoT type code (e.g., 'a-f-G').
            lat: Latitude.
            lon: Longitude.
            alt: Altitude in meters.
            speed: Speed in m/s.
            course: Heading in degrees.

        Returns:
            Valid CoT XML string.
        """
        now = datetime.now(tz=timezone.utc)
        stale = now + __import__("datetime").timedelta(minutes=5)

        return (
            f'<?xml version="1.0" encoding="UTF-8"?>'
            f'<event version="2.0" uid="{uid}" type="{event_type}" '
            f'time="{now.isoformat()}" start="{now.isoformat()}" '
            f'stale="{stale.isoformat()}" how="h-e">'
            f'<point lat="{lat}" lon="{lon}" hae="{alt}" ce="10" le="10"/>'
            f"<detail>"
            f'<contact callsign="{callsign}"/>'
            f'<track speed="{speed}" course="{course}"/>'
            f'<remarks source="BATTLE-TWIN"/>'
            f'<uid Droid="{callsign}"/>'
            f"</detail>"
            f"</event>"
        )


if __name__ == "__main__":
    parser = CoTParser()

    # Generate and parse sample CoT events
    sample_events = [
        CoTParser.generate_sample_cot("BLUE-01", "WARHORSE-6", "a-f-G", 34.05, -117.45),
        CoTParser.generate_sample_cot(
            "RED-01", "HOSTILE-1", "a-h-G", 34.30, -117.15, speed=5.0, course=180
        ),
        CoTParser.generate_sample_cot("UNKNOWN-01", "UNKNOWN-1", "a-u-G", 34.20, -117.30),
    ]

    events = parser.parse_batch(sample_events)
    for event in events:
        print(
            f"UID: {event.uid}, Type: {event.type_name}, "
            f"Pos: ({event.latitude}, {event.longitude})"
        )
        report = parser.to_contact_report(event)
        print(f"  SALUTE:\n{report.to_salute()}")

    print("cot_parser.py OK")
