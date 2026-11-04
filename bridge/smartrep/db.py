"""Small SQLite helpers; each request owns its connection."""
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
import sqlite3


def utc_now():
    return datetime.now(timezone.utc).isoformat()


@contextmanager
def connect(path):
    db = sqlite3.connect(path)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA foreign_keys = ON")
    try:
        yield db
        db.commit()
    except BaseException:
        db.rollback()
        raise
    finally:
        db.close()


def initialize(path):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with connect(path) as db:
        # Each CREATE is idempotent so restarting preserves saved work.
        schema = Path(__file__).with_name("schema.sql").read_text()
        db.executescript(schema.replace("CREATE TABLE ", "CREATE TABLE IF NOT EXISTS "))
        now = utc_now()
        db.execute("UPDATE sets SET ended_at=?, end_reason='disconnect' WHERE ended_at IS NULL", (now,))
        db.execute("UPDATE sessions SET ended_at=? WHERE ended_at IS NULL", (now,))
