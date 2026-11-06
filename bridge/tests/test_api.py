import time
import pytest
from fastapi.testclient import TestClient
from smartrep.api import create_app
from smartrep.db import connect
from smartrep.config import load_config

BODY = {'participant_id':'123129','station_id':'db-5lb','exercise_id':'bicep-curl'}


def test_live_websocket_set_finish_and_reconnect(tmp_path):
    app = create_app(tmp_path/'live.db',True)
    with TestClient(app) as client:
        assert client.get('/api/participants/123129/today').json()['dose']
        assert len(client.get('/api/participants/123129/stations/db-5lb/exercises').json()) == 3
        assert client.get('/api/participants/123129/stations/db-3lb/exercises').json() == []
        with client.websocket_connect('/ws?participant=123129') as socket:
            assert socket.receive_json()['type'] == 'snapshot'
            socket.send_json({'type':'ping'})
            assert socket.receive_json()['type'] == 'pong'
            started = client.post('/api/sets',json=BODY)
            assert started.status_code == 201
            set_id = started.json()['set_id']
            seen = []
            for _ in range(100):
                message = socket.receive_json()
                seen.append(message['type'])
                if message['type'] == 'rep':
                    assert message['count'] == 1
                    assert message['quality'] == 'good'
                    break
            assert 'set_started' in seen and 'rep' in seen
        # The set survives phone disconnect; a new socket resyncs from SQLite.
        with client.websocket_connect('/ws?participant=123129') as socket:
            snapshot = socket.receive_json()['data']
            assert snapshot['sets'][0]['reps_completed'] >= 1
        result = client.post(f'/api/sets/{set_id}/finish').json()
        assert result['reps_completed'] >= 1
        assert result['ended_at'] and result['end_reason'] == 'user'
        assert len(result['reps']) >= 1
        assert client.post(f'/api/sets/{set_id}/finish').json() == result
        assert not any(d['streaming'] for d in client.get('/api/devices').json())
        assert client.get('/api/sets/99999').status_code == 404


@pytest.mark.parametrize('change,code',[
    ({'exercise_id':'goblet-squat'},'NOT_IN_DOSE'),
    ({'station_id':'kb-10lb'},'WRONG_EQUIPMENT'),
    ({'station_id':'db-3lb'},'WRONG_EQUIPMENT'),
    ({'participant_id':'999999'},'PARTICIPANT_NOT_FOUND'),
    ({'station_id':'unknown'},'STATION_NOT_FOUND'),
])
def test_start_validation(tmp_path,change,code):
    with TestClient(create_app(tmp_path/'error.db',True)) as client:
        result = client.post('/api/sets',json={**BODY,**change})
        assert result.json()['error']['code'] == code


def test_busy_missing_reference_and_offline(tmp_path):
    path = tmp_path/'errors.db'
    with TestClient(create_app(path,True)) as client:
        first = client.post('/api/sets',json=BODY).json()
        result = client.post('/api/sets',json={**BODY,'participant_id':'150093'})
        assert result.json()['error']['code'] == 'STATION_BUSY'
        client.post(f"/api/sets/{first['set_id']}/finish")
        with connect(path) as db:
            db.execute("DELETE FROM rep_references WHERE participant_id='123129'")
        assert client.post('/api/sets',json=BODY).json()['error']['code'] == 'NEEDS_CALIBRATION'
    with TestClient(create_app(tmp_path/'offline.db',False)) as client:
        assert client.post('/api/sets',json=BODY).json()['error']['code'] == 'DEVICE_OFFLINE'


def test_idle_cleanup_and_progression_seed(tmp_path):
    config = load_config()
    config['sets']['idle_timeout_s'] = .05
    with TestClient(create_app(tmp_path/'idle.db',True,config)) as client:
        dashboard = client.get('/api/dashboard').json()
        tom = next(p for p in dashboard['participants'] if p['display_name']=='Tom')
        assert tom['status'] == 'ready_to_progress'
        set_id = client.post('/api/sets',json=BODY).json()['set_id']
        time.sleep(.4)
        assert client.get(f'/api/sets/{set_id}').json()['end_reason'] == 'idle'
        assert client.post('/api/participants/123129/visits/db-3lb').status_code == 200
        mary = next(p for p in client.get('/api/dashboard').json()['participants'] if p['id']=='123129')
        assert mary['status'] == 'behind'


def test_simulator_pattern_controls(tmp_path):
    with TestClient(create_app(tmp_path/'patterns.db',True)) as client:
        assert client.post('/api/sim/pattern',json={'device_id':'sim-02','pattern':'mixed'}).status_code == 200
        assert client.post('/api/sim/pattern',json={'device_id':'missing','pattern':'good'}).status_code == 404
        assert client.post('/api/sim/pattern',json={'device_id':'sim-02','pattern':'invalid'}).status_code == 422
    with TestClient(create_app(tmp_path/'hardware.db')) as client:
        assert client.post('/api/sim/pattern',json={'device_id':'sim-02','pattern':'good'}).status_code == 404


def test_device_disconnect_grace_and_session_end(tmp_path):
    config = load_config()
    config['sets']['disconnect_grace_s'] = .1
    app = create_app(tmp_path/'disconnect.db',True,config)
    with TestClient(app) as client:
        set_id = client.post('/api/sets',json=BODY).json()['set_id']
        client.portal.call(app.state.source.stop,'sim-02')
        time.sleep(.6)
        assert client.get(f'/api/sets/{set_id}').json()['end_reason'] == 'disconnect'
        assert client.post('/api/participants/123129/session/finish').status_code == 200
        mary = next(p for p in client.get('/api/dashboard').json()['participants'] if p['id']=='123129')
        assert mary['status'] == 'behind'


def test_restart_recovers_abandoned_sets(tmp_path):
    path = tmp_path/'restart.db'
    with TestClient(create_app(path,True)) as client:
        set_id = client.post('/api/sets',json=BODY).json()['set_id']
    with connect(path) as db:
        db.execute('UPDATE sets SET ended_at=NULL,end_reason=NULL WHERE id=?',(set_id,))
    with TestClient(create_app(path,True)) as client:
        result = client.get(f'/api/sets/{set_id}').json()
        assert result['end_reason'] == 'disconnect'
        assert result['ended_at']


def test_lcd_gets_participant_and_authoritative_count(tmp_path):
    app=create_app(tmp_path/'lcd.db',True)
    with TestClient(app) as client:
        updates=[]
        async def display(device,name,count,quality='good'):
            updates.append((device,name,count,quality))
        app.state.source.display=display
        set_id=client.post('/api/sets',json=BODY).json()['set_id']
        assert updates[0]==('sim-02','Mary',0,'good')
        deadline=time.monotonic()+5
        while time.monotonic()<deadline and not any(item[2]>=1 for item in updates):
            time.sleep(.05)
        assert any(item[1:] == ('Mary',1,'good') for item in updates)
        result=client.post(f'/api/sets/{set_id}/finish').json()
        assert updates[-1]==('sim-02','Mary',result['reps_completed'],'done')
