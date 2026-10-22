# TrustFlow live WSL mode

The live path is:

`Mininet traffic -> Open vSwitch -> TShark metadata capture -> /api/ingest -> TrustEngine -> SQLite event store -> WebSocket -> dashboard`

OS-Ken receives enforcement decisions from the backend-side collector over UDP on `127.0.0.1:9999` and applies OpenFlow rules to OVS on port `6653`.

## One-time WSL setup

From Ubuntu/WSL2, with this repository available under `/mnt/c/Users/siddm/Desktop/TrustFlowLive/trustflow`:

```bash
cd /mnt/c/Users/siddm/Desktop/TrustFlowLive/trustflow
TRUSTFLOW_VENV="$HOME/.venvs/trustflow" bash scripts/wsl/setup_trustflow_wsl.sh
```

If WSL reports access denied, enable the Windows optional features **Virtual Machine Platform** and **Windows Subsystem for Linux**, reboot, then install Ubuntu from the Microsoft Store or with `wsl --install -d Ubuntu` in an elevated PowerShell.

## Run

Start the Windows backend so it is reachable from WSL. If it is already running, do not start a second Uvicorn process on port 8000; that causes Windows error 10048. From PowerShell, the project launcher reuses a healthy backend:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\windows\start_trustflow.ps1
```

The launcher also starts the Vite frontend. If the backend is already healthy it prints that it is reusing it. Use `-ForceBackend` only after verifying that an unrelated process owns port 8000.

Then, in an elevated WSL shell:

```bash
cd /mnt/c/Users/siddm/Desktop/TrustFlowLive/trustflow
sudo TRUSTFLOW_VENV="$HOME/.venvs/trustflow" bash scripts/wsl/start_live.sh --iface any
```

The launcher automatically uses the Windows host gateway from WSL. If your network configuration needs a fixed address, set `TRUSTFLOW_WINDOWS_HOST` or pass `--api-url http://<windows-host-ip>:8000`.

## Start live mode from the website

The Control tab can now start and stop the live WSL pipeline through the FastAPI backend. Select **Live WSL**, choose the scenario, topology, host count, and capture interface, then select **Start run**. FastAPI launches WSL as root and passes the values to `start_live.sh`; the dashboard receives the resulting events through `/ws`.

The website does not require a new terminal command for each run. Starting a new live run stops the previous live process and starts a replacement with the new inputs. The WSL distribution defaults to `Ubuntu`; set the Windows environment variable `TRUSTFLOW_WSL_DISTRO` if the distribution has another name.

The **Simulator** option remains available for synthetic runs and custom attack timelines. Custom attack rows apply to simulator mode only; real WSL mode uses the scenario driver in `scenarios/mininet_run.py`.

Open the frontend at `http://localhost:5173`. The first captured host window creates the live run in the same backend event store; subsequent scores, state changes, and enforcement events are pushed over the existing WebSocket.

The capture adapter sends only timestamp, IPs, protocol, ports, frame length, and SYN metadata. Payload bytes are not read or sent to the backend.

Useful overrides are `TRUSTFLOW_IFACE`, `TRUSTFLOW_API_URL`, `TRUSTFLOW_RUN_ID`, `TRUSTFLOW_SCENARIO`, `TRUSTFLOW_TOPOLOGY`, and `TRUSTFLOW_HOSTS`.
