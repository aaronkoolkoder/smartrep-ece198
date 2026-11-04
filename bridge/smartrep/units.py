"""Raw sensor values to g and degrees/second; no device I/O here."""
import math
from .config import load_config


def convert(sample, units, config=None):
    settings = (config or load_config())["units"]
    if units not in settings:
        raise ValueError(f"Unsupported sensor units: {units}")
    scale = settings[units]
    keys = ("ax", "ay", "az", "gx", "gy", "gz") if units.startswith("mpu6050") else ("x", "y", "z")
    values = {key: float(sample[key]) for key in keys}
    if not all(math.isfinite(v) for v in values.values()):
        raise ValueError("Sensor values must be finite")
    if units.startswith("mpu6050"):
        return {k: v / scale["accel_per_g" if k.startswith("a") else "gyro_per_dps"] for k, v in values.items()}
    return {k: (v - scale["zero"]) / scale["per_g"] for k, v in values.items()}
