"""Leaving a calibration frees the station; sets do not end for inactivity by default."""
import time
from fastapi.testclient import TestClient
from smartrep.api import create_app

CAL = {'participant_id': '123129', 'station_id': 'db-5lb', 'pin': '0000'}
SET = {'participant_id': '123129', 'station_id': 'db-5lb', 'exercise_id': 'bicep-curl'}


def test_closing_calibration_frees_the_station(tmp_path):
    with TestClient(create_app(tmp_path / 'cancel.db', True)) as client:
        first = client.post('/api/calibrations', json={**CAL, 'exercise_id': 'bicep-curl'})
        assert first.status_code == 201
        cancelled = client.post(f"/api/calibrations/{first.json()['calibration_id']}/cancel").json()
        assert cancelled['cancelled']
        assert client.post('/api/sets', json=SET).status_code == 201


def test_reopening_calibration_replaces_an_abandoned_one(tmp_path):
    with TestClient(create_app(tmp_path / 'reopen.db', True)) as client:
        assert client.post('/api/calibrations', json={**CAL, 'exercise_id': 'bicep-curl'}).status_code == 201
        # Window closed without cancelling (e.g. tab closed): the next calibration still starts.
        again = client.post('/api/calibrations', json={**CAL, 'exercise_id': 'hammer-curl'})
        assert again.status_code == 201, again.json()


def test_active_set_still_blocks_calibration(tmp_path):
    with TestClient(create_app(tmp_path / 'busy.db', True)) as client:
        assert client.post('/api/sets', json=SET).status_code == 201
        busy = client.post('/api/calibrations', json={**CAL, 'exercise_id': 'hammer-curl'}).json()
        assert busy['error']['code'] == 'STATION_BUSY'


def test_sets_do_not_end_for_inactivity_by_default(tmp_path):
    app = create_app(tmp_path / 'idle.db', True)
    with TestClient(app) as client:
        set_id = client.post('/api/sets', json=SET).json()['set_id']
        app.state.manager.active[next(iter(app.state.manager.active))]['last_rep'] = time.monotonic() - 3600
        time.sleep(1.2)
        assert client.get(f'/api/sets/{set_id}').json()['ended_at'] is None
