"""
PHASE 7 (simulated half) - SCENARIO RUNNER SOURCE
Generates synthetic per-host flow features for a topology + attack timeline, feeds them to the
REAL TrustEngine, and yields schema events.  Used by:
  * the FastAPI backend (live demo, paced in real time)
  * evaluation/experiments.py (headless, no sleeping)

Closed loop: the engine's own decision feeds back into the traffic.  Enforcement scales the
attack component down (RATE_LIMIT/QUARANTINE/DROP), exactly like OVS would, so you can see
trust recover after mitigation.  Benign traffic is unaffected (simplification, see docs).

NOTE: features here are synthetic.  Phase 6 replaces them with TShark-derived features;
nothing downstream changes.
"""
import random
import uuid

from engine.core import TrustEngine, Params, FEATURES
from event_store.schema import make_event, ACTIONS

# ---- benign behaviour: (mean, noise) ----
NORMAL = {"pkt_rate": (50, 5), "mean_size": (600, 40), "unique_dsts": (3, 0.7),
          "unique_ports": (4, 0.8), "syn_ratio": (0.05, 0.01)}

# ---- abnormal behaviours: feature -> (multiplier, additive) at full intensity ----
ATTACKS = {
    "port_scan": {"unique_ports": (1, 80), "unique_dsts": (1, 10), "syn_ratio": (1, 0.6), "mean_size": (0.2, 0)},
    "ddos":      {"pkt_rate": (25, 0), "syn_ratio": (1, 0.5), "mean_size": (0.15, 0), "unique_dsts": (1, 2)},
    "exfil":     {"mean_size": (2.2, 0), "pkt_rate": (3, 0), "unique_dsts": (1, 1)},
    "beacon":    {"mean_size": (0.6, 0), "unique_ports": (1, 2), "unique_dsts": (1, 2)},   # low & slow
}

# how much of the attack still gets through per policy state (closed loop)
LEAK = {"Trusted": 1.0, "Monitored": 1.0, "Restricted": 0.6, "Quarantine": 0.35, "Blocked": 0.2}

SCENARIOS = {  # attack timelines, in ticks AFTER warmup
    "benign":    [],
    "port_scan": [("port_scan", "h3", 20, 70)],
    "ddos":      [("ddos", "h2", 20, 70)],
    "exfil":     [("exfil", "h4", 20, 70)],
    "beacon":    [("beacon", "h5", 20, 90)],
    "mixed":     [("port_scan", "h3", 20, 60), ("exfil", "h4", 50, 100),
                  ("ddos", "h2", 90, 130), ("beacon", "h5", 30, 140)],
}


def topology(kind="star", n=6):
    hosts = [f"h{i}" for i in range(1, n + 1)]
    nodes = [{"id": h, "kind": "host"} for h in hosts]
    if kind == "star":
        nodes.append({"id": "s1", "kind": "switch"})
        links = [["s1", h] for h in hosts]
    elif kind == "linear":
        sw = [f"s{i}" for i in range(1, 4)]
        nodes += [{"id": s, "kind": "switch"} for s in sw]
        links = [["s1", "s2"], ["s2", "s3"]] + [[sw[i * 3 // n], h] for i, h in enumerate(hosts)]
    elif kind == "tree":
        nodes += [{"id": s, "kind": "switch"} for s in ("s1", "s2", "s3")]
        links = [["s1", "s2"], ["s1", "s3"]] + [["s2" if i < n // 2 else "s3", h] for i, h in enumerate(hosts)]
    else:
        raise ValueError(kind)
    return hosts, nodes, links


def _sample(rng, host_scale, attack, intensity):
    f = {}
    for k, (mu, sd) in NORMAL.items():
        f[k] = max(0.0, rng.gauss(mu * host_scale.get(k, 1.0), sd * host_scale.get(k, 1.0)))
    if attack:
        for k, (mult, add) in ATTACKS[attack].items():
            f[k] = f[k] + (f[k] * (mult - 1) + add) * intensity
    f["syn_ratio"] = min(1.0, f["syn_ratio"])
    f["mean_size"] = min(1500.0, f["mean_size"])
    return f


def simulate(scenario="mixed", topo="star", n_hosts=6, duration=170, warmup=30,
             seed=1, params=None, run_id=None, timeline=None):
    """Generator: yields (tick, [events]) one tick at a time."""
    rng = random.Random(seed)
    run_id = run_id or uuid.uuid4().hex[:8]
    hosts, nodes, links = topology(topo, n_hosts)
    engine = TrustEngine(params or Params(warmup=warmup))
    base = timeline if timeline is not None else SCENARIOS[scenario]      # custom attacks from the dashboard
    timeline = [(a, h, s + warmup, e + warmup) for a, h, s, e in base if h in hosts and a in ATTACKS]
    # every host gets a slightly different normal profile
    scale = {h: {k: rng.uniform(0.85, 1.15) for k in NORMAL} for h in hosts}

    yield 0, [make_event(run_id, 0, "run_start", None, scenario=scenario, topology=topo,
                         nodes=nodes, links=links, duration=duration, warmup=warmup, mode="simulator")] + \
        [make_event(run_id, 0, "label", h, attack=a, t_start=s, t_end=e) for a, h, s, e in timeline]

    state = {h: "Trusted" for h in hosts}
    for t in range(1, duration + 1):
        evs = []
        for h in hosts:
            attack = next((a for a, hh, s, e in timeline if hh == h and s <= t < e), None)
            feats = _sample(rng, scale[h], attack, LEAK[state[h]])
            out = engine.process(h, feats)
            changed, prev = out.pop("changed"), out["prev_state"]
            state[h] = out["state"]
            evs.append(make_event(run_id, t, "flow_score", h, **out))
            if changed:
                evs.append(make_event(run_id, t, "state_change", h, **{"from": prev, "to": out["state"], "trust": out["trust"]}))
                evs.append(make_event(run_id, t, "enforcement", h, action=ACTIONS[out["state"]],
                                      rule=f"priority=100,ip,nw_src=10.0.0.{h[1:]} actions={ACTIONS[out['state']]}"))
        yield t, evs
    yield duration + 1, [make_event(run_id, duration + 1, "run_end", None)]
