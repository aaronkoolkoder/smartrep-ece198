import json
from io import BytesIO
from zipfile import ZipFile
from xml.etree import ElementTree as ET
from fastapi.testclient import TestClient
from smartrep.api import create_app
from smartrep.db import connect

BODY={'participant_id':'123129','station_id':'db-5lb','exercise_id':'bicep-curl','pin':'0000'}


def test_diagnostic_calibration_streams_graph_but_cannot_save_reference(tmp_path):
    path=tmp_path/'diagnostic.db'
    app=create_app(path,False)
    commands=[];events=[]
    async def send(command): commands.append(command)
    async def close(): pass
    async def broadcast(event,participant=None): events.append(event)
    token=object()
    with TestClient(app) as client:
        client.portal.call(app.state.source.register,{'device':'clip-01','sensor':'mpu6050',
            'units':'mpu6050_4g_500dps','sensor_ok':False},'serial',send,close,token)
        app.state.manager.broadcast=broadcast
        result=client.post('/api/calibrations',json=BODY).json()
        assert result['diagnostic'] and 'DIAGSTART' in commands
        async def feed():
            for i in range(20):
                await app.state.source.ingest('clip-01',{'t':'raw','ms':i*20,'ok':True,
                    'bytes':[0,0,0,0,32,0,0,0,0,0,0,0,0,0]},token)
        client.portal.call(feed)
        graphs=[event for event in events if event['type']=='calibration_signal']
        assert len(graphs)==4
        assert graphs[0]['diagnostic'] and graphs[0]['channels']['az']==8192
        saved=client.post(f"/api/calibrations/{result['calibration_id']}/done").json()
        assert not saved['ok'] and 'sensor reads' in saved['reason']
        with connect(path) as db:
            assert db.execute('SELECT count(*) FROM rep_references').fetchone()[0]==0
            assert db.execute('SELECT count(*) FROM motion_samples WHERE diagnostic=1').fetchone()[0]==4
        download=client.get('/api/participants/123129/history.xlsx')
        assert download.status_code==200
        assert download.headers['content-type'].startswith('application/vnd.openxmlformats')
        with ZipFile(BytesIO(download.content)) as archive:
            for name in archive.namelist():
                if name.endswith('.xml') or name.endswith('.rels'):
                    ET.fromstring(archive.read(name))
            graph=archive.read('xl/worksheets/sheet4.xml').decode()
            assert '8192' in graph and 'diagnostic' in graph
        other=client.get('/api/participants/204417/history.xlsx')
        with ZipFile(BytesIO(other.content)) as archive:
            assert '8192' not in archive.read('xl/worksheets/sheet4.xml').decode()
        assert client.get('/api/participants/unknown/history.xlsx').status_code==404


def test_history_keeps_literal_names_and_saved_set_graph(tmp_path):
    path=tmp_path/'history.db'
    app=create_app(path,True)
    with TestClient(app) as client:
        with connect(path) as db:
            db.execute("UPDATE participants SET display_name=? WHERE id='123129'",('=1+1 & <Mary>',))
        set_id=client.post('/api/sets',json={key:value for key,value in BODY.items() if key!='pin'}).json()['set_id']
        async def wait_samples():
            import asyncio
            for _ in range(100):
                with connect(path) as db:
                    if db.execute("SELECT count(*) FROM motion_samples WHERE phase='set'").fetchone()[0]:return
                await asyncio.sleep(.02)
            raise AssertionError('Graph samples missing')
        client.portal.call(wait_samples)
        client.post(f'/api/sets/{set_id}/finish')
        content=client.get('/api/participants/123129/history.xlsx').content
        with ZipFile(BytesIO(content)) as archive:
            name=ET.fromstring(archive.read('xl/worksheets/sheet1.xml'))
            assert '=1+1 & <Mary>' in ''.join(name.itertext())
            assert '<f>' not in archive.read('xl/worksheets/sheet1.xml').decode()
            assert 'normalized' in archive.read('xl/worksheets/sheet4.xml').decode()
