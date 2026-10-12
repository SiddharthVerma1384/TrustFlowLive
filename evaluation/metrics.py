"""
PHASE 9 - EVALUATION + GROUND TRUTH
Joins engine decisions with ground-truth labels (by host and tick) and computes
confusion matrix, precision / recall / F1, FP & FN lists, per-attack recall, detection delay.

Prediction rule: a window is "flagged" if state is at or beyond `min_state`
(default Restricted = TrustFlow actually restricts the host).
"""
from event_store.schema import STATES


def evaluate(events, min_state="Restricted"):
    labels = [e for e in events if e["type"] == "label"]
    scores = [e for e in events if e["type"] == "flow_score" and e["data"]["phase"] == "scoring"]
    thr = STATES.index(min_state)

    def truth(host, t):
        for l in labels:
            d = l["data"]
            if l["host"] == host and d["t_start"] <= t < d["t_end"]:
                return d["attack"]
        return None

    tp = fp = fn = tn = 0
    fps, fns, per = [], [], {}
    first_flag = {}
    for e in scores:
        atk = truth(e["host"], e["t"])
        flagged = STATES.index(e["data"]["state"]) >= thr
        if atk:
            r = per.setdefault(atk, {"tp": 0, "fn": 0})
            if flagged:
                tp += 1; r["tp"] += 1
                first_flag.setdefault((e["host"], atk), e["t"])
            else:
                fn += 1; r["fn"] += 1; fns.append({"host": e["host"], "t": e["t"], "attack": atk})
        else:
            if flagged:
                fp += 1; fps.append({"host": e["host"], "t": e["t"], "state": e["data"]["state"]})
            else:
                tn += 1

    P = tp / (tp + fp) if tp + fp else 0.0
    R = tp / (tp + fn) if tp + fn else 0.0
    F1 = 2 * P * R / (P + R) if P + R else 0.0
    delays = {}
    for l in labels:
        d = l["data"]; k = (l["host"], d["attack"])
        delays[f"{l['host']}:{d['attack']}"] = (first_flag[k] - d["t_start"]) if k in first_flag else None
    return {
        "min_state": min_state,
        "confusion": {"tp": tp, "fp": fp, "fn": fn, "tn": tn},
        "precision": round(P, 4), "recall": round(R, 4), "f1": round(F1, 4),
        "fpr": round(fp / (fp + tn), 4) if fp + tn else 0.0,
        "per_attack": {a: {**v, "recall": round(v["tp"] / (v["tp"] + v["fn"]), 4)} for a, v in per.items()},
        "detection_delay_ticks": delays,
        "false_positives": fps[:50], "false_negatives": fns[:50],
    }
