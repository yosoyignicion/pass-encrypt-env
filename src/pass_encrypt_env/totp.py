"""TOTP (RFC 6238) con librería estándar: sin dependencias externas."""

from __future__ import annotations

import base64
import hashlib
import hmac
import os
import struct
import time

DEFAULT_STEP = 30
DEFAULT_DIGITS = 6
DEFAULT_SECRET_LEN = 20


def generate_secret(length: int = DEFAULT_SECRET_LEN) -> bytes:
    return os.urandom(length)


def _hotp(secret: bytes, counter: int, digits: int) -> str:
    digest = hmac.new(secret, struct.pack(">Q", counter), hashlib.sha1).digest()
    offset = digest[-1] & 0x0F
    value = (
        (digest[offset] & 0x7F) << 24
        | digest[offset + 1] << 16
        | digest[offset + 2] << 8
        | digest[offset + 3]
    ) % (10**digits)
    return str(value).zfill(digits)


def totp(
    secret: bytes,
    at: float | None = None,
    *,
    step: int = DEFAULT_STEP,
    digits: int = DEFAULT_DIGITS,
) -> str:
    at = time.time() if at is None else at
    return _hotp(secret, int(at // step), digits)


def verify(
    secret: bytes,
    code: str,
    at: float | None = None,
    *,
    window: int = 1,
    step: int = DEFAULT_STEP,
    digits: int = DEFAULT_DIGITS,
) -> bool:
    code = "".join(ch for ch in (code or "") if ch.isdigit())
    if len(code) != digits:
        return False
    at = time.time() if at is None else at
    counter = int(at // step)
    return any(
        hmac.compare_digest(_hotp(secret, counter + delta, digits), code)
        for delta in range(-window, window + 1)
    )


def secret_b32(secret: bytes) -> str:
    return base64.b32encode(secret).decode("ascii").rstrip("=")


def secret_from_b32(text: str) -> bytes:
    s = text.strip().replace(" ", "").upper()
    return base64.b32decode(s + "=" * ((8 - len(s) % 8) % 8))


def provisioning_uri(secret: bytes, account: str, issuer: str = "passenv") -> str:
    from urllib.parse import quote

    label = quote(f"{issuer}:{account}", safe="")
    params = (
        f"secret={secret_b32(secret)}"
        f"&issuer={quote(issuer, safe='')}"
        f"&algorithm=SHA1&digits={DEFAULT_DIGITS}&period={DEFAULT_STEP}"
    )
    return f"otpauth://totp/{label}?{params}"
