# Contribuir a pass-encrypt-env

Gracias por el interés. Este documento resume cómo montar el entorno y qué debe
pasar cualquier cambio antes de un Pull Request.

## Entorno

El proyecto usa el intérprete del sistema (necesita **PyGObject** para el pop-up GTK3,
que no se instala por `pip`). Requisitos:

```bash
# Debian/Ubuntu
sudo apt install python3-gi python3-cryptography python3-click python3-qrcode libsecret-tools
```

Para desarrollo aislado (sin GUI):

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -e '.[dev]'            # pytest + ruff + bandit
```

## Gate obligatorio

Antes de abrir un PR:

```bash
./scripts/ci.sh          # ruff + bandit + pytest
./scripts/smoke.sh       # arranque del agente + IPC (headless)
./scripts/secret-scan.sh # 0 secretos en el árbol
```

- `ruff check .` debe dar **0**.
- `bandit -r src` sin hallazgos de severidad alta.
- `pytest` en verde.

## Arquitectura (no acoplar)

- `crypto/` primitivas puras y testeables sin GUI ni disco.
- `vault.py` orquesta KDF + AEAD; **no** conoce GTK.
- `ipc.py`/`agent.py` no dibujan salvo a través de `ui.py`.
- `ui.py` no deriva claves; solo recoge entradas y las pasa saneadas.

## Reglas no negociables

- **Nunca** commitear secretos, `vault.enc`, `.env*` ni claves de recuperación.
- **Nunca** escribir valores en claro en disco ni en logs.
- Sanear toda entrada de GUI (`strip`) antes de usarla en criptografía.
- El pop-up es no modal; el escritorio debe seguir usable.
- Un cambio lógico por PR, con tests cuando aplique.

## Estilo y commits

- Documentación y mensajes en **español**; `README.md` bilingüe ES/EN.
- [Conventional Commits](https://www.conventionalcommits.org/es/):
  `feat(...)`, `fix(...)`, `docs(...)`, `refactor(...)`, `test(...)`, `chore(release)`.
- `ruff` fija `line-length = 100`, `target-version = py311`.

## Pull Requests

- Rellena la plantilla y marca el gate ejecutado.
- Actualiza `CHANGELOG.md` en `Unreleased` si el cambio es visible.

¿Dudas? Abre una discusión o un issue de tipo *Propuesta de mejora*.
