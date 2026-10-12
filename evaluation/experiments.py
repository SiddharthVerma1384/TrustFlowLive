"""
PHASE 10 - RESEARCH EXPERIMENTS (headless - no FastAPI, no UI, no sleeping)
    python -m evaluation.experiments            # runs everything, writes evaluation/results/*.json
Dashboard's Research page just loads those files.

 1. ablation      : drop one feature at a time, measure F1 change         (req #13)
 2. formula       : sweep z_floor / beta_up / dwell, F1 + flapping         (req #1, #11, #12)
 3. hysteresis    : with vs without hysteresis -> state flips per host      (req #12)
 4. scalability   : hosts vs microseconds per window (O(1) per flow claim)  (req #14)
 5. multi-seed    : mean +/- std of P/R/F1 over seeds, per attack           (req #7-9)
"""
import json
import statistics as st
import time
from dataclasses import replace
from pathlib import Path

from engine.core import Params, FEATURES, TrustEngine
from scenarios.simulator import simulate, _sample, NORMAL
from evaluation.metrics import evaluate

OUT = Path(__file__).with_name("results")
SEEDS = range(1, 6)


def run(scenario="mixed", seed=1, **p):
    params = replace(Params(), **p)
    ev = [e for _, b in simulate(scenario, seed=seed, params=params) for e in b]
    return ev, evaluate(ev)


def flips(ev):
    return sum(1 for e in ev if e["type"] == "state_change")


def ablation():
    rows = []
    base = st.mean(run(seed=s)[1]["f1"] for s in SEEDS)
    rows.append({"removed": "none", "f1": round(base, 4), "delta": 0.0})
    for f in FEATURES:
        keep = tuple(x for x in FEATURES if x != f)
        v = st.mean(run(seed=s, features=keep)[1]["f1"] for s in SEEDS)
        rows.append({"removed": f, "f1": round(v, 4), "delta": round(v - base, 4)})
    return rows


def formula_sweep():
    rows = []
    for zf in (1.0, 1.5, 2.0, 3.0):
        for bu in (0.04, 0.08, 0.2):
            rs = [run(seed=s, z_floor=zf, beta_up=bu)[1] for s in SEEDS]
            rows.append({"z_floor": zf, "beta_up": bu, "precision": round(st.mean(r["precision"] for r in rs), 4),
                         "recall": round(st.mean(r["recall"] for r in rs), 4), "f1": round(st.mean(r["f1"] for r in rs), 4)})
    return rows


def hysteresis():
    out = []
    for name, kw in (("no hysteresis", dict(margin=0.0, dwell=1)), ("hysteresis (0.05, 3)", dict(margin=0.05, dwell=3)),
                     ("strong (0.10, 6)", dict(margin=0.10, dwell=6))):
        res = [run(seed=s, **kw) for s in SEEDS]
        out.append({"config": name, "state_changes": round(st.mean(flips(e) for e, _ in res), 1),
                    "f1": round(st.mean(r["f1"] for _, r in res), 4)})
    return out


def scalability():
    import random
    rng, rows = random.Random(0), []
    for n in (10, 100, 1000, 5000):
        eng = TrustEngine(Params(warmup=5))
        hosts = [f"h{i}" for i in range(n)]
        for _ in range(6):
            for h in hosts:
                eng.process(h, _sample(rng, {}, None, 0))
        t0 = time.perf_counter()
        for _ in range(20):
            for h in hosts:
                eng.process(h, _sample(rng, {}, None, 0))
        dt = (time.perf_counter() - t0) / (20 * n)
        rows.append({"hosts": n, "us_per_window": round(dt * 1e6, 2)})
    return rows


def per_attack():
    agg = {}
    for s in SEEDS:
        for a, v in run(seed=s)[1]["per_attack"].items():
            agg.setdefault(a, []).append(v["recall"])
    base = [run(seed=s)[1] for s in SEEDS]
    return {"recall_by_attack": {a: {"mean": round(st.mean(v), 3), "std": round(st.pstdev(v), 3)} for a, v in agg.items()},
            "overall": {k: {"mean": round(st.mean(r[k] for r in base), 4), "std": round(st.pstdev(r[k] for r in base), 4)}
                        for k in ("precision", "recall", "f1", "fpr")}}


def main():
    OUT.mkdir(exist_ok=True)
    for name, fn in (("ablation", ablation), ("formula", formula_sweep), ("hysteresis", hysteresis),
                     ("scalability", scalability), ("multi_seed", per_attack)):
        res = fn(); (OUT / f"{name}.json").write_text(json.dumps(res, indent=2)); print(name, "done")


if __name__ == "__main__":
    main()
