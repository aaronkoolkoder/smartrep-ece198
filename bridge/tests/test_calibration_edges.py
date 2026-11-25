import asyncio
import math
import time

import pytest
from fastapi.testclient import TestClient
from smartrep.api import create_app
from smartrep.db import connect
from smartrep.reps import Calibrator, CalibrationError

BODY={'participant_id':'123129','station_id':'db-5lb','exercise_id':'bent-over-row','pin':'0000'}


def wave(seconds,period=2.5):
    return (1-math.cos(2*math.pi*seconds/period))/2


@pytest.mark.parametrize('direction',[-1,1])
def test_three_clean_cycles_beat_single_larger_cross_axis_swing(direction):
    cal=Calibrator()
    for i in range(376):
        t=i/50
        cal.add(i*20,{'pitch':200*wave(t,7.5),'roll':direction*45*wave(t)})
    assert cal.progress()['count']==3
    assert cal.finish().signal=='roll'
    assert cal.finish().direction==direction


@pytest.mark.parametrize('count',[1,2,4])
def test_exactly_three_complete_cycles_are_required(count):
    cal=Calibrator()
    for i in range(round(count*2.5*50)+1):
        cal.add(i*20,{'pitch':90*wave(i/50)})
    with pytest.raises(CalibrationError):cal.finish()


def test_partial_return_does_not_announce_three_complete_reps():
    cal=Calibrator()
    for i in range(326):
        cal.add(i*20,{'pitch':90*wave(i/50)})
    assert cal.progress()['count']==2
    assert cal.progress()['reference'] is None


@pytest.fixture
def hardware(tmp_path):
    app=create_app(tmp_path/'edge.db',False)
    commands=[]
    async def send(command):commands.append(command)
    async def close():pass
    with TestClient(app) as client:
        client.portal.call(app.state.source.register,{'device':'clip-01','sensor':'adxl335',
            'units':'counts14','sensor_ok':True},'serial',send,close,object())
        yield client,app,commands


def feed(client,app,identifier,until=376):
    async def samples():
        for i in range(until):
            await app.state.calibrations.sample('clip-01',{'ms':i*20,
                'x':5400,'y':5400+1080*wave(i/50),'z':5400})
    client.portal.call(samples)


def test_displayed_three_is_frozen_and_saves_after_extra_motion_and_unplug(hardware):
    client,app,commands=hardware
    identifier=client.post('/api/calibrations',json=BODY).json()['calibration_id']
    feed(client,app,identifier)
    status=client.get(f'/api/calibrations/{identifier}').json()
    assert status['ready'] and status['cycles_seen']==3
    state=app.state.calibrations.recordings[identifier]
    captured=state['reference']
    # Reaching for Save is a large movement; it must not rescale past reps.
    client.portal.call(app.state.calibrations.sample,'clip-01',{'ms':9000,'x':0,'y':16000,'z':0})
    async def unplug(device):raise OSError('USB unplugged')
    app.state.source.stop=unplug
    result=client.post(f'/api/calibrations/{identifier}/done').json()
    assert result['ok'] and result['signal']==captured.signal
    assert result['ref_high']==captured.ref_high
    assert not app.state.manager.reserved
    assert client.post(f'/api/calibrations/{identifier}/done').json()==result
    assert client.get(f'/api/calibrations/{identifier}').json()['result']==result


def test_stalled_sensor_releases_station_and_keeps_old_reference(hardware):
    client,app,_=hardware
    identifier=client.post('/api/calibrations',json=BODY).json()['calibration_id']
    state=app.state.calibrations.recordings[identifier]
    state['last_sample_at']=time.monotonic()-6
    client.portal.call(app.state.calibrations.check_timeouts)
    result=client.get(f'/api/calibrations/{identifier}').json()['result']
    assert not result['ok'] and 'No live sensor readings' in result['reason']
    assert not app.state.manager.reserved
    assert client.post('/api/calibrations',json=BODY).status_code==201


@pytest.mark.parametrize('sample,reason',[
    ({'ms':20,'read_ok':False},'Sensor read failed'),
    ({'ms':20,'x':0,'y':float('nan'),'z':0},'finite'),
    ({'ms':600,'x':5400,'y':5400,'z':5400},'gap'),
    ({'ms':0,'x':5400,'y':5400,'z':5400},'timestamps'),
])
def test_bad_readings_fail_clearly_and_release_station(hardware,sample,reason):
    client,app,_=hardware
    identifier=client.post('/api/calibrations',json=BODY).json()['calibration_id']
    client.portal.call(app.state.calibrations.sample,'clip-01',{'ms':0,'x':5400,'y':5400,'z':5400})
    client.portal.call(app.state.calibrations.sample,'clip-01',sample)
    client.portal.call(app.state.calibrations.check_timeouts)
    result=client.get(f'/api/calibrations/{identifier}').json()['result']
    assert not result['ok'] and reason.lower() in result['reason'].lower()
    assert not app.state.manager.reserved


def test_finish_transport_error_before_three_does_not_strand_lock(hardware):
    client,app,_=hardware
    identifier=client.post('/api/calibrations',json=BODY).json()['calibration_id']
    async def fail(device):raise RuntimeError('Transport failed')
    app.state.source.stop=fail
    assert not client.post(f'/api/calibrations/{identifier}/done').json()['ok']
    assert not app.state.manager.reserved


def test_concurrent_save_and_cancel_have_one_terminal_result(hardware):
    client,app,_=hardware
    identifier=client.post('/api/calibrations',json=BODY).json()['calibration_id']
    feed(client,app,identifier)
    async def finish():
        return await asyncio.gather(app.state.calibrations.done(identifier),app.state.calibrations.cancel(identifier))
    a,b=client.portal.call(finish)
    assert a==b and a['ok']
    assert not app.state.manager.reserved


def test_rushed_cycles_are_not_accepted_as_a_reference():
    cal=Calibrator()
    for i in range(61):
        cal.add(i*20,{'pitch':90*wave(i/50,.4)})
    with pytest.raises(CalibrationError,match='slowly'):
        cal.finish()


def test_hung_stop_times_out_and_releases_station(hardware):
    client,app,_=hardware
    identifier=client.post('/api/calibrations',json=BODY).json()['calibration_id']
    async def hang(device):await asyncio.sleep(60)
    app.state.source.stop=hang
    before=time.monotonic()
    assert not client.post(f'/api/calibrations/{identifier}/done').json()['ok']
    assert time.monotonic()-before<4
    assert not app.state.manager.reserved


def test_missing_recording_returns_not_found(hardware):
    client,_,_=hardware
    for suffix in ['', '/done','/cancel']:
        response=client.get('/api/calibrations/999999') if not suffix else client.post('/api/calibrations/999999'+suffix)
        assert response.status_code==404


def test_invalid_three_cycles_do_not_send_a_third_success_beep(hardware):
    client,app,commands=hardware
    identifier=client.post('/api/calibrations',json=BODY).json()['calibration_id']
    async def samples():
        for i in range(61):
            await app.state.calibrations.sample('clip-01',{'ms':i*20,'x':5400,
                'y':5400+1080*wave(i/50,.4),'z':5400})
    client.portal.call(samples)
    client.portal.call(app.state.calibrations.check_timeouts)
    result=client.post(f'/api/calibrations/{identifier}/done').json()
    assert not result['ok']
    assert 'LCD|Mary|3|cal' not in commands
