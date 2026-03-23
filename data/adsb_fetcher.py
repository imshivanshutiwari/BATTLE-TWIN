"""
ADS-B aircraft track fetcher using the OpenSky Network API.

Fetches REAL aircraft position data including:
- Live aircraft states within a bounding box
- Military callsign filtering
- Continuous streaming with configurable intervals
- Track history caching
"""

import asyncio
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any, AsyncGenerator, Dict, List, Optional, Tuple

import requests
import numpy as np
import pandas as pd

from utils.logger import get_logger

log = get_logger("ADSB")

OPENSKY_API_URL = "https://opensky-network.org/api/states/all"
CACHE_DIR = Path("data/cache")

# Known military callsign prefixes
MILITARY_PREFIXES = [
    "RCH", "REACH", "JAKE", "DUKE", "EVAC", "DUSTOFF",
    "PEDRO", "JOLLY", "KING", "ROCKY", "GORDO", "TEAL",
    "DOOM", "HAVOC", "GUNFIGHTER", "REAPER", "HUNTER",
    "VIPER", "COBRA", "APACHE", "BLACKHAWK", "CHINOOK",
    "RFF", "CNV", "NAVY", "TOPCAT", "SENTRY",
]


@dataclass
class Aircraft:
    """Single aircraft state from ADS-B data."""
    icao24: str
    callsign: str
    latitude: float
    longitude: float
    origin_country: str = ""
    time_position: float = 0.0
    last_contact: float = 0.0
    baro_altitude: Optional[float] = None
    on_ground: bool = False
    velocity: Optional[float] = None
    true_track: Optional[float] = None
    vertical_rate: Optional[float] = None
    sensors: Optional[List[int]] = None
    geo_altitude: Optional[float] = None
    squawk: Optional[str] = None
    spi: bool = False
    position_source: int = 0

    @property
    def altitude_m(self) -> float:
        """Best available altitude in meters."""
        if self.geo_altitude is not None:
            return self.geo_altitude
        if self.baro_altitude is not None:
            return self.baro_altitude
        return 0.0

    @property
    def heading_deg(self) -> float:
        """Aircraft heading in degrees."""
        return self.true_track if self.true_track is not None else 0.0

    @property
    def speed_mps(self) -> float:
        """Ground speed in m/s."""
        return self.velocity if self.velocity is not None else 0.0

    def is_military_callsign(self) -> bool:
        """Check if callsign matches known military patterns."""
        cs = self.callsign.strip().upper()
        return any(cs.startswith(prefix) for prefix in MILITARY_PREFIXES)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "icao24": self.icao24,
            "callsign": self.callsign.strip(),
            "origin_country": self.origin_country,
            "latitude": self.latitude,
            "longitude": self.longitude,
            "altitude_m": self.altitude_m,
            "heading_deg": self.heading_deg,
            "speed_mps": self.speed_mps,
            "vertical_rate": self.vertical_rate,
            "on_ground": self.on_ground,
            "squawk": self.squawk,
            "is_military": self.is_military_callsign(),
            "timestamp": datetime.fromtimestamp(
                self.time_position or self.last_contact, tz=timezone.utc
            ).isoformat(),
        }


class ADSBFetcher:
    """
    Fetches REAL aircraft position data from the OpenSky Network.

    The OpenSky Network provides free, real-time ADS-B data
    for aircraft worldwide via a REST API (no API key needed
    for anonymous access with rate limits).
    """

    def __init__(
        self,
        api_url: str = OPENSKY_API_URL,
        cache_dir: Optional[Path] = None,
        username: Optional[str] = None,
        password: Optional[str] = None,
    ):
        self.api_url = api_url
        self.cache_dir = cache_dir or CACHE_DIR
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": "BATTLE-TWIN/1.0"})
        if username and password:
            self.session.auth = (username, password)
        self._track_history: Dict[str, List[Dict[str, Any]]] = {}

    def _parse_state_vector(self, sv: List[Any]) -> Optional[Aircraft]:
        """Parse a single OpenSky state vector into an Aircraft object."""
        if sv[5] is None or sv[6] is None:
            return None  # No position data
        try:
            return Aircraft(
                icao24=sv[0] or "",
                callsign=sv[1] or "",
                origin_country=sv[2] or "",
                time_position=sv[3] or 0,
                last_contact=sv[4] or 0,
                longitude=float(sv[5]),
                latitude=float(sv[6]),
                baro_altitude=float(sv[7]) if sv[7] is not None else None,
                on_ground=bool(sv[8]),
                velocity=float(sv[9]) if sv[9] is not None else None,
                true_track=float(sv[10]) if sv[10] is not None else None,
                vertical_rate=float(sv[11]) if sv[11] is not None else None,
                sensors=sv[12],
                geo_altitude=float(sv[13]) if sv[13] is not None else None,
                squawk=sv[14],
                spi=bool(sv[15]),
                position_source=int(sv[16]) if sv[16] is not None else 0,
            )
        except (IndexError, ValueError, TypeError) as e:
            log.warning(f"Failed to parse state vector: {e}")
            return None

    def fetch_live_aircraft(
        self,
        bbox: Tuple[float, float, float, float],
    ) -> List[Aircraft]:
        """
        Fetch live aircraft positions within a bounding box.

        Args:
            bbox: (min_lat, min_lon, max_lat, max_lon)

        Returns:
            List of Aircraft objects with current positions.
        """
        params = {
            "lamin": bbox[0],
            "lomin": bbox[1],
            "lamax": bbox[2],
            "lomax": bbox[3],
        }

        log.info(f"Fetching live aircraft in bbox {bbox}")
        try:
            response = self.session.get(
                self.api_url, params=params, timeout=15
            )
            response.raise_for_status()
            data = response.json()
        except requests.RequestException as e:
            log.error(f"OpenSky API error: {e}")
            return []

        states = data.get("states", [])
        if not states:
            log.info("No aircraft in requested area")
            return []

        aircraft = []
        for sv in states:
            ac = self._parse_state_vector(sv)
            if ac is not None:
                aircraft.append(ac)
                # Update track history
                self._update_track_history(ac)

        log.info(f"Fetched {len(aircraft)} aircraft")
        return aircraft

    def fetch_military_callsigns(
        self,
        bbox: Tuple[float, float, float, float],
    ) -> List[Aircraft]:
        """
        Fetch only aircraft with military-pattern callsigns.

        Args:
            bbox: (min_lat, min_lon, max_lat, max_lon)

        Returns:
            List of Aircraft matching military callsign patterns.
        """
        all_aircraft = self.fetch_live_aircraft(bbox)
        military = [ac for ac in all_aircraft if ac.is_military_callsign()]
        log.info(
            f"Filtered {len(military)} military callsigns "
            f"from {len(all_aircraft)} total"
        )
        return military

    async def stream_continuous(
        self,
        bbox: Tuple[float, float, float, float],
        interval_s: float = 10.0,
        max_iterations: Optional[int] = None,
    ) -> AsyncGenerator[List[Aircraft], None]:
        """
        Continuously stream aircraft updates.

        Args:
            bbox: Bounding box for area of interest.
            interval_s: Seconds between API polls.
            max_iterations: Optional limit on number of polls.

        Yields:
            List of Aircraft for each update cycle.
        """
        iteration = 0
        while max_iterations is None or iteration < max_iterations:
            aircraft = self.fetch_live_aircraft(bbox)
            yield aircraft
            iteration += 1
            await asyncio.sleep(interval_s)

    def _update_track_history(self, aircraft: Aircraft) -> None:
        """Append aircraft position to track history."""
        key = aircraft.icao24
        if key not in self._track_history:
            self._track_history[key] = []

        self._track_history[key].append({
            "timestamp": aircraft.time_position or aircraft.last_contact,
            "latitude": aircraft.latitude,
            "longitude": aircraft.longitude,
            "altitude_m": aircraft.altitude_m,
            "heading_deg": aircraft.heading_deg,
            "speed_mps": aircraft.speed_mps,
        })

        # Keep last 6 hours of data
        cutoff = time.time() - 6 * 3600
        self._track_history[key] = [
            pt for pt in self._track_history[key]
            if pt["timestamp"] > cutoff
        ]

    def cache_track_history(
        self,
        aircraft_id: str,
        hours: int = 6,
    ) -> pd.DataFrame:
        """
        Get cached track history for an aircraft.

        Args:
            aircraft_id: ICAO24 hex identifier.
            hours: Hours of history to return.

        Returns:
            DataFrame with track points.
        """
        tracks = self._track_history.get(aircraft_id, [])
        if not tracks:
            return pd.DataFrame(
                columns=["timestamp", "latitude", "longitude",
                         "altitude_m", "heading_deg", "speed_mps"]
            )

        cutoff = time.time() - hours * 3600
        filtered = [pt for pt in tracks if pt["timestamp"] > cutoff]
        df = pd.DataFrame(filtered)
        df["datetime"] = pd.to_datetime(df["timestamp"], unit="s", utc=True)
        return df.sort_values("timestamp")

    def get_all_tracks(self) -> Dict[str, pd.DataFrame]:
        """Get track history for all tracked aircraft."""
        return {
            icao24: self.cache_track_history(icao24)
            for icao24 in self._track_history
        }

    def to_geojson(self, aircraft_list: List[Aircraft]) -> Dict[str, Any]:
        """Convert aircraft list to GeoJSON FeatureCollection."""
        features = []
        for ac in aircraft_list:
            features.append({
                "type": "Feature",
                "geometry": {
                    "type": "Point",
                    "coordinates": [ac.longitude, ac.latitude, ac.altitude_m],
                },
                "properties": ac.to_dict(),
            })
        return {
            "type": "FeatureCollection",
            "features": features,
        }


if __name__ == "__main__":
    fetcher = ADSBFetcher()
    # OPERATION BLUE EAGLE AO
    bbox = (34.0, -117.5, 34.5, -117.0)
    print(f"Fetching ADS-B data for bbox: {bbox}")

    try:
        aircraft = fetcher.fetch_live_aircraft(bbox)
        print(f"Aircraft found: {len(aircraft)}")
        for ac in aircraft[:5]:
            print(f"  {ac.callsign.strip():10s} {ac.icao24} "
                  f"alt={ac.altitude_m:.0f}m spd={ac.speed_mps:.0f}m/s")
    except Exception as e:
        print(f"ADS-B fetch error: {e}")

    print("adsb_fetcher.py OK")
