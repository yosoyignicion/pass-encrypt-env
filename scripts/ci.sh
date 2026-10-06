#!/usr/bin/env bash
# Gate de calidad: ruff + bandit + pytest.
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."
PY="${1:-python3}"

echo "== ruff =="
"$PY" -m ruff check .
echo "== bandit =="
"$PY" -m bandit -q -c bandit.yaml -r src
echo "== pytest =="
"$PY" -m pytest -q
echo "CI OK"
