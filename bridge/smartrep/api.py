"""REST, WebSockets and application-owned source/session lifecycle."""
import asyncio
from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from pydantic import BaseModel
from typing import Literal
from .config import load_config
from .session import SessionManager, SessionError
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from .calibration import CalibrationManager
from .crowd import Crowd
from . import __version__
from .db import initialize, connect
from .seed import seed
from .sources.sim_source import SimSource
from .sources.hardware_source import HardwareSource
from fastapi.middleware.cors import CORSMiddleware


class StartSet(BaseModel):
    participant_id: str
    station_id: str
    exercise_id: str


class CalibrationBody(StartSet):
    pin: str


class CrowdBody(BaseModel):
    enabled: bool


class SimPattern(BaseModel):
    device_id: str
    pattern: Literal["good", "mixed", "stop_early"]


def create_app(db_path, simulate=False, config=None, crowd=False, ports=None):
    config = config or load_config()
    clients = {}

    async def broadcast(message, participant=None):
        async def send(socket):
            try:
                await asyncio.wait_for(socket.send_json(message), timeout=1)
            except Exception:
                clients.pop(socket, None)
        await asyncio.gather(*(send(socket) for socket, scope in list(clients.items())
                               if participant is None or scope == participant or scope == "dashboard"))
    path = Path(db_path)

    @asynccontextmanager
    async def lifespan(app):
        initialize(path)
        seed(path, simulate, config.get("devices", {}))
        app.state.samples_received = 0

        async def on_sample(device, sample):
            app.state.samples_received += 1
            await app.state.calibrations.sample(device, sample)
            await app.state.manager.sample(device, sample)

        app.state.source = SimSource(on_sample, config.get("signal", {}).get("sample_hz", 50)) if simulate else HardwareSource(on_sample, config, broadcast, ports)
        app.state.manager = SessionManager(path, app.state.source, broadcast, config)
        app.state.calibrations = CalibrationManager(app.state.manager)
        app.state.crowd = Crowd(app.state.manager)
        monitor = asyncio.create_task(app.state.manager.monitor())
        calibration_monitor = asyncio.create_task(app.state.calibrations.monitor())
        if not simulate:
            await app.state.source.open()
        if crowd and simulate:
            await app.state.crowd.set_enabled(True)
        try:
            yield
        finally:
            await app.state.crowd.set_enabled(False)
            calibration_monitor.cancel()
            monitor.cancel()
            await asyncio.gather(monitor, calibration_monitor, return_exceptions=True)
            await app.state.calibrations.close()
            for state in list(app.state.manager.active.values()):
                await app.state.manager.finish(state["set_id"], "disconnect")
            if app.state.source:
                await app.state.source.close()

    app = FastAPI(title="SmartRep bridge", version=__version__, lifespan=lifespan,
                  description="Student prototype with fake data: live sets, rep detection, progress and real-time events.")

    # Native Expo uses fetch directly; Expo web development can use localhost
    # on a different port. The deployed browser app uses same-origin requests.
    app.add_middleware(CORSMiddleware,allow_origin_regex=r"https?://(localhost|127\.0\.0\.1|10\.[0-9.]+|192\.168\.[0-9.]+|172\.(1[6-9]|2[0-9]|3[01])\.[0-9.]+)(:[0-9]+)?",allow_methods=["GET","POST"],allow_headers=["Content-Type"])

    def devices():
        return app.state.source.devices() if app.state.source else []

    @app.get("/api/health")
    def health():
        return {"ok": True, "version": __version__, "devices_online": sum(d["online"] for d in devices()),
                "simulate": simulate}

    @app.get("/api/devices")
    def device_list():
        return devices()

    @app.get("/api/participants/{participant_id}")
    def participant(participant_id: str):
        with connect(path) as db:
            row = db.execute("SELECT * FROM participants WHERE id=?", (participant_id,)).fetchone()
        if row is None:
            return JSONResponse(status_code=404, content={"error": {"code": "PARTICIPANT_NOT_FOUND",
                "message": "We couldn't find that ID. Check with staff."}})
        return dict(row)

    @app.get("/api/stations/{station_id}")
    def station(station_id: str):
        with connect(path) as db:
            row = db.execute("SELECT * FROM stations WHERE id=?", (station_id,)).fetchone()
        if row is None:
            return JSONResponse(status_code=404, content={"error": {"code": "STATION_NOT_FOUND",
                                                                    "message": "Station not found."}})
        result = dict(row)
        result["device"] = next((d for d in devices() if d["id"] == result["device_id"]), None)
        return result

    @app.exception_handler(SessionError)
    async def session_error(request, error):
        return JSONResponse(status_code=error.status, content={"error":{"code":error.code,"message":error.message}})

    @app.get("/api/participants/{participant_id}/today")
    def today(participant_id: str):
        return app.state.manager.today_data(participant_id)

    @app.get("/api/participants/{participant_id}/stations/{station_id}/exercises")
    def exercises_here(participant_id: str, station_id: str):
        station_data = station(station_id)
        if isinstance(station_data, JSONResponse):
            return station_data
        data = app.state.manager.today_data(participant_id)
        return [d for d in data["dose"] if d["equipment_type"] == station_data["equipment_type"]
                and d["load_lb"] == station_data["load_lb"]]

    @app.post("/api/sets", status_code=201)
    async def start_set(body: StartSet):
        return await app.state.manager.start(body.participant_id, body.station_id, body.exercise_id)

    @app.get("/api/sets/{set_id}")
    def set_detail(set_id: int):
        return app.state.manager.detail(set_id)

    @app.post("/api/sets/{set_id}/finish")
    async def finish_set(set_id: int):
        return await app.state.manager.finish(set_id)

    @app.post("/api/participants/{participant_id}/visits/{station_id}")
    async def visit(participant_id: str, station_id: str):
        return await app.state.manager.visit(participant_id, station_id)

    @app.post("/api/sim/pattern")
    async def sim_pattern(body: SimPattern):
        if not simulate:
            raise SessionError("SIMULATION_DISABLED","Simulator controls are unavailable in hardware mode.",404)
        try:
            app.state.source.set_pattern(body.device_id,body.pattern)
        except KeyError:
            raise SessionError("DEVICE_NOT_FOUND","Simulated station not found.",404)
        return {"ok":True}

    @app.post("/api/participants/{participant_id}/session/finish")
    async def end_session(participant_id: str):
        return await app.state.manager.end_session(participant_id)

    @app.get("/api/dashboard")
    async def dashboard():
        return {**app.state.manager.snapshot(), "crowd_running": app.state.crowd.running}

    @app.websocket("/ws")
    async def websocket(socket: WebSocket):
        participant = socket.query_params.get("participant")
        role = socket.query_params.get("role")
        if role != "dashboard":
            with connect(path) as db:
                if not participant or not db.execute("SELECT 1 FROM participants WHERE id=?",(participant,)).fetchone():
                    await socket.close(code=1008)
                    return
        await socket.accept()
        # Register before the snapshot so updates cannot fall through a gap.
        # A participant sees their own records; dashboards see the fake cohort.
        clients[socket] = "dashboard" if role == "dashboard" else participant
        try:
            snapshot = app.state.manager.snapshot() if role == "dashboard" else app.state.manager.today_data(participant)
            await socket.send_json({"type":"snapshot", "data":snapshot})
            while True:
                message = await socket.receive_json()
                if isinstance(message, dict) and message.get("type") == "ping":
                    await socket.send_json({"type":"pong"})
        except (WebSocketDisconnect, ValueError, RuntimeError):
            pass
        finally:
            clients.pop(socket,None)
            # The bridge keeps counting if a phone drops Wi-Fi. Reconnecting
            # clients receive persisted set counts in their initial snapshot.

    @app.get("/api/stations")
    def station_list():
        with connect(path) as db:
            rows = [dict(x) for x in db.execute("SELECT * FROM stations ORDER BY id")]
        for row in rows:
            row["device"] = next((d for d in devices() if d["id"] == row["device_id"]),None)
        return rows

    @app.post("/api/calibrations", status_code=201)
    async def start_calibration(body: CalibrationBody):
        return await app.state.calibrations.start(body.participant_id,body.exercise_id,body.station_id,body.pin)

    @app.post("/api/calibrations/{identifier}/done")
    async def finish_calibration(identifier: int):
        return await app.state.calibrations.done(identifier)

    @app.post("/api/sim/crowd")
    async def simulation_crowd(body: CrowdBody):
        if not simulate:
            raise SessionError("SIMULATION_DISABLED","Room simulation is unavailable in hardware mode.",404)
        await app.state.crowd.set_enabled(body.enabled)
        return {"ok":True,"crowd_running":app.state.crowd.running}

    @app.websocket("/device")
    async def device_socket(socket: WebSocket):
        if simulate:
            await socket.close(code=1008)
            return
        await app.state.source.accept(socket)

    @app.get("/sw.js",include_in_schema=False)
    async def service_worker():
        return FileResponse(Path(__file__).resolve().parents[1]/"static/sw.js",media_type="application/javascript",headers={"Cache-Control":"no-cache","Service-Worker-Allowed":"/"})

    @app.get("/station-qr.pdf", include_in_schema=False)
    async def station_qr():
        target=Path(__file__).resolve().parents[2]/"output/pdf/station_qr_codes.pdf"
        if not target.exists():
            raise SessionError("QR_NOT_GENERATED","Run tools/make_qr.py first.",404)
        return FileResponse(target,media_type="application/pdf",filename="SmartRep_station_QR_codes.pdf")

    # Expo's exported web build is an additional way to inspect the native
    # participant screens. The primary browser experience remains at /.
    phone=Path(__file__).resolve().parents[2]/"app/dist"
    if phone.exists():
        if (phone/"_expo").exists():
            app.mount("/_expo",StaticFiles(directory=phone/"_expo"),name="expo-build")
        if (phone/"assets").exists():
            app.mount("/assets",StaticFiles(directory=phone/"assets"),name="expo-assets")
        @app.get("/phone",include_in_schema=False)
        async def phone_preview():
            return FileResponse(phone/"index.html")

    static = Path(__file__).resolve().parents[1] / "static"
    app.mount("/static",StaticFiles(directory=static),name="static")

    @app.get("/",include_in_schema=False)
    async def welcome():
        return FileResponse(static / "welcome.html")

    @app.get("/app", include_in_schema=False)
    @app.get("/dashboard", include_in_schema=False)
    async def ui():
        return FileResponse(static / "index.html")

    return app
