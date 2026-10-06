# AGENTS.md

Guía para agentes/colaboradores que trabajen en **pass-encrypt-env**.

## Qué es
Bóveda local de secretos (master + TOTP) con **agente de sesión** que sirve las
claves a las apps durante el login sin volver a pedir nada (cero-prompt).

## Mapa del código (`src/pass_encrypt_env/`)
- `crypto.py` — primitivas: Argon2id (KDF), HKDF, AES-256-GCM (AEAD).
- `vault.py` — formato `vault.enc`, envoltura de la DEK (master+TOTP / recovery),
  carga/guardado atómico.
- `totp.py` — RFC 6238 con stdlib.
- `recovery.py` — clave de recuperación base32 + checksum.
- `ipc.py` — socket Unix + `SO_PEERCRED` (solo mismo UID) + `0600`.
- `agent.py` — `passenv-agent`: mantiene la bóveda en RAM, endurecimiento del proceso.
- `ui.py` — pop-up GTK3 no modal + bandeja.
- `cli.py` — `passenv`.

## Invariantes (no romper)
- **Nunca** escribir secretos en claro en disco; todo pasa por AEAD.
- La DEK se envuelve **dos veces**: `K2=HKDF(K1,·‖totp_secret)` y `K3=HKDF(recovery)`.
- Cualquier entrada pegada desde GUI se **sanea** (`strip`) antes de derivar claves.
- El socket es `0600` y valida UID con `SO_PEERCRED`.
- El agente no bloquea el escritorio; el pop-up es **no modal**.
- `bin/passenv-load` **nunca** se ejecuta con `-x` sin `set +x`.

## Comandos
- Tests: `pytest -q` · Lint: `ruff check .` · Seguridad: `bandit -q -r src`
- Gate completo: `./scripts/ci.sh`
- Smoke del agente: `./scripts/smoke.sh`
- Escaneo de secretos: `./scripts/secret-scan.sh`

## Convenciones
- Idiomas de docs: **bilingüe ES/EN** en `README.md`; resto en español.
- Conventional Commits. UN cambio lógico por PR con tests.
- `vault.enc`, `.env*`, `.engram/` jamás se commitean.
- UTF-8 estricto; sin comentarios innecesarios en el código.
