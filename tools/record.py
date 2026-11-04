"""Record raw USB samples for replay. Close the bridge/Serial Monitor first."""
import argparse
import csv
from datetime import datetime
import json
from pathlib import Path
import re
import sys
import time
import serial
from serial.tools import list_ports
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'bridge'))
from smartrep.units import convert


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    group=parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--port')
    group.add_argument('--device')
    parser.add_argument('--seconds',type=float,default=30)
    parser.add_argument('--label',default='curls_good')
    parser.add_argument('--output',type=Path,default=Path(__file__).resolve().parents[1]/'bridge/recordings')
    args=parser.parse_args()
    if not 0<args.seconds<=300:
        parser.error('--seconds must be between 0 and 300')
    ports=[args.port] if args.port else [p.device for p in list_ports.comports() if p.vid in (0x2341,0x2A03) or 'arduino' in p.description.lower()]
    connection=None;hello=None
    for port in ports:
        candidate=None
        try:
            candidate=serial.Serial(port,115200,timeout=.5,write_timeout=1)
            for _ in range(8):
                candidate.write(b'HELLO\n')
                try:
                    message=json.loads(candidate.readline())
                    if message.get('t')=='hello' and (not args.device or message.get('device')==args.device):
                        connection,hello=candidate,message
                        break
                except (ValueError,AttributeError):
                    pass
            if connection:
                break
        except serial.SerialException:
            pass
        if candidate:
            candidate.close()
    if not connection:
        parser.exit(1,'Arduino not found or port is busy. Close the bridge and Arduino Serial Monitor, then retry.\n')
    fields=['ms','ax','ay','az','gx','gy','gz'] if hello['units'].startswith('mpu6050') else ['ms','x','y','z']
    args.output.mkdir(parents=True,exist_ok=True)
    label=re.sub(r'[^A-Za-z0-9_-]','_',args.label)
    target=args.output/f"{label}_{datetime.now():%Y%m%d_%H%M%S}.csv"
    print('Hold still for the first half-second, then move. Recording',hello['device'])
    try:
        with target.open('w',newline='') as stream:
            writer=csv.DictWriter(stream,fieldnames=fields+['label','device','units'])
            writer.writeheader();connection.write(b'START\n');end=time.monotonic()+args.seconds;last_ping=0
            while time.monotonic()<end:
                if time.monotonic()-last_ping>3:
                    connection.write(b'PING\n');last_ping=time.monotonic()
                try:
                    message=json.loads(connection.readline())
                    if message.get('t')=='s':
                        convert(message,hello['units'])  # validate before saving
                        writer.writerow({**{k:message[k] for k in fields},'label':label,'device':hello['device'],'units':hello['units']})
                except (ValueError,KeyError,TypeError):
                    continue
    finally:
        try:connection.write(b'STOP\n')
        finally:connection.close()
    print(target)

if __name__=='__main__':
    main()
