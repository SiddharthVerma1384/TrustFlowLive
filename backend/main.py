"""
PHASE 2 + 4 - FASTAPI COMMUNICATION LAYER + LIVE WEBSOCKET PIPELINE

  REST       history, runs, state aggregate, evaluation, research results, scenario control
  WebSocket  /ws  pushes new events in batches (every 250 ms) so React never floods

Run from the project root:   uvicorn backend.main:app --reload --port 8000
"""
import asyncio
import base64
import json
import os
import subprocess
from datetime import datetime
from pathlib import Path

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from event_store.store import EventStore
from evaluation.metrics import evaluate
from typing import List, Optional
from adapter.ingest import Ingest
from scenarios.simulator import SCENARIOS, ATTACKS, simulate, topology as scenario_topology

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


class LiveRunRequest(BaseModel):
    scenario: str = "mixed"
    topology: str = "star"
    hosts: int = 6
    duration: int = 170
    iface: str = "any"
    custom: Optional[List[dict]] = None


current = {"task": None, "run_id": None}
live = {"process": None, "run_id": None, "request": None, "log": None}


def _live_running():
    process = live.get("process")
    return bool(process and process.poll() is None)


def _stop_live_process():
    process = live.get("process")
    if process and process.poll() is None:
        process.terminate()
        try:
            process.wait(timeout=8)
        except subprocess.TimeoutExpired:
            process.kill()
    # Keep the last run metadata visible after a run completes or the user
    # presses Stop.  Clearing it made `/api/live/status` look as though no run
    # had ever been started, even though the run and its logs still existed.
    live.update(process=None)


def _wsl_path(path):
    """Convert a Windows drive path to the standard WSL /mnt/<drive>/ form."""
    value = Path(path).resolve().as_posix()
    if len(value) >= 2 and value[1] == ":":
        return f"/mnt/{value[0].lower()}{value[2:]}"
    return value


def _start_live_process(req):
    _stop_live_process()
    root = Path(__file__).resolve().parent.parent
    script = root / "scripts" / "wsl" / "start_live.sh"
    log_dir = root / "logs" / "live"
    log_dir.mkdir(parents=True, exist_ok=True)
    run_id = f"live-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
    log_path = log_dir / "backend-live.log"
    distro = os.environ.get("TRUSTFLOW_WSL_DISTRO", "Ubuntu")
    venv = os.environ.get("TRUSTFLOW_VENV", "/home/user_ss/.venvs/trustflow")
    args = [
        "wsl.exe", "-d", distro, "-u", "root", "--", "env",
        f"TRUSTFLOW_VENV={venv}", "bash", _wsl_path(script),
        "--iface", req.iface, "--run-id", run_id,
        "--scenario", req.scenario, "--topology", req.topology,
        "--hosts", str(req.hosts), "--duration", str(req.duration),
    ]
    if req.custom:
        # Passing raw JSON through wsl.exe is unsafe: its Windows command-line
        # parsing splits the embedded quotes into separate Linux arguments.
        # Base64 keeps the value to a single shell-safe argument.
        timeline = json.dumps(req.custom, separators=(",", ":")).encode("utf-8")
        args.extend(["--timeline-b64", base64.b64encode(timeline).decode("ascii")])
    env = os.environ.copy()
    env["TRUSTFLOW_VENV"] = venv
    env["TRUSTFLOW_IFACE"] = req.iface
    hosts, nodes, links = scenario_topology(req.topology, req.hosts)
    duration = req.duration
    # Register the complete topology before TShark can observe its first packet.
    # Otherwise the collector could create an "external" run with only h1.
    ingest.start(
        run_id, req.scenario, req.topology, nodes, links, duration, 30, "real",
        inputs={
            "mode": "live",
            "scenario": req.scenario,
            "topology": req.topology,
            "hosts": req.hosts,
            "duration": req.duration,
            "interface": req.iface,
            "custom_attacks": req.custom or [],
        },
    )
    with log_path.open("a", encoding="utf-8") as log:
        process = subprocess.Popen(args, cwd=root, env=env, stdout=log, stderr=subprocess.STDOUT)
    live.update(process=process, run_id=run_id, request=req.model_dump(), log=str(log_path))
    return run_id


def _check_wsl_access():
    distro = os.environ.get("TRUSTFLOW_WSL_DISTRO", "Ubuntu")
    try:
        result = subprocess.run(
            ["wsl.exe", "-d", distro, "-u", "root", "--", "id", "-u"],
            capture_output=True, text=True, timeout=10, encoding="utf-8", errors="replace",
        )
    except (FileNotFoundError, subprocess.TimeoutExpired) as exc:
        raise HTTPException(503, f"WSL is not available: {exc}")
    output = result.stdout.replace("\x00", "").strip()
    if result.returncode != 0 or output != "0":
        detail = (result.stderr or result.stdout).replace("\x00", "").strip()
        raise HTTPException(503, f"WSL root access failed for {distro}: {detail[-500:]}")


@app.on_event("shutdown")
def stop_live_on_shutdown():
    _stop_live_process()


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
    _stop_live_process()
    if current["task"] and not current["task"].done():
        current["task"].cancel()
    current["task"] = asyncio.create_task(_drive(req))
    return {"started": True}


@app.post("/api/runs/stop")
async def stop_run():
    if current["task"] and not current["task"].done():
        current["task"].cancel()
    return {"stopped": True}


@app.post("/api/live/start")
def start_live(req: LiveRunRequest):
    if req.scenario not in SCENARIOS:
        raise HTTPException(400, "unknown scenario")
    if req.topology not in ("star", "linear", "tree"):
        raise HTTPException(400, "unknown topology")
    if not 3 <= req.hosts <= 12:
        raise HTTPException(400, "hosts must be between 3 and 12")
    if not 60 <= req.duration <= 400:
        raise HTTPException(400, "duration must be between 60 and 400 ticks")
    if not req.iface or any(c in req.iface for c in ";&|`$\n\r"):
        raise HTTPException(400, "invalid capture interface")
    for item in req.custom or []:
        attack = item.get("attack")
        source = item.get("host")
        target = item.get("target", "h1")
        try:
            start, end = int(item.get("start")), int(item.get("end"))
            source_num = int(str(source).removeprefix("h"))
            target_num = int(str(target).removeprefix("h"))
        except (TypeError, ValueError):
            raise HTTPException(400, "custom live attack hosts/times are invalid")
        if attack not in ATTACKS:
            raise HTTPException(400, f"unknown attack: {attack}")
        if not (1 <= source_num <= req.hosts and 1 <= target_num <= req.hosts):
            raise HTTPException(400, "custom live attack hosts must exist in the selected host range")
        if source_num == target_num or start < 0 or end <= start or end > req.duration:
            raise HTTPException(400, "custom live attack must have different hosts and fit inside the duration")
    _check_wsl_access()
    if current["task"] and not current["task"].done():
        current["task"].cancel()
    try:
        run_id = _start_live_process(req)
    except FileNotFoundError as e:
        raise HTTPException(500, f"WSL launcher unavailable: {e}")
    return {"started": True, "run_id": run_id, "mode": "real"}


@app.post("/api/live/stop")
def stop_live():
    _stop_live_process()
    return {"stopped": True}


@app.get("/api/live/status")
def live_status():
    process = live.get("process")
    return {
        "running": _live_running(),
        "run_id": live.get("run_id"),
        "pid": process.pid if process else None,
        "exit_code": process.poll() if process else None,
        "request": live.get("request"),
        "log": live.get("log"),
    }


@app.get("/api/live/preflight")
def live_preflight():
    _check_wsl_access()
    return {"ok": True, "wsl": "ready"}


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
    target: Optional[str] = None


class EndReq(BaseModel):
    run_id: str = "external"
    t: int = 0


class StartReq(BaseModel):
    run_id: str = "external"
    scenario: str = "external"
    topology: str = "external"
    nodes: List[dict] = []
    links: List[list] = []
    duration: int = 0
    warmup: int = 30
    mode: str = "external"


@app.post("/api/ingest")
def ingest_one(w: Window):
    try:
        out = ingest.push(w.run_id, w.t, w.host, w.features)
    except ValueError as e:
        raise HTTPException(422, str(e))
    return {"state": out["state"], "trust": out["trust"], "anomaly": out["anomaly"], "phase": out["phase"]}


@app.post("/api/ingest/start")
def ingest_start(s: StartReq):
    ingest.start(s.run_id, s.scenario, s.topology, s.nodes, s.links, s.duration, s.warmup, s.mode)
    return {"ok": True}


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
    ingest.label(l.run_id, l.host, l.attack, l.t_start, l.t_end, l.target)
    return {"ok": True}


@app.post("/api/ingest/end")
def ingest_end(e: EndReq):
    ingest.end(e.run_id, e.t)
    return {"ok": True}
