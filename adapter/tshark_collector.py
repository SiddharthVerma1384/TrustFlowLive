"""
PHASE 6 - REAL METADATA COLLECTION (needs root + a running Mininet/OVS; NOT tested in the sandbox)
Runs TShark on a switch port, aggregates 1-second windows per source IP, and pushes them through
EngineAdapter.  Only headers/metadata are read - payload bytes are never touched.

    sudo python -m adapter.tshark_collector --iface s1-eth1 --run-id live1
"""
import argparse
import subprocess
import time
from collections import defaultdict

from adapter.adapter import EngineAdapter, udp_enforcer
from event_store.store import EventStore
from event_store.schema import make_event

FIELDS = ["frame.time_epoch", "ip.src", "ip.dst", "frame.len", "tcp.dstport", "udp.dstport", "tcp.flags.syn"]


def ip_to_host(ip):                      # 10.0.0.3 -> h3 (Mininet default addressing)
    return "h" + ip.split(".")[-1]


def aggregate(rows):
    """rows: list of tshark field lists for one window -> {host: features}"""
    per = defaultdict(lambda: {"n": 0, "bytes": 0, "dsts": set(), "ports": set(), "syn": 0})
    for r in rows:
        if len(r) < 7 or not r[1]:
            continue
        d = per[ip_to_host(r[1])]
        d["n"] += 1; d["bytes"] += int(r[3] or 0); d["dsts"].add(r[2])
        d["ports"].add(r[4] or r[5]); d["syn"] += 1 if r[6] in ("1", "True") else 0
    return {h: {"pkt_rate": d["n"], "mean_size": d["bytes"] / d["n"], "unique_dsts": len(d["dsts"]),
                "unique_ports": len(d["ports"]), "syn_ratio": d["syn"] / d["n"]} for h, d in per.items()}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--iface", required=True); ap.add_argument("--run-id", default="live")
    ap.add_argument("--window", type=float, default=1.0)
    ap.add_argument("--no-enforce", action="store_true", help="score and display only; do not install rules")
    a = ap.parse_args()
    store = EventStore()
    store.add_many([make_event(a.run_id, 0, "run_start", None, scenario="live", topology="mininet",
                               nodes=[], links=[], duration=0, warmup=30, mode="real")])
    adapter = EngineAdapter(store, a.run_id, enforcer=None if a.no_enforce else udp_enforcer())
    cmd = ["tshark", "-i", a.iface, "-l", "-T", "fields", "-E", "separator=,"]
    for f in FIELDS:
        cmd += ["-e", f]
    p = subprocess.Popen(cmd, stdout=subprocess.PIPE, text=True)
    rows, t, start = [], 0, time.time()
    for line in p.stdout:
        rows.append(line.rstrip("\n").split(","))
        if time.time() - start >= a.window:
            t += 1; start = time.time()
            for host, feats in aggregate(rows).items():
                adapter.window(t, host, feats)
            rows = []


if __name__ == "__main__":
    main()
