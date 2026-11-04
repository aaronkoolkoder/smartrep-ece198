"""Complementary pitch/roll estimation for the calibrated movement plane.

Gyros are smooth but drift; accelerometers give a gravity reference but are
noisy under motion. The filter integrates the gyro and gently pulls it toward
gravity. A six-axis IMU cannot determine absolute yaw. Pitch beyond 90 degrees
uses atan2(-ax, az) rather than the folded +/-90 degree Euler convention; the
participant's calibration selects the useful movement plane.
"""
import math
from .config import load_config
from .units import convert
from .filters import EMA


def wrap(angle):
    return (angle + 180) % 360 - 180


class Orientation:
    def __init__(self, config=None):
        self.config = config or load_config()
        self.settings = self.config["orientation"]
        self.reset()

    def reset(self):
        self.first_ms = self.last_ms = None
        self.pitch = self.roll = None
        self.bias = {k: 0.0 for k in ("gx", "gy", "gz")}
        self.bias_samples = 0
        self.ready = False

    def update(self, ms, values):
        if self.last_ms is not None and ms <= self.last_ms:
            raise ValueError("Sample timestamps must increase")
        if self.first_ms is None:
            self.first_ms = ms
        dt = 0 if self.last_ms is None else (ms - self.last_ms) / 1000
        self.last_ms = ms
        accel_pitch = math.degrees(math.atan2(-values["ax"], values["az"]))
        accel_roll = math.degrees(math.atan2(values["ay"], math.hypot(values["ax"], values["az"])))
        if (ms - self.first_ms) / 1000 < self.settings["gyro_bias_still_s"]:
            # The UI must ask the participant to hold still during this interval.
            self.bias_samples += 1
            for key in self.bias:
                self.bias[key] += (values[key] - self.bias[key]) / self.bias_samples
            self.pitch, self.roll = accel_pitch, accel_roll
        else:
            self.ready = True
            # Scale alpha by elapsed time so a short sample gap doesn't change
            # the filter's time constant. Long gaps restart the whole pipeline.
            alpha = self.settings["complementary_alpha"] ** (dt * self.config["signal"]["sample_hz"])
            predicted_pitch = self.pitch + (values["gy"] - self.bias["gy"]) * dt
            predicted_roll = self.roll + (values["gx"] - self.bias["gx"]) * dt
            # Gravity alone has two tilt solutions beyond 90 degrees. Choose
            # the one nearest the gyro prediction. This avoids turning a full
            # pitch curl into a fictitious 180-degree roll when az is negative.
            pitch_base=math.degrees(math.atan2(-values["ax"],math.hypot(values["ay"],values["az"])))
            roll_base=accel_roll
            def closest(base,predicted):
                return min((base,180-base,-180-base),key=lambda angle:abs(wrap(angle-predicted)))
            accel_pitch=closest(pitch_base,predicted_pitch)
            accel_roll=closest(roll_base,predicted_roll)
            self.pitch = predicted_pitch + (1 - alpha) * wrap(accel_pitch - predicted_pitch)
            self.roll = predicted_roll + (1 - alpha) * wrap(accel_roll - predicted_roll)
        return {"pitch": self.pitch, "roll": self.roll}


class SignalPipeline:
    def __init__(self, units, config=None):
        self.config = config or load_config()
        self.units = units
        self.reset()

    def reset(self):
        self.orientation = Orientation(self.config)
        self.filters = {}
        self.last_ms = None

    def update(self, sample):
        ms = int(sample["ms"])
        gap = self.last_ms is not None and ms - self.last_ms > self.config["signal"]["max_gap_ms"]
        if self.last_ms is not None and ms <= self.last_ms:
            raise ValueError("Sample timestamps must increase")
        if gap:
            self.reset()
        self.last_ms = ms
        values = convert(sample, self.units, self.config)
        ready = True
        if self.units.startswith("mpu6050"):
            angles = self.orientation.update(ms, values)
            # Gyro values are not calibration candidates; only angles and accel.
            values = {**{k: v for k, v in values.items() if k.startswith("a")}, **angles}
            ready = self.orientation.ready
        smooth = {k: self.filters.setdefault(k, EMA(self.config["signal"]["ema_alpha"])).update(v)
                  for k, v in values.items()}
        return {"ms": ms, "signals": smooth, "ready": ready, "gap": gap}
