#!/usr/bin/env bash
# Comprueba que no haya secretos en el árbol de trabajo antes de publicar.
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."

if command -v gitleaks >/dev/null 2>&1; then
    echo "== gitleaks =="
    gitleaks detect --no-banner --redact --exit-code 1 || exit 1
    exit 0
fi

echo "== patrón (fallback; instala 'gitleaks' para un escaneo completo) =="
PAT='gh[posru]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}|AKIA[0-9A-Z]{16}|AIza[0-9A-Za-z_-]{35}|-----BEGIN (RSA|OPENSSH|EC|PGP) PRIVATE KEY-----'
HITS="$(grep -rIlE "$PAT" . \
    --exclude-dir=.git --exclude-dir=__pycache__ --exclude-dir=.venv \
    --exclude-dir=.pytest_cache --exclude-dir=.ruff_cache 2>/dev/null || true)"
if [ -n "$HITS" ]; then
    echo "POSIBLES SECRETOS ENCONTRADOS:"
    echo "$HITS"
    exit 1
fi
echo "secret-scan: limpio"
