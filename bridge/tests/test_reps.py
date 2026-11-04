import math
import random
import pytest
from smartrep.reps import Reference, RepDetector


def run_wave(count=10, period=2.5, amplitude=1, direction=1, noise=0):
    detector = RepDetector(Reference('pitch', 'deg', 0, 110, 2.5, direction))
    rng = random.Random(42)
    events = []
    for i in range(round(count * period * 50) + 1):
        ms = i * 20
        p = amplitude * (1 - math.cos(2 * math.pi * i / 50 / period)) / 2 + rng.gauss(0, noise)
        event = detector.update(ms, (p if direction == 1 else 1-p) * 110)
        if event:
            events.append(event)
    return detector, events


@pytest.mark.parametrize('direction', [1,-1])
def test_clean_and_inverted(direction):
    detector, events = run_wave(direction=direction)
    assert len(events) == detector.completed == 10
    assert {e['quality'] for e in events} == {'good'}


def test_noise_no_double_counts():
    # Fifty raw counts at the configured MPU scale is about 0.006 g.
    detector, events = run_wave(noise=50/8192)
    assert len(events) == detector.completed == 10


def test_half_reps():
    detector, events = run_wave(3, amplitude=.6)
    assert len(events) == 3
    assert detector.completed == 0
    assert {e['quality'] for e in events} == {'short'}


def test_rushed():
    detector, events = run_wave(3, period=.8)
    assert detector.completed == len(events) == 3
    assert {e['quality'] for e in events} == {'rushed'}


def test_slow():
    _, events = run_wave(2, period=15)
    assert {e['quality'] for e in events} == {'slow'}


def test_top_jitter_and_start_mid_rep():
    detector = RepDetector(Reference('pitch','deg',0,1,2.5))
    assert all(detector.update(i*20, .75 + .01*math.sin(i)) is None for i in range(500))


def test_debounce():
    detector, events = run_wave(2, period=.4)
    assert len(events) == 1


def test_gap_does_not_join_two_half_movements():
    d = RepDetector(Reference('pitch','deg',0,1,2.5))
    assert d.update(0,0) is None
    assert d.update(20,1) is None
    assert d.update(500,0) is None
    assert d.completed == 0
    with pytest.raises(ValueError):
        d.update(500,0)
