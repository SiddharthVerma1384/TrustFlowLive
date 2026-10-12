# TrustFlow - Observability Layer (dashboard + event pipeline)

## Folder map
| folder | role | phase |
|---|---|---|
| event_store/  | schema.py (common event format) + store.py (SQLite WAL) | 3 |
| backend/      | FastAPI: REST + WebSocket + experiment manager           | 2, 4 |
| frontend/     | React dashboard (Vite)                                   | 5 |
| engine/       | reference TrustFlow engine (baseline, anomaly, trust, hysteresis) | 6, 8 |
| adapter/      | event adapter, TShark collector (real traffic)           | 6 |
| controller/   | OS-Ken enforcement app (installs OpenFlow rules)         | 6 |
| scenarios/    | simulator + Mininet runner, attack timelines, topologies | 7 |
| evaluation/   | metrics.py (P/R/F1, FP/FN, delay), experiments.py        | 9, 10 |

## Run (demo mode, no Mininet needed)
    python -m venv .venv && source .venv/bin/activate
    pip install -r requirements.txt
    python -m evaluation.experiments            # fills the Research page
    uvicorn backend.main:app --port 8000        # terminal 1
    cd frontend && npm install && npm run dev   # terminal 2  -> http://localhost:5173
Press "Start run" in the Control tab.

## Run (real mode, Ubuntu/WSL with root)
    osken-manager controller/enforcer.py                                  # terminal 1
    uvicorn backend.main:app --port 8000                                  # terminal 2
    sudo python -m scenarios.mininet_run --scenario mixed --run-id live   # terminal 3
    sudo python -m adapter.tshark_collector --iface s1-eth1 --run-id live # terminal 4
The dashboard needs no change: it only reads the event store.

## Known simplifications (state these honestly in the paper)
* Simulator features are synthetic; real-mode numbers must come from Mininet runs.
* In the simulator, enforcement scales only the attack traffic, not benign traffic.
* "Recovery lag" windows (attack over, host still Restricted) count as false positives.
* DPI comparison is not implemented yet: add a DPI engine emitting the same schema with mode="dpi".
* Real-mode scripts (tshark_collector, enforcer, mininet_run) are untested without Mininet.
