"""
INGEST SERVICE - the door for external input. Used by:
  POST /api/ingest        (a teammate's script, curl, anything over HTTP)
  adapter/replay.py       (CSV replay)
Per run it keeps one engine, so baselines and trust persist across calls.
The dashboard shows a new host as soon as its first window arrives.
"""
import threading

from adapter.adapter import EngineAdapter
from adapter.mapping import to_features
from event_store.schema import make_event


class Ingest:
    def __init__(self, store):
        self.store, self.runs, self.lock = store, {}, threading.Lock()

    def _announce(self, run_id, r, scenario):
        hosts = sorted(r["hosts"], key=lambda h: int("".join(c for c in h if c.isdigit()) or 0))
        nodes = [{"id": h, "kind": "host"} for h in hosts] + [{"id": "s1", "kind": "switch"}]
        links = [["s1", h] for h in hosts]
        self.store.add_many([make_event(run_id, 0, "run_start", None, scenario=scenario, topology="external",
                                        nodes=nodes, links=links, duration=0, warmup=30, mode="external")])

    def start(self, run_id, scenario, topology, nodes, links, duration=0, warmup=30, mode="external"):
        """Register a source-defined run before its first scored window arrives."""
        with self.lock:
            r = self.runs.setdefault(run_id, {"adapter": EngineAdapter(self.store, run_id), "hosts": set()})
            if r.get("started"):
                return
            r["started"] = True
            r["hosts"].update(n["id"] for n in nodes if n.get("kind") == "host")
            self.store.add_many([make_event(run_id, 0, "run_start", None, scenario=scenario, topology=topology,
                                            nodes=nodes, links=links, duration=duration, warmup=warmup, mode=mode)])

    def push(self, run_id, t, host, raw, scenario="external"):
        feats = to_features(raw)                      # may raise ValueError -> HTTP 422
        with self.lock:
            r = self.runs.setdefault(run_id, {"adapter": EngineAdapter(self.store, run_id), "hosts": set()})
            if host not in r["hosts"]:
                r["hosts"].add(host)
                if not r.get("started"):
                    self._announce(run_id, r, scenario)
            return r["adapter"].window(t, host, feats)

    def label(self, run_id, host, attack, t_start, t_end):
        """Ground truth, from YOUR scenario definition. Never passed to the engine."""
        self.store.add_many([make_event(run_id, 0, "label", host, attack=attack, t_start=t_start, t_end=t_end)])

    def end(self, run_id):
        self.store.add_many([make_event(run_id, 0, "run_end", None)])
