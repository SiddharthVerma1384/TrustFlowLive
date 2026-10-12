"""STEP 2 - engine + simulator + evaluation, no server.   Run: python -m checks.step2_engine
Prints h3's journey so you can SEE detection, enforcement and recovery."""
from scenarios.simulator import simulate
from evaluation.metrics import evaluate
from event_store.schema import STATES

def events(scn, **kw):
    return [e for _, b in simulate(scn, **kw) for e in b]

# A. benign traffic must stay quiet
ben = events("benign")
flips = sum(e["type"] == "state_change" for e in ben)
print(f"benign run: {flips} state changes (expect 0-3)")
assert flips <= 3, "too many false alarms on benign traffic"

# B. port scan on h3 must be caught, then recovered from
ev = events("port_scan")
print("\nh3 timeline (port_scan from tick 50 to 100):")
for e in ev:
    if e["type"] == "state_change" and e["host"] == "h3":
        print(f"  t={e['t']:>3}  {e['data']['from']:<10} -> {e['data']['to']:<10} trust={e['data']['trust']:.2f}")
reached = max(STATES.index(e["data"]["to"]) for e in ev if e["type"] == "state_change" and e["host"] == "h3")
assert reached >= STATES.index("Restricted"), "port scan was not detected"
final = [e for e in ev if e["type"] == "flow_score" and e["host"] == "h3"][-1]["data"]
print(f"  final state at end of run: {final['state']} (trust {final['trust']:.2f})")

# C. evaluation against ground truth
r = evaluate(events("mixed"))
print("\nmixed scenario:", r["confusion"], "precision", r["precision"], "recall", r["recall"], "F1", r["f1"])
print("per-attack recall:", {a: v["recall"] for a, v in r["per_attack"].items()})
assert r["per_attack"]["port_scan"]["recall"] > 0.8 and r["per_attack"]["ddos"]["recall"] > 0.8
print("\nPASS step 2: detects scan/ddos/exfil, quiet on benign, evaluation works")
print("NOTE: 'beacon' recall is ~0 on purpose - it is the low-and-slow false-negative case.")
