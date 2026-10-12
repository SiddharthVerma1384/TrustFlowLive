"""STEP 4 - CSV replay with a foreign column format, into a throw-away DB.   Run: python -m checks.step4_csv"""
import os, tempfile
import adapter.replay as R
from event_store.store import EventStore
from evaluation.metrics import evaluate

db = os.path.join(tempfile.gettempdir(), "tf_check4.db")
if os.path.exists(db):
    os.remove(db)
R.EventStore = lambda: EventStore(db)          # keep this test away from your real dashboard DB
R.replay("data/my_data_example.csv", "csvtest", 0)
ev = EventStore(db).query("csvtest")
r = evaluate(ev)
print("events:", len(ev), "| confusion:", r["confusion"], "| precision", r["precision"], "recall", r["recall"])
print("detection delay:", r["detection_delay_ticks"])
assert r["confusion"]["tp"] > 0, "no attack windows were flagged"
print("PASS step 4: your CSV format flows through mapping -> engine -> store -> evaluation")
