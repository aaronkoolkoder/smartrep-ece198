"""Exclusive, staff-guided recordings using the same signal pipeline as sets."""
import asyncio
import hmac
import time
from .db import connect, utc_now
from .orientation import SignalPipeline
from .reps import Calibrator, CalibrationError
from .session import SessionError


class CalibrationManager:
    def __init__(self, sessions):
        self.sessions = sessions
        self.recordings = {}
        self.next_id = 1

    async def start(self, participant, exercise, station_id, pin):
        manager = self.sessions
        if not hmac.compare_digest(str(pin),str(manager.config["server"]["staff_pin"])):
            raise SessionError("INVALID_PIN","That PIN doesn't match. Ask staff.",403)
        async with manager.lock:
            with connect(manager.path) as db:
                manager.require_participant(db,participant)
                station = db.execute("SELECT * FROM stations WHERE id=?",(station_id,)).fetchone()
                dose = db.execute("SELECT d.*,e.equipment_type FROM doses d JOIN exercises e ON e.id=d.exercise_id WHERE participant_id=? AND exercise_id=?",(participant,exercise)).fetchone()
                if not station:
                    raise SessionError("STATION_NOT_FOUND","Station not found.",404)
                if not dose:
                    raise SessionError("NOT_IN_DOSE","Exercise is not in the participant's plan.",422)
                if dose["equipment_type"] != station["equipment_type"] or dose["load_lb"] != station["load_lb"]:
                    raise SessionError("WRONG_EQUIPMENT","Choose the prescribed equipment and load.",422)
            device = next((d for d in manager.devices() if d["id"] == station["device_id"] and d["online"]),None)
            if not device:
                raise SessionError("DEVICE_OFFLINE","Station disconnected, ask staff.",503)
            if device["id"] in manager.active or device["id"] in manager.reserved:
                raise SessionError("STATION_BUSY","Station is in use. Finish the current set or calibration first.")
            identifier = self.next_id
            self.next_id += 1
            manager.reserved.add(device["id"])
            self.recordings[identifier] = {"device":device["id"],"participant":participant,"exercise":exercise,
                "pipeline":SignalPipeline(device["units"],manager.config),"calibrator":Calibrator(manager.config),
                "started":time.monotonic(),"samples":[],"result":None,"progress":0}
            if hasattr(manager.source,"set_calibrating"):
                manager.source.set_calibrating(device["id"],True)
            try:
                await manager.source.start(device["id"])
            except Exception:
                manager.reserved.discard(device["id"])
                self.recordings.pop(identifier,None)
                raise SessionError("DEVICE_OFFLINE","Could not start this station.",503)
            return {"calibration_id":identifier}

    async def sample(self,device,raw):
        for identifier,state in list(self.recordings.items()):
            if state["device"] != device or state["result"] is not None:
                continue
            try:
                sample = state["pipeline"].update(raw)
                if sample["gap"]:
                    raise CalibrationError("Sensor gap during calibration; check the cable and try again.")
                if sample["ready"]:
                    state["calibrator"].add(sample["ms"],sample["signals"])
                    # A provisional peak count is feedback only; finish() makes
                    # the validated signal choice and computes the reference.
                    value=sample["signals"].get("pitch",sample["signals"].get("y",0))
                    state["samples"].append(value)
                    values=state["samples"]
                    if len(values)>2:
                        span=max(values)-min(values)
                        if span>25:
                            p=(value-min(values))/span
                            if p>.8:
                                state["raised"]=True
                            if state.get("raised") and p<.2:
                                state["raised"]=False
                                state["progress"]+=1
                                await self.sessions.broadcast({"type":"calibration_progress","calibration_id":identifier,"cycles_seen":state["progress"]},state["participant"])
            except (ValueError,KeyError,TypeError) as error:
                state["failure"]=str(error)

    async def done(self,identifier):
        state=self.recordings.get(identifier)
        if state is None:
            raise SessionError("CALIBRATION_NOT_FOUND","Calibration not found.",404)
        if state["result"] is not None:
            return state["result"]
        manager=self.sessions
        async with manager.lock:
            await manager.source.stop(state["device"])
            manager.reserved.discard(state["device"])
            if hasattr(manager.source,"set_calibrating"):
                manager.source.set_calibrating(state["device"],False)
            try:
                if state.get("failure"):
                    raise CalibrationError(state["failure"])
                ref=state["calibrator"].finish()
                with connect(manager.path) as db:
                    db.execute("INSERT OR REPLACE INTO rep_references VALUES (?,?,?,?,?,?,?,?,?,?)",(state["participant"],state["exercise"],ref.signal,ref.units,ref.ref_low,ref.ref_high,ref.ref_duration_s,ref.direction,state["device"],utc_now()))
                result={"ok":True,"signal":ref.signal,"units":ref.units,"ref_low":ref.ref_low,"ref_high":ref.ref_high,"ref_duration_s":ref.ref_duration_s,"direction":ref.direction}
            except CalibrationError as error:
                result={"ok":False,"reason":str(error)}
            state["result"]=result
            await manager.broadcast({"type":"calibration_done","calibration_id":identifier,**result},state["participant"])
            return result

    async def monitor(self):
        while True:
            await asyncio.sleep(.5)
            for identifier,state in list(self.recordings.items()):
                if state["result"] is None and time.monotonic()-state["started"] >= self.sessions.config["calibration"]["max_seconds"]:
                    await self.done(identifier)

    async def close(self):
        for identifier,state in list(self.recordings.items()):
            if state["result"] is None:
                await self.done(identifier)
