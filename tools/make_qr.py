"""Print station codes (two per Letter page) as phone-scannable web links.

The running app also serves these at /station-qr.pdf for whatever address the
browser is using; this script is for printing ahead of time.
"""
import argparse
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'bridge'))
from smartrep.seed import STATIONS
from smartrep.db import connect
from smartrep.network import public_base_url
from smartrep.station_codes import build_pdf, station_url


def generate(output,stations,base_url):
    output=Path(output);output.mkdir(parents=True,exist_ok=True)
    target=output/'station_qr_codes.pdf'
    target.write_bytes(build_pdf(stations,base_url))
    try:
        import qrcode
        for station in stations:
            qrcode.make(station_url(base_url,station['id'])).save(output/f"qr_{station['id']}.png")
    except ImportError:
        pass
    return target


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--db',type=Path)
    parser.add_argument('--from-seed',action='store_true')
    parser.add_argument('--base-url',help='Address phones will open, e.g. http://192.168.1.20:8000 or a phone-link URL (default: this computer on port 8000)')
    parser.add_argument('--output',type=Path,default=Path(__file__).resolve().parents[1]/'output/pdf')
    args=parser.parse_args()
    if args.db and not args.from_seed:
        with connect(args.db) as db:
            stations=[dict(s) for s in db.execute('SELECT id,label FROM stations ORDER BY id')]
    else:
        stations=[{'id':s[0],'label':s[1]} for s in STATIONS]
    base=public_base_url(args.base_url or 'http://127.0.0.1:8000')
    print(f'Station codes open {base}/app')
    print(generate(args.output,stations,base))

if __name__=='__main__':
    main()
