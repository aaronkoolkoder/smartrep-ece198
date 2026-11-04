"""Gravity and angular velocity for a consistent synthetic dumbbell curl."""
import asyncio
import math
import random
from .base import SampleCallback


def sample_at(seconds, rng, period=2.5, amplitude=110):
    phase = 2 * math.pi * seconds / period
    angle = math.radians(amplitude * (1 - math.cos(phase)) / 2)
    velocity = amplitude * math.pi / period * math.sin(phase)
    # Pitch = atan2(-ax, az) for this single-plane curl; gyro Y is its derivative.
    return {"t": "s", "ms": round(seconds * 1000),
            "ax": round(-math.sin(angle) * 8192 + rng.gauss(0, 15)),
            "ay": round(rng.gauss(0, 15)),
            "az": round(math.cos(angle) * 8192 + rng.gauss(0, 15)),
            "gx": round(0.2 * 65.5), "gy": round((velocity + 0.4) * 65.5),
            "gz": round(-0.1 * 65.5)}


class SimSource:
    def __init__(self, callback: SampleCallback, hz=50):
        self.callback = callback
        self.hz = hz
        self.tasks = {}
        self.last_samples = {}
        self.patterns = {}
        self.calibrating = set()
        self.ids = [f"sim-{i:02d}" for i in range(1, 6)]

    def devices(self):
        return [{"id": device, "link": "sim", "sensor": "mpu6050", "online": True,
                 "streaming": device in self.tasks, "hz": self.hz,
                 "units": "mpu6050_4g_500dps"} for device in self.ids]

    def set_calibrating(self, device_id, enabled):
        self.calibrating.add(device_id) if enabled else self.calibrating.discard(device_id)

    def set_pattern(self, device_id, pattern):
        if device_id not in self.ids:
            raise KeyError(device_id)
        self.patterns[device_id] = pattern

    async def start(self, device_id):
        if device_id not in self.ids:
            raise KeyError(device_id)
        if device_id not in self.tasks:
            self.tasks[device_id] = asyncio.create_task(self._stream(device_id))

    async def stop(self, device_id):
        task = self.tasks.pop(device_id, None)
        if task:
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)

    async def _stream(self, device_id):
        rng = random.Random(device_id)
        loop = asyncio.get_running_loop()
        origin = loop.time()
        index = 0
        cycle_start = .6
        cycle = 0
        pattern = "good" if device_id in self.calibrating else self.patterns.get(device_id,"good")
        while True:
            # Fixed sample timestamps with a monotonic deadline avoid delay drift.
            period = .8 if pattern == "mixed" and cycle % 10 == 9 else 2.5
            seconds = index / self.hz
            if seconds >= cycle_start + period:
                cycle_start += period
                cycle += 1
                pattern = "good" if device_id in self.calibrating else self.patterns.get(device_id,"good")
                period = .8 if pattern == "mixed" and cycle % 10 == 9 else 2.5
            amplitude = 66 if pattern == "mixed" and cycle % 10 in (7,8) else 110
            movement = max(0,seconds-cycle_start)
            if (pattern == "stop_early" and cycle >= 8) or (device_id in self.calibrating and cycle >= 3):
                movement = 0
            sample = sample_at(movement, rng,period,amplitude)
            sample["ms"] = round(index * 1000 / self.hz)
            self.last_samples[device_id] = sample
            await self.callback(device_id, sample)
            index += 1
            await asyncio.sleep(max(0, origin + index / self.hz - loop.time()))

    async def close(self):
        for device in list(self.tasks):
            await self.stop(device)
