"""Keep software tests from opening connected physical Arduinos."""
import pytest


@pytest.fixture(autouse=True)
def isolate_usb_discovery(monkeypatch):
    # Tests must not open real USB devices.
    monkeypatch.setattr('smartrep.sources.hardware_source.list_ports.comports',lambda: [])
