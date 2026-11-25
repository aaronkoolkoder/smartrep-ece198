"""Curl-family and row movements with the sensor rotating about different axes.

A bicep curl with the sensor on the forearm rotates about the sensor's Y axis (pitch).
A hammer curl or a different mount rotates about an arbitrary axis; a row with the
sensor above the elbow swings the upper arm about 60 degrees. Gravity and gyro readings
are generated from the true rotation, in raw MPU6050 counts.
"""
import math
import random
import pytest
from smartrep.config import load_config
from smartrep.orientation import SignalPipeline
from smartrep.reps import Calibrator, CalibrationError, RepDetector

UNITS = 'mpu6050_4g_500dps'


def rotate(v, u, phi):
    c, s = math.cos(phi), math.sin(phi)
    dot = sum(a * b for a, b in zip(u, v))
    cross = (u[1] * v[2] - u[2] * v[1], u[2] * v[0] - u[0] * v[2], u[0] * v[1] - u[1] * v[0])
    return tuple(v[i] * c + cross[i] * s + u[i] * dot * (1 - c) for i in range(3))


def movement(reps, axis, amplitude, start=(0, 0, 1), period=2.5, seed=5):
    """Still 0.6 s, then `reps` smooth out-and-back rotations, then still 0.6 s (50 Hz)."""
    norm = math.sqrt(sum(a * a for a in axis))
    u = tuple(a / norm for a in axis)
    rng = random.Random(seed)
    for index in range(round((0.6 + reps * period + 0.6) * 50)):
        t = min(max(index / 50 - 0.6, 0), reps * period)
        moving = 0 < index / 50 - 0.6 < reps * period
        theta = math.radians(amplitude) * (1 - math.cos(2 * math.pi * t / period)) / 2
        rate = math.degrees(math.radians(amplitude) * math.pi / period * math.sin(2 * math.pi * t / period)) if moving else 0
        g = rotate(start, u, -theta)
        sample = {'ms': index * 20}
        for i, k in enumerate(('ax', 'ay', 'az')):
            sample[k] = round(g[i] * 8192 + rng.gauss(0, 15))
        for i, k in enumerate(('gx', 'gy', 'gz')):
            sample[k] = round(u[i] * rate * 65.5 + rng.gauss(0, 8))
        yield sample


def calibrate(samples, config):
    pipeline, calibrator = SignalPipeline(UNITS, config), Calibrator(config)
    for raw in samples:
        sample = pipeline.update(raw)
        if sample['ready']:
            calibrator.add(sample['ms'], sample['signals'])
    return calibrator.finish()


def count(samples, ref, config):
    pipeline, detector, reps = SignalPipeline(UNITS, config), RepDetector(ref, config), 0
    for raw in samples:
        sample = pipeline.update(raw)
        if sample['ready'] and detector.update(sample['ms'], sample['signals'][ref.signal]):
            reps += 1
    return reps


CASES = {
    # name: (rotation axis in sensor frame, degrees of rotation, start orientation)
    'bicep curl, sensor on forearm': ((0, 1, 0), 110, (0, 0, 1)),
    'hammer curl, sensor turned on the dumbbell': ((0.35, 0.55, 0.76), 100, (0, 0, 1)),
    'hammer curl, sensor on its side': ((0, 0, 1), 100, (0, 1, 0)),
    'row, sensor above the elbow': ((1, 0.2, 0), 60, (0, 0, 1)),
}


@pytest.mark.parametrize('name', list(CASES))
def test_calibrate_then_count_ten_reps(name):
    axis, amplitude, start = CASES[name]
    config = load_config()
    ref = calibrate(movement(3, axis, amplitude, start), config)
    assert count(movement(10, axis, amplitude, start, seed=9), ref, config) == 10


def test_bicep_curl_keeps_its_signal():
    axis, amplitude, start = CASES['bicep curl, sensor on forearm']
    assert calibrate(movement(3, axis, amplitude, start), load_config()).signal == 'pitch'


def test_no_rotation_is_still_rejected():
    # A dumbbell moved straight up and down without rotating gives the sensor nothing to track.
    with pytest.raises(CalibrationError):
        calibrate(movement(3, (0, 1, 0), 3), load_config())
