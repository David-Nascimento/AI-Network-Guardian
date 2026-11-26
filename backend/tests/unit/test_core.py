from __future__ import annotations

import ipaddress

import jwt
import pytest

from app.core.config import Settings
from app.core.exceptions import AuthenticationError, DomainValidationError, RateLimitError
from app.core.network_guard import validate_host
from app.core.security import (
    SlidingWindowRateLimiter,
    create_access_token,
    decode_access_token,
    hash_password,
    verify_password,
)

SECRET = "x" * 40
NETS = [ipaddress.ip_network("192.168.0.0/16")]


def test_password_hash_roundtrip_and_salt() -> None:
    h1, h2 = hash_password("segredo-longo-1"), hash_password("segredo-longo-1")
    assert h1 != h2 and h1.startswith("scrypt$")
    assert verify_password("segredo-longo-1", h1)
    assert not verify_password("outra", h1)


@pytest.mark.parametrize("stored", ["", "lixo", "bcrypt$1$2$3$4$5", "scrypt$a$b$c$d$e"])
def test_verify_password_rejects_malformed(stored: str) -> None:
    assert verify_password("x", stored) is False


def test_token_roundtrip_and_tamper() -> None:
    token = create_access_token(subject="ana", role="admin", secret=SECRET, minutes=5)
    assert decode_access_token(token, secret=SECRET)["sub"] == "ana"
    with pytest.raises(AuthenticationError):
        decode_access_token(token, secret="y" * 40)
    with pytest.raises(AuthenticationError):
        decode_access_token(token + "x", secret=SECRET)


def test_expired_token_rejected() -> None:
    token = create_access_token(subject="ana", role="admin", secret=SECRET, minutes=-1)
    with pytest.raises(AuthenticationError):
        decode_access_token(token, secret=SECRET)


def test_token_with_alg_none_rejected() -> None:
    forged = jwt.encode({"sub": "ana", "exp": 9999999999}, key="", algorithm="none")
    with pytest.raises(AuthenticationError):
        decode_access_token(forged, secret=SECRET)


def test_rate_limiter_blocks_then_recovers() -> None:
    now = [0.0]
    limiter = SlidingWindowRateLimiter(2, 10, clock=lambda: now[0])
    limiter.check("a")
    limiter.check("a")
    with pytest.raises(RateLimitError) as err:
        limiter.check("a")
    assert int(err.value.headers["Retry-After"]) >= 1
    limiter.check("b")  # outra chave não é afetada
    now[0] = 11
    limiter.check("a")


@pytest.mark.parametrize(
    "host",
    ["127.0.0.1", "169.254.169.254", "0.0.0.0", "224.0.0.1", "10.0.0.5", "-oProxy", "a b", ""],
)
def test_validate_host_rejects_dangerous(host: str) -> None:
    with pytest.raises(DomainValidationError):
        validate_host(host, NETS)


@pytest.mark.parametrize(
    ("host", "expected"),
    [("1.1.1.1", "1.1.1.1"), ("192.168.100.1", "192.168.100.1"), ("Example.COM", "example.com")],
)
def test_validate_host_accepts_valid(host: str, expected: str) -> None:
    assert validate_host(host, NETS) == expected


def test_production_requires_strong_secret() -> None:
    with pytest.raises(ValueError, match="NG_SECRET_KEY"):
        Settings(environment="production")
    assert Settings(environment="production", secret_key="s" * 40)  # type: ignore[arg-type]


def test_settings_reject_short_admin_password_and_bad_cidr() -> None:
    with pytest.raises(ValueError, match="ADMIN_PASSWORD"):
        Settings(admin_password="curta")  # type: ignore[arg-type]
    with pytest.raises(ValueError):
        Settings(authorized_networks="não-é-cidr")


def test_blank_env_values_mean_unset(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("NG_SECRET_KEY", "")
    monkeypatch.setenv("NG_ADMIN_PASSWORD", "")
    s = Settings(_env_file=None)  # type: ignore[call-arg]
    assert s.admin_password is None and len(s.secret_key.get_secret_value()) >= 32
    with pytest.raises(ValueError, match="NG_SECRET_KEY"):
        Settings(_env_file=None, environment="production")  # type: ignore[call-arg]
