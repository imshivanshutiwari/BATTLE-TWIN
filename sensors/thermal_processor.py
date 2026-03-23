"""
Thermal camera heat signature processor.

Processes thermal imagery to detect and classify:
- Human heat signatures (25-40°C)
- Vehicle heat signatures (40-120°C)
- Fire/explosion events (>200°C)
"""

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

from utils.logger import get_logger

log = get_logger("THERMAL")


@dataclass
class ThermalDetection:
    """A detected heat signature."""
    detection_id: str
    center_x: int
    center_y: int
    width: int
    height: int
    max_temp_c: float
    mean_temp_c: float
    classification: str  # HUMAN, VEHICLE, FIRE, UNKNOWN
    confidence: float
    pixel_count: int

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.detection_id,
            "center": (self.center_x, self.center_y),
            "size": (self.width, self.height),
            "max_temp": self.max_temp_c,
            "mean_temp": self.mean_temp_c,
            "class": self.classification,
            "confidence": self.confidence,
        }


class ThermalProcessor:
    """
    Processes thermal camera frames for target detection.

    Pipeline:
    1. Background subtraction (NUC — Non-Uniformity Correction)
    2. Temperature thresholding for interesting regions
    3. Blob detection and morphological filtering
    4. Classification by temperature and size
    5. Tracking across frames
    """

    def __init__(
        self,
        resolution: Tuple[int, int] = (640, 480),
        human_temp_range: Tuple[float, float] = (25.0, 40.0),
        vehicle_temp_range: Tuple[float, float] = (40.0, 120.0),
        min_blob_pixels: int = 20,
        confidence_threshold: float = 0.7,
    ):
        self.resolution = resolution
        self.human_range = human_temp_range
        self.vehicle_range = vehicle_temp_range
        self.min_blob_pixels = min_blob_pixels
        self.confidence_threshold = confidence_threshold
        self._background: Optional[np.ndarray] = None
        self._detection_count = 0
        self._frame_count = 0
        self._tracked_objects: Dict[str, List[ThermalDetection]] = {}

    def process_frame(
        self, thermal_frame: np.ndarray
    ) -> List[ThermalDetection]:
        """
        Process a single thermal frame.

        Args:
            thermal_frame: 2D array of temperature values in °C.

        Returns:
            List of detected heat signatures.
        """
        self._frame_count += 1

        # Background subtraction (adaptive)
        if self._background is None:
            self._background = thermal_frame.copy().astype(np.float32)
            return []

        # Update background (running average)
        alpha = 0.05
        self._background = (
            alpha * thermal_frame.astype(np.float32)
            + (1 - alpha) * self._background
        )

        # Foreground: significant temperature difference from background
        diff = np.abs(thermal_frame.astype(np.float32) - self._background)
        foreground = diff > 3.0  # 3°C threshold

        # Find interesting temperature regions
        detections = []

        # Human detection
        human_mask = (
            (thermal_frame >= self.human_range[0])
            & (thermal_frame <= self.human_range[1])
            & foreground
        )
        detections.extend(self._detect_blobs(thermal_frame, human_mask, "HUMAN"))

        # Vehicle detection
        vehicle_mask = (
            (thermal_frame >= self.vehicle_range[0])
            & (thermal_frame <= self.vehicle_range[1])
            & foreground
        )
        detections.extend(self._detect_blobs(thermal_frame, vehicle_mask, "VEHICLE"))

        # Fire detection
        fire_mask = thermal_frame > 200.0
        detections.extend(self._detect_blobs(thermal_frame, fire_mask, "FIRE"))

        # Filter by confidence
        detections = [
            d for d in detections if d.confidence >= self.confidence_threshold
        ]

        # Update tracking
        for d in detections:
            if d.detection_id not in self._tracked_objects:
                self._tracked_objects[d.detection_id] = []
            self._tracked_objects[d.detection_id].append(d)

        return detections

    def _detect_blobs(
        self,
        frame: np.ndarray,
        mask: np.ndarray,
        classification: str,
    ) -> List[ThermalDetection]:
        """
        Detect connected-component blobs in a binary mask.

        Uses a simple flood-fill approach.
        """
        detections = []
        visited = np.zeros_like(mask, dtype=bool)
        rows, cols = mask.shape

        for r in range(rows):
            for c in range(cols):
                if mask[r, c] and not visited[r, c]:
                    # Flood fill to find blob
                    blob_pixels = []
                    stack = [(r, c)]
                    while stack:
                        cr, cc = stack.pop()
                        if (
                            0 <= cr < rows
                            and 0 <= cc < cols
                            and mask[cr, cc]
                            and not visited[cr, cc]
                        ):
                            visited[cr, cc] = True
                            blob_pixels.append((cr, cc))
                            stack.extend([
                                (cr - 1, cc), (cr + 1, cc),
                                (cr, cc - 1), (cr, cc + 1),
                            ])

                    if len(blob_pixels) >= self.min_blob_pixels:
                        detection = self._blob_to_detection(
                            frame, blob_pixels, classification
                        )
                        if detection:
                            detections.append(detection)

        return detections

    def _blob_to_detection(
        self,
        frame: np.ndarray,
        pixels: List[Tuple[int, int]],
        classification: str,
    ) -> Optional[ThermalDetection]:
        """Convert a blob of pixels to a ThermalDetection."""
        if not pixels:
            return None

        rows = [p[0] for p in pixels]
        cols = [p[1] for p in pixels]
        temps = [float(frame[r, c]) for r, c in pixels]

        self._detection_count += 1

        # Size-based confidence adjustment
        pixel_count = len(pixels)
        if classification == "HUMAN":
            expected_size = 50
        elif classification == "VEHICLE":
            expected_size = 200
        else:
            expected_size = 100

        size_ratio = min(pixel_count / expected_size, expected_size / max(pixel_count, 1))
        confidence = min(0.95, 0.5 + 0.3 * size_ratio + 0.2 * (np.mean(temps) / 50))

        return ThermalDetection(
            detection_id=f"TH-{self._detection_count:04d}",
            center_x=int(np.mean(cols)),
            center_y=int(np.mean(rows)),
            width=max(cols) - min(cols) + 1,
            height=max(rows) - min(rows) + 1,
            max_temp_c=max(temps),
            mean_temp_c=float(np.mean(temps)),
            classification=classification,
            confidence=confidence,
            pixel_count=pixel_count,
        )

    def get_detection_summary(self) -> Dict[str, Any]:
        """Get summary of all tracked detections."""
        return {
            "frame_count": self._frame_count,
            "total_detections": self._detection_count,
            "tracked_objects": len(self._tracked_objects),
        }


if __name__ == "__main__":
    processor = ThermalProcessor(resolution=(64, 64), min_blob_pixels=5)

    # Generate synthetic thermal frame with targets
    np.random.seed(42)
    frame = np.full((64, 64), 15.0, dtype=np.float32)  # Background ~15°C

    # Add human heat blob
    frame[20:25, 30:33] = 35.0  # Human signature
    # Add vehicle heat blob
    frame[40:48, 10:20] = 70.0  # Vehicle signature

    # Process two frames (first is background estimation)
    processor.process_frame(frame * 0.5)  # Initial background
    detections = processor.process_frame(frame)

    print(f"Detections: {len(detections)}")
    for d in detections:
        print(f"  {d.classification}: center=({d.center_x},{d.center_y}) "
              f"temp={d.mean_temp_c:.1f}°C conf={d.confidence:.2f}")

    print("thermal_processor.py OK")
