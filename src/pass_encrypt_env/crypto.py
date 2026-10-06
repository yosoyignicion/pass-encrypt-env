"""Primitivas criptográficas: Argon2id (KDF), HKDF y AES-256-GCM (AEAD).

Todo es público (Kerckhoffs): lo único secreto es la contraseña maestra, el
secreto TOTP y la clave de recuperación. Sin dependencias fuera de ``cryptography``.
"""

from __future__ import annotations

import base64
import os

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.argon2 import Argon2id
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

KEY_LEN = 32
NONCE_LEN = 12
SALT_LEN = 16

# Parámetros Argon2id por defecto (~64 MiB, 3 pasadas).
ARGON2_TIME_COST = 3
ARGON2_MEMORY_COST = 64 * 1024
ARGON2_LANES = 4


def b64e(raw: bytes) -> str:
    return base64.b64encode(raw).decode("ascii")


def b64d(text: str) -> bytes:
    return base64.b64decode(text.encode("ascii"))


def argon2id(
    password: bytes,
    salt: bytes,
    *,
    time_cost: int = ARGON2_TIME_COST,
    memory_cost: int = ARGON2_MEMORY_COST,
    lanes: int = ARGON2_LANES,
    length: int = KEY_LEN,
) -> bytes:
    return Argon2id(
        salt=salt,
        length=length,
        iterations=time_cost,
        memory_cost=memory_cost,
        lanes=lanes,
    ).derive(password)


def hkdf(ikm: bytes, info: bytes, *, length: int = KEY_LEN) -> bytes:
    return HKDF(
        algorithm=hashes.SHA256(),
        length=length,
        salt=None,
        info=info,
    ).derive(ikm)


def aead_encrypt(key: bytes, plaintext: bytes, aad: bytes = b"") -> tuple[bytes, bytes]:
    """Devuelve ``(nonce, ciphertext)``."""
    nonce = os.urandom(NONCE_LEN)
    ct = AESGCM(key).encrypt(nonce, plaintext, aad or None)
    return nonce, ct


def aead_decrypt(key: bytes, nonce: bytes, ciphertext: bytes, aad: bytes = b"") -> bytes:
    return AESGCM(key).decrypt(nonce, ciphertext, aad or None)


def random_bytes(n: int) -> bytes:
    return os.urandom(n)
