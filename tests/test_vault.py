import time

import pytest

from pass_encrypt_env import recovery, totp, vault

FAST = dict(time_cost=1, memory_cost=8 * 1024, lanes=1)
MASTER = "correct horse battery staple"


def _new(**kw):
    return vault.create_vault(MASTER, **FAST, **kw)


def test_roundtrip_master_unlock():
    v, unlocked, _ = _new()
    code = totp.totp(unlocked.totp_secret)
    out = vault.unlock_with_master(v, MASTER, code)
    assert out.payload["secrets"] == {}
    assert out.dek == unlocked.dek


def test_wrong_master():
    v, unlocked, _ = _new()
    code = totp.totp(unlocked.totp_secret)
    with pytest.raises(vault.WrongMaster):
        vault.unlock_with_master(v, "nope", code)


def test_wrong_totp():
    v, unlocked, _ = _new()
    with pytest.raises(vault.InvalidTOTP):
        vault.unlock_with_master(v, MASTER, "000000")


def test_recovery_unlock():
    v, unlocked, rec = _new()
    out = vault.unlock_with_recovery(v, rec)
    assert out.dek == unlocked.dek
    assert vault.unlock_with_recovery(v, rec).payload["secrets"] == {}


def test_wrong_recovery_key():
    v, _, rec = _new()
    bad = bytearray(rec)
    bad[0] ^= 0xFF
    with pytest.raises(vault.CorruptVault):
        vault.unlock_with_recovery(v, bytes(bad))


def test_secrets_persist_and_reseal(tmp_path):
    path = tmp_path / "vault.enc"
    v, unlocked, _ = _new()
    vault.set_secret(unlocked.payload, "API_KEY", "s3cr3t")
    vault.reseal(v, unlocked.dek, unlocked.payload)
    vault.save_vault(v, path)

    loaded = vault.load_vault(path)
    code = totp.totp(unlocked.totp_secret)
    out = vault.unlock_with_master(loaded, MASTER, code)
    assert out.payload["secrets"]["API_KEY"] == "s3cr3t"


def test_no_plaintext_on_disk(tmp_path):
    path = tmp_path / "vault.enc"
    v, unlocked, _ = _new()
    vault.set_secret(unlocked.payload, "TOKEN", "super-secret-value")
    vault.reseal(v, unlocked.dek, unlocked.payload)
    vault.save_vault(v, path)
    blob = path.read_text()
    assert "super-secret-value" not in blob
    assert (path.stat().st_mode & 0o777) == 0o600


def test_change_master():
    v, unlocked, _ = _new()
    vault.change_master(v, unlocked, "new-master-pass")
    code = totp.totp(unlocked.totp_secret)
    with pytest.raises(vault.WrongMaster):
        vault.unlock_with_master(v, MASTER, code)
    out = vault.unlock_with_master(v, "new-master-pass", code)
    assert out.dek == unlocked.dek


def test_recovery_roundtrip_and_checksum():
    raw = recovery.generate_recovery_key()
    text = recovery.format_recovery_key(raw)
    assert recovery.parse_recovery_key(text) == raw
    assert recovery.parse_recovery_key(text.lower().replace("-", " ")) == raw
    # Tamper en una posición INTERIOR (los bits finales base32 se ignoran).
    tampered = text[:10] + ("A" if text[10] != "A" else "B") + text[11:]
    with pytest.raises(ValueError):
        recovery.parse_recovery_key(tampered)


def test_totp_window_and_uri():
    secret = b"12345678901234567890"
    at = time.time()
    code = totp.totp(secret, at)
    assert totp.verify(secret, code, at)
    assert totp.verify(secret, code, at + 30, window=1)
    assert not totp.verify(secret, code, at + 300, window=1)
    uri = totp.provisioning_uri(secret, "me@example.com")
    assert uri.startswith("otpauth://totp/")
    assert "secret=" in uri


def test_corrupt_blob_detected():
    v, unlocked, _ = _new()
    v["data"]["ct"] = vault.crypto.b64e(b"\x00" * 32)
    code = totp.totp(unlocked.totp_secret)
    with pytest.raises(vault.CorruptVault):
        vault.unlock_with_master(v, MASTER, code)
