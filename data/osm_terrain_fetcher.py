"""
OpenStreetMap terrain fetcher using the Overpass API.

Fetches REAL geographic data for the battlefield area of operations:
- Military features (airfields, bunkers, ranges)
- Road networks (motorway through track)
- Terrain features (forests, water, urban, open)
- Building footprints for urban operations
- Combined tactical map assembly
"""

import json
import hashlib
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import requests
import numpy as np
import geopandas as gpd
from shapely.geometry import shape, LineString, Polygon, Point, MultiPolygon

from utils.logger import get_logger

log = get_logger("OSM_TERRAIN")

OVERPASS_API_URL = "https://overpass-api.de/api/interpreter"
CACHE_DIR = Path("data/cache")


class OSMTerrainFetcher:
    """
    Fetches REAL OpenStreetMap data via the Overpass API.

    All queries hit the live Overpass API endpoint and return
    real geographic features as GeoPandas GeoDataFrames.
    Results are cached locally to avoid repeated API calls.
    """

    def __init__(
        self,
        api_url: str = OVERPASS_API_URL,
        cache_dir: Optional[Path] = None,
        timeout_s: int = 60,
    ):
        self.api_url = api_url
        self.cache_dir = cache_dir or CACHE_DIR
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.timeout_s = timeout_s
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": "BATTLE-TWIN/1.0"})

    def _cache_key(self, query: str) -> str:
        """Generate a deterministic cache key from query string."""
        return hashlib.sha256(query.encode("utf-8")).hexdigest()[:16]

    def _get_cached(self, cache_key: str) -> Optional[gpd.GeoDataFrame]:
        """Load cached GeoDataFrame if available."""
        cache_file = self.cache_dir / f"osm_{cache_key}.geojson"
        if cache_file.exists():
            log.debug(f"Loading from cache: {cache_file}")
            return gpd.read_file(cache_file)
        return None

    def _save_cache(self, cache_key: str, gdf: gpd.GeoDataFrame) -> None:
        """Save GeoDataFrame to cache."""
        cache_file = self.cache_dir / f"osm_{cache_key}.geojson"
        gdf.to_file(cache_file, driver="GeoJSON")
        log.debug(f"Cached to: {cache_file}")

    def _query_overpass(self, query: str) -> Dict[str, Any]:
        """
        Execute an Overpass API query and return raw JSON response.

        Args:
            query: Overpass QL query string.

        Returns:
            Parsed JSON response dict.

        Raises:
            requests.HTTPError: On API error.
        """
        log.info(f"Querying Overpass API ({len(query)} chars)")
        response = self.session.post(
            self.api_url,
            data={"data": query},
            timeout=self.timeout_s,
        )
        response.raise_for_status()
        return response.json()

    def _overpass_to_gdf(
        self, data: Dict[str, Any], feature_type: str = "generic"
    ) -> gpd.GeoDataFrame:
        """
        Convert Overpass JSON response to GeoDataFrame.

        Handles nodes, ways, and relations with geometry.
        """
        features = []
        elements = data.get("elements", [])

        for elem in elements:
            props = elem.get("tags", {})
            props["osm_id"] = elem.get("id")
            props["osm_type"] = elem.get("type")
            props["feature_category"] = feature_type

            geom = None
            if elem["type"] == "node":
                geom = Point(elem["lon"], elem["lat"])
            elif elem["type"] == "way" and "geometry" in elem:
                coords = [(pt["lon"], pt["lat"]) for pt in elem["geometry"]]
                if len(coords) >= 2:
                    if coords[0] == coords[-1] and len(coords) >= 4:
                        geom = Polygon(coords)
                    else:
                        geom = LineString(coords)
            elif elem["type"] == "relation" and "members" in elem:
                # Simplified: extract outer ways from relation
                outer_coords = []
                for member in elem.get("members", []):
                    if member.get("role") == "outer" and "geometry" in member:
                        coords = [
                            (pt["lon"], pt["lat"]) for pt in member["geometry"]
                        ]
                        outer_coords.extend(coords)
                if len(outer_coords) >= 4:
                    try:
                        geom = Polygon(outer_coords)
                    except Exception:
                        geom = LineString(outer_coords) if len(outer_coords) >= 2 else None

            if geom is not None:
                features.append({"geometry": geom, **props})

        if not features:
            return gpd.GeoDataFrame(columns=["geometry", "feature_category"], crs="EPSG:4326")

        gdf = gpd.GeoDataFrame(features, crs="EPSG:4326")
        log.info(f"Parsed {len(gdf)} {feature_type} features")
        return gdf

    def _bbox_to_overpass(self, bbox: Tuple[float, float, float, float]) -> str:
        """Convert (min_lat, min_lon, max_lat, max_lon) to Overpass bbox format."""
        return f"{bbox[0]},{bbox[1]},{bbox[2]},{bbox[3]}"

    def fetch_military_features(
        self, bbox: Tuple[float, float, float, float]
    ) -> gpd.GeoDataFrame:
        """
        Fetch military features from OpenStreetMap.

        Returns airfields, bunkers, ranges, training areas, barracks.

        Args:
            bbox: (min_lat, min_lon, max_lat, max_lon)

        Returns:
            GeoDataFrame with military features.
        """
        query = f"""
        [out:json][timeout:{self.timeout_s}];
        (
          way["military"]({self._bbox_to_overpass(bbox)});
          node["military"]({self._bbox_to_overpass(bbox)});
          relation["military"]({self._bbox_to_overpass(bbox)});
          way["landuse"="military"]({self._bbox_to_overpass(bbox)});
        );
        out geom;
        """
        cache_key = self._cache_key(f"military_{bbox}")
        cached = self._get_cached(cache_key)
        if cached is not None:
            return cached

        data = self._query_overpass(query)
        gdf = self._overpass_to_gdf(data, "military")
        if not gdf.empty:
            self._save_cache(cache_key, gdf)
        return gdf

    def fetch_roads(
        self, bbox: Tuple[float, float, float, float]
    ) -> gpd.GeoDataFrame:
        """
        Fetch road network from OpenStreetMap.

        Includes: motorway, primary, secondary, tertiary, track.

        Args:
            bbox: (min_lat, min_lon, max_lat, max_lon)

        Returns:
            GeoDataFrame with road features.
        """
        query = f"""
        [out:json][timeout:{self.timeout_s}];
        (
          way["highway"~"motorway|trunk|primary|secondary|tertiary|unclassified|track"]
             ({self._bbox_to_overpass(bbox)});
        );
        out geom;
        """
        cache_key = self._cache_key(f"roads_{bbox}")
        cached = self._get_cached(cache_key)
        if cached is not None:
            return cached

        data = self._query_overpass(query)
        gdf = self._overpass_to_gdf(data, "road")

        # Classify trafficability by highway type
        speed_map = {
            "motorway": 100, "trunk": 80, "primary": 60,
            "secondary": 40, "tertiary": 30, "unclassified": 20, "track": 10,
        }
        if not gdf.empty and "highway" in gdf.columns:
            gdf["speed_kph"] = gdf["highway"].map(speed_map).fillna(15)
            gdf["trafficability"] = gdf["speed_kph"].apply(
                lambda s: "GO" if s >= 30 else ("SLOW_GO" if s >= 15 else "NO_GO")
            )

        if not gdf.empty:
            self._save_cache(cache_key, gdf)
        return gdf

    def fetch_terrain_features(
        self, bbox: Tuple[float, float, float, float]
    ) -> gpd.GeoDataFrame:
        """
        Fetch terrain classification features.

        Categories: forest, water, urban, open ground.

        Args:
            bbox: (min_lat, min_lon, max_lat, max_lon)

        Returns:
            GeoDataFrame with terrain features.
        """
        query = f"""
        [out:json][timeout:{self.timeout_s}];
        (
          way["natural"~"wood|water|wetland|scrub|grassland|heath|bare_rock"]
             ({self._bbox_to_overpass(bbox)});
          way["landuse"~"forest|farmland|residential|industrial|commercial|meadow"]
             ({self._bbox_to_overpass(bbox)});
          relation["natural"="water"]({self._bbox_to_overpass(bbox)});
        );
        out geom;
        """
        cache_key = self._cache_key(f"terrain_{bbox}")
        cached = self._get_cached(cache_key)
        if cached is not None:
            return cached

        data = self._query_overpass(query)
        gdf = self._overpass_to_gdf(data, "terrain")

        # Classify terrain type for tactical analysis
        if not gdf.empty:
            def classify_terrain(row):
                natural = row.get("natural", "")
                landuse = row.get("landuse", "")
                if natural in ("wood",) or landuse in ("forest",):
                    return "FOREST"
                if natural in ("water", "wetland"):
                    return "WATER"
                if landuse in ("residential", "industrial", "commercial"):
                    return "URBAN"
                if natural in ("scrub", "heath"):
                    return "SCRUB"
                return "OPEN"

            gdf["terrain_class"] = gdf.apply(classify_terrain, axis=1)

            # Concealment and cover scores for tactical planning
            concealment_map = {
                "FOREST": 0.9, "URBAN": 0.8, "SCRUB": 0.5,
                "WATER": 0.1, "OPEN": 0.1,
            }
            cover_map = {
                "FOREST": 0.3, "URBAN": 0.7, "SCRUB": 0.1,
                "WATER": 0.0, "OPEN": 0.0,
            }
            gdf["concealment_score"] = gdf["terrain_class"].map(concealment_map)
            gdf["cover_score"] = gdf["terrain_class"].map(cover_map)

        if not gdf.empty:
            self._save_cache(cache_key, gdf)
        return gdf

    def fetch_buildings(
        self, bbox: Tuple[float, float, float, float]
    ) -> gpd.GeoDataFrame:
        """
        Fetch building footprints for urban operations.

        Args:
            bbox: (min_lat, min_lon, max_lat, max_lon)

        Returns:
            GeoDataFrame with building polygons.
        """
        query = f"""
        [out:json][timeout:{self.timeout_s}];
        (
          way["building"]({self._bbox_to_overpass(bbox)});
          relation["building"]({self._bbox_to_overpass(bbox)});
        );
        out geom;
        """
        cache_key = self._cache_key(f"buildings_{bbox}")
        cached = self._get_cached(cache_key)
        if cached is not None:
            return cached

        data = self._query_overpass(query)
        gdf = self._overpass_to_gdf(data, "building")

        if not gdf.empty:
            # Estimate building height for LOS calculations
            if "building:levels" in gdf.columns:
                gdf["height_m"] = (
                    gdf["building:levels"]
                    .apply(lambda x: float(x) * 3.0 if x else 6.0)
                )
            else:
                gdf["height_m"] = 6.0  # Default 2-story building

            self._save_cache(cache_key, gdf)
        return gdf

    def build_tactical_map(
        self, bbox: Tuple[float, float, float, float]
    ) -> Dict[str, Any]:
        """
        Build a combined tactical map from all OSM data sources.

        Args:
            bbox: (min_lat, min_lon, max_lat, max_lon)

        Returns:
            Dictionary with GeoDataFrames for each feature layer.
        """
        log.info(f"Building tactical map for bbox {bbox}")

        tactical_map = {
            "military": self.fetch_military_features(bbox),
            "roads": self.fetch_roads(bbox),
            "terrain": self.fetch_terrain_features(bbox),
            "buildings": self.fetch_buildings(bbox),
            "bbox": bbox,
            "center_lat": (bbox[0] + bbox[2]) / 2,
            "center_lon": (bbox[1] + bbox[3]) / 2,
        }

        # Summary statistics
        stats = {
            layer: len(gdf) if isinstance(gdf, gpd.GeoDataFrame) else 0
            for layer, gdf in tactical_map.items()
            if isinstance(gdf, gpd.GeoDataFrame)
        }
        log.info(f"Tactical map assembled: {stats}")
        tactical_map["stats"] = stats

        # Save combined GeoJSON
        cache_file = self.cache_dir / f"tactical_map_{self._cache_key(str(bbox))}.geojson"
        combined_features = []
        for layer_name in ["military", "roads", "terrain", "buildings"]:
            gdf = tactical_map[layer_name]
            if isinstance(gdf, gpd.GeoDataFrame) and not gdf.empty:
                gdf_copy = gdf.copy()
                gdf_copy["layer"] = layer_name
                combined_features.append(gdf_copy)

        if combined_features:
            combined = gpd.GeoDataFrame(
                pd.concat(combined_features, ignore_index=True), crs="EPSG:4326"
            )
            combined.to_file(cache_file, driver="GeoJSON")
            log.info(f"Saved combined tactical map: {cache_file}")

        return tactical_map


# Need pandas for concat in build_tactical_map
import pandas as pd


if __name__ == "__main__":
    fetcher = OSMTerrainFetcher()
    # OPERATION BLUE EAGLE AO (Fort Irwin / NTC area)
    bbox = (34.0, -117.5, 34.5, -117.0)
    print(f"Fetching tactical data for bbox: {bbox}")

    try:
        roads = fetcher.fetch_roads(bbox)
        print(f"Roads fetched: {len(roads)} features")
        if not roads.empty:
            print(f"  Highway types: {roads.get('highway', pd.Series()).unique()}")
    except Exception as e:
        print(f"Roads fetch error (API may be rate-limited): {e}")

    print("osm_terrain_fetcher.py OK")
