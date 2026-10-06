import threading

from pass_encrypt_env import ipc


def test_ipc_roundtrip(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_RUNTIME_DIR", str(tmp_path))
    path = ipc.socket_path()
    path.unlink(missing_ok=True)

    server = ipc.Server(path, lambda req: {"ok": True, "echo": req})
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        assert ipc.is_agent_running() is True
        assert ipc.request({"cmd": "ping"})["echo"] == {"cmd": "ping"}
    finally:
        server.shutdown()
        path.unlink(missing_ok=True)

    assert ipc.is_agent_running() is False


def test_request_without_agent(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_RUNTIME_DIR", str(tmp_path))
    ipc.socket_path().unlink(missing_ok=True)
    try:
        ipc.request({"cmd": "ping"}, timeout=0.5)
    except OSError:
        pass
    else:  # pragma: no cover
        raise AssertionError("se esperaba OSError sin agente")
