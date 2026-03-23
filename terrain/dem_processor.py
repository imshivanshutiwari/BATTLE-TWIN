"""DEM processor for SRTM/USGS elevation analysis."""

import numpy as np
from typing import Dict, Tuple
from utils.logger import get_logger

log = get_logger("DEM_PROC")


class DEMProcessor:
    """Processes Digital Elevation Model data for terrain analysis."""

    def __init__(self, cell_size_m: float = 30.0):
        self.cell_size_m = cell_size_m

    def load_dem(self, filepath: str) -> np.ndarray:
        """Load DEM from numpy file."""
        return np.load(filepath).astype(np.float32)

    def compute_hillshade(
        self, dem: np.ndarray, azimuth_deg: float = 315.0, altitude_deg: float = 45.0
    ) -> np.ndarray:
        dy, dx = np.gradient(dem, self.cell_size_m)
        slope = np.arctan(np.sqrt(dx**2 + dy**2))
        aspect = np.arctan2(-dx, dy)
        az_rad = np.radians(azimuth_deg)
        alt_rad = np.radians(altitude_deg)
        hs = np.sin(alt_rad) * np.cos(slope) + np.cos(alt_rad) * np.sin(slope) * np.cos(
            az_rad - aspect
        )
        return np.clip(hs, 0, 1).astype(np.float32)

    def compute_curvature(self, dem: np.ndarray) -> np.ndarray:
        dy, dx = np.gradient(dem, self.cell_size_m)
        dyy, _ = np.gradient(dy, self.cell_size_m)
        _, dxx = np.gradient(dx, self.cell_size_m)
        return (dxx + dyy).astype(np.float32)

    def compute_roughness(self, dem: np.ndarray, window: int = 3) -> np.ndarray:
        from scipy.ndimage import generic_filter

        roughness = generic_filter(dem, np.std, size=window)
        return roughness.astype(np.float32)

    def compute_tpi(self, dem: np.ndarray, radius: int = 5) -> np.ndarray:
        from scipy.ndimage import uniform_filter

        mean_elev = uniform_filter(dem, size=2 * radius + 1)
        return (dem - mean_elev).astype(np.float32)

    def resample(self, dem: np.ndarray, target_shape: Tuple[int, int]) -> np.ndarray:
        from scipy.ndimage import zoom

        factors = (target_shape[0] / dem.shape[0], target_shape[1] / dem.shape[1])
        return zoom(dem, factors, order=1).astype(np.float32)

    def get_statistics(self, dem: np.ndarray) -> Dict:
        return {
            "min_elev": float(np.min(dem)),
            "max_elev": float(np.max(dem)),
            "mean_elev": float(np.mean(dem)),
            "std_elev": float(np.std(dem)),
            "shape": dem.shape,
        }


if __name__ == "__main__":
    proc = DEMProcessor()
    dem = np.random.uniform(800, 1200, (100, 100)).astype(np.float32)
    hs = proc.compute_hillshade(dem)
    print(f"DEM stats: {proc.get_statistics(dem)}")
    print(f"Hillshade range: [{hs.min():.2f}, {hs.max():.2f}]")
    print("dem_processor.py OK")
