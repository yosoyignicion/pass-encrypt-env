#!/usr/bin/env bash
# Smoke end-to-end (headless): levanta el agente con una bóveda temporal,
# comprueba IPC/estado y que `env --if-unlocked` sale con 3 si está bloqueada.
set -euo pipefail
REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO"
export PYTHONPATH="$REPO/src"
export XDG_RUNTIME_DIR="$(mktemp -d)"
VAULT="$(mktemp -d)/vault.enc"

python3 -c "from pass_encrypt_env import vault; v,_,_=vault.create_vault('smoke', time_cost=1, memory_cost=8192, lanes=1); vault.save_vault(v, '$VAULT')"

python3 -m pass_encrypt_env.agent --vault "$VAULT" --no-popup >/tmp/passenv-smoke-agent.log 2>&1 &
AGENT=$!
trap 'kill "$AGENT" 2>/dev/null || true' EXIT

for _ in $(seq 1 40); do
    if python3 -c "import sys; sys.path.insert(0,'src'); from pass_encrypt_env import ipc; sys.exit(0 if ipc.is_agent_running() else 1)"; then
        break
    fi
    sleep 0.25
done

echo "status: $(python3 -c "import sys; sys.path.insert(0,'src'); from pass_encrypt_env import ipc; print(ipc.request({'cmd':'status'}))")"

rc=0
python3 -m pass_encrypt_env.cli env --if-unlocked >/dev/null 2>&1 || rc=$?
echo "env --if-unlocked (bloqueada) -> exit $rc (esperado 3)"
[ "$rc" -eq 3 ]

echo "SMOKE OK"
