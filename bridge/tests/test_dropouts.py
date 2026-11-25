"""Flaky wiring: short sensor dropouts must not stop rep counting for the rest of the set."""
import random
from smartrep.config import load_config
from smartrep.orientation import SignalPipeline
from smartrep.reps import Calibrator, RepDetector
from smartrep.sources.sim_source import sample_at

UNITS = 'mpu6050_4g_500dps'


def stream(reps, dropouts=(), period=2.5, seed=3):
    """50 Hz curl samples after a 0.6 s still start; drop samples inside each (start_s, end_s) window."""
    rng = random.Random(seed)
    for index in range(round((0.6 + reps * period + 0.6) * 50)):
        t = index / 50
        if any(start <= t < end for start, end in dropouts):
            continue
        sample = sample_at(min(max(t - 0.6, 0), reps * period), rng, period)
        yield {**sample, 'ms': index * 20}


def reference(config):
    pipeline, calibrator = SignalPipeline(UNITS, config), Calibrator(config)
    for raw in stream(3):
        sample = pipeline.update(raw)
        if sample['ready']:
            calibrator.add(sample['ms'], sample['signals'])
    return calibrator.finish()


def count(raw_samples, config):
    ref = reference(config)
    pipeline, detector = SignalPipeline(UNITS, config), RepDetector(ref, config)
    reps = 0
    for raw in raw_samples:
        sample = pipeline.update(raw)
        if sample['gap']:
            detector.reset_motion()
        if sample['ready'] and detector.update(sample['ms'], sample['signals'][ref.signal]):
            reps += 1
    return reps


def test_clean_set_counts_every_rep():
    assert count(stream(10), load_config()) == 10


def test_reps_keep_counting_after_sensor_dropouts():
    # Three ~0.4 s dropouts (the firmware re-initialising the MPU) during a 10-rep set.
    config = load_config()
    counted = count(stream(10, dropouts=[(4.0, 4.4), (11.0, 11.4), (18.0, 18.4)]), config)
    # At most the rep in progress during each dropout is lost; the rest still count.
    assert counted >= 7, counted


def test_calibration_survives_a_brief_dropout():
    config = load_config()
    pipeline, calibrator = SignalPipeline(UNITS, config), Calibrator(config)
    for raw in stream(3, dropouts=[(3.0, 3.4)]):
        sample = pipeline.update(raw)
        if sample['ready']:
            calibrator.add(sample['ms'], sample['signals'])
    ref = calibrator.finish()
    assert ref.ref_high - ref.ref_low > 60
