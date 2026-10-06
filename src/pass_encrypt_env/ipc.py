"""IPC sobre socket Unix con verificación de UID (SO_PEERCRED)."""

from __future__ import annotations

import contextlib
import json
import os
import socket
import socketserver
import struct
from collections.abc import Callable
from pathlib import Path
from typing import Any


def runtime_dir() -> Path:
    base = os.environ.get("XDG_RUNTIME_DIR") or f"/tmp/passenv-{os.getuid()}"
    directory = Path(base) / "passenv"
    directory.mkdir(parents=True, exist_ok=True)
    with contextlib.suppress(OSError):
        os.chmod(directory, 0o700)
    return directory


def socket_path() -> Path:
    return runtime_dir() / "agent.sock"


def _peer_uid(sock: socket.socket) -> int:
    creds = sock.getsockopt(socket.SOL_SOCKET, socket.SO_PEERCRED, struct.calcsize("3i"))
    _pid, uid, _gid = struct.unpack("3i", creds)
    return uid


class _Handler(socketserver.StreamRequestHandler):
    def handle(self) -> None:  # noqa: D401
        if _peer_uid(self.connection) != os.getuid():
            return
        for raw in self.rfile:
            line = raw.strip()
            if not line:
                continue
            try:
                request = json.loads(line)
            except ValueError:
                response: dict[str, Any] = {"ok": False, "error": "json inválido"}
            else:
                try:
                    response = self.server.dispatch(request)  # type: ignore[attr-defined]
                except Exception as exc:  # noqa: BLE001
                    response = {"ok": False, "error": f"{type(exc).__name__}: {exc}"}
            self.wfile.write((json.dumps(response) + "\n").encode())
            self.wfile.flush()


class Server(socketserver.ThreadingUnixStreamServer):
    daemon_threads = True
    request_queue_size = 16

    def __init__(self, path: Path, dispatch: Callable[[dict], dict]):
        self.dispatch = dispatch  # type: ignore[assignment]
        super().__init__(str(path), _Handler)
        # Endurecimiento: el socket solo accesible por el propietario.
        with contextlib.suppress(OSError):
            os.chmod(path, 0o600)


def is_agent_running() -> bool:
    path = socket_path()
    if not path.exists():
        return False
    try:
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as s:
            s.settimeout(1.0)
            s.connect(str(path))
        return True
    except OSError:
        return False


def request(payload: dict, *, timeout: float = 5.0) -> dict:
    path = socket_path()
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as s:
        s.settimeout(timeout)
        s.connect(str(path))
        s.sendall((json.dumps(payload) + "\n").encode())
        buf = b""
        while b"\n" not in buf:
            chunk = s.recv(65536)
            if not chunk:
                break
            buf += chunk
    if not buf:
        return {"ok": False, "error": "sin respuesta del agente"}
    return json.loads(buf.decode().strip())
