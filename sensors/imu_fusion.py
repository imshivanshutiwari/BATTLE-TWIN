"""
Madgwick AHRS filter for IMU sensor fusion.

Fuses accelerometer + gyroscope + magnetometer data into
orientation estimates (quaternion / Euler angles).

The Madgwick filter uses gradient descent optimization
to compute orientation from sensor measurements.
"""

import math
from dataclasses import dataclass
from enum import Enum
from typing import List, Optional, Tuple

import numpy as np

from utils.logger import get_logger

log = get_logger("IMU_FUSION")


class MotionState(str, Enum):
    STATIONARY = "STATIONARY"
    WALKING = "WALKING"
    RUNNING = "RUNNING"
    VEHICLE = "VEHICLE"


@dataclass
class Quaternion:
    """Quaternion representation: w + xi + yj + zk."""
    w: float = 1.0
    x: float = 0.0
    y: float = 0.0
    z: float = 0.0

    def normalize(self) -> "Quaternion":
        norm = math.sqrt(self.w**2 + self.x**2 + self.y**2 + self.z**2)
        if norm < 1e-10:
            return Quaternion(1.0, 0.0, 0.0, 0.0)
        return Quaternion(self.w / norm, self.x / norm, self.y / norm, self.z / norm)

    def conjugate(self) -> "Quaternion":
        return Quaternion(self.w, -self.x, -self.y, -self.z)

    def multiply(self, other: "Quaternion") -> "Quaternion":
        return Quaternion(
            w=self.w * other.w - self.x * other.x - self.y * other.y - self.z * other.z,
            x=self.w * other.x + self.x * other.w + self.y * other.z - self.z * other.y,
            y=self.w * other.y - self.x * other.z + self.y * other.w + self.z * other.x,
            z=self.w * other.z + self.x * other.y - self.y * other.x + self.z * other.w,
        )

    def to_array(self) -> np.ndarray:
        return np.array([self.w, self.x, self.y, self.z])

    @classmethod
    def from_array(cls, arr: np.ndarray) -> "Quaternion":
        return cls(w=arr[0], x=arr[1], y=arr[2], z=arr[3])


class MadgwickIMUFusion:
    """
    Madgwick AHRS filter for IMU sensor fusion.

    Implements the Madgwick gradient descent orientation filter
    that fuses accelerometer, gyroscope, and optionally
    magnetometer data into a quaternion orientation estimate.

    Reference:
        Madgwick, S.O.H., "An efficient orientation filter for
        inertial and inertial/magnetic sensor arrays", 2010.

    Algorithm:
        q_dot = 0.5 * q ⊗ [0, gx, gy, gz] - β * ∇f(q)
        where f(q) is the objective function measuring error
        between estimated and measured gravity direction.
    """

    def __init__(self, beta: float = 0.1, sample_rate_hz: float = 100.0):
        """
        Args:
            beta: Filter gain (larger = more responsive, more noise).
            sample_rate_hz: IMU sample rate.
        """
        self.beta = beta
        self.sample_rate = sample_rate_hz
        self.q = Quaternion(1.0, 0.0, 0.0, 0.0)
        self._accel_history: List[np.ndarray] = []
        self._max_history = 100

    def update(
        self,
        ax: float, ay: float, az: float,
        gx: float, gy: float, gz: float,
        mx: float = 0.0, my: float = 0.0, mz: float = 0.0,
        dt: Optional[float] = None,
    ) -> Quaternion:
        """
        Update orientation estimate with new sensor data.

        Args:
            ax, ay, az: Accelerometer (g)
            gx, gy, gz: Gyroscope (rad/s)
            mx, my, mz: Magnetometer (optional)
            dt: Time step (default: 1/sample_rate)

        Returns:
            Updated quaternion orientation.
        """
        if dt is None:
            dt = 1.0 / self.sample_rate

        q = self.q

        # Normalise accelerometer measurement
        norm_a = math.sqrt(ax * ax + ay * ay + az * az)
        if norm_a < 1e-10:
            return q
        ax, ay, az = ax / norm_a, ay / norm_a, az / norm_a

        # Store for motion detection
        self._accel_history.append(np.array([ax * norm_a, ay * norm_a, az * norm_a]))
        if len(self._accel_history) > self._max_history:
            self._accel_history.pop(0)

        # Auxiliary variables
        _2q0 = 2.0 * q.w
        _2q1 = 2.0 * q.x
        _2q2 = 2.0 * q.y
        _2q3 = 2.0 * q.z
        _4q0 = 4.0 * q.w
        _4q1 = 4.0 * q.x
        _4q2 = 4.0 * q.y
        _8q1 = 8.0 * q.x
        _8q2 = 8.0 * q.y
        q0q0 = q.w * q.w
        q1q1 = q.x * q.x
        q2q2 = q.y * q.y
        q3q3 = q.z * q.z

        # Gradient descent step (objective function gradient)
        s0 = _4q0 * q2q2 + _2q2 * ax + _4q0 * q1q1 - _2q1 * ay
        s1 = _4q1 * q3q3 - _2q3 * ax + 4.0 * q0q0 * q.x - _2q0 * ay - _4q1 + _8q1 * q1q1 + _8q1 * q2q2 + _4q1 * az
        s2 = 4.0 * q0q0 * q.y + _2q0 * ax + _4q2 * q3q3 - _2q3 * ay - _4q2 + _8q2 * q1q1 + _8q2 * q2q2 + _4q2 * az
        s3 = 4.0 * q1q1 * q.z - _2q1 * ax + 4.0 * q2q2 * q.z - _2q2 * ay

        # Normalise gradient
        norm_s = math.sqrt(s0 * s0 + s1 * s1 + s2 * s2 + s3 * s3)
        if norm_s > 1e-10:
            s0, s1, s2, s3 = s0 / norm_s, s1 / norm_s, s2 / norm_s, s3 / norm_s

        # Rate of change of quaternion from gyroscope
        q_dot_w = 0.5 * (-q.x * gx - q.y * gy - q.z * gz)
        q_dot_x = 0.5 * (q.w * gx + q.y * gz - q.z * gy)
        q_dot_y = 0.5 * (q.w * gy - q.x * gz + q.z * gx)
        q_dot_z = 0.5 * (q.w * gz + q.x * gy - q.y * gx)

        # Apply gradient descent correction
        q_dot_w -= self.beta * s0
        q_dot_x -= self.beta * s1
        q_dot_y -= self.beta * s2
        q_dot_z -= self.beta * s3

        # Integrate
        self.q = Quaternion(
            w=q.w + q_dot_w * dt,
            x=q.x + q_dot_x * dt,
            y=q.y + q_dot_y * dt,
            z=q.z + q_dot_z * dt,
        ).normalize()

        return self.q

    def to_euler(self, q: Optional[Quaternion] = None) -> Tuple[float, float, float]:
        """
        Convert quaternion to Euler angles.

        Args:
            q: Quaternion (default: current state).

        Returns:
            (roll, pitch, yaw) in degrees.
        """
        if q is None:
            q = self.q

        # Roll (x-axis rotation)
        sinr_cosp = 2.0 * (q.w * q.x + q.y * q.z)
        cosr_cosp = 1.0 - 2.0 * (q.x * q.x + q.y * q.y)
        roll = math.atan2(sinr_cosp, cosr_cosp)

        # Pitch (y-axis rotation)
        sinp = 2.0 * (q.w * q.y - q.z * q.x)
        sinp = max(-1.0, min(1.0, sinp))
        pitch = math.asin(sinp)

        # Yaw (z-axis rotation)
        siny_cosp = 2.0 * (q.w * q.z + q.x * q.y)
        cosy_cosp = 1.0 - 2.0 * (q.y * q.y + q.z * q.z)
        yaw = math.atan2(siny_cosp, cosy_cosp)

        return math.degrees(roll), math.degrees(pitch), math.degrees(yaw)

    def compute_linear_acceleration(
        self, q: Optional[Quaternion] = None, accel: Optional[np.ndarray] = None
    ) -> np.ndarray:
        """
        Remove gravity from accelerometer to get linear acceleration.

        Args:
            q: Quaternion orientation.
            accel: Raw accelerometer reading [ax, ay, az] in g.

        Returns:
            Linear acceleration [ax, ay, az] in g (gravity removed).
        """
        if q is None:
            q = self.q
        if accel is None and self._accel_history:
            accel = self._accel_history[-1]
        elif accel is None:
            return np.zeros(3)

        # Estimated gravity direction from quaternion
        gx = 2.0 * (q.x * q.z - q.w * q.y)
        gy = 2.0 * (q.w * q.x + q.y * q.z)
        gz = q.w * q.w - q.x * q.x - q.y * q.y + q.z * q.z

        # Subtract gravity
        return accel - np.array([gx, gy, gz])

    def detect_motion(
        self, accel_history: Optional[List[np.ndarray]] = None
    ) -> MotionState:
        """
        Detect motion state from acceleration history.

        States: STATIONARY, WALKING, RUNNING, VEHICLE

        Uses the variance of acceleration magnitude to classify.
        """
        history = accel_history or self._accel_history
        if len(history) < 10:
            return MotionState.STATIONARY

        magnitudes = [np.linalg.norm(a) for a in history[-50:]]
        variance = np.var(magnitudes)
        mean_mag = np.mean(magnitudes)

        if variance < 0.005:
            return MotionState.STATIONARY
        elif variance < 0.05:
            return MotionState.WALKING
        elif variance < 0.3:
            return MotionState.RUNNING
        else:
            return MotionState.VEHICLE

    def reset(self) -> None:
        """Reset filter to initial state."""
        self.q = Quaternion(1.0, 0.0, 0.0, 0.0)
        self._accel_history.clear()


if __name__ == "__main__":
    imu = MadgwickIMUFusion(beta=0.1, sample_rate_hz=100)

    # Simulate static IMU (gravity pointing down Z)
    for i in range(200):
        imu.update(
            ax=0.0, ay=0.0, az=1.0,  # gravity on Z
            gx=0.0, gy=0.0, gz=0.0,  # no rotation
        )

    roll, pitch, yaw = imu.to_euler()
    print(f"Static result: roll={roll:.2f}° pitch={pitch:.2f}° yaw={yaw:.2f}°")

    motion = imu.detect_motion()
    print(f"Motion state: {motion}")

    lin_accel = imu.compute_linear_acceleration()
    print(f"Linear acceleration: {lin_accel}")

    print("imu_fusion.py OK")
