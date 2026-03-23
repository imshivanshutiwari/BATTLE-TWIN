"""
Acoustic event detector for battlefield sounds.
Detects gunshots, explosions, and vehicles via FFT + TDOA.
"""
import math
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple
import numpy as np
from utils.logger import get_logger

log = get_logger("ACOUSTIC")


@dataclass
class AcousticEvent:
    event_id: str
    event_type: str
    timestamp: float
    confidence: float
    estimated_range_m: float
    estimated_bearing_deg: float
    snr_db: float
    peak_frequency_hz: float
    duration_s: float

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.event_id, "type": self.event_type,
            "confidence": self.confidence, "range_m": self.estimated_range_m,
            "bearing_deg": self.estimated_bearing_deg, "snr_db": self.snr_db,
            "peak_freq_hz": self.peak_frequency_hz, "duration_s": self.duration_s,
        }


class AcousticDetector:
    def __init__(self, sample_rate=44100, buffer_size=4096, n_channels=4,
                 array_spacing_m=0.5, snr_threshold_db=10.0, energy_threshold=0.001,
                 speed_of_sound_mps=343.0):
        self.sample_rate = sample_rate
        self.buffer_size = buffer_size
        self.n_channels = n_channels
        self.array_spacing_m = array_spacing_m
        self.snr_threshold_db = snr_threshold_db
        self.energy_threshold = energy_threshold
        self.speed_of_sound = speed_of_sound_mps
        self.gunshot_range = (500, 8000)
        self.explosion_range = (20, 500)
        self.vehicle_range = (30, 2000)
        self._event_count = 0
        self._background_power: Optional[float] = None
        self._events: List[AcousticEvent] = []

    def process_buffer(self, audio_buffer: np.ndarray) -> List[AcousticEvent]:
        if audio_buffer.ndim == 1:
            audio_buffer = audio_buffer.reshape(1, -1)
        signal = audio_buffer[0]
        energy = float(np.mean(signal ** 2))
        if self._background_power is None:
            self._background_power = energy
            return []
        self._background_power = 0.95 * self._background_power + 0.05 * energy
        if energy < self.energy_threshold:
            return []
        snr = 10 * math.log10(max(energy / max(self._background_power, 1e-10), 1e-10))
        if snr < self.snr_threshold_db:
            return []
        fft_result = np.abs(np.fft.rfft(signal))
        freqs = np.fft.rfftfreq(len(signal), 1.0 / self.sample_rate)
        peak_idx = int(np.argmax(fft_result[1:])) + 1
        peak_freq = float(freqs[peak_idx])
        event_type, confidence = self._classify(fft_result, freqs)
        bearing = self._estimate_bearing(audio_buffer) if audio_buffer.shape[0] >= 2 else 0.0
        range_m = self._estimate_range(snr, event_type)
        above = signal ** 2 > self.energy_threshold
        duration_s = float(np.sum(above)) / self.sample_rate
        self._event_count += 1
        event = AcousticEvent(
            event_id=f"AC-{self._event_count:04d}", event_type=event_type,
            timestamp=0.0, confidence=confidence, estimated_range_m=range_m,
            estimated_bearing_deg=bearing, snr_db=snr,
            peak_frequency_hz=peak_freq, duration_s=duration_s,
        )
        self._events.append(event)
        return [event]

    def _classify(self, fft_mag, freqs):
        total_power = float(np.sum(fft_mag ** 2))
        if total_power < 1e-10:
            return "UNKNOWN", 0.0
        gm = (freqs >= self.gunshot_range[0]) & (freqs <= self.gunshot_range[1])
        em = (freqs >= self.explosion_range[0]) & (freqs <= self.explosion_range[1])
        vm = (freqs >= self.vehicle_range[0]) & (freqs <= self.vehicle_range[1])
        scores = {
            "GUNSHOT": float(np.sum(fft_mag[gm] ** 2)) / total_power,
            "EXPLOSION": float(np.sum(fft_mag[em] ** 2)) / total_power,
            "VEHICLE": float(np.sum(fft_mag[vm] ** 2)) / total_power,
        }
        best = max(scores, key=scores.get)
        return best, min(0.95, scores[best])

    def _estimate_bearing(self, multichannel):
        if multichannel.shape[0] < 2:
            return 0.0
        corr = np.correlate(multichannel[0], multichannel[1], mode="full")
        lag = int(np.argmax(corr)) - (len(multichannel[0]) - 1)
        td = lag / self.sample_rate
        md = self.array_spacing_m / self.speed_of_sound
        if abs(md) < 1e-10:
            return 0.0
        return float((math.degrees(math.asin(np.clip(td / md, -1, 1))) + 360) % 360)

    def _estimate_range(self, snr_db, event_type):
        ref = {"GUNSHOT": 160, "EXPLOSION": 170, "VEHICLE": 80, "UNKNOWN": 100}
        return max(10.0, min(10 ** ((ref.get(event_type, 100) - 60 - snr_db) / 20), 5000.0))

    def get_events(self, last_n=20):
        return self._events[-last_n:]


if __name__ == "__main__":
    detector = AcousticDetector(sample_rate=44100, buffer_size=4096)
    np.random.seed(42)
    t = np.linspace(0, 4096 / 44100, 4096)
    gunshot = np.zeros(4096)
    gunshot[100:200] = np.sin(2 * np.pi * 3000 * t[100:200]) * 0.8
    gunshot += np.random.normal(0, 0.005, 4096)
    bg = np.random.normal(0, 0.005, (4, 4096))
    detector.process_buffer(bg)
    signal = np.stack([gunshot] + [gunshot * 0.9] * 3)
    events = detector.process_buffer(signal)
    print(f"Detected events: {len(events)}")
    for e in events:
        print(f"  {e.event_type}: SNR={e.snr_db:.1f}dB range={e.estimated_range_m:.0f}m")
    print("acoustic_detector.py OK")
