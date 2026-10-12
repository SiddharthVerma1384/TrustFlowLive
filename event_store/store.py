"""
EVENT STORE - SQLite in WAL mode (engine/simulator writes while the API reads).
One table.  Append-only.  History, replay and evaluation all read from here.
"""
import json
import sqlite3
import threading
import time
from pathlib import Path

DEFAULT_DB = Path(__file__).with_name("trustflow.db")


class EventStore:
    def __init__(self, path=DEFAULT_DB):
        self.db = sqlite3.connect(str(path), check_same_thread=False)
        self.db.row_factory = sqlite3.Row
        self.lock = threading.Lock()
        with self.lock:
            self.db.execute("PRAGMA journal_mode=WAL")
            self.db.execute(
                """CREATE TABLE IF NOT EXISTS events(
                     id INTEGER PRIMARY KEY AUTOINCREMENT,
                     ts REAL, run_id TEXT, t INTEGER, type TEXT, host TEXT, data TEXT)"""
            )
            self.db.execute("CREATE INDEX IF NOT EXISTS ix_run ON events(run_id, id)")
            self.db.execute("CREATE INDEX IF NOT EXISTS ix_type ON events(run_id, type, host)")
            self.db.commit()

    def add_many(self, events):
        now = time.time()
        rows = [(now, e["run_id"], e["t"], e["type"], e.get("host"), json.dumps(e["data"])) for e in events]
        with self.lock:
            self.db.executemany(
                "INSERT INTO events(ts,run_id,t,type,host,data) VALUES(?,?,?,?,?,?)", rows)
            self.db.commit()

    @staticmethod
    def _row(r):
        d = dict(r)
        d["data"] = json.loads(d["data"])
        return d

    def query(self, run_id=None, since_id=0, types=None, host=None, limit=50000):
        sql, args = "SELECT * FROM events WHERE id>?", [since_id]
        if run_id:
            sql += " AND run_id=?"; args.append(run_id)
        if types:
            sql += f" AND type IN ({','.join('?' * len(types))})"; args += list(types)
        if host:
            sql += " AND host=?"; args.append(host)
        sql += " ORDER BY id LIMIT ?"; args.append(limit)
        with self.lock:
            return [self._row(r) for r in self.db.execute(sql, args)]

    def runs(self):
        with self.lock:
            rows = self.db.execute(
                "SELECT * FROM events WHERE type='run_start' ORDER BY id DESC").fetchall()
        return [self._row(r) for r in rows]

    def latest_run_id(self):
        r = self.runs()
        return r[0]["run_id"] if r else None

    def latest_per_host(self, run_id):
        with self.lock:
            rows = self.db.execute(
                """SELECT e.* FROM events e JOIN
                   (SELECT host, MAX(id) mid FROM events
                    WHERE run_id=? AND type='flow_score' GROUP BY host) m ON e.id=m.mid""",
                (run_id,)).fetchall()
        return [self._row(r) for r in rows]

    def max_id(self):
        with self.lock:
            return self.db.execute("SELECT COALESCE(MAX(id),0) FROM events").fetchone()[0]

    def clear(self):
        with self.lock:
            self.db.execute("DELETE FROM events"); self.db.commit()
