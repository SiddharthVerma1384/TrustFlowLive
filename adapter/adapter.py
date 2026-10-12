"""
EVENT ADAPTER - the ONLY place that knows how a source's raw output maps to the common schema.
Two entry points:
  * EngineAdapter.window(...)  : real pipeline (TShark windows -> TrustEngine -> events -> store)
  * normalize(raw)             : validates/repairs any raw dict a teammate's code emits
If your teammates' engine prints something different, change ONLY this file.
"""
from engine.core import TrustEngine, FEATURES
from event_store.schema import make_event, ACTIONS, EVENT_TYPES


def normalize(raw, run_id):
    """Accepts a loose dict from any source and returns a schema-valid event."""
    if raw.get("type") not in EVENT_TYPES:
        raise ValueError(f"bad event type: {raw.get('type')}")
    return make_event(run_id, int(raw.get("t", 0)), raw["type"], raw.get("host"), **raw.get("data", {}))


class EngineAdapter:
    """Wraps the engine for the real pipeline and turns each scored window into events."""

    def __init__(self, store, run_id, engine=None, enforcer=None):
        self.store, self.run_id = store, run_id
        self.engine = engine or TrustEngine()
        self.enforcer = enforcer          # callable(host, action) -> talks to OS-Ken (controller/)

    def window(self, t, host, feats):
        out = self.engine.process(host, {k: feats.get(k, 0.0) for k in FEATURES})
        changed, prev = out.pop("changed"), out["prev_state"]
        evs = [make_event(self.run_id, t, "flow_score", host, **out)]
        if changed:
            evs.append(make_event(self.run_id, t, "state_change", host, **{"from": prev, "to": out["state"], "trust": out["trust"]}))
            evs.append(make_event(self.run_id, t, "enforcement", host, action=out["action"], rule=f"{host} -> {out['action']}"))
            if self.enforcer:
                self.enforcer(host, out["action"])
        self.store.add_many(evs)
        return out


def udp_enforcer(host_addr=("127.0.0.1", 9999)):
    """Returns a callable(host, action) that sends the decision to controller/enforcer.py over UDP."""
    import json, socket
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    return lambda host, action: sock.sendto(json.dumps({"host": host, "action": action}).encode(), host_addr)
