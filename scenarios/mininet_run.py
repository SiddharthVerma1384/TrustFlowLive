"""
PHASE 7 (real half) - MININET TOPOLOGY + ATTACK DRIVER (needs root; NOT tested in the sandbox)
Builds the same topologies as the simulator, with OVS + the OS-Ken RemoteController, then runs
the attack timeline using real traffic tools.  Ground-truth labels are written to the event store
directly from the scenario definition - the engine never sees them.

    sudo python -m scenarios.mininet_run --scenario mixed --topo star --hosts 6
Requires: mininet, hping3, iperf, (nmap optional).
"""
import argparse
import base64
import json
import time
from urllib import request

from mininet.net import Mininet
from mininet.node import RemoteController, OVSSwitch
from mininet.log import setLogLevel

from event_store.store import EventStore
from event_store.schema import make_event
from scenarios.simulator import SCENARIOS, topology

# real command per attack; {dst} is a victim IP.  Each runs in the attacker host for `d` seconds
CMDS = {
    "port_scan": "timeout {d} nmap -sS -p 1-1000 {dst} >/dev/null 2>&1",
    "ddos":      "timeout {d} hping3 -S --flood -p 80 {dst} >/dev/null 2>&1",
    "exfil":     "timeout {d} iperf -c {dst} -t {d} -l 1400 >/dev/null 2>&1",
    "beacon":    "for i in $(seq 1 {d}); do echo hi | nc -w1 {dst} 8080; sleep 5; done",
}


def post(api_url, path, body):
    req = request.Request(api_url.rstrip("/") + path,
                          data=json.dumps(body).encode(),
                          headers={"Content-Type": "application/json"})
    with request.urlopen(req, timeout=10) as response:
        if response.status >= 300:
            raise RuntimeError(f"backend rejected {path}: HTTP {response.status}")


def build(kind, n):
    hosts, nodes, links = topology(kind, n)
    net = Mininet(controller=None, switch=OVSSwitch, autoSetMacs=True)
    net.addController("c0", controller=RemoteController, ip="127.0.0.1", port=6653)
    objs = {x["id"]: (net.addHost(x["id"]) if x["kind"] == "host" else net.addSwitch(x["id"], protocols="OpenFlow13"))
            for x in nodes}
    for a, b in links:
        net.addLink(objs[a], objs[b])
    return net, hosts, nodes, links


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--scenario", default="mixed"); ap.add_argument("--topo", default="star")
    ap.add_argument("--hosts", type=int, default=6); ap.add_argument("--warmup", type=int, default=30)
    ap.add_argument("--run-id", default="live")
    ap.add_argument("--api-url", help="FastAPI base URL; use this in WSL live mode to avoid sharing SQLite")
    ap.add_argument("--timeline-json", help="JSON attack overrides: [{attack,host,target,start,end}]")
    ap.add_argument("--timeline-b64", help="Base64-encoded JSON attack overrides (safe across wsl.exe)")
    a = ap.parse_args()
    setLogLevel("info")
    store = None if a.api_url else EventStore()
    net, hosts, nodes, links = build(a.topo, a.hosts)
    net.start()
    if a.timeline_json and a.timeline_b64:
        raise SystemExit("use only one of --timeline-json and --timeline-b64")
    if a.timeline_b64:
        try:
            a.timeline_json = base64.b64decode(a.timeline_b64, validate=True).decode("utf-8")
        except (ValueError, UnicodeDecodeError) as exc:
            raise SystemExit(f"invalid --timeline-b64: {exc}")
    if a.timeline_json:
        try:
            custom = json.loads(a.timeline_json)
            base = [(item["attack"], item["host"], int(item["start"]), int(item["end"]), item.get("target", "h1"))
                    for item in custom]
        except (TypeError, ValueError, KeyError, json.JSONDecodeError) as exc:
            raise SystemExit(f"invalid --timeline-json: {exc}")
    else:
        base = [(x, h, s, e, "h1") for x, h, s, e in SCENARIOS[a.scenario]]
    host_set = set(hosts)
    for attack, source, start, end, target in base:
        if attack not in CMDS:
            raise SystemExit(f"unknown attack: {attack}")
        if source not in host_set or target not in host_set or source == target:
            raise SystemExit(f"invalid attack endpoints: {source} -> {target}")
        if start < 0 or end <= start:
            raise SystemExit(f"invalid attack window: {start}-{end}")
    tl = [(x, h, s + a.warmup, e + a.warmup, target) for x, h, s, e, target in base]
    if a.api_url:
        post(a.api_url, "/api/ingest/start", {"run_id": a.run_id, "scenario": a.scenario,
                                               "topology": a.topo, "nodes": nodes, "links": links,
                                                "duration": max([row[3] for row in tl] + [60]) + 20,
                                               "warmup": a.warmup, "mode": "real"})
        for x, h, s, e, target in tl:
            post(a.api_url, "/api/ingest/label", {"run_id": a.run_id, "host": h, "attack": x,
                                                    "t_start": s, "t_end": e, "target": target})
    else:
        store.add_many([make_event(a.run_id, 0, "run_start", None, scenario=a.scenario, topology=a.topo,
                                   nodes=nodes, links=links, duration=max([row[3] for row in tl] + [60]) + 20,
                                   warmup=a.warmup, mode="real")] +
                       [make_event(a.run_id, 0, "label", h, attack=x, t_start=s, t_end=e, target=target)
                        for x, h, s, e, target in tl])
    # benign background: every host pings the victim (h1)
    for h in hosts[1:]:
        net.get(h).cmd(f"ping -i 0.5 {net.get('h1').IP()} >/dev/null 2>&1 &")
    t0 = time.time()
    for x, h, s, e, target in sorted(tl, key=lambda r: r[2]):
        time.sleep(max(0, t0 + s - time.time()))
        net.get(h).cmd(CMDS[x].format(d=e - s, dst=net.get(target).IP()) + " &")
    time.sleep(max([row[3] for row in tl] + [0]) - (time.time() - t0) + 10)
    if a.api_url:
        post(a.api_url, "/api/ingest/end", {"run_id": a.run_id})
    else:
        store.add_many([make_event(a.run_id, 0, "run_end", None)])
    net.stop()


if __name__ == "__main__":
    main()
