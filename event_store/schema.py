"""
PHASE 3 - COMMON EVENT SCHEMA
Every component (simulator, real engine, adapter, evaluation, dashboard) speaks this
one format.  An event is a plain dict:

    {run_id, t, type, host, data}      # store adds: id, ts (wall clock)

t    = tick number inside a run (simulated seconds).  All joins (labels vs scores) use t.
type = one of EVENT_TYPES below.
data = type-specific payload (documented next to each type).
"""

EVENT_TYPES = {
    # data: {scenario, topology, nodes:[{id,kind}], links:[[a,b]], duration, warmup, mode}
    "run_start",
    # data: {features{}, z{}, anomaly, trust, state, prev_state, phase, payload_bytes_inspected, mode}
    "flow_score",
    # data: {from, to, trust}
    "state_change",
    # data: {action, rule}      (the OpenFlow rule TrustFlow asked OS-Ken to install)
    "enforcement",
    # GROUND TRUTH. data: {attack, t_start, t_end}.  The engine must NEVER read these.
    "label",
    # data: {}
    "run_end",
}

STATES = ["Trusted", "Monitored", "Restricted", "Quarantine", "Blocked"]

ACTIONS = {
    "Trusted": "ALLOW",
    "Monitored": "ALLOW+LOG",
    "Restricted": "RATE_LIMIT",
    "Quarantine": "QUARANTINE",
    "Blocked": "DROP",
}


def make_event(run_id, t, type_, host=None, **data):
    if type_ not in EVENT_TYPES:
        raise ValueError(f"unknown event type {type_}")
    return {"run_id": run_id, "t": t, "type": type_, "host": host, "data": data}
