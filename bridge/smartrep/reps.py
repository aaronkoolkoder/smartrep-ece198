"""Pure rep detection and calibration. Run `python -m smartrep.reps replay ...`."""
from dataclasses import asdict, dataclass
import math
from statistics import median, pvariance
from .config import load_config


@dataclass(frozen=True)
class Reference:
    signal: str
    units: str
    ref_low: float
    ref_high: float
    ref_duration_s: float
    direction: int = 1

    def __post_init__(self):
        if self.direction not in (-1, 1) or self.ref_high <= self.ref_low:
            raise ValueError("Reference needs a positive range and direction +1 or -1")
        if not all(math.isfinite(v) for v in (self.ref_low, self.ref_high, self.ref_duration_s)):
            raise ValueError("Reference values must be finite")

    @property
    def ref_range(self):
        return self.ref_high - self.ref_low

    def normalize(self, value):
        p = (value - self.ref_low) / self.ref_range
        return p if self.direction == 1 else 1 - p


class RepDetector:
    def __init__(self, reference, config=None):
        self.reference = reference
        self.config = config or load_config()
        self.settings = self.config["reps"]
        self.last_ms = self.last_completion = None
        self.attempts = self.completed = 0
        self.reset_motion()

    def reset_motion(self):
        # Must see the bottom first, including after a disconnect or long gap.
        self.armed = False
        self.start_ms = self.departure_ms = None
        self.peak = 0
        self.crossed_top = False
        self.top_since = None

    def update(self, ms, value):
        if not math.isfinite(value):
            raise ValueError("Signal must be finite")
        if self.last_ms is not None:
            if ms <= self.last_ms:
                raise ValueError("Sample timestamps must increase")
            if ms - self.last_ms > self.config["signal"]["max_gap_ms"]:
                self.reset_motion()
        self.last_ms = ms
        p = self.reference.normalize(value)
        bottom = self.settings["bottom_line"]
        if not self.armed:
            if p <= bottom:
                self.armed = True
            return None
        if self.departure_ms is None and p > bottom:
            self.departure_ms = ms
        if self.start_ms is None and p >= self.settings["attempt_line"]:
            self.start_ms = self.departure_ms or ms
            self.peak = p
        if self.start_ms is None:
            if p <= bottom:
                self.departure_ms = None
            return None
        self.peak = max(self.peak, p)
        if p>=self.settings["top_line"]:
            if self.top_since is None:
                self.top_since=ms
            if ms-self.top_since>=self.settings.get("top_hold_ms",100):
                self.crossed_top=True
        else:
            self.top_since=None
        if p > bottom:
            return None
        start, peak, full = self.start_ms, self.peak, self.crossed_top
        self.start_ms = self.departure_ms = None
        self.peak = 0
        self.crossed_top = False
        self.top_since = None
        duration = (ms-start)/1000
        if duration<self.settings.get("min_motion_s",.35):
            return None
        # Debounce between completed attempts, not by time spent above the top.
        if self.last_completion is not None and (ms - self.last_completion) / 1000 < self.settings["min_rep_s"]:
            return None
        self.last_completion = ms
        duration = (ms - start) / 1000
        if not full or peak < self.settings["good_min_peak"]:
            quality = "short"
        elif duration < self.settings["rushed_max_s"]:
            quality = "rushed"
        elif duration > self.settings["slow_min_s"]:
            quality = "slow"
        else:
            quality = "good"
        self.attempts += 1
        if quality != "short":
            self.completed += 1
        return {"index": self.attempts, "quality": quality, "peak_p": peak,
                "duration_s": duration, "t_start_ms": start, "t_end_ms": ms,
                "rom": peak * self.reference.ref_range, "rom_units": self.reference.units,
                "count": self.completed, "attempts": self.attempts}


class CalibrationError(ValueError):
    pass


class Calibrator:
    def __init__(self, config=None):
        self.config = config or load_config()
        self.samples = []

    def add(self, ms, signals):
        if self.samples and ms <= self.samples[-1][0]:
            raise CalibrationError("Sample timestamps must increase")
        if self.samples and ms - self.samples[-1][0] > self.config["signal"]["max_gap_ms"]:
            raise CalibrationError("Sensor gap during calibration; check the cable and try again.")
        if self.samples and signals.keys() != self.samples[0][1].keys():
            raise CalibrationError("Sensor channels changed during calibration")
        if not signals or not all(math.isfinite(v) for v in signals.values()):
            raise CalibrationError("Calibration contains invalid sensor values")
        if self.samples and (ms - self.samples[0][0]) / 1000 > self.config["calibration"]["max_seconds"]:
            raise CalibrationError("Calibration timed out; please do 3 slow, full reps.")
        self.samples.append((ms, signals))

    def progress(self):
        """Use the same channel selection and complete-cycle checks as saving."""
        settings = self.config["calibration"]
        required = settings["reps_required"]
        candidates = []
        if len(self.samples) < 3:
            return {"count":0,"reference":None,"reason":"Hold still, then do three full reps."}
        for key in self.samples[0][1]:
            values = [signals[key] for _, signals in self.samples]
            low, high = min(values), max(values)
            span = high-low
            angle = key in ("pitch", "roll")
            floor = settings["min_ref_range_deg" if angle else "min_ref_range_g"]
            if span < floor:
                continue
            initial = values[0]
            direction = next((1 if value>initial else -1 for value in values[1:]
                              if abs(value-initial)>=settings["min_prominence_frac"]*span),1)
            normalized = [(v-low)/span if direction==1 else (high-v)/span for v in values]
            # A peak is complete only after returning to the bottom, not just
            # after the signal falls partway from its maximum.
            peaks, valleys, peak_times = [], [], []
            bottom = self.config["reps"]["bottom_line"]
            valley = normalized[0]
            peak, peak_time = valley, self.samples[0][0]
            rising = False
            too_fast = False
            for (ms,_),value in zip(self.samples,normalized):
                if not rising:
                    valley = min(valley,value)
                    if value-valley>=settings["min_prominence_frac"]:
                        peak,peak_time,rising = value,ms,True
                else:
                    if value>peak:
                        peak,peak_time = value,ms
                    if peak-value>=settings["min_prominence_frac"] and value<=bottom:
                        if peak_times and (peak_time-peak_times[-1])/1000<settings["min_cycle_s"]:
                            too_fast = True
                        peaks.append(peak)
                        valleys.append(valley)
                        peak_times.append(peak_time)
                        valley,rising = value,False
            count = len(peaks)
            reason = None
            if too_fast:
                reason = "Reps were too close together; please move slowly."
            elif count != required:
                reason = f"Detected {count} rep{'s' if count!=1 else ''}; please do {required} slow, full reps."
            elif rising or normalized[-1]>bottom:
                reason = "Finish the last rep at the starting position and try again."
            elif normalized[0]>bottom:
                reason = "Start at the resting position and return there after each rep."
            reference = None
            if reason is None:
                duration = median((b-a)/1000 for a,b in zip(peak_times,peak_times[1:]))
                ref_bottom = low+median(valleys+[valley])*span if direction==1 else high-median(valleys+[valley])*span
                ref_top = low+median(peaks)*span if direction==1 else high-median(peaks)*span
                reference = Reference(key,"deg" if angle else "g",min(ref_bottom,ref_top),
                                      max(ref_bottom,ref_top),duration,direction)
            noise = settings["angle_noise_deg" if angle else "accel_noise_g"]
            rank = (count<=required, min(count+int(rising),required),
                    angle and span>=settings["prefer_angle_min_deg"], reference is not None, count,
                    pvariance(values)/noise**2)
            candidates.append((rank,{"count":count,"signal":key,"reference":reference,"reason":reason}))
        if not candidates:
            return {"count":0,"reference":None,"reason":"Movement range too small; check the sensor and try 3 full reps."}
        return max(candidates,key=lambda candidate:candidate[0])[1]

    def finish(self):
        if len(self.samples)<3:
            raise CalibrationError("Not enough samples; please do 3 slow, full reps.")
        result = self.progress()
        if result["reference"] is None:
            raise CalibrationError(result["reason"])
        return result["reference"]


def replay(path, reference_path, units="mpu6050_4g_500dps", config=None):
    import csv
    from .orientation import SignalPipeline
    config = config or load_config()

    def rows(filename):
        pipeline = SignalPipeline(units, config)
        with open(filename, newline="") as stream:
            for raw in csv.DictReader(stream):
                sample = pipeline.update(raw)
                if sample["ready"]:
                    yield sample

    calibration = Calibrator(config)
    for sample in rows(reference_path):
        if sample["gap"]:
            raise CalibrationError("Calibration contains a long sensor gap; record it again.")
        calibration.add(sample["ms"], sample["signals"])
    reference = calibration.finish()
    detector = RepDetector(reference, config)
    events = []
    for sample in rows(path):
        if sample["gap"]:
            detector.reset_motion()
        event = detector.update(sample["ms"], sample["signals"][reference.signal])
        if event:
            events.append(event)
    return reference, events


def main():
    import argparse
    import json
    parser = argparse.ArgumentParser(description="Replay raw sensor CSVs through calibration and rep detection")
    sub = parser.add_subparsers(dest="command", required=True)
    command = sub.add_parser("replay")
    command.add_argument("csv")
    command.add_argument("--ref", required=True)
    command.add_argument("--units", default="mpu6050_4g_500dps", choices=["mpu6050_4g_500dps", "counts14", "counts10"])
    command.add_argument("--config")
    args = parser.parse_args()
    try:
        reference, events = replay(args.csv, args.ref, args.units, load_config(args.config))
    except (ValueError, KeyError, OSError) as error:
        parser.exit(1, f"Replay failed: {error}\n")
    print("Reference:", json.dumps(asdict(reference)))
    for event in events:
        print(json.dumps(event))
    print(f"Completed: {sum(e['quality'] != 'short' for e in events)}; attempts: {len(events)}")


if __name__ == "__main__":
    main()
