"""Print two station labels per Letter page; no bridge needs to be running."""
import argparse
from io import BytesIO
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'bridge'))
from smartrep.seed import STATIONS
from smartrep.db import connect
import qrcode
from reportlab.lib.colors import HexColor
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter


def generate(output,stations):
    output=Path(output);output.mkdir(parents=True,exist_ok=True)
    pdf=canvas.Canvas(str(output/'station_qr_codes.pdf'),pagesize=letter)
    pdf.setTitle('SmartRep station QR codes')
    for index,station in enumerate(stations):
        if index and index%2==0:
            pdf.showPage()
        y=792-(index%2)*396
        pdf.setFillColor(HexColor('#173c36'))
        pdf.setFont('Helvetica-Bold',20);pdf.drawString(38,y-32,'smartrep.')
        pdf.setFont('Helvetica',13);pdf.drawRightString(574,y-30,'SCAN & LIFT')
        label=station['label'].replace('·','-')
        pdf.setFont('Helvetica-Bold',22);pdf.drawCentredString(306,y-65,label)
        image=qrcode.make('smartrep://station/'+station['id'])
        image.save(output/f"qr_{station['id']}.png")
        buffer=BytesIO();image.save(buffer,format='PNG');buffer.seek(0)
        # 8 cm = 226.8 points, with the QR's own quiet zone preserved.
        pdf.drawImage(ImageReader(buffer),192.6,y-308,width=226.8,height=226.8)
        pdf.setFont('Helvetica',12);pdf.drawCentredString(306,y-331,'Open SmartRep and scan this station to begin.')
        pdf.setFont('Helvetica',10);pdf.drawCentredString(306,y-352,station['id']+'  |  Student prototype - fake data only')
        pdf.setStrokeColor(HexColor('#dce4dc'));pdf.line(30,y-385,582,y-385)
    pdf.save()
    return output/'station_qr_codes.pdf'


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--db',type=Path)
    parser.add_argument('--from-seed',action='store_true')
    parser.add_argument('--output',type=Path,default=Path(__file__).resolve().parents[1]/'output/pdf')
    args=parser.parse_args()
    if args.db and not args.from_seed:
        with connect(args.db) as db:
            stations=[dict(s) for s in db.execute('SELECT id,label FROM stations ORDER BY id')]
    else:
        stations=[{'id':s[0],'label':s[1]} for s in STATIONS]
    print(generate(args.output,stations))

if __name__=='__main__':
    main()
