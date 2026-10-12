"""
CSV REPLAY - feed recorded or exported metadata through the engine and onto the dashboard.

CSV columns:  t, host, <feature columns>, label      (label = attack name, blank = benign)
Column names are translated by adapter/mapping.py, so your own headers work after one mapping edit.

    python -m adapter.replay --make-sample sample.csv          # export a ready-made example
    python -m adapter.replay sample.csv --run-id csv1 --speed 20
(--speed = ticks per second; 0 = as fast as possible)
"""
import argparse
import csv
import time
from itertools import groupby

from adapter.ingest import Ingest
from event_store.store import EventStore
from engine.core import FEATURES


def make_sample(path):
    from scenarios.simulator import simulate
    ev = [e for _, b in simulate("mixed") for e in b]
    labels = [(e["host"], e["data"]) for e in ev if e["type"] == "label"]
    with open(path, "w", newline="") as f:
        w = csv.writer(f); w.writerow(["t", "host", *FEATURES, "label"])
        for e in ev:
            if e["type"] != "flow_score":
                continue
            lab = next((d["attack"] for h, d in labels if h == e["host"] and d["t_start"] <= e["t"] < d["t_end"]), "")
            w.writerow([e["t"], e["host"], *[e["data"]["features"][k] for k in FEATURES], lab])
    print("wrote", path)


def replay(path, run_id, speed):
    ing = Ingest(EventStore())
    rows = sorted(csv.DictReader(open(path)), key=lambda r: int(r["t"]))
    spans = {}                                         # (host, attack) -> [start, end]
    for t, grp in groupby(rows, key=lambda r: int(r["t"])):
        for r in grp:
            raw = {k: v for k, v in r.items() if k not in ("t", "host", "label")}
            ing.push(run_id, t, r["host"], raw, scenario="csv-replay")
            if r.get("label"):
                sp = spans.setdefault((r["host"], r["label"]), [t, t]); sp[1] = t + 1
        if speed:
            time.sleep(1 / speed)
    for (host, attack), (a, b) in spans.items():
        ing.label(run_id, host, attack, a, b)
    ing.end(run_id)
    print("replayed", len(rows), "windows as run", run_id)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("csv", nargs="?"); ap.add_argument("--run-id", default="csv1")
    ap.add_argument("--speed", type=float, default=20); ap.add_argument("--make-sample")
    a = ap.parse_args()
    make_sample(a.make_sample) if a.make_sample else replay(a.csv, a.run_id, a.speed)
