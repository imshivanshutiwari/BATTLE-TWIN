"""
Multi-sensor data fusion aggregator.
Combines IMU, GPS, thermal, and acoustic sensor data into unified position/state.
"""

from dataclasses import dataclass
from typing import Dict, List, Optional
import numpy as np
from sensors.imu_fusion import MadgwickIMUFusion
from sensors.gps_kalman import GPSKalmanTracker, GPSMeasurement, UnitPosition
from sensors.thermal_processor import ThermalProcessor
from sensors.acoustic_detector import AcousticDetector
from utils.logger import get_logger

log = get_logger("SENSOR_AGG")


@dataclass
class FusedSensorState:
    position: Optional[UnitPosition] = None
    motion_state: str = "STATIONARY"
    orientation_euler: tuple = (0.0, 0.0, 0.0)
    thermal_detections: List[Dict] = None
    acoustic_events: List[Dict] = None
    agreement_score: float = 1.0
    timestamp: float = 0.0

    def __post_init__(self):
        if self.thermal_detections is None:
            self.thermal_detections = []
        if self.acoustic_events is None:
            self.acoustic_events = []

    def to_dict(self):
        return {
            "position": {
                "lat": self.position.latitude if self.position else 0,
                "lon": self.position.longitude if self.position else 0,
                "alt": self.position.altitude if self.position else 0,
                "cep_m": self.position.cep_m if self.position else 0,
                "speed": self.position.speed_mps if self.position else 0,
                "heading": self.position.heading_deg if self.position else 0,
            },
            "motion_state": self.motion_state,
            "orientation": self.orientation_euler,
            "thermal_detections": self.thermal_detections,
            "acoustic_events": self.acoustic_events,
            "agreement_score": self.agreement_score,
        }


class SensorAggregator:
    """Multi-sensor fusion: IMU + GPS + thermal + acoustic."""

    def __init__(self, weights=None):
        self.imu = MadgwickIMUFusion(beta=0.1)
        self.gps = GPSKalmanTracker()
        self.thermal = ThermalProcessor()
        self.acoustic = AcousticDetector()
        self.weights = weights or {"imu": 0.20, "gps": 0.40, "thermal": 0.25, "acoustic": 0.15}
        self._latest_state = FusedSensorState()

    def update_imu(self, ax, ay, az, gx, gy, gz, dt=None):
        _ = self.imu.update(ax, ay, az, gx, gy, gz, dt=dt)
        euler = self.imu.to_euler()
        motion = self.imu.detect_motion()
        self._latest_state.orientation_euler = euler
        self._latest_state.motion_state = motion.value
        return euler, motion

    def update_gps(self, lat, lon, alt, hdop=1.0, ts=0.0):
        meas = GPSMeasurement(lat, lon, alt, hdop=hdop, timestamp=ts)
        self.gps.update(meas)
        imu_vel = (0.0, 0.0, 0.0)
        pos = self.gps.fuse_with_imu(imu_vel, imu_weight=self.weights["imu"])
        self._latest_state.position = pos
        return pos

    def update_thermal(self, frame):
        dets = self.thermal.process_frame(frame)
        self._latest_state.thermal_detections = [d.to_dict() for d in dets]
        return dets

    def update_acoustic(self, buffer):
        events = self.acoustic.process_buffer(buffer)
        self._latest_state.acoustic_events = [e.to_dict() for e in events]
        return events

    def compute_agreement(self):
        scores = []
        if self._latest_state.position and self._latest_state.position.cep_m < 10:
            scores.append(1.0)
        elif self._latest_state.position:
            scores.append(max(0, 1.0 - self._latest_state.position.cep_m / 100))
        motion = self._latest_state.motion_state
        if self._latest_state.position:
            spd = self._latest_state.position.speed_mps
            if (motion == "STATIONARY" and spd < 0.5) or (motion != "STATIONARY" and spd > 0.5):
                scores.append(1.0)
            else:
                scores.append(0.5)
        self._latest_state.agreement_score = float(np.mean(scores)) if scores else 1.0
        return self._latest_state.agreement_score

    def get_fused_state(self):
        self.compute_agreement()
        return self._latest_state

    def get_summary(self):
        return {
            "gps_cep": self._latest_state.position.cep_m if self._latest_state.position else None,
            "motion": self._latest_state.motion_state,
            "agreement": self._latest_state.agreement_score,
            "thermal_count": len(self._latest_state.thermal_detections),
            "acoustic_count": len(self._latest_state.acoustic_events),
        }


if __name__ == "__main__":
    agg = SensorAggregator()
    for i in range(20):
        agg.update_imu(0, 0, 1, 0, 0, 0)
    agg.update_gps(34.25, -117.25, 900)
    state = agg.get_fused_state()
    print(f"Position: ({state.position.latitude:.4f}, {state.position.longitude:.4f})")
    print(f"Motion: {state.motion_state}, Agreement: {state.agreement_score:.2f}")
    print("sensor_aggregator.py OK")
