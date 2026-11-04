import asyncio
import json
from fastapi.testclient import TestClient
from smartrep.api import create_app
from smartrep.config import load_config
from smartrep.sources.hardware_source import HardwareSource

HELLO={'t':'hello','device':'clip-01','sensor':'mpu6050','units':'mpu6050_4g_500dps','hz':50}


def test_multiline_wifi_and_health(tmp_path):
    app=create_app(tmp_path/'wifi.db',False)
    with TestClient(app) as client:
        with client.websocket_connect('/device') as socket:
            socket.send_text(json.dumps(HELLO))
            # A client-side ping roundtrip lets the registration finish.
            socket.send_text(json.dumps({'t':'pong'}))
            async def wait_registered():
                for _ in range(100):
                    if app.state.source.devices():
                        return
                    await asyncio.sleep(.01)
                raise AssertionError('Device not registered')
            client.portal.call(wait_registered)
            assert client.get('/api/health').json()['devices_online']==1
            socket.send_text('\n'.join(json.dumps({'t':'s','ms':i*20,'ax':0,'ay':0,'az':8192,'gx':0,'gy':0,'gz':0}) for i in range(5)))
            socket.send_text(json.dumps({'t':'err','msg':'no data from Arduino'}))
            async def wait_samples():
                for _ in range(100):
                    if app.state.samples_received==5:
                        return
                    await asyncio.sleep(.01)
                raise AssertionError('Samples missing')
            client.portal.call(wait_samples)
            assert app.state.samples_received==5


def test_duplicate_connection_replaces_and_resumes():
    async def scenario():
        received=[]
        async def callback(device,sample):received.append(sample['ms'])
        source=HardwareSource(callback,load_config())
        closed=[];commands=[]
        async def send(command):commands.append(command)
        async def close():closed.append(True)
        a,b=object(),object()
        await source.register(HELLO,'wifi',send,close,a)
        await source.start('clip-01')
        await source.ingest('clip-01',{'t':'s','ms':1000},a)
        await source.register(HELLO,'wifi',send,close,b)
        await source.disconnected('clip-01',a)
        assert source.devices()[0]['online']
        assert len(closed)==1 and commands==['START','START']
        await source.ingest('clip-01',{'t':'s','ms':20},a)
        await source.ingest('clip-01',{'t':'s','ms':20},b)
        assert len(received)==2 and received[1]>received[0]
        await source.ingest('clip-01',{'t':'err','msg':'no data from Arduino'},b)
        assert not source.devices()[0]['uart_ok']
    asyncio.run(scenario())
