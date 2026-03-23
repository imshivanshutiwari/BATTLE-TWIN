"""
Extended Kalman Filter GPS position tracker.

State vector: [lat, lon, alt, vel_n, vel_e, vel_d]
Fuses GPS measurements with IMU-derived velocity for
improved position accuracy and GPS spoofing detection.
"""

import math
from dataclasses import dataclass
from typing import List, Optional, Tuple

import numpy as np

from utils.logger import get_logger

log = get_logger("GPS_KALMAN")


@dataclass
class GPSMeasurement:
    """Raw GPS measurement."""

    latitude: float
    longitude: float
    altitude: float
    speed_mps: float = 0.0
    heading_deg: float = 0.0
    hdop: float = 1.0
    timestamp: float = 0.0


@dataclass
class UnitPosition:
    """Fused position estimate."""

    latitude: float
    longitude: float
    altitude: float
    vel_north: float
    vel_east: float
    vel_down: float
    cep_m: float  # Circular Error Probable
    timestamp: float = 0.0

    @property
    def speed_mps(self) -> float:
        return math.sqrt(self.vel_north**2 + self.vel_east**2)

    @property
    def heading_deg(self) -> float:
        return math.degrees(math.atan2(self.vel_east, self.vel_north)) % 360


class GPSKalmanTracker:
    """
    EKF-based GPS position tracker.

    State: [lat, lon, alt, vel_n, vel_e, vel_d]
    Uses Extended Kalman Filter for non-linear GPS measurements.

    Features:
    - GPS position filtering
    - Velocity estimation from position changes
    - CEP (Circular Error Probable) computation
    - GPS spoofing detection
    - IMU data fusion for improved accuracy
    """

    def __init__(
        self,
        process_noise: float = 0.01,
        measurement_noise: float = 0.5,
        initial_uncertainty: float = 10.0,
    ):
        self.state_dim = 6  # [lat, lon, alt, vel_n, vel_e, vel_d]
        self.meas_dim = 3  # [lat, lon, alt]

        # State vector
        self.x = np.zeros(self.state_dim)

        # State covariance matrix
        self.P = np.eye(self.state_dim) * initial_uncertainty

        # Process noise
        self.Q = np.eye(self.state_dim) * process_noise
        self.Q[3:, 3:] *= 0.1  # Lower process noise for velocity

        # Measurement noise
        self.R = np.eye(self.meas_dim) * measurement_noise

        # Measurement matrix (observe position only)
        self.H = np.zeros((self.meas_dim, self.state_dim))
        self.H[0, 0] = 1.0  # lat
        self.H[1, 1] = 1.0  # lon
        self.H[2, 2] = 1.0  # alt

        self._initialized = False
        self._prev_timestamp = 0.0
        self._measurement_history: List[GPSMeasurement] = []
        self._max_history = 100

        # Spoofing detection
        self._spoofing_threshold_mps = 100.0  # max reasonable speed
        self._spoofing_threshold_alt = 15000.0  # max reasonable altitude

    def predict(self, dt: float) -> np.ndarray:
        """
        Predict state forward by dt seconds.

        Uses constant velocity model.

        Args:
            dt: Time step in seconds.

        Returns:
            Predicted state vector.
        """
        # State transition matrix (constant velocity model)
        F = np.eye(self.state_dim)
        # Convert velocity to lat/lon changes
        # Approximate: 1 degree lat ≈ 111320 m
        m_per_deg_lat = 111320.0
        m_per_deg_lon = (
            111320.0 * math.cos(math.radians(self.x[0])) if abs(self.x[0]) < 90 else 111320.0
        )

        F[0, 3] = dt / m_per_deg_lat  # lat += vel_n * dt / meters_per_deg
        F[1, 4] = dt / m_per_deg_lon  # lon += vel_e * dt / meters_per_deg
        F[2, 5] = dt  # alt += vel_d * dt

        # Predict state
        self.x = F @ self.x

        # Predict covariance
        self.P = F @ self.P @ F.T + self.Q * dt

        return self.x

    def update(self, gps: GPSMeasurement) -> np.ndarray:
        """
        Update state with GPS measurement.

        Args:
            gps: GPS measurement.

        Returns:
            Updated state vector.
        """
        if not self._initialized:
            self.x[0] = gps.latitude
            self.x[1] = gps.longitude
            self.x[2] = gps.altitude
            self._initialized = True
            self._prev_timestamp = gps.timestamp
            self._measurement_history.append(gps)
            return self.x

        # Time step
        dt = max(gps.timestamp - self._prev_timestamp, 0.001) if gps.timestamp > 0 else 1.0
        self._prev_timestamp = gps.timestamp

        # Predict
        self.predict(dt)

        # Measurement vector
        z = np.array([gps.latitude, gps.longitude, gps.altitude])

        # Adjust measurement noise by HDOP
        R_adj = self.R * (gps.hdop**2)

        # Innovation
        y = z - self.H @ self.x

        # Innovation covariance
        S = self.H @ self.P @ self.H.T + R_adj

        # Kalman gain
        try:
            K = self.P @ self.H.T @ np.linalg.inv(S)
        except np.linalg.LinAlgError:
            K = self.P @ self.H.T @ np.linalg.pinv(S)

        # Update state
        self.x = self.x + K @ y

        # Update covariance (Joseph form for numerical stability)
        I_KH = np.eye(self.state_dim) - K @ self.H
        self.P = I_KH @ self.P @ I_KH.T + K @ R_adj @ K.T

        # Store history
        self._measurement_history.append(gps)
        if len(self._measurement_history) > self._max_history:
            self._measurement_history.pop(0)

        return self.x

    def estimate_accuracy(self) -> float:
        """
        Estimate position accuracy as CEP (Circular Error Probable) in meters.

        CEP is the radius of a circle centered on the true position
        that contains 50% of position estimates.
        """
        # CEP approximation from covariance
        pos_cov = self.P[:2, :2]
        # Convert from degrees to meters
        m_per_deg = 111320.0
        pos_cov_m = pos_cov * (m_per_deg**2)

        eigenvalues = np.linalg.eigvalsh(pos_cov_m)
        eigenvalues = np.maximum(eigenvalues, 0)

        sigma_x = math.sqrt(eigenvalues[0])
        sigma_y = math.sqrt(eigenvalues[1])

        # CEP approximation (for bivariate normal)
        cep = 0.5887 * (sigma_x + sigma_y)
        return cep

    def detect_spoofing(
        self,
        measurements: Optional[List[GPSMeasurement]] = None,
    ) -> bool:
        """
        Detect potential GPS spoofing.

        Checks:
        1. Sudden position jumps (impossible velocity)
        2. Altitude anomalies
        3. Temporal consistency

        Args:
            measurements: GPS measurements to check.

        Returns:
            True if spoofing is suspected.
        """
        measurements = measurements or self._measurement_history

        if len(measurements) < 2:
            return False

        for i in range(1, len(measurements)):
            curr = measurements[i]
            prev = measurements[i - 1]

            # Check velocity plausibility
            dt = max(curr.timestamp - prev.timestamp, 0.001) if curr.timestamp > 0 else 1.0
            dlat = (curr.latitude - prev.latitude) * 111320
            dlon = (
                (curr.longitude - prev.longitude) * 111320 * math.cos(math.radians(curr.latitude))
            )
            dist = math.sqrt(dlat**2 + dlon**2)
            speed = dist / dt

            if speed > self._spoofing_threshold_mps:
                log.warning(
                    f"GPS spoofing suspected: speed={speed:.0f} m/s > "
                    f"{self._spoofing_threshold_mps} m/s"
                )
                return True

            # Check altitude plausibility
            if abs(curr.altitude) > self._spoofing_threshold_alt:
                log.warning(f"GPS spoofing suspected: altitude={curr.altitude:.0f}m")
                return True

        return False

    def fuse_with_imu(
        self,
        imu_vel: Tuple[float, float, float],
        imu_weight: float = 0.3,
    ) -> "UnitPosition":
        """
        Fuse current GPS estimate with IMU velocity data.

        Args:
            imu_vel: IMU-derived velocity (north, east, down) m/s.
            imu_weight: Weight for IMU velocity (0-1).

        Returns:
            Fused UnitPosition.
        """
        gps_weight = 1.0 - imu_weight

        # Weighted velocity fusion
        fused_vn = gps_weight * self.x[3] + imu_weight * imu_vel[0]
        fused_ve = gps_weight * self.x[4] + imu_weight * imu_vel[1]
        fused_vd = gps_weight * self.x[5] + imu_weight * imu_vel[2]

        return UnitPosition(
            latitude=self.x[0],
            longitude=self.x[1],
            altitude=self.x[2],
            vel_north=fused_vn,
            vel_east=fused_ve,
            vel_down=fused_vd,
            cep_m=self.estimate_accuracy(),
            timestamp=self._prev_timestamp,
        )

    def get_position(self) -> UnitPosition:
        """Get current position estimate."""
        return UnitPosition(
            latitude=self.x[0],
            longitude=self.x[1],
            altitude=self.x[2],
            vel_north=self.x[3],
            vel_east=self.x[4],
            vel_down=self.x[5],
            cep_m=self.estimate_accuracy(),
            timestamp=self._prev_timestamp,
        )

    def reset(self) -> None:
        """Reset filter state."""
        self.x = np.zeros(self.state_dim)
        self.P = np.eye(self.state_dim) * 10.0
        self._initialized = False
        self._measurement_history.clear()


if __name__ == "__main__":
    tracker = GPSKalmanTracker(process_noise=0.01, measurement_noise=0.5)

    # Simulate noisy GPS measurements along a path
    np.random.seed(42)
    true_lat, true_lon = 34.25, -117.25

    for i in range(50):
        noisy_lat = true_lat + 0.001 * i + np.random.normal(0, 0.0001)
        noisy_lon = true_lon + 0.0005 * i + np.random.normal(0, 0.0001)
        noisy_alt = 900 + np.random.normal(0, 5)

        meas = GPSMeasurement(
            latitude=noisy_lat,
            longitude=noisy_lon,
            altitude=noisy_alt,
            hdop=1.2,
            timestamp=float(i),
        )
        tracker.update(meas)

    pos = tracker.get_position()
    print(f"Position: ({pos.latitude:.5f}, {pos.longitude:.5f})")
    print(f"Speed: {pos.speed_mps:.1f} m/s, Heading: {pos.heading_deg:.0f}°")
    print(f"CEP: {pos.cep_m:.1f} m")
    print(f"Spoofing detected: {tracker.detect_spoofing()}")

    print("gps_kalman.py OK")
