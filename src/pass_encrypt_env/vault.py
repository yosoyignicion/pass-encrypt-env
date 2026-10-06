"""Bóveda cifrada: Argon2id + AES-256-GCM, doble envoltura de la DEK.

Estructura de ``vault.enc`` (JSON, todo público salvo lo cifrado):

    version, kdf{name,salt,time_cost,memory_cost,lanes},
    totp.wrapped{nonce,ct},            # secreto TOTP envuelto con K1(master)
    wraps.master{nonce,ct},            # DEK envuelta con K2 = HKDF(K1 || totp_secret)
    wraps.recovery{nonce,ct},          # DEK envuelta con K3(recovery_key)
    data{nonce,ct}                     # payload {secrets} cifrado con la DEK

- ``K1`` = Argon2id(contraseña maestra, salt)
- ``K2`` = HKDF(K1, info + totp_secret)  -> abrir sin TOTP correcto no da la DEK
- ``K3`` = HKDF(recovery_key)            -> recuperación si se pierde master/TOTP
"""

from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from cryptography.exceptions import InvalidTag

from . import crypto, recovery, totp

VAULT_VERSION = 1

AAD_TOTP = b"passenv:totp:v1"
AAD_DEK = b"passenv:dek:v1"
AAD_RECOVERY = b"passenv:recovery:v1"
AAD_DATA = b"passenv:data:v1"
INFO_DEK = b"passenv:dek-wrap:v1"
INFO_RECOVERY = b"passenv:recovery-wrap:v1"

DEFAULT_VAULT_PATH = Path(
    os.environ.get("PASSENV_VAULT", Path.home() / ".config" / "pass-encrypt-env" / "vault.enc")
)


class VaultError(Exception):
    """Error base de la bóveda."""


class WrongMaster(VaultError):
    """Contraseña maestra incorrecta."""


class InvalidTOTP(VaultError):
    """Código TOTP incorrecto."""


class CorruptVault(VaultError):
    """El archivo de bóveda está dañado o manipulado."""


class WrongRecoveryKey(VaultError):
    """Clave de recuperación incorrecta."""


@dataclass
class Unlocked:
    dek: bytes
    payload: dict[str, Any]
    totp_secret: bytes


def default_vault_path() -> Path:
    return DEFAULT_VAULT_PATH


def new_payload() -> dict[str, Any]:
    return {
        "meta": {"created": int(time.time()), "version": VAULT_VERSION},
        "secrets": {},
    }


def _enc_dict(key: bytes, plaintext: bytes, aad: bytes) -> dict[str, str]:
    nonce, ct = crypto.aead_encrypt(key, plaintext, aad)
    return {"nonce": crypto.b64e(nonce), "ct": crypto.b64e(ct)}


def _dec_dict(key: bytes, blob: dict[str, str], aad: bytes) -> bytes:
    try:
        return crypto.aead_decrypt(key, crypto.b64d(blob["nonce"]), crypto.b64d(blob["ct"]), aad)
    except (InvalidTag, KeyError, ValueError) as exc:
        raise CorruptVault("bloque cifrado inválido") from exc


def create_vault(
    master: str,
    *,
    totp_secret: bytes | None = None,
    time_cost: int = crypto.ARGON2_TIME_COST,
    memory_cost: int = crypto.ARGON2_MEMORY_COST,
    lanes: int = crypto.ARGON2_LANES,
) -> tuple[dict[str, Any], Unlocked, bytes]:
    """Crea una bóveda nueva. Devuelve (vault_dict, unlocked, recovery_key_raw)."""
    totp_secret = totp_secret or totp.generate_secret()
    salt = crypto.random_bytes(crypto.SALT_LEN)
    kdf = {
        "name": "argon2id",
        "salt": crypto.b64e(salt),
        "time_cost": time_cost,
        "memory_cost": memory_cost,
        "lanes": lanes,
    }
    k1 = crypto.argon2id(
        master.encode(), salt, time_cost=time_cost, memory_cost=memory_cost, lanes=lanes
    )
    dek = crypto.random_bytes(crypto.KEY_LEN)
    recovery_raw = recovery.generate_recovery_key()

    k2 = crypto.hkdf(k1, INFO_DEK + totp_secret)
    k3 = crypto.hkdf(recovery_raw, INFO_RECOVERY)

    payload = new_payload()
    vault: dict[str, Any] = {
        "version": VAULT_VERSION,
        "kdf": kdf,
        "totp": {"wrapped": _enc_dict(k1, totp_secret, AAD_TOTP)},
        "wraps": {
            "master": _enc_dict(k2, dek, AAD_DEK),
            "recovery": _enc_dict(k3, dek, AAD_RECOVERY),
        },
        "data": _enc_dict(dek, json.dumps(payload, separators=(",", ":")).encode(), AAD_DATA),
    }
    return vault, Unlocked(dek, payload, totp_secret), recovery_raw


def _derive_k1(vault: dict[str, Any], master: str) -> bytes:
    kdf = vault.get("kdf", {})
    return crypto.argon2id(
        master.encode(),
        crypto.b64d(kdf["salt"]),
        time_cost=kdf.get("time_cost", crypto.ARGON2_TIME_COST),
        memory_cost=kdf.get("memory_cost", crypto.ARGON2_MEMORY_COST),
        lanes=kdf.get("lanes", crypto.ARGON2_LANES),
    )


def _decrypt_payload(dek: bytes, vault: dict[str, Any]) -> dict[str, Any]:
    raw = _dec_dict(dek, vault["data"], AAD_DATA)
    try:
        return json.loads(raw.decode())
    except (ValueError, UnicodeDecodeError) as exc:
        raise CorruptVault("payload no es JSON válido") from exc


def unlock_with_master(
    vault: dict[str, Any], master: str, totp_code: str, *, window: int = 1
) -> Unlocked:
    k1 = _derive_k1(vault, master)
    try:
        totp_secret = crypto.aead_decrypt(
            k1,
            crypto.b64d(vault["totp"]["wrapped"]["nonce"]),
            crypto.b64d(vault["totp"]["wrapped"]["ct"]),
            AAD_TOTP,
        )
    except (InvalidTag, KeyError, ValueError) as exc:
        raise WrongMaster("contraseña maestra incorrecta o bóveda corrupta") from exc
    if not totp.verify(totp_secret, totp_code, window=window):
        raise InvalidTOTP("código TOTP inválido")
    k2 = crypto.hkdf(k1, INFO_DEK + totp_secret)
    dek = _dec_dict(k2, vault["wraps"]["master"], AAD_DEK)
    return Unlocked(dek, _decrypt_payload(dek, vault), totp_secret)


def unlock_with_recovery(vault: dict[str, Any], recovery_key_raw: bytes) -> Unlocked:
    k3 = crypto.hkdf(recovery_key_raw, INFO_RECOVERY)
    dek = _dec_dict(k3, vault["wraps"]["recovery"], AAD_RECOVERY)
    payload = _decrypt_payload(dek, vault)
    return Unlocked(dek, payload, totp_secret=b"")


def set_secret(payload: dict[str, Any], key: str, value: str) -> None:
    payload.setdefault("secrets", {})[key] = value


def remove_secret(payload: dict[str, Any], key: str) -> bool:
    return payload.get("secrets", {}).pop(key, None) is not None


def reseal(vault: dict[str, Any], dek: bytes, payload: dict[str, Any]) -> None:
    """Vuelve a cifrar el payload con un nonce nuevo (in-place)."""
    vault["data"] = _enc_dict(dek, json.dumps(payload, separators=(",", ":")).encode(), AAD_DATA)


def change_master(
    vault: dict[str, Any], unlocked: Unlocked, new_master: str
) -> dict[str, Any]:
    """Re-deriva K1/K2 con la nueva maestra conservando totp_secret y DEK."""
    kdf = vault["kdf"]
    salt = crypto.b64d(kdf["salt"])
    k1 = crypto.argon2id(
        new_master.encode(),
        salt,
        time_cost=kdf.get("time_cost", crypto.ARGON2_TIME_COST),
        memory_cost=kdf.get("memory_cost", crypto.ARGON2_MEMORY_COST),
        lanes=kdf.get("lanes", crypto.ARGON2_LANES),
    )
    k2 = crypto.hkdf(k1, INFO_DEK + unlocked.totp_secret)
    vault["totp"]["wrapped"] = _enc_dict(k1, unlocked.totp_secret, AAD_TOTP)
    vault["wraps"]["master"] = _enc_dict(k2, unlocked.dek, AAD_DEK)
    return vault


def load_vault(path: Path | str = DEFAULT_VAULT_PATH) -> dict[str, Any]:
    p = Path(path)
    try:
        data = json.loads(p.read_text("utf-8"))
    except FileNotFoundError:
        raise VaultError(f"no existe la bóveda: {p}") from None
    except ValueError as exc:
        raise CorruptVault("la bóveda no es JSON válido") from exc
    if data.get("version") != VAULT_VERSION:
        raise CorruptVault(f"versión de bóveda no soportada: {data.get('version')!r}")
    return data


def save_vault(vault: dict[str, Any], path: Path | str = DEFAULT_VAULT_PATH) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    os.chmod(p.parent, 0o700)
    tmp = p.with_suffix(p.suffix + ".tmp")
    data = json.dumps(vault, indent=2).encode()
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    try:
        os.write(fd, data)
        os.fsync(fd)
    finally:
        os.close(fd)
    os.replace(tmp, p)
