"""Exclusive live input checks, using the bridge's existing device connection."""
import asyncio
import time
from .session import SessionError


class DiagnosticViews:
    def __init__(self,manager):
        self.manager=manager
        self.views={}

    async def open(self,device,socket):
        async with self.manager.lock:
            source=self.manager.source
            entry=next((d for d in source.devices() if d['id']==device and d['online']),None)
            if not entry:
                raise SessionError('DEVICE_OFFLINE','Connect the Arduino and close Serial Monitor.',503)
            if not hasattr(source,'start_diagnostics') or entry['sensor']!='mpu6050':
                raise SessionError('DIAGNOSTICS_UNAVAILABLE','Live raw diagnostics require the MPU hardware firmware.',422)
            if device in self.manager.active or device in self.manager.reserved:
                raise SessionError('STATION_BUSY','Finish the current set or calibration before testing raw inputs.')
            self.manager.reserved.add(device)
            view={'socket':socket,'frames':0,'last_ms':None}
            self.views[device]=view
            try:
                await source.start_diagnostics(device)
            except Exception:
                self.views.pop(device,None)
                self.manager.reserved.discard(device)
                raise SessionError('DEVICE_OFFLINE','Could not start raw readings.',503)
            return view

    async def sample(self,device,sample):
        view=self.views.get(device)
        if not view or not sample.get('diagnostic'):
            return
        if view['last_ms'] is not None and sample['ms']-view['last_ms']<100:
            return
        view['last_ms']=sample['ms']
        entry=next((d for d in self.manager.source.devices() if d['id']==device),{})
        try:
            if sample.get('read_ok') is False:
                await asyncio.wait_for(view['socket'].send_json({'connected':entry.get('online',False),'frames':view['frames'],
                    'read_error':True,'message':'MPU register read failed — check wiring or power-cycle.',
                    'sensor_ok':False,'lcd_ok':entry.get('lcd_ok'),'port':entry.get('address',''),'sample':None}),timeout=1)
                return
            view['frames']+=1
            await asyncio.wait_for(view['socket'].send_json({'connected':entry.get('online',False),
                'message':'Live raw readings','frames':view['frames'],'sensor_ok':entry.get('sensor_ok'),
                'lcd_ok':entry.get('lcd_ok'),'port':entry.get('address','Wi-Fi'),
                'sample':{'time':time.time(),**{key:sample[key] for key in ('ax','ay','az','gx','gy','gz')},
                          'bytes':sample.get('raw_bytes',[])}}),timeout=1)
        except Exception:
            await self.close(device,view)

    async def close(self,device,view):
        async with self.manager.lock:
            if self.views.get(device) is not view:
                return
            self.views.pop(device,None)
            try:
                await self.manager.source.stop(device)
            finally:
                self.manager.reserved.discard(device)

    async def close_all(self):
        for device,view in list(self.views.items()):
            await self.close(device,view)
