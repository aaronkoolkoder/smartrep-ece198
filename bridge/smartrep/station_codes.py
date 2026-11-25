"""Printable station codes: QR links that open SmartRep at a station.

Each code is an ordinary web link (for example
http://10.0.0.5:8000/app?station=db-5lb), so a phone's built-in Camera app
can open it directly. Labels use the app's typography.
"""
from io import BytesIO
from pathlib import Path
from urllib.parse import quote

from reportlab.graphics import renderPDF
from reportlab.graphics.barcode.qr import QrCodeWidget
from reportlab.graphics.shapes import Drawing
from reportlab.lib.colors import HexColor
from reportlab.lib.pagesizes import letter
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas

FONTS = Path(__file__).resolve().parents[1] / "static" / "fonts"
INK, MUTED, LINE = HexColor("#383139"), HexColor("#6b6270"), HexColor("#e8e3ec")


def station_url(base_url, station_id):
    return f"{str(base_url).rstrip('/')}/app?station={quote(str(station_id))}"


def display_label(label):
    """'Dumbbells · 5 lb' -> '5 lb Dumbbells'; 'Movement glove' -> 'Movement Glove'."""
    name, _, load = str(label).partition("·")
    text = f"{load.strip()} {name.strip()}" if load.strip() else name.strip()
    return " ".join(w if w in ("lb", "kg") or w[:1].isdigit() else w[:1].upper() + w[1:] for w in text.split())


def _fonts():
    try:
        for name, weight in (("SmartRep", 400), ("SmartRep-Bold", 700)):
            if name not in pdfmetrics.getRegisteredFontNames():
                pdfmetrics.registerFont(TTFont(name, str(FONTS / f"instrument-{weight}.ttf")))
        return "SmartRep", "SmartRep-Bold"
    except Exception:
        return "Helvetica", "Helvetica-Bold"


def _qr(pdf, value, x, y, size):
    widget = QrCodeWidget(value, barLevel="M")
    left, bottom, right, top = widget.getBounds()
    drawing = Drawing(size, size, transform=[size / (right - left), 0, 0, size / (top - bottom), 0, 0])
    drawing.add(widget)
    renderPDF.draw(drawing, pdf, x, y)


def build_pdf(stations, base_url):
    """Two station labels per US Letter page; returns PDF bytes."""
    regular, bold = _fonts()
    buffer = BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=letter)
    pdf.setTitle("SmartRep Station Codes")
    width, height = letter
    for index, station in enumerate(stations):
        if index and index % 2 == 0:
            pdf.showPage()
        top = height - (index % 2) * (height / 2)
        pdf.setFillColor(INK)
        pdf.setFont(bold, 18)
        pdf.drawString(40, top - 42, "smartrep.")
        pdf.setFillColor(MUTED)
        pdf.setFont(regular, 11)
        pdf.drawRightString(width - 40, top - 40, "Station Code")
        pdf.setFillColor(INK)
        pdf.setFont(bold, 26)
        pdf.drawCentredString(width / 2, top - 86, display_label(station["label"]))
        size = 214
        _qr(pdf, station_url(base_url, station["id"]), (width - size) / 2, top - 112 - size, size)
        pdf.setFont(bold, 17)
        pdf.drawCentredString(width / 2, top - 350, station["id"].upper(), charSpace=1.5)
        pdf.setFillColor(MUTED)
        pdf.setFont(regular, 12)
        pdf.drawCentredString(width / 2, top - 370, "Scan With Your Phone Camera or Enter the Code in SmartRep")
        if index % 2 == 0:
            pdf.setStrokeColor(LINE)
            pdf.line(40, height / 2, width - 40, height / 2)
    pdf.save()
    return buffer.getvalue()
