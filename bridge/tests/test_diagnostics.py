import asyncio
from fastapi.testclient import TestClient
from smartrep.api import create_app


def test_integrated_live_raw_page_and_station_ownership(tmp_path):
    app=create_app(tmp_path/'raw.db',False)
    commands=[]
    async def send(command):commands.append(command)
    async def close():pass
    token=object()
    with TestClient(app) as client:
        assert client.get('/diagnostics').status_code==200
        client.portal.call(app.state.source.register,{'device':'clip-01','sensor':'mpu6050',
            'units':'mpu6050_4g_500dps','sensor_ok':False,'lcd_ok':True},'serial',send,close,token)
        with client.websocket_connect('/diagnostics/live') as socket:
            async def wait_started():
                for _ in range(100):
                    if 'DIAGSTART' in commands:return
                    await asyncio.sleep(.01)
                raise AssertionError('Diagnostics not started')
            client.portal.call(wait_started)
            client.portal.call(app.state.source.ingest,'clip-01',{'t':'raw','ok':True,'ms':100,
                'bytes':[255,255,0,1,32,0,0,0,0,2,0,3,0,4]},token)
            frame=socket.receive_json()
            assert frame['frames']==1 and frame['sample']['ax']==-1
            assert frame['sample']['az']==8192 and frame['sample']['gz']==4
            assert not frame['sensor_ok'] and frame['lcd_ok']
            client.portal.call(app.state.source.ingest,'clip-01',{'t':'raw','ok':False,'ms':200},token)
            failure=socket.receive_json()
            assert failure['read_error'] and failure['sample'] is None
            assert failure['frames']==1
            socket.send_text('BUZZTEST')
            assert socket.receive_json()['control']=='buzzer'
            assert commands[-1]=='BUZZTEST'
            body={'participant_id':'123129','station_id':'db-5lb','exercise_id':'bicep-curl','pin':'0000'}
            assert client.post('/api/calibrations',json=body).json()['error']['code']=='STATION_BUSY'
        async def wait_released():
            for _ in range(100):
                if 'clip-01' not in app.state.manager.reserved:return
                await asyncio.sleep(.01)
            raise AssertionError('Diagnostic page did not release station')
        client.portal.call(wait_released)
        assert commands[-1]=='STOP'


def test_diagnostics_reconnect_resumes_diagnostic_stream(tmp_path):
    app=create_app(tmp_path/'resume.db',False)
    commands=[]
    async def send(command):commands.append(command)
    async def close():pass
    hello={'device':'clip-01','sensor':'mpu6050','units':'mpu6050_4g_500dps'}
    with TestClient(app) as client:
        client.portal.call(app.state.source.register,hello,'wifi',send,close,object())
        client.portal.call(app.state.source.start_diagnostics,'clip-01')
        client.portal.call(app.state.source.register,hello,'wifi',send,close,object())
        assert commands==['DIAGSTART','DIAGSTART']
