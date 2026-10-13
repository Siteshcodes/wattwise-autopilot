import json
import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timedelta
from decimal import Decimal
from pathlib import Path
from uuid import uuid4

from dotenv import load_dotenv

from .engine import schedule
from .models import Device, DomainError, Proposal, Tariff

load_dotenv()


def demo_now():
    value = datetime.fromisoformat(os.getenv("WATTWISE_DEMO_NOW", "2026-10-12T20:00:00+05:30"))
    if value.utcoffset() is None:
        raise ValueError("WATTWISE_DEMO_NOW must include a timezone offset")
    return value


class Store:
    def __init__(self, path=None):
        self.path = path or os.getenv("WATTWISE_DB", "data/wattwise.sqlite3")
        Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS devices(id TEXT PRIMARY KEY, body TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS tariffs(start TEXT PRIMARY KEY, body TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS proposals(id TEXT PRIMARY KEY, body TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS executions(id TEXT PRIMARY KEY, plan_id TEXT UNIQUE NOT NULL, body TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS metadata(key TEXT PRIMARY KEY, value TEXT NOT NULL);
            """)
            now = demo_now()
            stored = db.execute("SELECT value FROM metadata WHERE key='clock'").fetchone()
            if stored and stored[0] != now.isoformat():
                raise ValueError("Demo clock changed: use a new WATTWISE_DB to seed a new scenario.")
            db.execute("INSERT OR IGNORE INTO metadata VALUES ('clock', ?)", (now.isoformat(),))
            device = Device(available_from=now, available_until=now+timedelta(hours=11))
            db.execute("INSERT OR IGNORE INTO devices VALUES (?,?)", (device.device_id, device.model_dump_json()))
            for i, rate in enumerate([12,11,10,8,6,4,3,2,5,7,9]):
                tariff = Tariff(start=now+timedelta(hours=i), end=now+timedelta(hours=i+1), price_per_kwh=Decimal(rate))
                db.execute("INSERT OR IGNORE INTO tariffs VALUES (?,?)", (tariff.start.isoformat(), tariff.model_dump_json()))

    @contextmanager
    def connect(self):
        db = sqlite3.connect(self.path, timeout=10)
        try:
            db.execute("PRAGMA journal_mode=WAL")
            with db:
                yield db
        finally:
            db.close()

    def device(self, device_id="ev-1", db=None):
        if db is None:
            with self.connect() as conn:
                return self.device(device_id, conn)
        row = db.execute("SELECT body FROM devices WHERE id=?", (device_id,)).fetchone()
        if not row:
            raise DomainError("UNKNOWN_DEVICE", f"Unknown simulated device: {device_id}")
        return Device.model_validate_json(row[0])

    def prices(self):
        with self.connect() as db:
            return [Tariff.model_validate_json(r[0]) for r in db.execute("SELECT body FROM tariffs ORDER BY start")]

    def optimize(self, device_id, deadline):
        device = self.device(device_id)
        if device.active_plan_id:
            raise DomainError("ALREADY_SCHEDULED", "This simulated charger already has an approved schedule. Use a fresh demo database for another run.")
        prices = self.prices()
        optimized = schedule(device, prices, demo_now(), deadline)
        baseline = schedule(device, prices, demo_now(), deadline, cheapest=False)
        savings = baseline.cost - optimized.cost
        plan = Proposal(plan_id=str(uuid4()), device_id=device_id, device_revision=device.revision, deadline=deadline, optimized=optimized, baseline=baseline, savings=savings, savings_percent=(savings/baseline.cost*100 if baseline.cost > 0 else Decimal(0)))
        with self.connect() as db:
            db.execute("INSERT INTO proposals VALUES (?,?)", (plan.plan_id, plan.model_dump_json()))
        return plan

    def apply(self, plan_id, confirmed):
        if confirmed is not True:
            raise DomainError("CONFIRMATION_REQUIRED", "Explicit user approval of this exact proposal is required.")
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            prior = db.execute("SELECT body FROM executions WHERE plan_id=?", (plan_id,)).fetchone()
            if prior:
                return json.loads(prior[0])
            row = db.execute("SELECT body FROM proposals WHERE id=?", (plan_id,)).fetchone()
            if not row:
                raise DomainError("UNKNOWN_PLAN", "Proposal does not exist.")
            plan = Proposal.model_validate_json(row[0])
            device = self.device(plan.device_id, db)
            if device.revision != plan.device_revision or device.active_plan_id:
                raise DomainError("STALE_PLAN", "Device state changed; this proposal can no longer be applied.")
            device.active_plan_id = plan_id
            device.revision += 1
            execution = {"execution_id": str(uuid4()), "plan_id": plan_id, "status": "scheduled", "simulated": True, "confirmed": True, "executed_at": datetime.now().astimezone().isoformat(), "demo_clock": demo_now().isoformat(), "proposal": plan.model_dump(mode="json")}
            db.execute("UPDATE devices SET body=? WHERE id=?", (device.model_dump_json(), device.device_id))
            db.execute("INSERT INTO executions VALUES (?,?,?)", (execution["execution_id"], plan_id, json.dumps(execution)))
            return execution

    def history(self, limit=20):
        with self.connect() as db:
            return [json.loads(r[0]) for r in db.execute("SELECT body FROM executions ORDER BY rowid DESC LIMIT ?", (limit,))]
