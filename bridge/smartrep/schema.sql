CREATE TABLE participants (
  id            TEXT PRIMARY KEY,          -- 6-digit string, e.g. '123129'
  display_name  TEXT NOT NULL,             -- first name only (fake)
  program       TEXT NOT NULL              -- 'general' | 'cancer' | 'stroke' | 'graduate'
);
CREATE TABLE equipment_types (
  id     TEXT PRIMARY KEY,                 -- 'dumbbell' | 'kettlebell' | 'glove'
  label  TEXT NOT NULL
);
CREATE TABLE stations (
  id              TEXT PRIMARY KEY,        -- 'db-5lb'
  label           TEXT NOT NULL,           -- 'Dumbbells · 5 lb'
  equipment_type  TEXT NOT NULL REFERENCES equipment_types(id),
  load_lb         REAL,                    -- NULL for bodyweight/glove
  device_id       TEXT                     -- 'clip-01' / 'sim-01'
);
CREATE TABLE exercises (
  id              TEXT PRIMARY KEY,        -- 'bicep-curl'
  name            TEXT NOT NULL,
  category        TEXT NOT NULL,           -- mobility|squat|push|hinge|pull|carry|core|stretch
  equipment_type  TEXT NOT NULL REFERENCES equipment_types(id)
);
CREATE TABLE doses (
  participant_id  TEXT NOT NULL REFERENCES participants(id),
  exercise_id     TEXT NOT NULL REFERENCES exercises(id),
  sets            INTEGER NOT NULL,        -- 1 or 2
  reps_min        INTEGER NOT NULL,        -- 10..20
  reps_max        INTEGER NOT NULL,
  load_lb         REAL,
  PRIMARY KEY (participant_id, exercise_id)
);
CREATE TABLE rep_references (
  participant_id  TEXT NOT NULL,
  exercise_id     TEXT NOT NULL,
  signal          TEXT NOT NULL,           -- 'pitch' | 'roll' | 'ax' | 'ay' | 'az' | 'x' | 'y' | 'z'
  units           TEXT NOT NULL,           -- 'deg' | 'g'
  ref_low         REAL NOT NULL,
  ref_high        REAL NOT NULL,
  ref_duration_s  REAL NOT NULL,
  direction       INTEGER NOT NULL,        -- +1 / -1
  device_id       TEXT,
  created_at      TEXT NOT NULL,
  PRIMARY KEY (participant_id, exercise_id)
);
CREATE TABLE sessions (
  id              INTEGER PRIMARY KEY AUTOINCREMENT,
  participant_id  TEXT NOT NULL,
  date            TEXT NOT NULL,           -- 'YYYY-MM-DD'
  started_at      TEXT NOT NULL,
  ended_at        TEXT
);
CREATE TABLE sets (
  id              INTEGER PRIMARY KEY AUTOINCREMENT,
  session_id      INTEGER NOT NULL REFERENCES sessions(id),
  participant_id  TEXT NOT NULL,
  exercise_id     TEXT NOT NULL,
  station_id      TEXT NOT NULL,
  set_number      INTEGER NOT NULL,
  load_lb         REAL,
  started_at      TEXT NOT NULL,
  ended_at        TEXT,
  end_reason      TEXT,                    -- 'user' | 'idle' | 'disconnect'
  reps_completed  INTEGER NOT NULL DEFAULT 0,   -- good + rushed + slow
  good            INTEGER NOT NULL DEFAULT 0,
  short           INTEGER NOT NULL DEFAULT 0,
  rushed          INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE reps (
  set_id      INTEGER NOT NULL REFERENCES sets(id),
  idx         INTEGER NOT NULL,
  quality     TEXT NOT NULL,
  peak_p      REAL NOT NULL,
  rom         REAL,                        -- range of motion in ref units (degrees for MPU clips)
  duration_s  REAL NOT NULL,
  t_start_ms  INTEGER NOT NULL,
  PRIMARY KEY (set_id, idx)
);
