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
                profile = manager.require_participant(db,participant)
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
                "started":time.monotonic(),"samples":[],"result":None,"progress":0,
                "display_name":profile["display_name"],"channels":{},"progress_signal":None}
            if hasattr(manager.source,"set_calibrating"):
                manager.source.set_calibrating(device["id"],True)
            try:
                await manager.source.start(device["id"])
            except Exception:
                manager.reserved.discard(device["id"])
                self.recordings.pop(identifier,None)
                raise SessionError("DEVICE_OFFLINE","Could not start this station.",503)
            await manager.show_display(device["id"],profile["display_name"],0,'cal')
            return {"calibration_id":identifier,"target":manager.config["calibration"]["reps_required"]}

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
                    # Lock the feedback axis after its first full cycle.
                    settings=self.sessions.config["calibration"]
                    for key,value in sample["signals"].items():
                        channel=state["channels"].setdefault(key,{
                            "initial":value,"low":value,"high":value,
                            "direction":None,"raised":False,"count":0,"last":None})
                        channel["low"]=min(channel["low"],value)
                        channel["high"]=max(channel["high"],value)
                        floor=settings["min_ref_range_deg" if key in ("pitch","roll") else "min_ref_range_g"]
                        span=channel["high"]-channel["low"]
                        if channel["direction"] is None and abs(value-channel["initial"])>=floor:
                            channel["direction"]=1 if value>channel["initial"] else -1
                        if span<floor or channel["direction"] is None:
                            continue
                        p=(value-channel["low"])/span
                        if channel["direction"]<0:
                            p=1-p
                        if p>.8:
                            channel["raised"]=True
                        if channel["raised"] and p<.2:
                            channel["raised"]=False
                            if channel["last"] is None or (sample["ms"]-channel["last"])/1000>=settings["min_cycle_s"]:
                                channel["count"]+=1
                                channel["last"]=sample["ms"]
                    if state["progress_signal"] is None:
                        candidates=[key for key,c in state["channels"].items() if c["count"]]
                        if candidates:
                            def score(key):
                                c=state["channels"][key]
                                angle=key in ("pitch","roll")
                                noise=settings["angle_noise_deg" if angle else "accel_noise_g"]
                                span=c["high"]-c["low"]
                                return (angle and span>=settings["prefer_angle_min_deg"],span/noise)
                            state["progress_signal"]=max(candidates,key=score)
                    key=state["progress_signal"]
                    count=state["channels"][key]["count"] if key else 0
                    if count!=state["progress"]:
                        state["progress"]=count
                        await self.sessions.show_display(device,state["display_name"],count,'cal')
                        await self.sessions.broadcast({"type":"calibration_progress","calibration_id":identifier,
                            "cycles_seen":count,"target":settings["reps_required"],"provisional":True},state["participant"])
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
            await manager.show_display(state["device"],state["display_name"],state["progress"],
                                       'cal_saved' if result['ok'] else 'cal_error')
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
