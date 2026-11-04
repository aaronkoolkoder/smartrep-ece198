import math
import pytest
from smartrep.reps import Calibrator, CalibrationError
from smartrep.synthetic import write_csv
from smartrep.reps import replay


def calibrate(count=3, inverted=False):
    cal = Calibrator()
    for i in range(round(count*2.5*50)+1):
        p = (1-math.cos(2*math.pi*i/50/2.5))/2
        cal.add(i*20, {'x':.01*math.sin(i),'y':1-p if inverted else p,'z':0})
    return cal.finish()


def test_dominant_adxl_y_and_direction():
    for inverted in [False,True]:
        ref = calibrate(inverted=inverted)
        assert ref.signal == 'y'
        assert ref.direction == (-1 if inverted else 1)
        assert abs(ref.ref_low) < .05
        assert abs(ref.ref_high-1) < .05
        assert abs(ref.ref_duration_s-2.5) < .05


def test_single_and_flat_fail():
    with pytest.raises(CalibrationError,match='Detected 1 rep'):
        calibrate(1)
    cal = Calibrator()
    for i in range(200):
        cal.add(i*20,{'pitch':0,'ax':0})
    with pytest.raises(CalibrationError,match='range too small'):
        cal.finish()


def test_raw_csv_full_pipeline(tmp_path):
    reference = tmp_path/'cal.csv'
    data = tmp_path/'good.csv'
    write_csv(reference,3)
    write_csv(data,10)
    ref,events = replay(data,reference)
    assert ref.signal == 'pitch'
    assert ref.units == 'deg'
    assert abs(ref.ref_low) < 8
    assert abs(ref.ref_high-110) < 8
    assert len(events) == 10
    assert {e['quality'] for e in events} == {'good'}


def test_sensor_gap_and_channel_change_fail():
    cal = Calibrator()
    cal.add(0,{'pitch':0})
    with pytest.raises(CalibrationError,match='Sensor gap'):
        cal.add(500,{'pitch':10})
    with pytest.raises(CalibrationError,match='channels changed'):
        cal.add(20,{'roll':10})


@pytest.mark.parametrize('period,amplitude,expected',[(.8,110,'rushed'),(2.5,66,'short')])
def test_raw_csv_quality(tmp_path,period,amplitude,expected):
    reference = tmp_path/'cal.csv'
    data = tmp_path/'reps.csv'
    write_csv(reference,3)
    write_csv(data,3,period=period,amplitude=amplitude)
    _,events = replay(data,reference)
    assert len(events) == 3
    assert {e['quality'] for e in events} == {expected}


@pytest.mark.parametrize('seed',['sim-01','sim-02','sim-03','sim-04','sim-05'])
def test_station_noise_does_not_invent_cross_axis_rotation(tmp_path,seed):
    reference=tmp_path/'station-cal.csv'
    data=tmp_path/'station-set.csv'
    write_csv(reference,3,seed=seed)
    write_csv(data,3,seed=seed)
    ref,events=replay(data,reference)
    assert ref.signal=='pitch'
    assert len(events)==3
    assert {event['quality'] for event in events}=={'good'}
