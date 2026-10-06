from pass_encrypt_env import totp, vault
from pass_encrypt_env.agent import Agent

FAST = dict(time_cost=1, memory_cost=8 * 1024, lanes=1)


def _vault(tmp_path):
    v, unlocked, _ = vault.create_vault("master-pass", **FAST)
    path = tmp_path / "vault.enc"
    vault.save_vault(v, path)
    return v, unlocked, path


def test_dispatch_locked(tmp_path):
    _v, _u, path = _vault(tmp_path)
    agent = Agent(path)
    assert agent.dispatch({"cmd": "status"})["unlocked"] is False
    assert agent.dispatch({"cmd": "get", "key": "X"})["ok"] is False
    assert agent.dispatch({"cmd": "export"})["ok"] is False


def test_dispatch_crud_and_persist(tmp_path):
    v, unlocked, path = _vault(tmp_path)
    agent = Agent(path)
    agent._vault_dict = v
    agent._unlocked = unlocked

    assert agent.dispatch({"cmd": "set", "key": "API_KEY", "value": "abc"})["ok"]
    assert agent.dispatch({"cmd": "get", "key": "API_KEY"})["value"] == "abc"
    assert agent.dispatch({"cmd": "list"})["keys"] == ["API_KEY"]
    assert agent.dispatch({"cmd": "export"})["secrets"] == {"API_KEY": "abc"}

    # Persistencia en disco
    reloaded = vault.load_vault(path)
    code = totp.totp(unlocked.totp_secret)
    out = vault.unlock_with_master(reloaded, "master-pass", code)
    assert out.payload["secrets"]["API_KEY"] == "abc"

    assert agent.dispatch({"cmd": "rm", "key": "API_KEY"})["removed"] is True
    assert agent.dispatch({"cmd": "rm", "key": "API_KEY"})["removed"] is False


def test_lock_wipes_memory(tmp_path):
    v, unlocked, path = _vault(tmp_path)
    agent = Agent(path)
    agent._vault_dict = v
    agent._unlocked = unlocked
    assert agent.dispatch({"cmd": "status"})["unlocked"] is True
    assert agent.dispatch({"cmd": "lock"})["ok"] is True
    assert agent.dispatch({"cmd": "status"})["unlocked"] is False
