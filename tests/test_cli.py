import threading

from click.testing import CliRunner

from pass_encrypt_env import ipc
from pass_encrypt_env.cli import main


def _serve(tmp_path, monkeypatch, dispatch):
    monkeypatch.setenv("XDG_RUNTIME_DIR", str(tmp_path))
    path = ipc.socket_path()
    path.unlink(missing_ok=True)
    server = ipc.Server(path, dispatch)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, path


def test_env_if_unlocked_without_agent(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_RUNTIME_DIR", str(tmp_path))
    ipc.socket_path().unlink(missing_ok=True)
    result = CliRunner().invoke(main, ["env", "--if-unlocked"])
    assert result.exit_code == 3, result.output


def test_env_if_unlocked_emits_exports(tmp_path, monkeypatch):
    server, path = _serve(tmp_path, monkeypatch, lambda req: {"ok": True, "secrets": {"A": "1", "B": "two words"}})
    try:
        result = CliRunner().invoke(main, ["env", "--if-unlocked"])
        assert result.exit_code == 0, result.output
        assert "export A=1" in result.output
        assert "export B='two words'" in result.output
    finally:
        server.shutdown()
        path.unlink(missing_ok=True)


def test_env_if_unlocked_when_locked(tmp_path, monkeypatch):
    server, path = _serve(tmp_path, monkeypatch, lambda req: {"ok": False, "error": "bóveda bloqueada"})
    try:
        result = CliRunner().invoke(main, ["env", "--if-unlocked"])
        assert result.exit_code == 3, result.output
    finally:
        server.shutdown()
        path.unlink(missing_ok=True)
