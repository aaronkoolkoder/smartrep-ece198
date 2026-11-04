"""Run from bridge/: python -m smartrep --simulate."""
import asyncio
import argparse
import logging
from pathlib import Path
import socket
import tomllib
import qrcode
import uvicorn
from .api import create_app


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


def main():
    parser = argparse.ArgumentParser(description="SmartRep student prototype bridge (simulation + hardware)")
    parser.add_argument("--simulate", action="store_true", help="Register five simulated MPU-6050 devices")
    parser.add_argument("--port",action="append",default=[],help="Force a USB serial port (repeatable)")
    parser.add_argument("--crowd",action="store_true",help="Run virtual participants (requires --simulate)")
    parser.add_argument("--host", default=None)
    parser.add_argument("--http-port", type=int, default=None)
    parser.add_argument("--config", type=Path, default=Path(__file__).resolve().parents[1] / "config.toml")
    parser.add_argument("--db", type=Path, default=Path("smartrep.db"))
    parser.add_argument("--reset-db", action="store_true", help="Delete the local demo DB and re-seed")
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()
    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO)
    config = tomllib.loads(args.config.read_text()) if args.config.exists() else {}
    host = args.host or config.get("server", {}).get("host", "0.0.0.0")
    port = args.http_port or config.get("server", {}).get("port", 8000)
    if not 1 <= port <= 65535:
        parser.error("--http-port must be between 1 and 65535")
    if args.reset_db:
        args.db.unlink(missing_ok=True)
    addresses = local_addresses() if host == "0.0.0.0" else [host]
    print("\nSmartRep bridge running · Scan & Lift · fake data only", flush=True)
    for ip in addresses:
        print(f"  Bridge: http://{ip}:{port}  |  API docs: http://{ip}:{port}/docs", flush=True)
    print(f"  Devices: {'five simulated clips' if args.simulate else 'Wi-Fi devices + USB auto-detection'}")
    print(f"  App: http://{addresses[0]}:{port}/  |  Dashboard: http://{addresses[0]}:{port}/dashboard")
    print("  Connection QR (bridge URL):")
    qr = qrcode.QRCode(border=1)
    qr.add_data(f"http://{addresses[0]}:{port}")
    qr.print_ascii(invert=True)
    async def serve():
        from .discovery import advertise
        publisher=await advertise(addresses,port)
        try:
            server=uvicorn.Server(uvicorn.Config(create_app(args.db,args.simulate,config,crowd=args.crowd,ports=args.port),host=host,port=port,log_level="debug" if args.verbose else "info"))
            await server.serve()
        finally:
            if publisher:
                await publisher.async_unregister_all_services()
                await publisher.async_close()
    try:
        asyncio.run(serve())
    except KeyboardInterrupt:
        pass
