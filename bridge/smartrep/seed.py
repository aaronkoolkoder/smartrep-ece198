"""Repeatable fake records, never real participant information."""
from datetime import datetime, timedelta, timezone
from .db import connect, utc_now

STATIONS = [
    ("db-3lb", "Dumbbells · 3 lb", "dumbbell", 3),
    ("db-5lb", "Dumbbells · 5 lb", "dumbbell", 5),
    ("db-8lb", "Dumbbells · 8 lb", "dumbbell", 8),
    ("kb-10lb", "Kettlebell · 10 lb", "kettlebell", 10),
    ("glove-1", "Movement glove", "glove", None),
]
EXERCISES = [
    ("bicep-curl", "Bicep curl", "pull", "dumbbell"),
    ("hammer-curl", "Hammer curl", "pull", "dumbbell"),
    ("bent-over-row", "Bent-over row", "pull", "dumbbell"),
    ("shoulder-press", "Shoulder press", "push", "dumbbell"),
    ("front-raise", "Front raise", "mobility", "dumbbell"),
    ("goblet-squat", "Goblet squat", "squat", "kettlebell"),
    ("kettlebell-deadlift", "Kettlebell deadlift", "hinge", "kettlebell"),
    ("wall-push-up", "Wall push-up", "push", "glove"),
    ("bird-dog", "Bird dog", "core", "glove"),
    ("arm-rainbow", "Arm rainbow", "mobility", "glove"),
]


def seed(path, simulate=False, device_mapping=None):
    with connect(path) as db:
        db.executemany("INSERT OR IGNORE INTO equipment_types VALUES (?, ?)",
                       [("dumbbell", "Dumbbells"), ("kettlebell", "Kettlebell"), ("glove", "Glove")])
        db.executemany("INSERT OR IGNORE INTO participants VALUES (?, ?, ?)", [
            ("123129", "Mary", "general"), ("204417", "Raj", "stroke"),
            ("311802", "Linda", "cancer"), ("118560", "Tom", "graduate"),
            ("150093", "Grace", "graduate")])
        for i, station in enumerate(STATIONS, 1):
            device = f"sim-{i:02d}" if simulate else (device_mapping or {}).get(station[0], {"db-3lb":"clip-03","db-5lb":"clip-01","db-8lb":"clip-04","kb-10lb":"clip-05","glove-1":"clip-02"}[station[0]])
            db.execute("INSERT OR IGNORE INTO stations VALUES (?, ?, ?, ?, ?)", (*station, device))
            # Mode changes alter routing, without deleting saved doses or history.
            db.execute("UPDATE stations SET device_id=? WHERE id=?", (device, station[0]))
        db.executemany("INSERT OR IGNORE INTO exercises VALUES (?, ?, ?, ?)", EXERCISES)
        for participant, load in [("123129", 5), ("204417", 3), ("311802", 3), ("118560", 8), ("150093", 5)]:
            for exercise in ["bicep-curl", "hammer-curl", "bent-over-row", "wall-push-up"]:
                db.execute("INSERT OR IGNORE INTO doses VALUES (?, ?, 2, 10, 20, ?)",
                           (participant, exercise, None if exercise == "wall-push-up" else load))
                # References are specifically associated with simulated devices.
                # Real-hardware mode never silently substitutes these references.
                if simulate:
                    db.execute("INSERT OR IGNORE INTO rep_references VALUES (?, ?, 'pitch', 'deg', 0, 110, 2.5, 1, ?, ?)",
                               (participant, exercise, "sim-05" if exercise == "wall-push-up" else
                                {3: "sim-01", 5: "sim-02", 8: "sim-03"}[load], utc_now()))
        # Add historical fixtures once, so ordinary restarts don't grow the DB.
        for participant, days, good, short, station in [
            ("118560", 4, 20, 0, "db-8lb"), ("118560", 2, 20, 0, "db-8lb"),
            ("204417", 2, 8, 7, "db-3lb")]:
            date = (datetime.now(timezone.utc) - timedelta(days=days)).date().isoformat()
            if db.execute("SELECT 1 FROM sessions WHERE participant_id=?", (participant,)).fetchone() and participant == "204417":
                continue
            # Tom needs two different dates; the unique check uses the seed marker time.
            stamp = date + "T12:00:00+00:00"
            if db.execute("SELECT 1 FROM sessions WHERE participant_id=? AND started_at=?", (participant, stamp)).fetchone():
                continue
            # If already seeded on an earlier launch date, don't add a moving history.
            count = db.execute("SELECT count(*) FROM sessions WHERE participant_id=?", (participant,)).fetchone()[0]
            if participant == "118560" and count >= 2:
                continue
            sid = db.execute("INSERT INTO sessions(participant_id,date,started_at,ended_at) VALUES (?,?,?,?)",
                             (participant, date, stamp, stamp)).lastrowid
            db.execute("""INSERT INTO sets(session_id,participant_id,exercise_id,station_id,set_number,
                       load_lb,started_at,ended_at,end_reason,reps_completed,good,short,rushed)
                       VALUES (?,?,'bicep-curl',?,1,?,?,?,'user',?,?,?,0)""",
                       (sid, participant, station, 8 if participant == "118560" else 3, stamp, stamp, good, good, short))
