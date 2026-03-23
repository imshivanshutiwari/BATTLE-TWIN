"""
Dataset builder that assembles the full Area of Operations dataset.

Orchestrates all data fetchers to build a complete battlefield dataset:
- OSM terrain + roads + buildings
- USGS DEM elevation
- ADS-B aircraft tracks
- Weather conditions
- Sentinel-2 imagery
- CoT event samples

Produces a unified AODataset object ready for C2 system consumption.
"""

import argparse
import json
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

from data.osm_terrain_fetcher import OSMTerrainFetcher
from data.adsb_fetcher import ADSBFetcher
from data.weather_fetcher import WeatherFetcher
from data.usgs_dem_fetcher import USGSDEMFetcher
from data.sentinel_fetcher import SentinelFetcher
from data.cot_parser import CoTParser
from utils.logger import get_logger
from utils.config_loader import load_config

log = get_logger("DATASET_BUILDER")

CACHE_DIR = Path("data/cache")


@dataclass
class AODataset:
    """Complete Area of Operations dataset."""
    bbox: Tuple[float, float, float, float]
    ao_name: str
    timestamp: datetime = field(default_factory=lambda: datetime.now(tz=timezone.utc))

    # Terrain data
    dem: Optional[np.ndarray] = None
    slope: Optional[np.ndarray] = None
    aspect: Optional[np.ndarray] = None
    trafficability: Optional[np.ndarray] = None
    terrain_rgb: Optional[np.ndarray] = None

    # Vector features
    roads: Optional[Any] = None        # GeoDataFrame
    terrain_features: Optional[Any] = None  # GeoDataFrame
    buildings: Optional[Any] = None    # GeoDataFrame
    military_features: Optional[Any] = None  # GeoDataFrame

    # Real-time data
    aircraft: Optional[List[Dict]] = None
    weather: Optional[Dict] = None
    cot_events: Optional[List[Dict]] = None

    # Metadata
    stats: Dict[str, Any] = field(default_factory=dict)

    def summary(self) -> Dict[str, Any]:
        """Generate dataset summary."""
        return {
            "ao_name": self.ao_name,
            "bbox": self.bbox,
            "timestamp": self.timestamp.isoformat(),
            "dem_shape": self.dem.shape if self.dem is not None else None,
            "n_roads": len(self.roads) if self.roads is not None else 0,
            "n_terrain_features": (
                len(self.terrain_features) if self.terrain_features is not None else 0
            ),
            "n_buildings": len(self.buildings) if self.buildings is not None else 0,
            "n_military": (
                len(self.military_features) if self.military_features is not None else 0
            ),
            "n_aircraft": len(self.aircraft) if self.aircraft is not None else 0,
            "weather_available": self.weather is not None,
            "n_cot_events": len(self.cot_events) if self.cot_events is not None else 0,
            "stats": self.stats,
        }


class DatasetBuilder:
    """
    Assembles the full AO dataset from all real data sources.

    Orchestrates parallel fetching from:
    - OpenStreetMap (Overpass API)
    - USGS National Map (elevation)
    - OpenSky Network (ADS-B aircraft)
    - OpenWeatherMap (conditions)
    - Copernicus (Sentinel-2 imagery)
    """

    def __init__(
        self,
        bbox: Optional[Tuple[float, float, float, float]] = None,
        ao_name: Optional[str] = None,
    ):
        try:
            config = load_config("battlefield_config")
            self.bbox = bbox or tuple(config.get("ao_bbox", [34.0, -117.5, 34.5, -117.0]))
            self.ao_name = ao_name or config.get("ao_name", "OPERATION BLUE EAGLE")
        except FileNotFoundError:
            self.bbox = bbox or (34.0, -117.5, 34.5, -117.0)
            self.ao_name = ao_name or "OPERATION BLUE EAGLE"

        self.osm_fetcher = OSMTerrainFetcher()
        self.adsb_fetcher = ADSBFetcher()
        self.weather_fetcher = WeatherFetcher()
        self.dem_fetcher = USGSDEMFetcher()
        self.sentinel_fetcher = SentinelFetcher()
        self.cot_parser = CoTParser()

        CACHE_DIR.mkdir(parents=True, exist_ok=True)

    def build(self, fetch_real: bool = True) -> AODataset:
        """
        Build the complete AO dataset.

        Args:
            fetch_real: If True, fetch from real APIs. If False, use cache only.

        Returns:
            Complete AODataset object.
        """
        start_time = time.time()
        dataset = AODataset(bbox=self.bbox, ao_name=self.ao_name)
        log.info(f"Building AO dataset: {self.ao_name}, bbox={self.bbox}")

        # 1. DEM elevation data
        log.info("Step 1/7: Fetching DEM elevation data...")
        try:
            dataset.dem = self.dem_fetcher.fetch_dem(self.bbox, resolution_m=30)
            dataset.slope = self.dem_fetcher.compute_slope(dataset.dem)
            dataset.aspect = self.dem_fetcher.compute_aspect(dataset.dem)
            dataset.trafficability = self.dem_fetcher.compute_trafficability(dataset.slope)
            dataset.stats["dem_shape"] = dataset.dem.shape
            dataset.stats["elev_range"] = [float(dataset.dem.min()), float(dataset.dem.max())]
        except Exception as e:
            log.error(f"DEM fetch error: {e}")

        # 2. OSM terrain features
        log.info("Step 2/7: Fetching OSM terrain features...")
        try:
            dataset.roads = self.osm_fetcher.fetch_roads(self.bbox)
            dataset.terrain_features = self.osm_fetcher.fetch_terrain_features(self.bbox)
            dataset.buildings = self.osm_fetcher.fetch_buildings(self.bbox)
            dataset.military_features = self.osm_fetcher.fetch_military_features(self.bbox)
            dataset.stats["n_roads"] = len(dataset.roads) if dataset.roads is not None else 0
        except Exception as e:
            log.error(f"OSM fetch error: {e}")

        # 3. ADS-B aircraft tracks
        if fetch_real:
            log.info("Step 3/7: Fetching ADS-B aircraft data...")
            try:
                aircraft = self.adsb_fetcher.fetch_live_aircraft(self.bbox)
                dataset.aircraft = [ac.to_dict() for ac in aircraft]
                dataset.stats["n_aircraft"] = len(dataset.aircraft)
            except Exception as e:
                log.error(f"ADS-B fetch error: {e}")
                dataset.aircraft = []

        # 4. Weather conditions
        log.info("Step 4/7: Fetching weather data...")
        try:
            center_lat = (self.bbox[0] + self.bbox[2]) / 2
            center_lon = (self.bbox[1] + self.bbox[3]) / 2
            weather = self.weather_fetcher.fetch_current(center_lat, center_lon)
            dataset.weather = weather.to_dict()
            dataset.stats["weather"] = weather.weather_description
        except Exception as e:
            log.error(f"Weather fetch error: {e}")

        # 5. Sentinel-2 terrain imagery
        log.info("Step 5/7: Generating terrain imagery...")
        try:
            dataset.terrain_rgb = self.sentinel_fetcher.get_imagery(self.bbox)
            dataset.stats["imagery_shape"] = dataset.terrain_rgb.shape
        except Exception as e:
            log.error(f"Imagery error: {e}")

        # 6. Generate sample CoT events from battlefield config
        log.info("Step 6/7: Generating CoT events...")
        try:
            config = load_config("battlefield_config")
            cot_events = []

            # Generate CoT for friendly units
            for unit in config.get("friendly_units", []):
                xml = CoTParser.generate_sample_cot(
                    uid=unit["uid"],
                    callsign=unit["callsign"],
                    event_type="a-f-G",
                    lat=unit["initial_lat"],
                    lon=unit["initial_lon"],
                )
                event = self.cot_parser.parse_event(xml)
                cot_events.append(event.to_dict())

            # Generate CoT for hostile contacts
            for contact in config.get("hostile_contacts_initial", []):
                xml = CoTParser.generate_sample_cot(
                    uid=contact["uid"],
                    callsign=contact["callsign"],
                    event_type="a-h-G",
                    lat=contact["last_known_lat"],
                    lon=contact["last_known_lon"],
                )
                event = self.cot_parser.parse_event(xml)
                cot_events.append(event.to_dict())

            dataset.cot_events = cot_events
            dataset.stats["n_cot_events"] = len(cot_events)
        except Exception as e:
            log.error(f"CoT generation error: {e}")
            dataset.cot_events = []

        # 7. Save dataset summary
        log.info("Step 7/7: Saving dataset summary...")
        elapsed = time.time() - start_time
        dataset.stats["build_time_s"] = round(elapsed, 2)

        summary = dataset.summary()
        summary_file = CACHE_DIR / "dataset_summary.json"
        with open(summary_file, "w", encoding="utf-8") as f:
            json.dump(summary, f, indent=2, default=str)

        log.info(f"Dataset build complete in {elapsed:.1f}s: {summary}")
        return dataset

    def load_cached(self) -> Optional[AODataset]:
        """Load a previously built dataset from cache."""
        summary_file = CACHE_DIR / "dataset_summary.json"
        if not summary_file.exists():
            return None

        log.info("Loading cached dataset")
        return self.build(fetch_real=False)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="BATTLE-TWIN Dataset Builder")
    parser.add_argument(
        "--fetch-real",
        action="store_true",
        help="Fetch real data from APIs (requires internet)",
    )
    parser.add_argument(
        "--bbox",
        type=float,
        nargs=4,
        default=[34.0, -117.5, 34.5, -117.0],
        help="Bounding box: min_lat min_lon max_lat max_lon",
    )
    args = parser.parse_args()

    builder = DatasetBuilder(bbox=tuple(args.bbox))
    dataset = builder.build(fetch_real=args.fetch_real)

    print("\n=== DATASET SUMMARY ===")
    for key, value in dataset.summary().items():
        print(f"  {key}: {value}")

    print("\ndataset_builder.py OK")
