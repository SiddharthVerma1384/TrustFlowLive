"""
STEP 6 - SEND YOUR OWN TRAFFIC to the running backend, one window per second, and watch the engine react.
Everything you may want to change is in the CONFIG block.  Nothing here uses the simulator.

    python -m checks.step6_send_traffic                    # port-scan style attack on h2
    python -m checks.step6_send_traffic --attack ddos --host h3 --run-id demo2
    python -m checks.step6_send_traffic --attack custom    # uses CUSTOM below
"""
import argparse, json, random, time, urllib.request

# ===================== CONFIG: edit freely =====================
HOSTS = ["h1", "h2", "h3", "h4"]
NORMAL = {"pps": (50, 5), "avg_pkt_len": (600, 40), "dst_count": (3, 0.7), "port_count": (4, 0.8), "syn_pct": (5, 1)}
ATTACKS = {                                 # field -> (multiplier, additive) applied on top of normal values
    "scan":   {"port_count": (1, 80), "dst_count": (1, 10), "syn_pct": (1, 60), "avg_pkt_len": (0.2, 0)},
    "ddos":   {"pps": (25, 0), "syn_pct": (1, 50), "avg_pkt_len": (0.15, 0)},
    "exfil":  {"avg_pkt_len": (2.2, 0), "pps": (3, 0)},
    "custom": {"pps": (10, 0)},             # <- invent your own behaviour here
}
BASELINE_TICKS, ATTACK_TICKS, RECOVERY_TICKS = 35, 25, 45
# ===============================================================
BASE = "http://localhost:8000"


def post(path, body):
    req = urllib.request.Request(BASE + path, json.dumps(body).encode(), {"Content-Type": "application/json"})
    return json.loads(urllib.request.urlopen(req, timeout=5).read())


def sample(attack):
    row = {k: max(0.0, random.gauss(m, s)) for k, (m, s) in NORMAL.items()}
    for k, (mult, add) in (attack or {}).items():
        row[k] = row[k] + row[k] * (mult - 1) + add
    return row


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--attack", default="scan", choices=list(ATTACKS)); ap.add_argument("--host", default="h2")
    ap.add_argument("--run-id", default="mytraffic"); ap.add_argument("--delay", type=float, default=0.3)
    a = ap.parse_args()
    t0, t1 = BASELINE_TICKS, BASELINE_TICKS + ATTACK_TICKS
    total = t1 + RECOVERY_TICKS
    print(f"run={a.run_id}: baseline 1-{t0}, '{a.attack}' attack on {a.host} {t0}-{t1}, recovery until {total}")
    for t in range(1, total + 1):
        for h in HOSTS:
            attacking = (h == a.host and t0 <= t < t1)
            out = post("/api/ingest", {"run_id": a.run_id, "t": t, "host": h,
                                       "features": sample(ATTACKS[a.attack] if attacking else None)})
            if h == a.host:
                tag = "ATTACK " if attacking else "       "
                print(f"t={t:>3} {tag}{h}: {out['state']:<10} trust={out['trust']:.2f} anomaly={out['anomaly']:.2f} [{out['phase']}]")
        time.sleep(a.delay)
    post("/api/ingest/label", {"run_id": a.run_id, "host": a.host, "attack": a.attack, "t_start": t0, "t_end": t1})
    print("done. Open the dashboard -> Evaluation tab for precision/recall on this run.")
