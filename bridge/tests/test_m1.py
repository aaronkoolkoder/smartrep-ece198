import asyncio
import math
import random
from fastapi.testclient import TestClient
from smartrep.api import create_app
from smartrep.db import connect
from smartrep.sources.sim_source import SimSource, sample_at


def test_startup_seed_health_and_restart(tmp_path):
    path = tmp_path / "test.db"
    for _ in range(2):
        with TestClient(create_app(path, simulate=True)) as client:
            assert client.get("/api/health").json()["devices_online"] == 5
            assert client.get("/docs").status_code == 200
            assert client.get("/api/participants/123129").json()["display_name"] == "Mary"
            assert client.get("/api/participants/999999").status_code == 404
            assert client.get("/api/stations/db-5lb").json()["device"]["id"] == "sim-02"
    with connect(path) as db:
        assert db.execute("SELECT count(*) FROM participants").fetchone()[0] == 5
        assert db.execute("SELECT count(*) FROM exercises").fetchone()[0] == 10
        assert db.execute("SELECT count(*) FROM sessions").fetchone()[0] == 3
        assert db.execute("SELECT count(*) FROM rep_references").fetchone()[0] == 20
        assert db.execute("PRAGMA foreign_key_check").fetchall() == []


def test_real_mode_does_not_claim_simulators_online(tmp_path):
    with TestClient(create_app(tmp_path / "real.db")) as client:
        assert client.get("/api/health").json()["devices_online"] == 0
        assert client.get("/api/stations/db-5lb").json()["device"] is None


def test_motion_matches_gravity_and_gyro():
    rng = random.Random(1)
    for t in [0, 0.3, 0.6, 1.25]:
        sample = sample_at(t, rng)
        # atan2 with a positive denominator folds at 90°; atan2(-ax, az)
        # retains the full 110° curl for the orientation stage in M2.
        pitch = math.degrees(math.atan2(-sample["ax"], sample["az"]))
        expected = 110 * (1 - math.cos(2 * math.pi * t / 2.5)) / 2
        assert abs(pitch - expected) < 1
        assert abs(sample["gy"] / 65.5 - (110 * math.pi / 2.5 * math.sin(2 * math.pi * t / 2.5) + 0.4)) < 0.02


def test_simulator_start_stop_lifecycle():
    async def scenario():
        received = []
        async def callback(device, sample):
            received.append((device, sample))
        source = SimSource(callback)
        await source.start("sim-01")
        await source.start("sim-01")
        await asyncio.sleep(0.12)
        await source.stop("sim-01")
        count = len(received)
        await asyncio.sleep(0.05)
        assert len(received) == count
        assert count >= 4
        assert all(b[1]["ms"] - a[1]["ms"] == 20 for a, b in zip(received, received[1:]))
        assert not any(d["streaming"] for d in source.devices())
        await source.close()
    asyncio.run(scenario())
