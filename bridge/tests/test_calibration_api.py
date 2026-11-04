import csv
from fastapi.testclient import TestClient
from smartrep.api import create_app
from smartrep.db import connect
from smartrep.synthetic import write_csv

BODY={'participant_id':'123129','station_id':'db-5lb','exercise_id':'bicep-curl','pin':'0000'}


def test_calibration_exclusivity_pin_and_persistence(tmp_path):
    app=create_app(tmp_path/'cal.db',True)
    fixture=tmp_path/'cal.csv'
    write_csv(fixture,3)
    with TestClient(app) as client:
        assert client.post('/api/calibrations',json={**BODY,'pin':'9999'}).status_code==403
        started=client.post('/api/calibrations',json=BODY)
        assert started.status_code==201
        identifier=started.json()['calibration_id']
        assert client.post('/api/sets',json={k:v for k,v in BODY.items() if k!='pin'}).json()['error']['code']=='STATION_BUSY'
        async def feed():
            await app.state.source.stop('sim-02')
            offset=(app.state.calibrations.recordings[identifier]['pipeline'].last_ms or 0)+20
            with fixture.open() as stream:
                for sample in csv.DictReader(stream):
                    sample['ms']=int(sample['ms'])+offset
                    await app.state.calibrations.sample('sim-02',sample)
        client.portal.call(feed)
        result=client.post(f'/api/calibrations/{identifier}/done').json()
        assert result['ok'] and result['signal']=='pitch'
        assert client.post(f'/api/calibrations/{identifier}/done').json()==result
        with connect(tmp_path/'cal.db') as db:
            reference=db.execute("SELECT * FROM rep_references WHERE participant_id='123129' AND exercise_id='bicep-curl'").fetchone()
            assert abs(reference['ref_high']-110)<8
        assert client.post('/api/sets',json={k:v for k,v in BODY.items() if k!='pin'}).status_code==201


def test_failed_calibration_releases_station(tmp_path):
    app=create_app(tmp_path/'fail.db',True)
    with TestClient(app) as client:
        identifier=client.post('/api/calibrations',json=BODY).json()['calibration_id']
        assert not client.post(f'/api/calibrations/{identifier}/done').json()['ok']
        assert client.post('/api/sets',json={k:v for k,v in BODY.items() if k!='pin'}).status_code==201


def test_ui_and_station_list(tmp_path):
    with TestClient(create_app(tmp_path/'ui.db',True)) as client:
        assert 'smartrep' in client.get('/').text
        assert client.get('/dashboard').status_code==200
        assert client.get('/static/app.js').status_code==200
        assert len(client.get('/api/stations').json())==5
        assert client.post('/api/sim/crowd',json={'enabled':True}).json()['crowd_running']
        assert not client.post('/api/sim/crowd',json={'enabled':False}).json()['crowd_running']
