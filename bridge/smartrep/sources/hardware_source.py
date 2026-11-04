"""One raw-sample interface for USB Arduinos and ESP32 WebSocket modems."""
import asyncio
import json
import logging
import time
import serial
from serial.tools import list_ports


class HardwareSource:
    def __init__(self, callback, config, status_callback=None, ports=None):
        self.callback, self.config = callback, config
        self.status_callback = status_callback
        self.forced_ports = ports or []
        self.entries = {}
        self.tasks = []
        self.port_tasks = {}
        self.closed = False
        self.clocks = {}

    def devices(self):
        return [{k:v for k,v in d.items() if k not in ('send','close','token','last_pong','raw_ms','offset')}
                for d in self.entries.values()]

    async def open(self):
        self.tasks = [asyncio.create_task(self._heartbeat()),asyncio.create_task(self._discover())]

    async def _status(self,device):
        if self.status_callback:
            await self.status_callback({'type':'device_status','device_id':device,**next(d for d in self.devices() if d['id']==device)})

    async def register(self,hello,link,send,close,token):
        device = hello.get('device')
        if not isinstance(device,str) or not device or len(device)>64:
            raise ValueError('A device ID is required')
        if hello.get('units') not in self.config['units']:
            raise ValueError('Unsupported device units')
        previous = self.entries.get(device)
        if previous and previous['online']:
            logging.warning('Duplicate device %s: replacing %s with %s',device,previous.get('address'),str(token))
            await previous['close']()
        resume=bool(previous and previous['streaming'])
        self.entries[device] = {'id':device,'link':link,'sensor':hello.get('sensor','unknown'),
            'units':hello['units'],'hz':hello.get('hz',50),'fw':hello.get('fw','unknown'),
            'online':True,'streaming':resume,'uart_ok':hello.get('uart_ok',True),
            'rssi':hello.get('rssi'),'address':hello.get('_address',link),'send':send,'close':close,'token':token,
            'last_pong':time.monotonic()}
        if resume:
            await send('START')
        await self._status(device)
        logging.info('Device %s connected over %s',device,link)
        return device

    async def ingest(self,device,line,token):
        entry=self.entries.get(device)
        if not entry or entry['token'] != token:
            return
        try:
            msg=json.loads(line) if isinstance(line,str) else line
            if not isinstance(msg,dict):
                return
            kind=msg.get('t')
            if kind in ('pong','hello','info','status'):
                entry['last_pong']=time.monotonic()
                for key in ('rssi','uart_ok','uptime_s','i2c_err'):
                    if key in msg:
                        entry[key]=msg[key]
                if not entry['online']:
                    entry['online']=True
                    # An active set may survive a temporary link interruption.
                await self._status(device)
            if kind=='s':
                raw=int(msg['ms'])
                clock=self.clocks.setdefault(device,{'raw':raw,'offset':0,'last':raw})
                if raw<clock['raw']:
                    clock['offset']=clock['last']+1000-raw
                clock['raw']=raw
                msg={**msg,'ms':raw+clock['offset']}
                clock['last']=msg['ms']
                await self.callback(device,msg)
            elif kind=='b':
                for index,values in enumerate(msg.get('samples',[])):
                    if not isinstance(values,dict):
                        continue
                    await self.ingest(device,{'t':'s','ms':msg['ms0']+index*msg['dt'],**values},token)
            elif kind=='err':
                logging.warning('Device %s: %s',device,msg.get('msg'))
                if msg.get('msg')=='no data from Arduino':
                    entry['uart_ok']=False
                    await self._status(device)
        except (ValueError,TypeError,KeyError):
            logging.debug('Skipping malformed line from %s',device)

    async def _send(self,device,command):
        entry=self.entries.get(device)
        if not entry or not entry['online']:
            raise ConnectionError(f'{device} is offline')
        await entry['send'](command)

    async def start(self,device):
        await self._send(device,'START')
        self.entries[device]['streaming']=True
        await self._status(device)

    async def stop(self,device):
        entry=self.entries.get(device)
        if entry:
            if entry['online']:
                try:
                    await self._send(device,'STOP')
                except Exception:
                    logging.debug('Could not stop disconnected device %s',device)
            entry['streaming']=False
            await self._status(device)

    async def disconnected(self,device,token):
        entry=self.entries.get(device)
        if entry and entry['token']==token:
            entry['online']=False
            await self._status(device)

    async def accept(self,socket):
        await socket.accept()
        device=None
        token=object()
        async def send(command):
            await socket.send_text(command)
        async def close():
            try:
                await socket.close()
            except RuntimeError:
                pass
        try:
            frame=await asyncio.wait_for(socket.receive_text(),timeout=5)
            lines=frame.splitlines()
            hello=json.loads(lines[0])
            if hello.get('t')!='hello':
                raise ValueError('First frame must be hello')
            hello['_address']=str(socket.client)
            device=await self.register(hello,'wifi',send,close,token)
            for line in lines[1:]:
                await self.ingest(device,line,token)
            while True:
                frame=await socket.receive_text()
                for line in frame.splitlines():
                    await self.ingest(device,line,token)
        except Exception:
            logging.debug('Device connection ended',exc_info=True)
        finally:
            if device:
                await self.disconnected(device,token)
            await close()

    async def _heartbeat(self):
        interval=self.config['serial']['ping_interval_s']
        while True:
            await asyncio.sleep(interval)
            for device,entry in list(self.entries.items()):
                if not entry['online']:
                    continue
                if time.monotonic()-entry['last_pong']>interval*self.config['serial']['offline_after_missed_pings']:
                    await self.disconnected(device,entry['token'])
                    await entry['close']()
                    continue
                try:
                    await self._send(device,'PING')
                except Exception:
                    await self.disconnected(device,entry['token'])

    async def _discover(self):
        while True:
            found=await asyncio.to_thread(list_ports.comports)
            ports=set(self.forced_ports)
            ports.update(p.device for p in found if 'arduino' in (p.description or '').lower() or p.vid in (0x2341,0x2A03))
            for port in ports:
                if port not in self.port_tasks or self.port_tasks[port].done():
                    self.port_tasks[port]=asyncio.create_task(self._serial(port))
            await asyncio.sleep(3)

    async def _serial(self,port):
        connection=None
        device=None
        token=object()
        try:
            connection=await asyncio.to_thread(serial.Serial,port,self.config['serial']['baud'],timeout=.5,write_timeout=1)
            async def send(command):
                await asyncio.to_thread(connection.write,(command+'\n').encode())
            async def close():
                connection.close()
            # Some boards reset on opening USB. Retry HELLO for a few seconds.
            for _ in range(8):
                await send('HELLO')
                raw=await asyncio.to_thread(connection.readline)
                try:
                    hello=json.loads(raw)
                    if hello.get('t')=='hello':
                        hello['_address']=port
                        device=await self.register(hello,'serial',send,close,token)
                        break
                except (ValueError,AttributeError):
                    pass
            if not device:
                return
            while True:
                raw=await asyncio.to_thread(connection.readline)
                if raw:
                    await self.ingest(device,raw.decode(errors='replace').strip(),token)
        except (serial.SerialException,OSError):
            logging.warning('%s unavailable. If it is in use, close the Arduino Serial Monitor and try again.',port)
        finally:
            if connection:
                connection.close()
            if device:
                await self.disconnected(device,token)

    async def close(self):
        for task in [*self.tasks,*self.port_tasks.values()]:
            task.cancel()
        for entry in list(self.entries.values()):
            await entry['close']()
        await asyncio.gather(*self.tasks,*self.port_tasks.values(),return_exceptions=True)
