"""
PHASE 2 + 4 - FASTAPI COMMUNICATION LAYER + LIVE WEBSOCKET PIPELINE

  REST       history, runs, state aggregate, evaluation, research results, scenario control
  WebSocket  /ws  pushes new events in batches (every 250 ms) so React never floods

Run from the project root:   uvicorn backend.main:app --reload --port 8000
"""
import asyncio
import json
from pathlib import Path

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from event_store.store import EventStore
from evaluation.metrics import evaluate
from typing import List, Optional
from adapter.ingest import Ingest
from scenarios.simulator import SCENARIOS, ATTACKS, simulate

app = FastAPI(title="TrustFlow Observability Layer")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
store = EventStore()
ingest = Ingest(store)
RESULTS = Path(__file__).resolve().parent.parent / "evaluation" / "results"


# ------------------------------------------------------------------ WebSocket hub
class Hub:
    def __init__(self):
        self.clients = set()

    async def connect(self, ws):
        await ws.accept(); self.clients.add(ws)

    def drop(self, ws):
        self.clients.discard(ws)

    async def broadcast(self, payload):
        dead = []
        for c in self.clients:
            try:
                await c.send_text(payload)
            except Exception:
                dead.append(c)
        for c in dead:
            self.drop(c)


hub = Hub()


@app.on_event("startup")
async def start_tailer():
    """Tails the event store (works for simulator AND the real pipeline - anything that writes to it)."""
    async def tail():
        last = store.max_id()
        while True:
            await asyncio.sleep(0.25)
            batch = store.query(since_id=last, limit=2000)
            for e in batch:                      # the terminal shows the decisions too
                if e["type"] == "state_change":
                    d = e["data"]
                    print(f"[trustflow] run={e['run_id']} t={e['t']:>3} {e['host']}: {d['from']} -> {d['to']} (trust {d['trust']:.2f})", flush=True)
                elif e["type"] == "enforcement":
                    print(f"[openflow ] {e['host']}: {e['data']['action']}  {e['data']['rule']}", flush=True)
            if batch and hub.clients:
                last = batch[-1]["id"]
                await hub.broadcast(json.dumps({"events": batch}))
            elif batch:
                last = batch[-1]["id"]
    asyncio.create_task(tail())


@app.websocket("/ws")
async def ws_endpoint(ws: WebSocket):
    await hub.connect(ws)
    try:
        while True:
            await ws.receive_text()      # keep-alive; client never needs to send anything
    except WebSocketDisconnect:
        hub.drop(ws)


# ------------------------------------------------------------------ Experiment manager (simulator mode)
class RunRequest(BaseModel):
    scenario: str = "mixed"
    topology: str = "star"
    hosts: int = 6
    duration: int = 170
    speed: float = 5.0         # ticks per second
    seed: int = 1
    custom: Optional[List[dict]] = None     # [{attack, host, start, end}] built in the dashboard


current = {"task": None, "run_id": None}


async def _drive(req: RunRequest):
    tl = None
    if req.custom:
        tl = [(c["attack"], c["host"], int(c["start"]), int(c["end"])) for c in req.custom if c["attack"] in ATTACKS]
    gen = simulate("benign" if tl is not None else req.scenario, req.topology, req.hosts, req.duration,
                   seed=req.seed, timeline=tl)
    for _, evs in gen:
        current["run_id"] = evs[0]["run_id"]
        store.add_many(evs)
        await asyncio.sleep(1.0 / req.speed)


@app.get("/api/scenarios")
def scenarios():
    return {"scenarios": list(SCENARIOS), "topologies": ["star", "linear", "tree"], "attacks": list(ATTACKS)}


@app.post("/api/runs")
async def start_run(req: RunRequest):
    if req.scenario not in SCENARIOS:
        raise HTTPException(400, "unknown scenario")
    if current["task"] and not current["task"].done():
        current["task"].cancel()
    current["task"] = asyncio.create_task(_drive(req))
    return {"started": True}


@app.post("/api/runs/stop")
async def stop_run():
    if current["task"] and not current["task"].done():
        current["task"].cancel()
    return {"stopped": True}


@app.delete("/api/events")
def wipe():
    store.clear(); return {"cleared": True}


# ------------------------------------------------------------------ REST: history / state / evaluation
@app.get("/api/health")
def health():
    return {"ok": True, "latest_run": store.latest_run_id()}


@app.get("/api/runs")
def runs():
    seen, out = set(), []
    for r in store.runs():                    # newest first; ingest re-announces runs as hosts appear
        if r["run_id"] not in seen:
            seen.add(r["run_id"])
            out.append({"run_id": r["run_id"], **{k: r["data"].get(k) for k in ("scenario", "topology", "mode", "duration")}})
    return out


@app.get("/api/runs/{run_id}/events")
def events(run_id: str, since_id: int = 0, types: str = "", host: str = "", limit: int = 50000):
    rid = store.latest_run_id() if run_id == "latest" else run_id
    return store.query(rid, since_id, types.split(",") if types else None, host or None, limit)


@app.get("/api/runs/{run_id}/state")
def state(run_id: str):
    """State aggregator: one row per host (latest score) + counts per state."""
    rid = store.latest_run_id() if run_id == "latest" else run_id
    rows = store.latest_per_host(rid) if rid else []
    counts = {}
    for r in rows:
        counts[r["data"]["state"]] = counts.get(r["data"]["state"], 0) + 1
    return {"run_id": rid, "hosts": rows, "state_counts": counts}


@app.get("/api/runs/{run_id}/evaluation")
def evaluation(run_id: str, min_state: str = "Restricted"):
    rid = store.latest_run_id() if run_id == "latest" else run_id
    return evaluate(store.query(rid, types=["flow_score", "label"]), min_state)


@app.get("/api/research")
def research():
    out = {}
    for f in RESULTS.glob("*.json"):
        out[f.stem] = json.loads(f.read_text())
    return out


# ------------------------------------------------------------------ DYNAMIC INPUT (any source -> engine -> dashboard)
class Window(BaseModel):
    run_id: str = "external"
    t: int
    host: str
    features: dict          # keys translated by adapter/mapping.py


class LabelReq(BaseModel):
    run_id: str = "external"
    host: str
    attack: str
    t_start: int
    t_end: int


@app.post("/api/ingest")
def ingest_one(w: Window):
    try:
        out = ingest.push(w.run_id, w.t, w.host, w.features)
    except ValueError as e:
        raise HTTPException(422, str(e))
    return {"state": out["state"], "trust": out["trust"], "anomaly": out["anomaly"], "phase": out["phase"]}


@app.post("/api/ingest/batch")
def ingest_batch(ws: List[Window]):
    try:
        for w in ws:
            ingest.push(w.run_id, w.t, w.host, w.features)
    except ValueError as e:
        raise HTTPException(422, str(e))
    return {"accepted": len(ws)}


@app.post("/api/ingest/label")
def ingest_label(l: LabelReq):
    ingest.label(l.run_id, l.host, l.attack, l.t_start, l.t_end)
    return {"ok": True}
