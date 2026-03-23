"""
MGRS (Military Grid Reference System) coordinate converter.

Provides bidirectional conversion between:
- WGS84 latitude/longitude
- UTM (Universal Transverse Mercator)
- MGRS grid coordinates

Uses pyproj for datum transformations and implements
the full MGRS encoding/decoding per NATO STANAG 2211.
"""

import math
import re
from dataclasses import dataclass
from typing import Tuple, Optional

import numpy as np
from pyproj import Proj, Transformer


# MGRS 100km square letter columns (set 1–6 repeating)
_COL_LETTERS_BY_SET = {
    1: "ABCDEFGH",
    2: "JKLMNPQR",
    3: "STUVWXYZ",
    4: "ABCDEFGH",
    5: "JKLMNPQR",
    6: "STUVWXYZ",
}

# MGRS row letters (repeating every 2,000,000 m)
_ROW_LETTERS_ODD = "ABCDEFGHJKLMNPQRSTUV"
_ROW_LETTERS_EVEN = "FGHJKLMNPQRSTUVABCDE"

# UTM latitude band letters
_LAT_BANDS = "CDEFGHJKLMNPQRSTUVWX"


@dataclass
class MGRSCoord:
    """Military Grid Reference System coordinate."""
    zone_number: int
    zone_letter: str
    col_letter: str
    row_letter: str
    easting: int
    northing: int
    precision: int = 5  # digits (1=10km, 2=1km, 3=100m, 4=10m, 5=1m)

    def __str__(self) -> str:
        fmt = f"{{:0{self.precision}d}}"
        return (
            f"{self.zone_number}{self.zone_letter}"
            f"{self.col_letter}{self.row_letter}"
            f"{fmt.format(self.easting)}{fmt.format(self.northing)}"
        )

    @property
    def grid_string(self) -> str:
        return str(self)


class MGRSConverter:
    """
    Full MGRS converter with support for:
    - lat/lon to MGRS
    - MGRS to lat/lon
    - UTM to MGRS
    - MGRS to UTM
    - Distance between two MGRS coordinates
    - Grid zone designation
    """

    def __init__(self):
        self._transformers = {}

    def _get_utm_proj(self, zone: int, northern: bool) -> Proj:
        """Get UTM projection for a given zone."""
        return Proj(proj="utm", zone=zone, datum="WGS84", south=not northern)

    def _get_transformer(self, from_crs: str, to_crs: str) -> Transformer:
        """Get or create a cached coordinate transformer."""
        key = (from_crs, to_crs)
        if key not in self._transformers:
            self._transformers[key] = Transformer.from_crs(
                from_crs, to_crs, always_xy=True
            )
        return self._transformers[key]

    def latlon_to_utm(
        self, lat: float, lon: float
    ) -> Tuple[int, str, float, float]:
        """
        Convert WGS84 lat/lon to UTM coordinates.

        Args:
            lat: Latitude in decimal degrees.
            lon: Longitude in decimal degrees.

        Returns:
            (zone_number, zone_letter, easting, northing)
        """
        zone_number = int((lon + 180) / 6) + 1

        # Special zones for Norway/Svalbard
        if 56 <= lat < 64 and 3 <= lon < 12:
            zone_number = 32
        elif 72 <= lat < 84:
            if 0 <= lon < 9:
                zone_number = 31
            elif 9 <= lon < 21:
                zone_number = 33
            elif 21 <= lon < 33:
                zone_number = 35
            elif 33 <= lon < 42:
                zone_number = 37

        # Latitude band letter
        band_idx = min(int((lat + 80) / 8), 19)
        zone_letter = _LAT_BANDS[band_idx]

        northern = lat >= 0
        proj = self._get_utm_proj(zone_number, northern)
        easting, northing = proj(lon, lat)

        return zone_number, zone_letter, easting, northing

    def utm_to_latlon(
        self,
        zone_number: int,
        zone_letter: str,
        easting: float,
        northing: float,
    ) -> Tuple[float, float]:
        """
        Convert UTM to WGS84 lat/lon.

        Args:
            zone_number: UTM zone number (1–60).
            zone_letter: UTM latitude band letter.
            easting: UTM easting in meters.
            northing: UTM northing in meters.

        Returns:
            (latitude, longitude) in decimal degrees.
        """
        northern = zone_letter >= "N"
        proj = self._get_utm_proj(zone_number, northern)
        lon, lat = proj(easting, northing, inverse=True)
        return lat, lon

    def latlon_to_mgrs(
        self, lat: float, lon: float, precision: int = 5
    ) -> MGRSCoord:
        """
        Convert WGS84 lat/lon to MGRS coordinate.

        Args:
            lat: Latitude in decimal degrees.
            lon: Longitude in decimal degrees.
            precision: Number of digits for easting/northing (1–5).

        Returns:
            MGRSCoord object.
        """
        zone_number, zone_letter, easting, northing = self.latlon_to_utm(lat, lon)

        # 100km square identification
        set_number = ((zone_number - 1) % 6) + 1
        col_idx = int(easting / 100000) - 1
        col_letters = _COL_LETTERS_BY_SET[set_number]
        col_letter = col_letters[col_idx % len(col_letters)]

        row_letters = _ROW_LETTERS_ODD if zone_number % 2 == 1 else _ROW_LETTERS_EVEN
        row_idx = int(northing / 100000) % 20
        row_letter = row_letters[row_idx]

        # Numeric portion
        e_remainder = int(easting) % 100000
        n_remainder = int(northing) % 100000

        # Adjust precision
        divisor = 10 ** (5 - precision)
        e_digits = e_remainder // divisor
        n_digits = n_remainder // divisor

        return MGRSCoord(
            zone_number=zone_number,
            zone_letter=zone_letter,
            col_letter=col_letter,
            row_letter=row_letter,
            easting=e_digits,
            northing=n_digits,
            precision=precision,
        )

    def mgrs_to_latlon(self, mgrs_input) -> Tuple[float, float]:
        """
        Convert MGRS string or MGRSCoord to WGS84 lat/lon.

        Args:
            mgrs_input: MGRS coordinate string (e.g., '11SPA1234567890')
                        or an MGRSCoord object.

        Returns:
            (latitude, longitude) in decimal degrees.
        """
        if isinstance(mgrs_input, MGRSCoord):
            mgrs_string = str(mgrs_input)
        else:
            mgrs_string = mgrs_input
        parsed = self.parse_mgrs(mgrs_string)
        zone_number = parsed.zone_number
        zone_letter = parsed.zone_letter

        set_number = ((zone_number - 1) % 6) + 1
        col_letters = _COL_LETTERS_BY_SET[set_number]
        col_idx = col_letters.index(parsed.col_letter)

        row_letters = (
            _ROW_LETTERS_ODD if zone_number % 2 == 1 else _ROW_LETTERS_EVEN
        )
        row_idx = row_letters.index(parsed.row_letter)

        multiplier = 10 ** (5 - parsed.precision)
        easting = (col_idx + 1) * 100000 + parsed.easting * multiplier
        northing_base = row_idx * 100000 + parsed.northing * multiplier

        # Determine northing offset (which 2,000,000m band)
        northern = zone_letter >= "N"
        band_idx = _LAT_BANDS.index(zone_letter)
        min_northing = (band_idx - 10) * 8 * 111320 if not northern else band_idx * 8 * 111320

        # Find the correct 2,000,000m multiple
        northing = northing_base
        for mult in range(0, 100):
            candidate = mult * 2000000 + northing_base
            lat_check, _ = self.utm_to_latlon(
                zone_number, zone_letter, easting, candidate
            )
            expected_band = _LAT_BANDS[min(int((lat_check + 80) / 8), 19)]
            if expected_band == zone_letter:
                northing = candidate
                break

        return self.utm_to_latlon(zone_number, zone_letter, easting, northing)

    def parse_mgrs(self, mgrs_string: str) -> MGRSCoord:
        """
        Parse an MGRS coordinate string.

        Args:
            mgrs_string: E.g., '11SPA1234567890'

        Returns:
            MGRSCoord object.
        """
        mgrs_string = mgrs_string.strip().upper()
        pattern = r"^(\d{1,2})([C-X])([A-Z])([A-Z])(\d+)$"
        match = re.match(pattern, mgrs_string)
        if not match:
            raise ValueError(f"Invalid MGRS string: {mgrs_string}")

        zone_number = int(match.group(1))
        zone_letter = match.group(2)
        col_letter = match.group(3)
        row_letter = match.group(4)
        digits = match.group(5)

        if len(digits) % 2 != 0:
            raise ValueError(f"MGRS numeric portion must have even digits: {digits}")

        precision = len(digits) // 2
        easting = int(digits[:precision])
        northing = int(digits[precision:])

        return MGRSCoord(
            zone_number=zone_number,
            zone_letter=zone_letter,
            col_letter=col_letter,
            row_letter=row_letter,
            easting=easting,
            northing=northing,
            precision=precision,
        )

    def distance_m(
        self,
        lat1_or_coord1,
        lon1_or_coord2,
        lat2: Optional[float] = None,
        lon2: Optional[float] = None,
    ) -> float:
        """
        Compute distance in meters between two points.

        Can be called as:
          distance_m(lat1, lon1, lat2, lon2)   — four floats
          distance_m(coord1, coord2)            — two MGRSCoord objects

        Returns:
            Distance in meters.
        """
        if lat2 is not None and lon2 is not None:
            # Called with four lat/lon floats
            return self.haversine(lat1_or_coord1, lon1_or_coord2, lat2, lon2)
        # Called with two MGRSCoord objects
        coord1, coord2 = lat1_or_coord1, lon1_or_coord2
        lat1, lon1 = self.mgrs_to_latlon(str(coord1))
        lat2, lon2 = self.mgrs_to_latlon(str(coord2))
        return self.haversine(lat1, lon1, lat2, lon2)

    @staticmethod
    def haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        """
        Compute Haversine distance between two lat/lon points.

        Returns:
            Distance in meters.
        """
        R = 6371000  # Earth radius in meters
        phi1, phi2 = math.radians(lat1), math.radians(lat2)
        dphi = math.radians(lat2 - lat1)
        dlambda = math.radians(lon2 - lon1)

        a = (
            math.sin(dphi / 2) ** 2
            + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
        )
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
        return R * c

    def latlon_to_mgrs_string(
        self, lat: float, lon: float, precision: int = 5
    ) -> str:
        """Convenience: lat/lon to MGRS string."""
        return str(self.latlon_to_mgrs(lat, lon, precision))

    def bearing_deg(
        self, lat1: float, lon1: float, lat2: float, lon2: float
    ) -> float:
        """Alias for bearing(). Returns bearing in degrees (0-360)."""
        return self.bearing(lat1, lon1, lat2, lon2)

    def bearing(
        self, lat1: float, lon1: float, lat2: float, lon2: float
    ) -> float:
        """
        Compute initial bearing from point 1 to point 2.

        Returns:
            Bearing in degrees (0-360, clockwise from North).
        """
        phi1, phi2 = math.radians(lat1), math.radians(lat2)
        dl = math.radians(lon2 - lon1)

        x = math.sin(dl) * math.cos(phi2)
        y = math.cos(phi1) * math.sin(phi2) - math.sin(phi1) * math.cos(phi2) * math.cos(dl)
        theta = math.atan2(x, y)
        return (math.degrees(theta) + 360) % 360


if __name__ == "__main__":
    converter = MGRSConverter()

    # Test: Fort Irwin NTC (34.25, -116.68)
    lat, lon = 34.25, -116.68
    mgrs = converter.latlon_to_mgrs(lat, lon)
    print(f"Fort Irwin NTC: ({lat}, {lon}) -> MGRS: {mgrs}")

    back_lat, back_lon = converter.mgrs_to_latlon(str(mgrs))
    print(f"Back to lat/lon: ({back_lat:.4f}, {back_lon:.4f})")

    dist = converter.haversine(lat, lon, back_lat, back_lon)
    print(f"Round-trip error: {dist:.2f} m")

    brg = converter.bearing(34.0, -117.5, 34.5, -117.0)
    print(f"Bearing SW→NE corner of AO: {brg:.1f}°")
    print("mgrs_converter.py OK")
