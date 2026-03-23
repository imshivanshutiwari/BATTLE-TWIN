"""Tests for sensor modules: IMU, GPS Kalman, thermal, acoustic."""
import numpy as np
from sensors.imu_fusion import MadgwickIMUFusion, Quaternion, MotionState
from sensors.gps_kalman import GPSKalmanTracker, GPSMeasurement
from sensors.thermal_processor import ThermalProcessor
from sensors.acoustic_detector import AcousticDetector


def test_imu_static():
    imu = MadgwickIMUFusion(beta=0.1)
    for _ in range(100):
        imu.update(0, 0, 1, 0, 0, 0)
    roll, pitch, yaw = imu.to_euler()
    assert abs(roll) < 5
    assert abs(pitch) < 5


def test_imu_motion_detection():
    imu = MadgwickIMUFusion()
    for _ in range(50):
        imu.update(0, 0, 1, 0, 0, 0)
    assert imu.detect_motion() == MotionState.STATIONARY


def test_quaternion_normalize():
    q = Quaternion(2, 0, 0, 0)
    qn = q.normalize()
    assert abs(qn.w - 1.0) < 1e-6


def test_gps_kalman_init():
    tracker = GPSKalmanTracker()
    meas = GPSMeasurement(latitude=34.0, longitude=-117.0, altitude=900, timestamp=0.0)
    tracker.update(meas)
    pos = tracker.get_position()
    assert abs(pos.latitude - 34.0) < 0.01


def test_gps_kalman_convergence():
    tracker = GPSKalmanTracker()
    np.random.seed(42)
    for i in range(20):
        meas = GPSMeasurement(latitude=34.0 + np.random.normal(0, 0.0001),
                              longitude=-117.0 + np.random.normal(0, 0.0001),
                              altitude=900, timestamp=float(i))
        tracker.update(meas)
    pos = tracker.get_position()
    assert abs(pos.latitude - 34.0) < 0.001


def test_gps_spoofing_detection():
    tracker = GPSKalmanTracker()
    m1 = GPSMeasurement(34.0, -117.0, 900, timestamp=0.0)
    m2 = GPSMeasurement(35.0, -117.0, 900, timestamp=1.0)  # 111km in 1s = impossible
    tracker.update(m1)
    tracker.update(m2)
    assert tracker.detect_spoofing()


def test_thermal_init():
    proc = ThermalProcessor(resolution=(64, 64), min_blob_pixels=5)
    assert proc is not None


def test_acoustic_init():
    det = AcousticDetector(sample_rate=44100)
    assert det is not None


def test_acoustic_detection():
    det = AcousticDetector(sample_rate=44100)
    np.random.seed(42)
    bg = np.random.normal(0, 0.005, (4, 4096))
    det.process_buffer(bg)  # background
    gunshot = np.zeros(4096)
    t = np.linspace(0, 4096/44100, 4096)
    gunshot[100:200] = np.sin(2*np.pi*3000*t[100:200]) * 0.8
    gunshot += np.random.normal(0, 0.005, 4096)
    signal = np.stack([gunshot]*4)
    events = det.process_buffer(signal)
    assert len(events) >= 1
