"""Local network addresses for printed links and phone access."""
import socket
from urllib.parse import urlsplit


def local_addresses():
    addresses = {"127.0.0.1"}
    try:
        addresses.update(socket.gethostbyname_ex(socket.gethostname())[2])
        # UDP connect chooses a default interface without sending a packet.
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as probe:
            probe.connect(("192.0.2.1", 80))
            addresses.add(probe.getsockname()[0])
    except OSError:
        pass
    return sorted(addresses, key=lambda ip: (ip.startswith("127."), ip))


def public_base_url(candidate, fallback_port=8000):
    """Origin that a phone can open: keep real hosts, replace loopback with the LAN address."""
    parts = urlsplit(str(candidate or ""))
    if parts.scheme not in ("http", "https") or not parts.hostname:
        parts = urlsplit(f"http://127.0.0.1:{fallback_port}")
    host = parts.hostname
    if host in ("localhost", "127.0.0.1", "::1", "0.0.0.0"):
        host = local_addresses()[0]
    port = f":{parts.port}" if parts.port else ""
    return f"{parts.scheme}://{host}{port}"
