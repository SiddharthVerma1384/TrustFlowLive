"""
PHASE 8 - CONTINUOUS TRUSTFLOW ENGINE (reference implementation)

Per host, per time window:
  features -> compare to stored baseline -> anomaly score -> trust score -> policy state

Complexity: O(F) per window, F = number of features (O(1) for a fixed set).
The baseline is kept as running mean/variance (Welford) - history is never re-read.
This is the "optimised approach" of your slide 5.

Every tunable number lives in Params so ablation / formula experiments (Phase 10)
can change them without touching the logic.
"""
import math
from dataclasses import dataclass, field

from event_store.schema import STATES, ACTIONS

FEATURES = ["pkt_rate", "mean_size", "unique_dsts", "unique_ports", "syn_ratio"]
ENTER = {"Trusted": 0.80, "Monitored": 0.60, "Restricted": 0.40, "Quarantine": 0.20, "Blocked": 0.0}


@dataclass
class Params:
    warmup: int = 30            # windows used only to learn the baseline
    z_cap: float = 10.0         # clip each z-score so one feature cannot dominate forever
    z_floor: float = 1.5        # aggregate z below this = normal noise, anomaly 0
    z_scale: float = 3.0        # larger = gentler anomaly curve
    beta_down: float = 0.6      # trust falls fast ...
    beta_up: float = 0.08       # ... and recovers slowly (asymmetric EMA)
    margin: float = 0.05        # HYSTERESIS: must exceed threshold by this to improve
    dwell: int = 3              # HYSTERESIS: ... for this many consecutive windows
    features: tuple = tuple(FEATURES)   # ablation: pass a subset


class Welford:
    __slots__ = ("n", "mean", "m2")

    def __init__(self):
        self.n, self.mean, self.m2 = 0, 0.0, 0.0

    def update(self, x):
        self.n += 1
        d = x - self.mean
        self.mean += d / self.n
        self.m2 += d * (x - self.mean)

    def std(self):
        s = math.sqrt(self.m2 / (self.n - 1)) if self.n > 1 else 0.0
        return max(s, 0.1 * abs(self.mean) + 1e-3)   # floor avoids z explosions


class HostModel:
    def __init__(self):
        self.stats = {f: Welford() for f in FEATURES}
        self.trust, self.state, self.windows, self.better = 1.0, "Trusted", 0, 0


def raw_state(trust):
    for s in STATES:
        if trust >= ENTER[s]:
            return s
    return "Blocked"


class TrustEngine:
    def __init__(self, params=None):
        self.p = params or Params()
        self.hosts = {}

    def process(self, host, feats):
        p = self.p
        m = self.hosts.setdefault(host, HostModel())
        m.windows += 1

        # ---- learning phase: baseline only, no decisions ----
        if m.windows <= p.warmup:
            for f in FEATURES:
                m.stats[f].update(feats[f])
            return self._out(m, feats, {}, 0.0, "Trusted", False, "learning")

        # ---- 1. anomaly score ----
        z = {f: abs(feats[f] - m.stats[f].mean) / m.stats[f].std() for f in p.features}
        zc = [min(v, p.z_cap) for v in z.values()]
        agg = math.sqrt(sum(v * v for v in zc) / len(zc))
        anomaly = 1.0 - math.exp(-max(0.0, agg - p.z_floor) / p.z_scale)

        # ---- 2. trust score (asymmetric EMA) ----
        target = 1.0 - anomaly
        beta = p.beta_down if target < m.trust else p.beta_up
        m.trust += beta * (target - m.trust)

        # ---- 3. policy with hysteresis ----
        prev = m.state
        new = raw_state(m.trust)
        i_cur, i_new = STATES.index(m.state), STATES.index(new)
        if i_new > i_cur:                       # getting worse -> act immediately
            m.state, m.better = new, 0
        elif i_new < i_cur:                     # getting better -> be patient
            up = STATES[i_cur - 1]
            if m.trust >= ENTER[up] + p.margin:
                m.better += 1
                if m.better >= p.dwell:
                    m.state, m.better = up, 0
            else:
                m.better = 0
        else:
            m.better = 0

        # ---- 4. baseline update only from trustworthy windows (anti-poisoning) ----
        if m.state in ("Trusted", "Monitored") and anomaly < 0.3:
            for f in FEATURES:
                m.stats[f].update(feats[f])

        return self._out(m, feats, z, anomaly, prev, m.state != prev, "scoring")

    @staticmethod
    def _out(m, feats, z, anomaly, prev, changed, phase):
        return {
            "features": {k: round(v, 3) for k, v in feats.items()},
            "z": {k: round(v, 2) for k, v in z.items()},
            "anomaly": round(anomaly, 4), "trust": round(m.trust, 4),
            "state": m.state, "prev_state": prev, "changed": changed,
            "action": ACTIONS[m.state], "phase": phase,
            "payload_bytes_inspected": 0,      # metadata-only: the privacy claim, per event
            "mode": "trustflow",
        }
