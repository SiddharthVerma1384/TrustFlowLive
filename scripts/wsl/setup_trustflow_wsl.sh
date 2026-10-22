#!/usr/bin/env bash
set -Eeuo pipefail

# Run from Ubuntu/WSL2. This installs the host-side tools required for the
# real Mininet -> OVS -> OS-Ken -> TShark -> TrustFlow API path.
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
VENV_DIR="${TRUSTFLOW_VENV:-$ROOT_DIR/.venv-wsl}"

if [[ "$(id -u)" -ne 0 ]]; then
  SUDO=sudo
else
  SUDO=
fi

$SUDO apt-get update
$SUDO env DEBIAN_FRONTEND=noninteractive apt-get install -y \
  python3 python3-venv python3-pip build-essential git \
  mininet openvswitch-switch tshark nmap hping3 iperf netcat-openbsd

mkdir -p "$(dirname "$VENV_DIR")"
# Mininet is supplied by Ubuntu's system package, so expose system site
# packages to the venv while keeping OS-Ken and TrustFlow dependencies isolated.
python3 -m venv --system-site-packages "$VENV_DIR"
source "$VENV_DIR/bin/activate"
python -m pip install --upgrade pip
python -m pip install -r "$ROOT_DIR/requirements.txt" -r "$ROOT_DIR/requirements-live.txt"

echo
echo "TrustFlow WSL environment ready."
echo "Activate it with: source '$VENV_DIR/bin/activate'"
echo "Next: 'bash $ROOT_DIR/scripts/wsl/start_live.sh --help'"
