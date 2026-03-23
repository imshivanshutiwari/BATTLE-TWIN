"""Cover and concealment scoring for terrain analysis."""
import numpy as np
from typing import Dict, Tuple
from utils.logger import get_logger
log = get_logger("COVER")


class CoverAnalyzer:
    """Scores terrain for cover (protection) and concealment (hiding)."""

    def __init__(self):
        self.terrain_cover = {"FOREST": 0.3, "URBAN": 0.7, "SCRUB": 0.1, "WATER": 0.0, "OPEN": 0.0, "ROCK": 0.5}
        self.terrain_concealment = {"FOREST": 0.9, "URBAN": 0.8, "SCRUB": 0.5, "WATER": 0.1, "OPEN": 0.1, "ROCK": 0.2}

    def compute_cover_score(self, terrain_grid: np.ndarray, terrain_labels: Dict[int, str]) -> np.ndarray:
        score = np.zeros_like(terrain_grid, dtype=np.float32)
        for val, label in terrain_labels.items():
            mask = terrain_grid == val
            score[mask] = self.terrain_cover.get(label, 0.0)
        return score

    def compute_concealment_score(self, terrain_grid: np.ndarray, terrain_labels: Dict[int, str]) -> np.ndarray:
        score = np.zeros_like(terrain_grid, dtype=np.float32)
        for val, label in terrain_labels.items():
            mask = terrain_grid == val
            score[mask] = self.terrain_concealment.get(label, 0.0)
        return score

    def compute_combined_score(self, cover: np.ndarray, concealment: np.ndarray,
                               cover_weight: float = 0.6) -> np.ndarray:
        return (cover_weight * cover + (1 - cover_weight) * concealment).astype(np.float32)

    def find_best_positions(self, combined: np.ndarray, n: int = 10) -> list:
        flat = combined.flatten()
        top_indices = np.argsort(flat)[-n:][::-1]
        rows, cols = combined.shape
        return [(int(idx // cols), int(idx % cols), float(flat[idx])) for idx in top_indices]

    def compute_defilade_score(self, dem: np.ndarray, cell_size_m: float = 30.0) -> np.ndarray:
        from scipy.ndimage import uniform_filter
        local_mean = uniform_filter(dem, size=5)
        depression = np.clip(local_mean - dem, 0, None)
        return (depression / (depression.max() + 1e-10)).astype(np.float32)


if __name__ == "__main__":
    analyzer = CoverAnalyzer()
    grid = np.random.choice([0, 1, 2, 3], size=(50, 50))
    labels = {0: "OPEN", 1: "FOREST", 2: "URBAN", 3: "SCRUB"}
    cover = analyzer.compute_cover_score(grid, labels)
    concealment = analyzer.compute_concealment_score(grid, labels)
    combined = analyzer.compute_combined_score(cover, concealment)
    best = analyzer.find_best_positions(combined, 5)
    print(f"Best positions: {best[:3]}")
    print("cover_analyzer.py OK")
