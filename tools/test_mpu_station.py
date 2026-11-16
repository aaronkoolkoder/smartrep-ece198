"""USB check for the MPU/LCD/D2 sketch. Close the bridge and Serial Monitor first."""
import argparse
import json
import time
import serial


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('port')
    args=parser.parse_args()
    with serial.Serial(args.port,115200,timeout=.5,write_timeout=1) as port:
        hello=None
        for _ in range(12):
            port.write(b'HELLO\n')
            try:
                message=json.loads(port.readline())
            except (ValueError,UnicodeDecodeError):
                continue
            if message.get('t')=='hello':
                hello=message
                break
        if not hello:
            raise SystemExit('No SmartRep firmware reply.')
        print(json.dumps(hello,indent=2))
        if hello.get('sensor')!='mpu6050' or not hello.get('sensor_ok'):
            raise SystemExit('MPU not ready. Check SDA/SCL, supply and solder joints.')
        if not hello.get('lcd_ok'):
            raise SystemExit('LCD not detected. Check its I2C wiring.')
        port.write(b'TEST\nSTART\n')
        samples=[]
        deadline=time.monotonic()+3
        try:
            while time.monotonic()<deadline:
                try:
                    message=json.loads(port.readline())
                except (ValueError,UnicodeDecodeError):
                    continue
                if message.get('t')=='s':
                    samples.append(message)
        finally:
            port.write(b'STOP\n')
        if len(samples)<50:
            raise SystemExit(f'Only {len(samples)} samples received. Check sensor/bus.')
        keys=('ax','ay','az','gx','gy','gz')
        if not all(all(key in sample for key in keys) for sample in samples):
            raise SystemExit('Incomplete sensor readings.')
        print(f'PASS: {len(samples)} MPU samples received.')
        print('First reading:',json.dumps(samples[0]))
        print('Confirm on hardware: LCD says LCD test OK; buzzer made a short beep on D2.')


if __name__=='__main__':
    main()
