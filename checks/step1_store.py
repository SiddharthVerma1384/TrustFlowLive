"""STEP 1 - event store: can we write and read events?   Run: python -m checks.step1_store"""
import os, tempfile
from event_store.store import EventStore
from event_store.schema import make_event

db = os.path.join(tempfile.gettempdir(), "tf_check1.db")
if os.path.exists(db):
    os.remove(db)
s = EventStore(db)
s.add_many([make_event("r1", 1, "run_start", None, scenario="x", topology="star", nodes=[], links=[],
                       duration=1, warmup=1, mode="t"),
            make_event("r1", 2, "flow_score", "h1", trust=0.9, state="Trusted", phase="scoring", features={}, anomaly=0.0)])
assert s.latest_run_id() == "r1", "run not stored"
assert len(s.query("r1")) == 2, "events not stored"
assert s.latest_per_host("r1")[0]["host"] == "h1"
try:
    make_event("r1", 1, "not_a_type", None)
    raise SystemExit("FAIL: schema accepted a bad event type")
except ValueError:
    pass
print("PASS step 1: store writes/reads, schema rejects bad event types")
