"""STEP 5 - backend must be RUNNING (uvicorn backend.main:app --port 8000).   Run: python -m checks.step5_api"""
import json, urllib.request, urllib.error

BASE = "http://localhost:8000"

def call(path, body=None, method=None):
    req = urllib.request.Request(BASE + path, data=json.dumps(body).encode() if body is not None else None,
                                 headers={"Content-Type": "application/json"}, method=method)
    with urllib.request.urlopen(req, timeout=5) as r:
        return json.loads(r.read())

try:
    print("health:", call("/api/health"))
except Exception as e:
    raise SystemExit(f"FAIL: backend not reachable ({e}). Start it first: uvicorn backend.main:app --port 8000")

w = {"run_id": "apicheck", "t": 1, "host": "h1",
     "features": {"pps": 50, "avg_pkt_len": 600, "dst_count": 3, "port_count": 4, "syn_pct": 5}}
print("ingest ok:", call("/api/ingest", w))
try:
    call("/api/ingest", {"run_id": "apicheck", "t": 2, "host": "h1", "features": {"pps": 50}})
    raise SystemExit("FAIL: incomplete window was accepted")
except urllib.error.HTTPError as e:
    print("incomplete window rejected with HTTP", e.code, "-", json.loads(e.read())["detail"][:70])
print("state:", call("/api/runs/apicheck/state")["state_counts"])
print("scenarios:", call("/api/scenarios")["scenarios"])
print("PASS step 5: REST + ingest + error handling work. Now open the dashboard and look for run 'apicheck'.")
