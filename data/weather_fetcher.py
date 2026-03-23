"""
Weather data fetcher using the OpenWeatherMap API.

Fetches REAL weather conditions for battlefield operations:
- Current weather (temperature, wind, visibility, precipitation)
- Wind vectors for fire support calculations
- Visibility and cloud ceiling for CAS availability
- Hourly forecast for mission planning
"""

import os
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import requests
import numpy as np

from utils.logger import get_logger

log = get_logger("WEATHER")

OPENWEATHER_API_URL = "https://api.openweathermap.org/data/2.5"
CACHE_DIR = Path("data/cache")


@dataclass
class WeatherCondition:
    """Weather conditions at a specific location and time."""
    timestamp: datetime
    latitude: float
    longitude: float
    temperature_c: float
    feels_like_c: float
    pressure_hpa: float
    humidity_pct: float
    wind_speed_mps: float
    wind_direction_deg: float
    wind_gust_mps: Optional[float]
    visibility_m: float
    cloud_cover_pct: float
    weather_main: str  # e.g., "Clear", "Clouds", "Rain"
    weather_description: str
    rain_1h_mm: float
    snow_1h_mm: float
    sunrise: Optional[datetime]
    sunset: Optional[datetime]

    @property
    def is_day(self) -> bool:
        """Check if it's currently daytime."""
        if self.sunrise and self.sunset:
            return self.sunrise <= self.timestamp <= self.sunset
        return True

    @property
    def wind_correction_mils(self) -> float:
        """
        Compute wind correction factor for artillery in mils.
        Simplified NATO ballistic wind correction.
        """
        return self.wind_speed_mps * 0.3  # mils per m/s crosswind (simplified)

    @property
    def cas_available(self) -> bool:
        """
        Check if weather supports Close Air Support.
        VMC requirements: visibility > 3 miles, ceiling > 1000 ft.
        """
        vis_ok = self.visibility_m > 4828  # 3 statute miles
        ceiling_ok = self.cloud_cover_pct < 90  # Approximate ceiling check
        return vis_ok and ceiling_ok

    @property
    def aviation_category(self) -> str:
        """Determine aviation weather category."""
        vis_m = self.visibility_m
        if vis_m >= 9260 and self.cloud_cover_pct < 25:
            return "VFR"  # Visual Flight Rules
        elif vis_m >= 4828:
            return "MVFR"  # Marginal VFR
        elif vis_m >= 1609:
            return "IFR"  # Instrument Flight Rules
        return "LIFR"  # Low IFR

    def to_dict(self) -> Dict[str, Any]:
        """Convert to serializable dictionary."""
        return {
            "timestamp": self.timestamp.isoformat(),
            "latitude": self.latitude,
            "longitude": self.longitude,
            "temperature_c": self.temperature_c,
            "feels_like_c": self.feels_like_c,
            "pressure_hpa": self.pressure_hpa,
            "humidity_pct": self.humidity_pct,
            "wind_speed_mps": self.wind_speed_mps,
            "wind_direction_deg": self.wind_direction_deg,
            "wind_gust_mps": self.wind_gust_mps,
            "visibility_m": self.visibility_m,
            "cloud_cover_pct": self.cloud_cover_pct,
            "weather_main": self.weather_main,
            "weather_description": self.weather_description,
            "rain_1h_mm": self.rain_1h_mm,
            "snow_1h_mm": self.snow_1h_mm,
            "is_day": self.is_day,
            "cas_available": self.cas_available,
            "aviation_category": self.aviation_category,
            "wind_correction_mils": self.wind_correction_mils,
        }


class WeatherFetcher:
    """
    Fetches REAL weather data from OpenWeatherMap API.

    Requires a free API key (set OPENWEATHER_API_KEY in .env).
    Falls back to reasonable default conditions if API unavailable.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        api_url: str = OPENWEATHER_API_URL,
        cache_dir: Optional[Path] = None,
    ):
        self.api_key = api_key or os.environ.get("OPENWEATHER_API_KEY", "")
        self.api_url = api_url
        self.cache_dir = cache_dir or CACHE_DIR
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.session = requests.Session()
        self._cache: Dict[str, Tuple[float, WeatherCondition]] = {}
        self._cache_ttl_s = 300  # 5-minute cache

    def _parse_weather_response(
        self, data: Dict[str, Any], lat: float, lon: float
    ) -> WeatherCondition:
        """Parse OpenWeatherMap API response into WeatherCondition."""
        main = data.get("main", {})
        wind = data.get("wind", {})
        clouds = data.get("clouds", {})
        weather = data.get("weather", [{}])[0]
        rain = data.get("rain", {})
        snow = data.get("snow", {})
        sys_data = data.get("sys", {})

        sunrise = None
        sunset = None
        if "sunrise" in sys_data:
            sunrise = datetime.fromtimestamp(sys_data["sunrise"], tz=timezone.utc)
        if "sunset" in sys_data:
            sunset = datetime.fromtimestamp(sys_data["sunset"], tz=timezone.utc)

        return WeatherCondition(
            timestamp=datetime.fromtimestamp(
                data.get("dt", time.time()), tz=timezone.utc
            ),
            latitude=lat,
            longitude=lon,
            temperature_c=main.get("temp", 20.0),
            feels_like_c=main.get("feels_like", 20.0),
            pressure_hpa=main.get("pressure", 1013.25),
            humidity_pct=main.get("humidity", 50.0),
            wind_speed_mps=wind.get("speed", 0.0),
            wind_direction_deg=wind.get("deg", 0.0),
            wind_gust_mps=wind.get("gust"),
            visibility_m=data.get("visibility", 10000),
            cloud_cover_pct=clouds.get("all", 0),
            weather_main=weather.get("main", "Clear"),
            weather_description=weather.get("description", "clear sky"),
            rain_1h_mm=rain.get("1h", 0.0),
            snow_1h_mm=snow.get("1h", 0.0),
            sunrise=sunrise,
            sunset=sunset,
        )

    def fetch_current(
        self,
        lat: float,
        lon: float,
    ) -> WeatherCondition:
        """
        Fetch current weather conditions for a location.

        Args:
            lat: Latitude in decimal degrees.
            lon: Longitude in decimal degrees.

        Returns:
            WeatherCondition with current conditions.
        """
        cache_key = f"{lat:.2f}_{lon:.2f}"
        if cache_key in self._cache:
            cached_time, cached_data = self._cache[cache_key]
            if time.time() - cached_time < self._cache_ttl_s:
                return cached_data

        if not self.api_key:
            log.warning("No OPENWEATHER_API_KEY set, using default conditions")
            return self._default_conditions(lat, lon)

        try:
            response = self.session.get(
                f"{self.api_url}/weather",
                params={
                    "lat": lat,
                    "lon": lon,
                    "appid": self.api_key,
                    "units": "metric",
                },
                timeout=10,
            )
            response.raise_for_status()
            data = response.json()
            condition = self._parse_weather_response(data, lat, lon)
            self._cache[cache_key] = (time.time(), condition)
            log.info(
                f"Weather at ({lat:.2f}, {lon:.2f}): "
                f"{condition.weather_description}, "
                f"wind {condition.wind_speed_mps:.1f}m/s @ {condition.wind_direction_deg:.0f}°"
            )
            return condition

        except requests.RequestException as e:
            log.error(f"Weather API error: {e}")
            return self._default_conditions(lat, lon)

    def fetch_ao_weather(
        self,
        bbox: Tuple[float, float, float, float],
        grid_points: int = 4,
    ) -> List[WeatherCondition]:
        """
        Fetch weather at multiple points across the AO.

        Args:
            bbox: (min_lat, min_lon, max_lat, max_lon)
            grid_points: Number of sample points per axis.

        Returns:
            List of WeatherConditions across the AO.
        """
        lats = np.linspace(bbox[0], bbox[2], grid_points)
        lons = np.linspace(bbox[1], bbox[3], grid_points)

        conditions = []
        for lat in lats:
            for lon in lons:
                conditions.append(self.fetch_current(lat, lon))

        return conditions

    def fetch_forecast(
        self,
        lat: float,
        lon: float,
        hours: int = 24,
    ) -> List[WeatherCondition]:
        """
        Fetch hourly weather forecast.

        Args:
            lat: Latitude.
            lon: Longitude.
            hours: Number of forecast hours.

        Returns:
            List of forecasted WeatherConditions.
        """
        if not self.api_key:
            log.warning("No API key, returning current conditions only")
            return [self._default_conditions(lat, lon)]

        try:
            response = self.session.get(
                f"{self.api_url}/forecast",
                params={
                    "lat": lat,
                    "lon": lon,
                    "appid": self.api_key,
                    "units": "metric",
                    "cnt": min(hours // 3, 40),  # 3-hour intervals, max 5 days
                },
                timeout=10,
            )
            response.raise_for_status()
            data = response.json()

            forecasts = []
            for item in data.get("list", []):
                forecasts.append(self._parse_weather_response(item, lat, lon))
            return forecasts

        except requests.RequestException as e:
            log.error(f"Forecast API error: {e}")
            return [self._default_conditions(lat, lon)]

    def compute_wind_vector(
        self,
        condition: WeatherCondition,
    ) -> Tuple[float, float]:
        """
        Compute wind vector components (north, east) in m/s.

        Args:
            condition: Weather condition with wind data.

        Returns:
            (wind_north_mps, wind_east_mps)
        """
        wind_rad = np.radians(condition.wind_direction_deg)
        # Wind direction is "from" direction, convert to vector components
        wind_north = -condition.wind_speed_mps * np.cos(wind_rad)
        wind_east = -condition.wind_speed_mps * np.sin(wind_rad)
        return float(wind_north), float(wind_east)

    def _default_conditions(
        self, lat: float, lon: float
    ) -> WeatherCondition:
        """Return physically reasonable default weather conditions."""
        return WeatherCondition(
            timestamp=datetime.now(tz=timezone.utc),
            latitude=lat,
            longitude=lon,
            temperature_c=22.0,
            feels_like_c=21.0,
            pressure_hpa=1013.25,
            humidity_pct=45.0,
            wind_speed_mps=3.5,
            wind_direction_deg=225.0,
            wind_gust_mps=5.2,
            visibility_m=16093,  # 10 miles
            cloud_cover_pct=25,
            weather_main="Clear",
            weather_description="clear sky",
            rain_1h_mm=0.0,
            snow_1h_mm=0.0,
            sunrise=datetime.now(tz=timezone.utc).replace(hour=6, minute=15),
            sunset=datetime.now(tz=timezone.utc).replace(hour=18, minute=45),
        )


if __name__ == "__main__":
    fetcher = WeatherFetcher()
    # AO center
    lat, lon = 34.25, -117.25
    print(f"Fetching weather for ({lat}, {lon})")

    condition = fetcher.fetch_current(lat, lon)
    print(f"Temperature: {condition.temperature_c:.1f}°C")
    print(f"Wind: {condition.wind_speed_mps:.1f} m/s @ {condition.wind_direction_deg:.0f}°")
    print(f"Visibility: {condition.visibility_m:.0f} m")
    print(f"CAS Available: {condition.cas_available}")
    print(f"Aviation Category: {condition.aviation_category}")

    wn, we = fetcher.compute_wind_vector(condition)
    print(f"Wind vector (N,E): ({wn:.1f}, {we:.1f}) m/s")
    print("weather_fetcher.py OK")
