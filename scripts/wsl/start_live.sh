#!/usr/bin/env bash
set -Eeuo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
VENV_DIR="${TRUSTFLOW_VENV:-$ROOT_DIR/.venv-wsl}"
# In WSL mirrored/NAT networking the Windows host is the default route gateway.
# resolv.conf can contain a DNS-only address, so use it only as a fallback.
WINDOWS_HOST="${TRUSTFLOW_WINDOWS_HOST:-$(ip route | awk '/default/{print $3; exit}')}"
WINDOWS_HOST="${WINDOWS_HOST:-$(awk '/nameserver/{print $2; exit}' /etc/resolv.conf)}"
API_URL="${TRUSTFLOW_API_URL:-http://${WINDOWS_HOST}:8000}"
IFACE="${TRUSTFLOW_IFACE:-any}"
RUN_ID="${TRUSTFLOW_RUN_ID:-live-$(date +%Y%m%d-%H%M%S)}"
SCENARIO="${TRUSTFLOW_SCENARIO:-mixed}"
TOPOLOGY="${TRUSTFLOW_TOPOLOGY:-star}"
HOSTS="${TRUSTFLOW_HOSTS:-6}"
TIMELINE_JSON="${TRUSTFLOW_TIMELINE_JSON:-}"
TIMELINE_B64="${TRUSTFLOW_TIMELINE_B64:-}"
LOG_DIR="${TRUSTFLOW_LOG_DIR:-$ROOT_DIR/logs/live}"

usage() {
  echo "Usage: sudo $0 [--api-url URL] [--iface IFACE] [--run-id ID] [--scenario NAME] [--topology NAME] [--hosts N] [--timeline-json JSON|--timeline-b64 VALUE]"
  echo "Starts OS-Ken, metadata-only TShark capture, and the Mininet scenario."
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --api-url) API_URL="$2"; shift 2 ;;
    --iface) IFACE="$2"; shift 2 ;;
    --run-id) RUN_ID="$2"; shift 2 ;;
    --scenario) SCENARIO="$2"; shift 2 ;;
    --topology|--topo) TOPOLOGY="$2"; shift 2 ;;
    --hosts) HOSTS="$2"; shift 2 ;;
    --timeline-json) TIMELINE_JSON="$2"; shift 2 ;;
    --timeline-b64) TIMELINE_B64="$2"; shift 2 ;;
    -h|--help) usage; exit 0 ;;
    *) echo "Unknown option: $1" >&2; usage >&2; exit 2 ;;
  esac
done

if [[ "$(id -u)" -ne 0 ]]; then
  echo "Run this script with sudo because Mininet and TShark need network privileges." >&2
  exit 1
fi
[[ -f "$VENV_DIR/bin/activate" ]] || { echo "Missing $VENV_DIR; run setup_trustflow_wsl.sh first." >&2; exit 1; }

source "$VENV_DIR/bin/activate"
PYTHON="$VENV_DIR/bin/python"
OSKEN_MANAGER="$VENV_DIR/bin/osken-manager"
[[ -x "$PYTHON" ]] || { echo "Missing venv Python: $PYTHON" >&2; exit 1; }
[[ -x "$OSKEN_MANAGER" ]] || { echo "Missing OS-Ken: $OSKEN_MANAGER; rerun setup_trustflow_wsl.sh" >&2; exit 1; }
export PYTHONPATH="$ROOT_DIR${PYTHONPATH:+:$PYTHONPATH}"
cd "$ROOT_DIR"
mkdir -p "$LOG_DIR"

echo "Cleaning stale Mininet/OVS state..."
mn -c >"$LOG_DIR/mininet-clean.log" 2>&1 || true

cleanup() {
  set +e
  [[ -n "${MININET_PID:-}" ]] && kill "$MININET_PID" 2>/dev/null
  [[ -n "${TSHARK_PID:-}" ]] && kill "$TSHARK_PID" 2>/dev/null
  [[ -n "${OSKEN_PID:-}" ]] && kill "$OSKEN_PID" 2>/dev/null
  mn -c >/dev/null 2>&1
}
trap cleanup EXIT INT TERM

echo "Starting OS-Ken controller..."
"$OSKEN_MANAGER" "$ROOT_DIR/controller/enforcer.py" --ofp-tcp-listen-port 6653 \
  >"$LOG_DIR/osken.log" 2>&1 & OSKEN_PID=$!
sleep 2
if ! kill -0 "$OSKEN_PID" 2>/dev/null; then
  echo "OS-Ken failed to start. Last log lines:" >&2
  tail -n 40 "$LOG_DIR/osken.log" >&2
  exit 1
fi

echo "Starting metadata-only TShark capture on $IFACE..."
"$PYTHON" -m adapter.tshark_collector --iface "$IFACE" --run-id "$RUN_ID" \
  --api-url "$API_URL" --host-max "$HOSTS" >"$LOG_DIR/tshark.log" 2>&1 & TSHARK_PID=$!
sleep 1
if ! kill -0 "$TSHARK_PID" 2>/dev/null; then
  echo "TShark collector failed to start. Last log lines:" >&2
  tail -n 40 "$LOG_DIR/tshark.log" >&2
  exit 1
fi

echo "Starting Mininet ($TOPOLOGY, $HOSTS hosts, scenario=$SCENARIO)..."
MININET_ARGS=(--scenario "$SCENARIO" --topo "$TOPOLOGY" --hosts "$HOSTS" --run-id "$RUN_ID" --api-url "$API_URL")
if [[ -n "$TIMELINE_JSON" ]]; then
  MININET_ARGS+=(--timeline-json "$TIMELINE_JSON")
elif [[ -n "$TIMELINE_B64" ]]; then
  MININET_ARGS+=(--timeline-b64 "$TIMELINE_B64")
fi
"$PYTHON" -m scenarios.mininet_run "${MININET_ARGS[@]}" \
  >"$LOG_DIR/mininet.log" 2>&1 & MININET_PID=$!

while kill -0 "$MININET_PID" 2>/dev/null; do
  if ! kill -0 "$OSKEN_PID" 2>/dev/null; then
    echo "OS-Ken stopped while Mininet was running. Last log lines:" >&2
    tail -n 40 "$LOG_DIR/osken.log" >&2
    kill "$MININET_PID" 2>/dev/null
    exit 1
  fi
  if ! kill -0 "$TSHARK_PID" 2>/dev/null; then
    echo "TShark collector stopped while Mininet was running. Last log lines:" >&2
    tail -n 40 "$LOG_DIR/tshark.log" >&2
    kill "$MININET_PID" 2>/dev/null
    exit 1
  fi
  sleep 1
done

set +e
wait "$MININET_PID"
STATUS=$?
set -e
if [[ "$STATUS" -ne 0 ]]; then
  echo "Mininet scenario failed. Last log lines:" >&2
  tail -n 40 "$LOG_DIR/mininet.log" >&2
  exit "$STATUS"
fi
