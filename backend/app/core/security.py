"""Hash de senhas (scrypt, stdlib), tokens JWT e rate limiting."""

from __future__ import annotations

import base64
import hashlib
import hmac
import secrets
import threading
import time
from collections import defaultdict, deque
from collections.abc import Callable
from datetime import UTC, datetime, timedelta

import jwt

from app.core.exceptions import AuthenticationError, RateLimitError

_N, _R, _P = 2**14, 8, 1
_ALGORITHM = "HS256"


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.scrypt(password.encode(), salt=salt, n=_N, r=_R, p=_P, dklen=32)
    b64 = base64.b64encode
    return f"scrypt${_N}${_R}${_P}${b64(salt).decode()}${b64(digest).decode()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        scheme, n, r, p, salt_b64, digest_b64 = stored.split("$")
        if scheme != "scrypt":
            return False
        salt = base64.b64decode(salt_b64)
        expected = base64.b64decode(digest_b64)
        actual = hashlib.scrypt(
            password.encode(), salt=salt, n=int(n), r=int(r), p=int(p), dklen=len(expected)
        )
    except (ValueError, TypeError):
        return False
    return hmac.compare_digest(actual, expected)


def create_access_token(*, subject: str, role: str, secret: str, minutes: int) -> str:
    now = datetime.now(UTC)
    claims = {"sub": subject, "role": role, "iat": now, "exp": now + timedelta(minutes=minutes)}
    return jwt.encode(claims, secret, algorithm=_ALGORITHM)


def decode_access_token(token: str, *, secret: str) -> dict[str, object]:
    try:
        return jwt.decode(
            token, secret, algorithms=[_ALGORITHM], options={"require": ["exp", "sub"]}
        )
    except jwt.PyJWTError as exc:
        raise AuthenticationError("Token inválido ou expirado") from exc


class SlidingWindowRateLimiter:
    """Limitador em memória por chave (ex.: IP). Suficiente para uma instância única."""

    def __init__(
        self, limit: int, window_seconds: float, clock: Callable[[], float] = time.monotonic
    ) -> None:
        self._limit = limit
        self._window = window_seconds
        self._clock = clock
        self._hits: dict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def check(self, key: str) -> None:
        now = self._clock()
        with self._lock:
            hits = self._hits[key]
            while hits and now - hits[0] >= self._window:
                hits.popleft()
            if len(hits) >= self._limit:
                retry = max(1, int(self._window - (now - hits[0])))
                raise RateLimitError(
                    "Muitas tentativas. Aguarde antes de tentar novamente.",
                    headers={"Retry-After": str(retry)},
                )
            hits.append(now)
