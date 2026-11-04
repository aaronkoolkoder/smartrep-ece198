"""Own active sets and persist every rep before publishing it to clients."""
import asyncio
import logging
from datetime import datetime
from zoneinfo import ZoneInfo
import time
from .db import connect, utc_now
from .orientation import SignalPipeline
from .reps import Reference, RepDetector

ORDER = ["over_dose", "behind", "form_check", "ready_to_progress", "on_track", "done"]
LABELS = dict(zip(ORDER, ["Over dose", "Behind", "Check form", "Ready to progress", "On track", "Done ✓"]))


class SessionError(Exception):
    def __init__(self, code, message, status=409):
        self.code, self.message, self.status = code, message, status


def status_for(doses, sets, ready=False, left_incomplete=False, config=None):
    """Pure priority rules; short attempts do not count toward the dose."""
    cfg = config or {"form_check_frac": .30}
    for dose in doses:
        rows = [s for s in sets if s["exercise_id"] == dose["exercise_id"]]
        if len(rows) > dose["sets"] or any(s["reps_completed"] > dose["reps_max"] + 5 for s in rows):
            return "over_dose"
    done = bool(doses) and all(sum(s["ended_at"] is not None and s["reps_completed"] >= d["reps_min"]
                                for s in sets if s["exercise_id"] == d["exercise_id"]) >= d["sets"] for d in doses)
    if left_incomplete and not done:
        return "behind"
    if sets:
        last = sets[-1]
        attempts = last["reps_completed"] + last["short"]
        if attempts and (last["short"] + last["rushed"]) / attempts >= cfg["form_check_frac"]:
            return "form_check"
    if ready:
        return "ready_to_progress"
    return "done" if done else "on_track"


class SessionManager:
    def __init__(self, path, source, broadcast, config):
        self.path, self.source, self.broadcast, self.config = path, source, broadcast, config
        self.active = {}
        self.reserved = set()
        self.lock = asyncio.Lock()
        self.visits = {}
        self.left_exercises = {}

    def today(self):
        return datetime.now(ZoneInfo(self.config["server"].get("timezone", "America/Toronto"))).date().isoformat()

    def devices(self):
        return self.source.devices() if self.source else []

    def require_participant(self, db, participant):
        row = db.execute("SELECT * FROM participants WHERE id=?", (participant,)).fetchone()
        if row is None:
            raise SessionError("PARTICIPANT_NOT_FOUND", "We couldn't find that ID. Check with staff.", 404)
        return dict(row)

    def today_data(self, participant):
        with connect(self.path) as db:
            profile = self.require_participant(db, participant)
            doses = [dict(x) for x in db.execute("SELECT d.*,e.name,e.equipment_type FROM doses d JOIN exercises e ON e.id=d.exercise_id WHERE d.participant_id=?", (participant,))]
            sets = [dict(x) for x in db.execute("SELECT s.* FROM sets s JOIN sessions t ON t.id=s.session_id WHERE s.participant_id=? AND t.date=? ORDER BY s.id", (participant,self.today()))]
        for dose in doses:
            dose["sets_completed"] = sum(s["ended_at"] is not None and s["reps_completed"] >= dose["reps_min"] for s in sets if s["exercise_id"] == dose["exercise_id"])
        return {"participant":profile,"date":self.today(),"dose":doses,"sets":sets}

    async def start(self, participant, station_id, exercise):
        async with self.lock:
            with connect(self.path) as db:
                self.require_participant(db, participant)
                station = db.execute("SELECT * FROM stations WHERE id=?", (station_id,)).fetchone()
                if not station:
                    raise SessionError("STATION_NOT_FOUND", "Station not found.",404)
                dose = db.execute("SELECT d.*, e.equipment_type FROM doses d JOIN exercises e ON e.id=d.exercise_id WHERE participant_id=? AND exercise_id=?", (participant,exercise)).fetchone()
                if not dose:
                    raise SessionError("NOT_IN_DOSE", "This exercise isn't in your plan.",422)
                if dose["equipment_type"] != station["equipment_type"] or dose["load_lb"] != station["load_lb"]:
                    raise SessionError("WRONG_EQUIPMENT", "Choose the equipment and load in your plan.",422)
                device_id = station["device_id"]
                if device_id in self.active or device_id in self.reserved:
                    raise SessionError("STATION_BUSY", "This station is in use. Please wait.")
                if any(s["participant_id"] == participant for s in self.active.values()):
                    raise SessionError("SET_ACTIVE", "Finish your current set first.")
                device = next((d for d in self.devices() if d["id"] == device_id and d["online"]),None)
                if not device:
                    raise SessionError("DEVICE_OFFLINE", "Station disconnected, ask staff.",503)
                ref = db.execute("SELECT * FROM rep_references WHERE participant_id=? AND exercise_id=?", (participant,exercise)).fetchone()
                # Simulator references cannot silently authorize real hardware.
                if not ref or (ref["device_id"] and ref["device_id"].startswith("sim-") != device_id.startswith("sim-")):
                    raise SessionError("NEEDS_CALIBRATION", "Ask staff to set up this exercise first.",422)
                reference = Reference(**{k:ref[k] for k in ("signal","units","ref_low","ref_high","ref_duration_s","direction")})
                session = db.execute("SELECT id FROM sessions WHERE participant_id=? AND date=? AND ended_at IS NULL", (participant,self.today())).fetchone()
                now = utc_now()
                session_id = session[0] if session else db.execute("INSERT INTO sessions(participant_id,date,started_at) VALUES (?,?,?)", (participant,self.today(),now)).lastrowid
                number = db.execute("SELECT count(*) FROM sets WHERE session_id=? AND exercise_id=?",(session_id,exercise)).fetchone()[0] + 1
                set_id = db.execute("INSERT INTO sets(session_id,participant_id,exercise_id,station_id,set_number,load_lb,started_at) VALUES (?,?,?,?,?,?,?)",(session_id,participant,exercise,station_id,number,dose["load_lb"],now)).lastrowid
                target = {k:dose[k] for k in ("sets","reps_min","reps_max","load_lb")}
            self.active[device_id] = {"set_id":set_id,"participant_id":participant,"station_id":station_id,
                "exercise_id":exercise,"set_number":number,"target":target,
                "pipeline":SignalPipeline(device["units"],self.config),"detector":RepDetector(reference,self.config),
                "last_rep":time.monotonic(),"last_sample":time.monotonic(),"last_signal_ms":-1000}
            try:
                await self.source.start(device_id)
            except Exception:
                self.active.pop(device_id,None)
                with connect(self.path) as db:
                    db.execute("UPDATE sets SET ended_at=?,end_reason='disconnect' WHERE id=?",(utc_now(),set_id))
                raise SessionError("DEVICE_OFFLINE","Could not start this station. Ask staff.",503)
            self.visits[participant] = {"station_id":station_id,"at":time.monotonic(),"left":False}
            logging.info("Set %s started: participant %s, station %s",set_id,participant,station_id)
            result = {"set_id":set_id,"set_number":number,"exercise_id":exercise,"target":target}
            await self.broadcast({"type":"set_started",**result},participant)
            await self.broadcast({"type":"device_status",**device,"device_id":device_id,"streaming":True})
            await self.publish_status(participant)
            return result

    async def sample(self, device, raw):
        state = self.active.get(device)
        if not state:
            return
        state["last_sample"] = time.monotonic()
        try:
            sample = state["pipeline"].update(raw)
        except (ValueError,KeyError,TypeError):
            logging.debug("Skipping malformed sample from %s",device,exc_info=True)
            return
        if sample["gap"]:
            state["detector"].reset_motion()
        if not sample["ready"]:
            return
        value = sample["signals"][state["detector"].reference.signal]
        event = state["detector"].update(sample["ms"],value)
        if sample["ms"] - state["last_signal_ms"] >= 100:
            state["last_signal_ms"] = sample["ms"]
            await self.broadcast({"type":"signal","set_id":state["set_id"],"p":[state["detector"].reference.normalize(value)]},state["participant_id"])
        if not event:
            return
        state["last_rep"] = time.monotonic()
        with connect(self.path) as db:
            db.execute("INSERT INTO reps VALUES (?,?,?,?,?,?,?)",(state["set_id"],event["index"],event["quality"],event["peak_p"],event["rom"],event["duration_s"],event["t_start_ms"]))
            # Explicit field names prevent a quality label becoming SQL input.
            good,short,rushed = (int(event["quality"] == q) for q in ("good","short","rushed"))
            db.execute("UPDATE sets SET reps_completed=?,good=good+?,short=short+?,rushed=rushed+? WHERE id=?",(event["count"],good,short,rushed,state["set_id"]))
        await self.broadcast({"type":"rep","set_id":state["set_id"],**event},state["participant_id"])
        await self.publish_status(state["participant_id"])

    def detail(self, set_id):
        with connect(self.path) as db:
            row = db.execute("SELECT * FROM sets WHERE id=?",(set_id,)).fetchone()
            if not row:
                raise SessionError("SET_NOT_FOUND","Set not found.",404)
            result = dict(row)
            result["reps"] = [dict(x) for x in db.execute("SELECT * FROM reps WHERE set_id=? ORDER BY idx",(set_id,))]
        result["avg_rom"] = sum(x["rom"] or 0 for x in result["reps"]) / len(result["reps"]) if result["reps"] else None
        return result

    async def finish(self, set_id, reason="user"):
        async with self.lock:
            result = self.detail(set_id)
            if result["ended_at"]:
                return result
            device = next((d for d,s in self.active.items() if s["set_id"] == set_id),None)
            if device:
                self.active.pop(device)
                await self.source.stop(device)
            with connect(self.path) as db:
                db.execute("UPDATE sets SET ended_at=?,end_reason=? WHERE id=?",(utc_now(),reason,set_id))
            result = self.detail(set_id)
            logging.info("Set %s ended: %s (%s completed reps)",set_id,reason,result["reps_completed"])
            await self.broadcast({"type":"set_complete","set_id":set_id,"reason":reason,**result},result["participant_id"])
            await self.broadcast({"type":"device_status","device_id":device,"online":True,"streaming":False})
            await self.publish_status(result["participant_id"])
            return result

    def progress_ready(self, participant):
        with connect(self.path) as db:
            exercises = [x[0] for x in db.execute("SELECT exercise_id FROM doses WHERE participant_id=?",(participant,))]
            for exercise in exercises:
                # An incomplete current session doesn't invalidate prior sessions.
                sessions = db.execute("SELECT id FROM sessions WHERE participant_id=? AND ended_at IS NOT NULL ORDER BY date DESC,id DESC LIMIT ?",(participant,self.config["status"]["progress_sessions_in_row"])).fetchall()
                if len(sessions) != self.config["status"]["progress_sessions_in_row"]:
                    continue
                if all(db.execute("SELECT 1 FROM sets WHERE session_id=? AND exercise_id=? AND good>=?",(s[0],exercise,self.config["status"]["progress_good_reps"])).fetchone() for s in sessions):
                    return True
        return False

    def snapshot(self):
        with connect(self.path) as db:
            ids = [x[0] for x in db.execute("SELECT id FROM participants")]
        participants = []
        for participant in ids:
            data = self.today_data(participant)
            visit = self.visits.get(participant)
            left_ids = set(self.left_exercises.get(participant, set()))
            if visit and time.monotonic()-visit["at"] > self.config["status"]["left_station_idle_min"]*60:
                left_ids.update(s["exercise_id"] for s in data["sets"] if s["station_id"] == visit["station_id"])
            left = any(d["exercise_id"] in left_ids and d["sets_completed"] < d["sets"] for d in data["dose"])
            status = status_for(data["dose"],data["sets"],self.progress_ready(participant),bool(left),self.config["status"])
            active = next((s for s in self.active.values() if s["participant_id"] == participant),None)
            participants.append({**data["participant"],"status":status,"status_label":LABELS[status],
                "dose":data["dose"],"sets":data["sets"],"active_set": self.detail(active["set_id"]) if active else None})
        participants.sort(key=lambda p:(ORDER.index(p["status"]),p["display_name"]))
        return {"participants":participants,"devices":self.devices(),"alerts":[{"participant_id":p["id"],"status":p["status"],"message":p["display_name"]+": "+p["status_label"]} for p in participants if p["status"] in ORDER[:4]]}

    async def publish_status(self, participant):
        row = next(p for p in self.snapshot()["participants"] if p["id"] == participant)
        await self.broadcast({"type":"dashboard_update","participant_id":participant,"status":row["status"],"participant":row},participant)

    async def visit(self, participant, station):
        with connect(self.path) as db:
            self.require_participant(db,participant)
            if not db.execute("SELECT 1 FROM stations WHERE id=?",(station,)).fetchone():
                raise SessionError("STATION_NOT_FOUND","Station not found.",404)
        old = self.visits.get(participant)
        if old and old["station_id"] != station:
            data = self.today_data(participant)
            self.left_exercises.setdefault(participant,set()).update(s["exercise_id"] for s in data["sets"] if s["station_id"] == old["station_id"])
        self.visits[participant] = {"station_id":station,"at":time.monotonic(),"left":bool(old and (old["left"] or old["station_id"] != station))}
        await self.publish_status(participant)
        return {"ok":True}

    async def end_session(self, participant):
        with connect(self.path) as db:
            self.require_participant(db,participant)
        for state in list(self.active.values()):
            if state["participant_id"] == participant:
                await self.finish(state["set_id"])
        with connect(self.path) as db:
            db.execute("UPDATE sessions SET ended_at=? WHERE participant_id=? AND date=? AND ended_at IS NULL",(utc_now(),participant,self.today()))
        self.left_exercises[participant] = {d["exercise_id"] for d in self.today_data(participant)["dose"]}
        await self.publish_status(participant)
        return {"ok":True}

    async def monitor(self):
        while True:
            await asyncio.sleep(.25)
            now = time.monotonic()
            online = {d["id"] for d in self.devices() if d["online"]}
            for device,state in list(self.active.items()):
                disconnected = device not in online or now-state["last_sample"] > self.config["signal"]["max_gap_ms"]/1000
                if disconnected:
                    if now-state["last_sample"] > self.config["sets"]["disconnect_grace_s"]:
                        await self.finish(state["set_id"],"disconnect")
                elif now-state["last_rep"] > self.config["sets"]["idle_timeout_s"]:
                    await self.finish(state["set_id"],"idle")
