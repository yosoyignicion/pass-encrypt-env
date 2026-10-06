"""Clave de recuperación: 256 bits en Base32 con checksum, legible y a prueba de typos."""

from __future__ import annotations

import base64
import hashlib
import os
import re

RECOVERY_LEN = 32
CHECKSUM_LEN = 2
_GROUP = 4


def generate_recovery_key() -> bytes:
    return os.urandom(RECOVERY_LEN)


def _b32(raw: bytes) -> str:
    return base64.b32encode(raw).decode("ascii").rstrip("=")


def format_recovery_key(raw: bytes) -> str:
    if len(raw) != RECOVERY_LEN:
        raise ValueError("clave de recuperación con longitud inválida")
    checksum = hashlib.sha256(raw).digest()[:CHECKSUM_LEN]
    text = _b32(raw + checksum)
    return "-".join(text[i : i + _GROUP] for i in range(0, len(text), _GROUP))


def parse_recovery_key(text: str) -> bytes:
    s = re.sub(r"[^A-Za-z0-9]", "", text or "").upper()
    if not s:
        raise ValueError("clave de recuperación vacía")
    data = base64.b32decode(s + "=" * ((8 - len(s) % 8) % 8))
    if len(data) < CHECKSUM_LEN + 1:
        raise ValueError("clave de recuperación demasiado corta")
    raw, checksum = data[:-CHECKSUM_LEN], data[-CHECKSUM_LEN:]
    if hashlib.sha256(raw).digest()[:CHECKSUM_LEN] != checksum:
        raise ValueError("checksum inválido: revisa la clave de recuperación")
    return raw
