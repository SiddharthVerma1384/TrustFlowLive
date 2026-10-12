# TrustFlow - step-by-step guide (Windows + VS Code)

Always run commands from the project root (the folder that contains backend/, engine/, checks/ ...).
Python commands need the venv active -> prompt starts with (.venv). The frontend (npm) does NOT need it.

## A. One-time setup
    py -m venv .venv
    .venv\Scripts\Activate.ps1          # if blocked: Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
    pip install -r requirements.txt
    cd frontend ; npm install ; cd ..   # needs Node 18+

## B. Understand each layer WITHOUT any server (run in order)
    python -m checks.step1_store      # store + schema
    python -m checks.step2_engine     # engine, enforcement, recovery, evaluation (prints h3's journey)
    python -m checks.step3_mapping    # your field names -> engine features
    python -m checks.step4_csv        # data\my_data_example.csv through the whole pipeline
    python -m checks.run_offline_checks   # all four at once

What each proves, and what a failure means:
| step | proves | if it fails |
|---|---|---|
| 1 | SQLite store writes/reads; schema rejects bad types | folder wrong / venv not active |
| 2 | scan/ddos/exfil detected, benign quiet, recovery works, P/R/F1 computed | you changed engine/core.py thresholds |
| 3 | field names translate | add your names to adapter\mapping.py FIELD_MAP |
| 4 | CSV in a foreign format works end to end | CSV missing a feature column or bad header |

## C. Start the system (two terminals, or VS Code: Terminal > Run Task > "Start both")
Terminal 1 (venv):   uvicorn backend.main:app --port 8000
Terminal 2:          cd frontend ; npm run dev        -> http://localhost:5173
Python check while backend runs:   python -m checks.step5_api      (third terminal, venv)

## D. See the flow (demo traffic from the simulator)
1. Dashboard > Control > Start run (mixed).
2. Watch Terminal 1 print lines like:
     [trustflow] run=ab12 t= 50 h3: Trusted -> Restricted (trust 0.45)
     [openflow ] h3: RATE_LIMIT  priority=100,ip,nw_src=10.0.0.3 actions=RATE_LIMIT
3. Dashboard tabs: Live network (colours), Trust timeline (click h3), Event feed, Evaluation, Research.
   (Research needs:  python -m evaluation.experiments  once.)

## E. Send YOUR OWN traffic
E1. Live, window by window, over HTTP (backend running):
      python -m checks.step6_send_traffic
      python -m checks.step6_send_traffic --attack ddos --host h3 --run-id demo2
   Edit the CONFIG block at the top of checks\step6_send_traffic.py to change normal behaviour or
   invent a new attack (the "custom" entry). Terminal prints the engine's verdict every tick;
   the dashboard shows the same run live. Evaluation tab works because the script sends the label.

E2. From a CSV file:
      python -m adapter.replay --make-sample sample.csv     # shows our own format
      python -m adapter.replay data\my_data_example.csv --run-id mydata --speed 20
   Columns: t, host, <5 features>, label. Names are translated by adapter\mapping.py.
   Use YOUR export: change header names or add them to FIELD_MAP.

E3. From your own Python code (no HTTP):
      from event_store.store import EventStore
      from adapter.ingest import Ingest
      ing = Ingest(EventStore())
      ing.push("myrun", t, "h1", {"pps": 50, "avg_pkt_len": 600, "dst_count": 3, "port_count": 4, "syn_pct": 5})
      ing.label("myrun", "h1", "port_scan", 40, 80)   # ground truth, kept away from the engine

## F. Where to implement your own changes
| goal | file |
|---|---|
| new input format | adapter\mapping.py |
| new behavioural feature | engine\core.py FEATURES + adapter\mapping.py + simulator/collector |
| tune thresholds, trust speed, hysteresis | engine\core.py Params |
| new attack pattern | scenarios\simulator.py ATTACKS (and checks\step6 ATTACKS) |
| new dashboard view | frontend\src\components\ + register in App.jsx |
| new experiment | evaluation\experiments.py |
After editing engine/adapter/scenario files restart uvicorn (Ctrl+C, run again). Frontend hot-reloads.

## G. Reading errors
| message | meaning / fix |
|---|---|
| ModuleNotFoundError: engine | not in project root |
| ModuleNotFoundError: fastapi | venv not active / pip install not run |
| header badge "offline" | backend not running or other port: edit frontend\src\api.js |
| HTTP 422 "missing features [...]" | window lacks a field: fix names or add mapping |
| nodes stay grey | baseline learning: first 30 windows per host make no decisions |
| port already in use | old uvicorn still running: close it or use --port 8001 and edit api.js |
| database is locked | rare; stop everything, delete event_store\trustflow.db* |

## H. Honest limits
* Simulator and your own generated numbers are NOT measurements. Paper numbers must come from real
  Mininet/TShark captures (adapter\tshark_collector.py, scenarios\mininet_run.py, controller\enforcer.py - run in WSL2/Ubuntu, untested here).
* DPI comparison (sir's item 4) is not implemented yet.
* Recovery-lag windows after an attack count as false positives in evaluation.
