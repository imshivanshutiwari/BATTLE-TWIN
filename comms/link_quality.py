"""Radio link quality modeling for MANET simulation."""

import math
from utils.logger import get_logger

log = get_logger("LINK_QUAL")


class LinkQualityModel:
    """Models RF propagation and link quality between nodes."""

    def __init__(
        self,
        freq_mhz: float = 225.0,
        tx_power_dbm: float = 37.0,
        rx_sensitivity_dbm: float = -100.0,
    ):
        self.freq_mhz = freq_mhz
        self.tx_power_dbm = tx_power_dbm
        self.rx_sensitivity_dbm = rx_sensitivity_dbm

    def free_space_loss_db(self, distance_m: float) -> float:
        """Friis free-space path loss."""
        if distance_m <= 0:
            return 0.0
        return 20 * math.log10(distance_m) + 20 * math.log10(self.freq_mhz) - 27.55

    def two_ray_ground_loss_db(
        self, distance_m: float, ht_m: float = 2.0, hr_m: float = 2.0
    ) -> float:
        """Two-ray ground reflection model."""
        if distance_m <= 0:
            return 0.0
        crossover = (4 * math.pi * ht_m * hr_m) / (3e8 / (self.freq_mhz * 1e6))
        if distance_m < crossover:
            return self.free_space_loss_db(distance_m)
        return 40 * math.log10(distance_m) - 20 * math.log10(ht_m) - 20 * math.log10(hr_m)

    def terrain_attenuation_db(self, terrain_type: str) -> float:
        atten = {"OPEN": 0, "SCRUB": 3, "FOREST": 12, "URBAN": 18, "DENSE_URBAN": 25, "WATER": -2}
        return atten.get(terrain_type, 5)

    def atmospheric_loss_db(self, distance_km: float, rain_rate_mmh: float = 0) -> float:
        base = 0.01 * distance_km  # oxygen absorption
        rain = 0.0
        if rain_rate_mmh > 0 and self.freq_mhz > 1000:
            rain = 0.01 * rain_rate_mmh * distance_km
        return base + rain

    def compute_rssi(self, distance_m: float, terrain: str = "OPEN", rain_rate: float = 0) -> float:
        """Compute received signal strength indicator."""
        path_loss = self.two_ray_ground_loss_db(distance_m)
        terrain_loss = self.terrain_attenuation_db(terrain)
        atm_loss = self.atmospheric_loss_db(distance_m / 1000, rain_rate)
        return self.tx_power_dbm - path_loss - terrain_loss - atm_loss

    def compute_link_quality(self, distance_m: float, terrain: str = "OPEN") -> float:
        """Return 0-1 link quality score."""
        rssi = self.compute_rssi(distance_m, terrain)
        if rssi < self.rx_sensitivity_dbm:
            return 0.0
        margin = rssi - self.rx_sensitivity_dbm
        return min(1.0, margin / 40.0)

    def compute_ber(self, snr_db: float) -> float:
        """Bit error rate from SNR (QPSK approximation)."""
        snr_lin = 10 ** (snr_db / 10)
        return 0.5 * math.erfc(math.sqrt(snr_lin))

    def compute_throughput_kbps(self, link_quality: float, max_rate_kbps: float = 2400) -> float:
        """Estimate effective throughput."""
        return max_rate_kbps * link_quality * (1 - (1 - link_quality) ** 8)

    def get_max_range_m(self, terrain: str = "OPEN") -> float:
        """Estimate maximum comms range."""
        for r in range(100, 50000, 100):
            if self.compute_link_quality(r, terrain) <= 0:
                return float(r - 100)
        return 50000.0


if __name__ == "__main__":
    model = LinkQualityModel()
    for d in [1000, 3000, 5000, 8000, 10000]:
        q = model.compute_link_quality(d)
        rssi = model.compute_rssi(d)
        tp = model.compute_throughput_kbps(q)
        print(f"{d/1000:.0f}km: quality={q:.2f} RSSI={rssi:.0f}dBm throughput={tp:.0f}kbps")
    print(f"Max range (OPEN): {model.get_max_range_m('OPEN')/1000:.1f}km")
    print(f"Max range (FOREST): {model.get_max_range_m('FOREST')/1000:.1f}km")
    print("link_quality.py OK")
