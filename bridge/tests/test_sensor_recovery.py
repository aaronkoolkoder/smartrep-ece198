"""A transient MPU read failure must not block sets after the firmware recovers the sensor."""
import asyncio
from fastapi.testclient import TestClient
from smartrep.api import create_app
from smartrep.db import connect

HELLO = {'device': 'clip-01', 'sensor': 'mpu6050', 'units': 'mpu6050_4g_500dps', 'sensor_ok': True}
SET = {'participant_id': '123129', 'station_id': 'db-5lb', 'exercise_id': 'bicep-curl'}


def _hardware_app(tmp_path, recovered):
    """Hardware app with clip-01 registered, calibrated, then flagged by a read failure.
    The fake board answers HELLO with sensor_ok=recovered, like the firmware's identity reply."""
    path = tmp_path / 'hw.db'
    app = create_app(path, False)
    commands, token = [], object()

    async def send(command):
        commands.append(command)
        if command == 'HELLO':
            asyncio.get_running_loop().create_task(
                app.state.source.ingest('clip-01', {'t': 'hello', 'sensor_ok': recovered}, token))

    async def close():
        pass
    return app, path, commands, token, send, close


def _prepare(client, app, path, token, send, close):
    client.portal.call(app.state.source.register, HELLO, 'serial', send, close, token)
    with connect(path) as db:
        db.execute("INSERT INTO rep_references VALUES (?,?,?,?,?,?,?,?,?,?)",
                   ('123129', 'bicep-curl', 'pitch', 'deg', 0, 100, 2.5, 1, 'clip-01', '2026-11-24T00:00:00+00:00'))
    client.portal.call(app.state.source.ingest, 'clip-01', {'t': 'err', 'msg': 'sensor read failed, re-initialising'}, token)
    assert app.state.source.devices()[0]['sensor_ok'] is False


def test_start_rechecks_sensor_and_proceeds_after_recovery(tmp_path):
    app, path, commands, token, send, close = _hardware_app(tmp_path, recovered=True)
    with TestClient(app) as client:
        _prepare(client, app, path, token, send, close)
        response = client.post('/api/sets', json=SET)
        assert response.status_code == 201, response.json()
        assert 'HELLO' in commands and commands[-1].startswith(('START', 'LCD'))


def test_start_still_refuses_when_sensor_is_really_failing(tmp_path):
    app, path, commands, token, send, close = _hardware_app(tmp_path, recovered=False)
    with TestClient(app) as client:
        _prepare(client, app, path, token, send, close)
        response = client.post('/api/sets', json=SET)
        assert response.status_code == 422
        assert response.json()['error']['code'] == 'SENSOR_NOT_READY'


def test_streamed_samples_clear_a_transient_failure(tmp_path):
    app, path, commands, token, send, close = _hardware_app(tmp_path, recovered=False)
    with TestClient(app) as client:
        _prepare(client, app, path, token, send, close)
        client.portal.call(app.state.source.ingest, 'clip-01', {'t': 's', 'ms': 20, 'ax': 0, 'ay': 0, 'az': 8192, 'gx': 0, 'gy': 0, 'gz': 0}, token)
        assert app.state.source.devices()[0]['sensor_ok'] is True
