"""Exclusive, staff-guided recordings using the same signal pipeline as sets."""
import asyncio
import hmac
import time
import json
import logging
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
            with connect(manager.path) as db:
                identifier=db.execute("INSERT INTO calibration_runs(participant_id,exercise_id,device_id,started_at) VALUES (?,?,?,?)",
                    (participant,exercise,device['id'],utc_now())).lastrowid
            manager.reserved.add(device["id"])
            self.recordings[identifier] = {"device":device["id"],"participant":participant,"exercise":exercise,
                "pipeline":SignalPipeline(device["units"],manager.config),"calibrator":Calibrator(manager.config),
                "started":time.monotonic(),"samples":[],"result":None,"progress":0,
                "diagnostic":device.get("sensor_ok") is False,"last_graph_ms":-1000,
                "display_name":profile["display_name"],"reference":None,"last_sample_at":time.monotonic(),"last_progress_ms":-1000}
            if hasattr(manager.source,"set_calibrating"):
                manager.source.set_calibrating(device["id"],True)
            try:
                if self.recordings[identifier]['diagnostic'] and hasattr(manager.source,'start_diagnostics'):
                    await manager.source.start_diagnostics(device['id'])
                else:
                    await manager.source.start(device["id"])
            except Exception:
                manager.reserved.discard(device["id"])
                self.recordings.pop(identifier,None)
                if hasattr(manager.source,'set_calibrating'):
                    manager.source.set_calibrating(device['id'],False)
                with connect(manager.path) as db:
                    db.execute("UPDATE calibration_runs SET ended_at=?,status='failed',result_json=? WHERE id=?",
                        (utc_now(),json.dumps({'ok':False,'reason':'Could not start this station.'}),identifier))
                raise SessionError("DEVICE_OFFLINE","Could not start this station.",503)
            await manager.show_display(device["id"],profile["display_name"],0,'cal')
            return {"calibration_id":identifier,"target":manager.config["calibration"]["reps_required"],"diagnostic":self.recordings[identifier]["diagnostic"]}

    async def sample(self,device,raw):
        async with self.sessions.lock:
            await self._sample(device,raw)

    async def _sample(self,device,raw):
        for identifier,state in list(self.recordings.items()):
            if state["device"] != device or state["result"] is not None or state.get("reference") or state.get("failure"):
                continue
            try:
                state["last_sample_at"]=time.monotonic()
                if raw.get("read_ok") is False:
                    raise CalibrationError("Sensor read failed. Check wiring and start calibration again.")
                ms=int(raw['ms'])
                if ms-state['last_graph_ms']>=100:
                    state['last_graph_ms']=ms
                    keys=('ax','ay','az','gx','gy','gz') if 'ax' in raw else ('x','y','z')
                    channels={key:float(raw[key]) for key in keys}
                    import math
                    if not all(math.isfinite(value) for value in channels.values()):
                        raise ValueError('Invalid graph sample')
                    diagnostic=bool(raw.get('diagnostic') or state['diagnostic'])
                    with connect(self.sessions.path) as db:
                        db.execute("INSERT INTO motion_samples(participant_id,exercise_id,phase,run_id,sample_ms,channels_json,units,diagnostic,captured_at) VALUES (?,?,?,?,?,?,?,?,?)",
                            (state['participant'],state['exercise'],'calibration',identifier,ms,json.dumps(channels),'raw counts',int(diagnostic),utc_now()))
                    await self.sessions.broadcast({'type':'calibration_signal','calibration_id':identifier,'ms':ms,
                        'channels':channels,'diagnostic':diagnostic,'units':'raw counts'},state['participant'])
                if raw.get('diagnostic') or state['diagnostic']:
                    continue
                sample = state["pipeline"].update(raw)
                if sample["gap"]:
                    raise CalibrationError("Sensor gap during calibration; check the cable and try again.")
                if sample["ready"]:
                    state["calibrator"].add(sample["ms"],sample["signals"])
                    if ms-state["last_progress_ms"]<100:
                        continue
                    state["last_progress_ms"]=ms
                    progress=state["calibrator"].progress()
                    count=progress["count"]
                    ready=progress["reference"] is not None
                    if count>=self.sessions.config["calibration"]["reps_required"] and not ready:
                        state["failure"]=progress["reason"]
                        continue
                    if ready:
                        # Freeze the validated three cycles. Reaching for Save,
                        # more movements or a later unplug cannot change them.
                        state["reference"]=progress["reference"]
                    if count!=state["progress"] or ready:
                        state["progress"]=count
                        await self.sessions.show_display(device,state["display_name"],count,'cal_ready' if ready else 'cal')
                        await self.sessions.broadcast({"type":"calibration_progress","calibration_id":identifier,
                            "cycles_seen":count,"target":self.sessions.config["calibration"]["reps_required"],
                            "ready":ready,"provisional":not ready,
                            "message":"Three reps captured. Save reference." if ready else progress["reason"]},state["participant"])
            except (ValueError,KeyError,TypeError) as error:
                state["failure"]=str(error)

    def status(self,identifier):
        state=self.recordings.get(identifier)
        if state is None:
            raise SessionError("CALIBRATION_NOT_FOUND","Calibration not found.",404)
        return {"calibration_id":identifier,"cycles_seen":state["progress"],
                "target":self.sessions.config["calibration"]["reps_required"],
                "ready":state.get("reference") is not None,"result":state["result"],
                "failure":state.get("failure"),"diagnostic":state["diagnostic"]}

    async def done(self,identifier):
        state=self.recordings.get(identifier)
        if state is None:
            raise SessionError("CALIBRATION_NOT_FOUND","Calibration not found.",404)
        if state["result"] is not None:
            return state["result"]
        manager=self.sessions
        async with manager.lock:
            if state["result"] is not None:
                return state["result"]
            try:
                await asyncio.wait_for(manager.source.stop(state["device"]),timeout=2)
            except Exception:
                logging.warning("Could not stop calibration stream for %s",state["device"],exc_info=True)
                if not state.get("reference"):
                    state["failure"]="Station disconnected before calibration completed. Reconnect and try again."
            finally:
                manager.reserved.discard(state["device"])
            if hasattr(manager.source,"set_calibrating"):
                manager.source.set_calibrating(state["device"],False)
            try:
                if state['diagnostic']:
                    raise CalibrationError('Diagnostic readings only: restore successful sensor reads before saving a movement reference.')
                if state.get("failure"):
                    raise CalibrationError(state["failure"])
                ref=state.get("reference") or state["calibrator"].finish()
                with connect(manager.path) as db:
                    db.execute("INSERT OR REPLACE INTO rep_references VALUES (?,?,?,?,?,?,?,?,?,?)",(state["participant"],state["exercise"],ref.signal,ref.units,ref.ref_low,ref.ref_high,ref.ref_duration_s,ref.direction,state["device"],utc_now()))
                result={"ok":True,"signal":ref.signal,"units":ref.units,"ref_low":ref.ref_low,"ref_high":ref.ref_high,"ref_duration_s":ref.ref_duration_s,"direction":ref.direction}
            except CalibrationError as error:
                result={"ok":False,"reason":str(error)}
            with connect(manager.path) as db:
                db.execute("UPDATE calibration_runs SET ended_at=?,status=?,result_json=? WHERE id=?",
                    (utc_now(),'saved' if result['ok'] else 'failed',json.dumps(result),identifier))
            state["result"]=result
            await manager.show_display(state["device"],state["display_name"],state["progress"],
                                       'cal_saved' if result['ok'] else 'cal_error')
            await manager.broadcast({"type":"calibration_done","calibration_id":identifier,**result},state["participant"])
            return result

    async def cancel(self,identifier):
        manager=self.sessions
        async with manager.lock:
            state=self.recordings.get(identifier)
            if state is None:
                raise SessionError("CALIBRATION_NOT_FOUND","Calibration not found.",404)
            if state["result"] is not None:
                return state["result"]
            result={"ok":False,"cancelled":True,"reason":"Calibration cancelled."}
            # Mark finished before awaiting transport so late samples cannot enter it.
            state["result"]=result
            try:
                await asyncio.wait_for(manager.source.stop(state["device"]),timeout=2)
            except Exception:
                logging.warning("Could not stop cancelled stream for %s",state["device"],exc_info=True)
            finally:
                manager.reserved.discard(state["device"])
                if hasattr(manager.source,"set_calibrating"):
                    manager.source.set_calibrating(state["device"],False)
                with connect(manager.path) as db:
                    db.execute("UPDATE calibration_runs SET ended_at=?,status='cancelled',result_json=? WHERE id=?",
                        (utc_now(),json.dumps(result),identifier))
            await manager.broadcast({"type":"calibration_done","calibration_id":identifier,**result},state["participant"])
            return result

    async def check_timeouts(self):
        for identifier,state in list(self.recordings.items()):
            if state["result"] is not None:
                continue
            now=time.monotonic()
            if not state.get("reference") and now-state["last_sample_at"]>=5:
                state["failure"]="No live sensor readings for 5 seconds. Check wiring and reconnect before retrying."
            if state.get("failure") or now-state["started"]>=self.sessions.config["calibration"]["max_seconds"]:
                await self.done(identifier)

    async def monitor(self):
        while True:
            await asyncio.sleep(.5)
            await self.check_timeouts()

    async def close(self):
        for identifier,state in list(self.recordings.items()):
            if state["result"] is None:
                await self.done(identifier)
