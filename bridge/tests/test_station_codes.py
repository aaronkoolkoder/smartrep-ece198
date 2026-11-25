"""Station codes are phone-scannable web links; diagnostics explain why they cannot start."""
from fastapi.testclient import TestClient
from smartrep import network
from smartrep.api import create_app
from smartrep.station_codes import build_pdf, display_label, station_url


def test_station_links_and_labels():
    assert station_url('https://abc.trycloudflare.com/', 'db-5lb') == 'https://abc.trycloudflare.com/app?station=db-5lb'
    assert display_label('Dumbbells · 5 lb') == '5 lb Dumbbells'
    assert display_label('Kettlebell · 10 lb') == '10 lb Kettlebell'
    assert display_label('Movement glove') == 'Movement Glove'


def test_public_base_url_replaces_loopback(monkeypatch):
    monkeypatch.setattr(network, 'local_addresses', lambda: ['10.0.0.5', '127.0.0.1'])
    assert network.public_base_url('http://127.0.0.1:8000/') == 'http://10.0.0.5:8000'
    assert network.public_base_url('http://localhost:8001') == 'http://10.0.0.5:8001'
    assert network.public_base_url('https://abc.trycloudflare.com/app') == 'https://abc.trycloudflare.com'
    assert network.public_base_url('javascript:alert(1)') == 'http://10.0.0.5:8000'


def test_station_code_pdf_endpoint(tmp_path):
    assert build_pdf([{'id': 'db-5lb', 'label': 'Dumbbells · 5 lb'}], 'http://10.0.0.5:8000').startswith(b'%PDF')
    with TestClient(create_app(tmp_path / 'codes.db', True)) as client:
        response = client.get('/station-qr.pdf', params={'base': 'https://abc.trycloudflare.com'})
        assert response.status_code == 200
        assert response.headers['content-type'] == 'application/pdf'
        assert response.content.startswith(b'%PDF')


def test_diagnostics_reports_unplugged_station(tmp_path):
    with TestClient(create_app(tmp_path / 'offline.db', False)) as client:
        with client.websocket_connect('/diagnostics/live') as socket:
            message = socket.receive_json()
    assert message['connected'] is False
    assert message['code'] == 'DEVICE_OFFLINE'
    assert message['simulate'] is False
