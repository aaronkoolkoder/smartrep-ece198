"""Real hardware mode with MMA ADC samples and outbound LCD commands."""
import math
import pytest
from fastapi.testclient import TestClient
from smartrep.api import create_app
from smartrep.units import convert

BODY = {'participant_id':'123129','station_id':'db-5lb','exercise_id':'bicep-curl'}


def test_mma7361_scale():
    values=convert({'x':1351.35,'y':2006.55,'z':696.15},'mma7361_counts12')
    assert values == pytest.approx({'x':0,'y':1,'z':-1})


@pytest.mark.parametrize('amplitude,direction',[(1,1),(.06,1),(.06,-1)])
def test_hardware_calibration_reps_and_lcd(tmp_path,amplitude,direction):
    from smartrep.config import load_config
    config=load_config()
    if amplitude<1:
        config['calibration']['min_ref_range_g']=0.025
    app=create_app(tmp_path/'mma.db',False,config)
    commands=[]
    async def send(command): commands.append(command)
    async def close(): pass
    token=object()
    with TestClient(app) as client:
        client.portal.call(app.state.source.register,
            {'device':'clip-01','sensor':'mma7361','units':'mma7361_counts12','hz':50},
            'serial',send,close,token)
        assert client.post('/api/sets',json=BODY).json()['error']['code']=='NEEDS_CALIBRATION'
        response=client.post('/api/calibrations',json={**BODY,'pin':'0000'})
        assert response.status_code==201
        identifier=response.json()['calibration_id']
        async def feed(offset,cycles):
            for i in range(cycles*150+51):
                # Still at the bottom before/after three 3-second cycles.
                phase=max(0,min(i-25,cycles*150))
                movement=direction*amplitude*(1-math.cos(2*math.pi*phase/150))/2
                sample={'t':'s','ms':offset+i*20,'x':round(1351.35+655.2*movement),
                        'y':1351,'z':2007}
                await app.state.source.ingest('clip-01',sample,token)
        assert 'LCD|Mary|0|cal' in commands
        client.portal.call(feed,0,3)
        assert app.state.calibrations.recordings[identifier]['progress']==3
        assert 'LCD|Mary|1|cal' in commands
        assert commands[-1]=='LCD|Mary|3|cal'
        result=client.post(f'/api/calibrations/{identifier}/done').json()
        assert result['ok'],result
        assert commands[-1]=='LCD|Mary|3|cal_saved'
        assert result['signal']=='x' and result['units']=='g'
        started=client.post('/api/sets',json=BODY)
        assert started.status_code==201,started.json()
        assert 'LCD|Mary|0|good' in commands
        client.portal.call(feed,11000,3)
        summary=client.post(f"/api/sets/{started.json()['set_id']}/finish").json()
        assert summary['reps_completed']==3
        assert 'LCD|Mary|1|good' in commands
        assert commands[-1]=='LCD|Mary|3|done'


def test_small_movement_demo_counts_small_signal_but_not_flat_noise():
    from smartrep.config import load_config
    from smartrep.orientation import SignalPipeline
    from smartrep.reps import Calibrator, CalibrationError, RepDetector
    config=load_config()
    config['calibration']['min_ref_range_g']=0.025
    def record(amplitude,settings):
        pipeline=SignalPipeline('mma7361_counts12',settings)
        cal=Calibrator(settings)
        samples=[]
        for i in range(501):
            phase=max(0,min(i-25,450))
            movement=amplitude*(1-math.cos(2*math.pi*phase/150))/2
            raw={'ms':i*20,'x':round(1351.35+655.2*movement),
                 'y':1351,'z':2007}
            sample=pipeline.update(raw)
            cal.add(sample['ms'],sample['signals'])
            samples.append(sample)
        return cal,samples
    cal,samples=record(0.06,config)
    reference=cal.finish()
    detector=RepDetector(reference,config)
    events=[event for s in samples if (event:=detector.update(s['ms'],s['signals'][reference.signal]))]
    assert len(events)==3 and events[-1]['count']==3
    with pytest.raises(CalibrationError,match='range too small'):
        record(0.06,load_config())[0].finish()
    with pytest.raises(CalibrationError,match='range too small'):
        record(0.003,config)[0].finish()
