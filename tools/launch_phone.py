"""Start the hardware demo and a temporary phone link."""
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import time
import urllib.request
import webbrowser

ROOT = Path(__file__).resolve().parents[1]
LOCAL = ROOT / '.local'


def health():
    try:
        with urllib.request.urlopen('http://127.0.0.1:8000/api/health', timeout=1) as response:
            return json.load(response)
    except (OSError, ValueError):
        return None


def main():
    LOCAL.mkdir(exist_ok=True)
    executable = shutil.which('cloudflared') or str(LOCAL / 'cloudflared')
    if not Path(executable).is_file():
        print('Install cloudflared, then reopen this file: https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/downloads/')
        return 1
    server = tunnel = None
    try:
        current = health()
        if current and (current.get('simulate') or not current.get('small_movement_demo')):
            print('Another SmartRep mode is using port 8000. Stop it with Control+C, then reopen this file.')
            return 1
        if not current:
            server = subprocess.Popen([sys.executable, '-m', 'smartrep', '--small-movement-demo',
                                       '--db', 'smartrep-small-demo.db'], cwd=ROOT / 'bridge')
            for _ in range(60):
                if health():
                    break
                if server.poll() is not None:
                    raise RuntimeError('The server could not start.')
                time.sleep(.5)
            else:
                raise RuntimeError('The server did not respond on port 8000.')
        log_path = LOCAL / f'tunnel-{os.getpid()}.log'
        with log_path.open('w') as log:
            tunnel = subprocess.Popen([executable, 'tunnel', '--url', 'http://127.0.0.1:8000',
                                       '--protocol', 'http2', '--no-autoupdate'], stdout=log, stderr=log)
            url = None
            for _ in range(90):
                match = re.search(r'https://[a-z0-9-]+\.trycloudflare\.com', log_path.read_text())
                if match:
                    url = match.group() + '/app'
                    break
                if tunnel.poll() is not None:
                    raise RuntimeError(f'The phone tunnel failed. See {log_path}')
                time.sleep(.5)
            if not url:
                raise RuntimeError(f'No phone link was received. See {log_path}')
            import qrcode
            image = ROOT / 'output' / 'phone-connect.png'
            image.parent.mkdir(exist_ok=True)
            qrcode.make(url).save(image)
            print(f'\nPHONE LINK: {url}\n', flush=True)
            qr = qrcode.QRCode(border=1)
            qr.add_data(url)
            qr.print_ascii(invert=True)
            print('\nKeep this window open and the laptop awake. Press Control+C to stop.\n', flush=True)
            webbrowser.open(url)
            subprocess.Popen(['open', str(image)])
            while tunnel.poll() is None:
                if server and server.poll() is not None:
                    raise RuntimeError('The server stopped unexpectedly.')
                time.sleep(1)
            raise RuntimeError(f'The phone tunnel stopped. See {log_path}')
    except KeyboardInterrupt:
        print('\nSmartRep stopped.')
    except (OSError, RuntimeError) as error:
        print(f'\n{error}')
        return 1
    finally:
        for process in (tunnel, server):
            if process and process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
    return 0


if __name__ == '__main__':
    sys.exit(main())
