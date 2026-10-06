"""Agente de sesión: mantiene la bóveda desbloqueada en RAM y sirve por IPC.

Se lanza en el autostart del escritorio. Tras ``--delay`` segundos (5 por
defecto) muestra el pop-up de desbloqueo, sin bloquear el escritorio. Una vez
desbloqueado, las apps obtienen secretos sin más prompts durante la sesión.
"""

from __future__ import annotations

import argparse
import contextlib
import ctypes
import resource
import sys
import threading
from pathlib import Path

try:  # PyGObject/GTK es opcional: el núcleo del agente es testeable sin GUI.
    import gi

    gi.require_version("Gtk", "3.0")
    from gi.repository import GLib

    HAS_GTK = True
except (ImportError, ValueError):  # pragma: no cover - depende del entorno
    GLib = None  # type: ignore[assignment]
    HAS_GTK = False

from . import ipc, vault  # noqa: E402
from .ui import UnlockWindow, make_indicator  # noqa: E402


class Agent:
    def __init__(self, vault_path: Path | str) -> None:
        self.vault_path = Path(vault_path)
        self._mutex = threading.RLock()
        self._unlocked: vault.Unlocked | None = None
        self._vault_dict: dict | None = None
        self._window: UnlockWindow | None = None
        self._indicator = None
        self._loop: GLib.MainLoop | None = None
        self._server: ipc.Server | None = None

    # ---------------------------------------------------------------- estado
    def vault_exists(self) -> bool:
        return self.vault_path.exists()

    def _require_unlocked(self) -> dict:
        with self._mutex:
            if self._unlocked is None:
                return {"ok": False, "error": "bóveda bloqueada"}
            return {"ok": True}

    # ----------------------------------------------------------- dispatch IPC
    def dispatch(self, req: dict) -> dict:
        cmd = req.get("cmd")
        if cmd == "status":
            return self.status()
        if cmd == "unlock":
            self.show_prompt()
            return {"ok": True, "shown": True}
        if cmd == "lock":
            return self.lock()
        if cmd == "list":
            guard = self._require_unlocked()
            if not guard["ok"]:
                return guard
            return {"ok": True, "keys": sorted(self._secrets().keys())}
        if cmd == "get":
            guard = self._require_unlocked()
            if not guard["ok"]:
                return guard
            key = req.get("key", "")
            value = self._secrets().get(key)
            if value is None:
                return {"ok": False, "error": f"clave no encontrada: {key}"}
            return {"ok": True, "value": value}
        if cmd == "export":
            guard = self._require_unlocked()
            if not guard["ok"]:
                return guard
            return {"ok": True, "secrets": self._secrets()}
        if cmd == "set":
            return self._set(req.get("key", ""), req.get("value", ""))
        if cmd == "rm":
            return self._rm(req.get("key", ""))
        return {"ok": False, "error": f"comando desconocido: {cmd}"}

    def status(self) -> dict:
        with self._mutex:
            unlocked = self._unlocked is not None
            count = len(self._unlocked.payload.get("secrets", {})) if self._unlocked else 0
        return {
            "ok": True,
            "unlocked": unlocked,
            "count": count,
            "vault": str(self.vault_path),
            "exists": self.vault_exists(),
        }

    def _secrets(self) -> dict:
        with self._mutex:
            if self._unlocked is None:
                return {}
            return dict(self._unlocked.payload.get("secrets", {}))

    def _set(self, key: str, value: str) -> dict:
        if not key:
            return {"ok": False, "error": "clave vacía"}
        with self._mutex:
            if self._unlocked is None:
                return {"ok": False, "error": "bóveda bloqueada"}
            vault.set_secret(self._unlocked.payload, key, value)
            self._persist()
        return {"ok": True}

    def _rm(self, key: str) -> dict:
        with self._mutex:
            if self._unlocked is None:
                return {"ok": False, "error": "bóveda bloqueada"}
            removed = vault.remove_secret(self._unlocked.payload, key)
            self._persist()
        return {"ok": True, "removed": removed}

    def _persist(self) -> None:
        if self._unlocked is None or self._vault_dict is None:
            raise RuntimeError("no se puede persistir con la bóveda bloqueada")
        vault.reseal(self._vault_dict, self._unlocked.dek, self._unlocked.payload)
        vault.save_vault(self._vault_dict, self.vault_path)

    def lock(self) -> dict:
        with self._mutex:
            self._unlocked = None
            self._vault_dict = None
        if self._indicator is not None:
            self._indicator.set_label("bloqueada", "passenv")
        return {"ok": True}

    # -------------------------------------------------------------------- UI
    def setup_ui(self) -> None:
        if not HAS_GTK:
            return
        self._window = UnlockWindow(self.on_submit, self.quit)
        self._indicator = make_indicator(
            on_lock=self.lock, on_unlock=self.show_prompt, on_quit=self.quit
        )
        if self._indicator is not None:
            self._indicator.set_label("bloqueada", "passenv")

    def show_prompt(self) -> None:
        if GLib is None:
            return
        GLib.idle_add(self._show_now)

    def _show_now(self) -> bool:
        if self._window is None:
            self.setup_ui()
        if self._window is not None:
            self._window.show_prompt()
        return False

    def on_submit(self, master: str, code: str) -> None:
        """Ejecutado en hilo de trabajo desde el pop-up; lanza error legible."""
        self._log(f"intento de desbloqueo: master_len={len(master)} code_len={len(code)}")
        try:
            vault_dict = vault.load_vault(self.vault_path)
        except vault.VaultError as exc:
            self._log(f"fallo: {exc}")
            raise RuntimeError(str(exc)) from exc
        try:
            unlocked = vault.unlock_with_master(vault_dict, master, code, window=2)
        except vault.WrongMaster as exc:
            self._log("fallo: contraseña maestra incorrecta")
            raise RuntimeError("Contraseña maestra incorrecta.") from exc
        except vault.InvalidTOTP as exc:
            self._log("fallo: código TOTP inválido (¿reloj desincronizado o código caducado?)")
            raise RuntimeError("Código TOTP inválido.") from exc
        with self._mutex:
            self._vault_dict = vault_dict
            self._unlocked = unlocked
        if self._indicator is not None:
            self._indicator.set_label("desbloqueada", "passenv")
        if GLib is not None:
            GLib.idle_add(lambda: self._log("bóveda desbloqueada") or False)

    def _log(self, msg: str) -> None:
        print(f"[passenv-agent] {msg}", flush=True)

    def quit(self) -> None:
        if self._server is not None:
            self._server.shutdown()
        if self._loop is not None:
            self._loop.quit()

    # --------------------------------------------------------------- arranque
    def run(self, *, delay: int, popup: bool) -> int:
        if ipc.is_agent_running():
            self._log("ya hay una instancia en ejecución")
            return 0

        path = ipc.socket_path()
        path.unlink(missing_ok=True)
        self._server = ipc.Server(path, self.dispatch)
        threading.Thread(target=self._server.serve_forever, daemon=True).start()
        self._log(f"escuchando en {path}")

        if not HAS_GTK:
            self._log("PyGObject/GTK no disponible: modo headless (sin pop-up)")
            try:
                threading.Event().wait()
            except KeyboardInterrupt:
                pass
            finally:
                path.unlink(missing_ok=True)
            return 0

        self.setup_ui()
        if popup and self.vault_exists():
            GLib.timeout_add_seconds(delay, self._auto_prompt)
        elif popup and not self.vault_exists():
            self._log("no existe bóveda todavía; ejecuta 'passenv init'")

        self._loop = GLib.MainLoop()
        try:
            self._loop.run()
        finally:
            path.unlink(missing_ok=True)
            self._log("detenido")
        return 0

    def _auto_prompt(self) -> bool:
        with self._mutex:
            locked = self._unlocked is None
        if locked:
            self.show_prompt()
        return False


def _harden_process() -> None:
    """Endurecimiento del proceso que custodia los secretos.

    - PR_SET_DUMPABLE=0: impide que otros procesos del mismo UID hagan ptrace o
      lean /proc/<pid>/mem del agente (mitiga espías en la misma sesión).
    - RLIMIT_CORE=0: no se generan core dumps con secretos en memoria.
    Best-effort: si falla, se continúa (no rompe el servicio).
    """
    with contextlib.suppress(ValueError, OSError):
        resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    try:
        libc = ctypes.CDLL("libc.so.6", use_errno=True)
        PR_SET_DUMPABLE = 4
        libc.prctl(PR_SET_DUMPABLE, 0, 0, 0, 0)
    except OSError:
        pass
    # Best-effort: bloquear en RAM lo ya cargado (evita swap). Puede fallar sin privilegios.
    try:
        libc = ctypes.CDLL("libc.so.6", use_errno=True)
        MCL_CURRENT = 1
        libc.mlockall(MCL_CURRENT)
    except OSError:
        pass


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="passenv-agent", description="Agente de sesión passenv")
    parser.add_argument("--vault", default=str(vault.default_vault_path()), help="ruta de la bóveda")
    parser.add_argument("--delay", type=int, default=5, help="segundos antes del pop-up")
    parser.add_argument("--no-popup", action="store_true", help="arrancar sin mostrar el pop-up")
    args = parser.parse_args(argv)

    _harden_process()
    agent = Agent(args.vault)
    return agent.run(delay=args.delay, popup=not args.no_popup)


if __name__ == "__main__":
    sys.exit(main())
