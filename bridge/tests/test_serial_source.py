"""Exercise actual pyserial over a pseudo-terminal (no USB board required)."""
import asyncio
import json
import os
import select
import threading
import pytest
from smartrep.sources.hardware_source import HardwareSource
from smartrep.config import load_config


@pytest.mark.skipif(os.name=='nt',reason='Pseudo-terminal integration runs on macOS/Linux')
def test_usb_protocol_reader():
    import pty
    master,slave=pty.openpty()
    port=os.ttyname(slave)
    ended=threading.Event()
    def board():
        buffer=b''
        while not ended.is_set():
            if not select.select([master],[],[],.05)[0]:continue
            try:data=os.read(master,1024)
            except OSError:return
            buffer+=data
            while b'\n' in buffer:
                line,buffer=buffer.split(b'\n',1)
                command=line.strip()
                if command==b'HELLO':
                    os.write(master,(json.dumps({'t':'hello','device':'clip-01','sensor':'mpu6050','units':'mpu6050_4g_500dps'})+'\n').encode())
                elif command==b'START':
                    for i in range(4):
                        os.write(master,(json.dumps({'t':'s','ms':i*20,'ax':0,'ay':0,'az':8192,'gx':0,'gy':0,'gz':0})+'\n').encode())
    worker=threading.Thread(target=board,daemon=True);worker.start()
    async def scenario():
        samples=[]
        async def callback(device,sample):samples.append(sample)
        source=HardwareSource(callback,load_config(),ports=[port])
        await source.open()
        try:
            for _ in range(100):
                if source.devices():break
                await asyncio.sleep(.02)
            assert source.devices()[0]['link']=='serial'
            await source.start('clip-01')
            for _ in range(100):
                if len(samples)==4:break
                await asyncio.sleep(.02)
            assert [s['ms'] for s in samples]==[0,20,40,60]
        finally:
            await source.close()
    try:asyncio.run(scenario())
    finally:
        ended.set();worker.join(timeout=1);os.close(master);os.close(slave)
