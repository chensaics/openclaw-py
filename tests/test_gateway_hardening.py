"""Tests for gateway security hardening."""

from __future__ import annotations

import time

from pyclaw.security.gateway_hardening import (
    CanonicalAuthHeader,
    PairingMetadata,
    WebhookReplayGuard,
    canonicalize_auth_header,
    compute_env_fingerprint,
    hash_env_value,
    sanitize_env_for_logging,
)


class TestHashEnvValue:
    def test_normal_value(self) -> None:
        result = hash_env_value("sk-1234567890abcdef")
        assert result.startswith("sk-1")
        assert "..." in result
        assert len(result) < len("sk-1234567890abcdef")

    def test_short_value(self) -> None:
        assert hash_env_value("abc") == "***"

    def test_prefix_length(self) -> None:
        result = hash_env_value("my-secret-key", prefix_len=6)
        assert result.startswith("my-sec")


class TestSanitizeEnv:
    def test_sensitive_keys_hashed(self) -> None:
        env = {
            "API_KEY": "sk-1234567890abcdef",
            "SECRET_TOKEN": "ghp-abcdef123456",
            "PATH": "/usr/bin",
            "HOME": "/home/user",
        }
        result = sanitize_env_for_logging(env)
        assert "..." in result["API_KEY"]
        assert "..." in result["SECRET_TOKEN"]
        assert result["PATH"] == "/usr/bin"
        assert result["HOME"] == "/home/user"

    def test_password_key(self) -> None:
        result = sanitize_env_for_logging({"DB_PASSWORD": "supersecretpassword"})
        assert result["DB_PASSWORD"] != "supersecretpassword"
        assert "..." in result["DB_PASSWORD"]


class TestEnvFingerprint:
    def test_stable_fingerprint(self) -> None:
        env = {"A": "1", "B": "2", "C": "3"}
        fp1 = compute_env_fingerprint(env)
        fp2 = compute_env_fingerprint(env)
        assert fp1 == fp2

    def test_different_values(self) -> None:
        fp1 = compute_env_fingerprint({"A": "1"})
        fp2 = compute_env_fingerprint({"A": "2"})
        assert fp1 != fp2

    def test_selected_keys(self) -> None:
        env = {"A": "1", "B": "2", "C": "3"}
        fp1 = compute_env_fingerprint(env, keys=["A", "B"])
        fp2 = compute_env_fingerprint(env, keys=["A", "B"])
        assert fp1 == fp2

        fp3 = compute_env_fingerprint(env, keys=["A"])
        assert fp1 != fp3


class TestCanonicalizeAuth:
    def test_bearer(self) -> None:
        result = canonicalize_auth_header("Bearer eyJtoken123")
        assert result is not None
        assert result.scheme == "bearer"
        assert result.credential == "eyJtoken123"
        assert result.is_bearer

    def test_basic(self) -> None:
        result = canonicalize_auth_header("Basic dXNlcjpwYXNz")
        assert result is not None
        assert result.scheme == "basic"
        assert result.is_basic

    def test_api_key(self) -> None:
        result = canonicalize_auth_header("Api-Key my-api-key-value")
        assert result is not None
        assert result.scheme == "api-key"
        assert result.credential == "my-api-key-value"

    def test_raw_token(self) -> None:
        token = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9"
        result = canonicalize_auth_header(token)
        assert result is not None
        assert result.scheme == "bearer"
        assert result.credential == token

    def test_empty(self) -> None:
        assert canonicalize_auth_header("") is None
        assert canonicalize_auth_header("   ") is None

    def test_short_non_token(self) -> None:
        assert canonicalize_auth_header("short") is None

    def test_to_header(self) -> None:
        h = CanonicalAuthHeader(scheme="bearer", credential="tok123")
        assert h.to_header() == "Bearer tok123"


class TestPairingMetadata:
    def test_auto_timestamp(self) -> None:
        before = time.time()
        pm = PairingMetadata(channel_id="telegram", account_id="a1", peer_id="p1")
        after = time.time()
        assert before <= pm.paired_at <= after

    def test_fingerprint(self) -> None:
        pm = PairingMetadata(
            channel_id="telegram",
            account_id="a1",
            peer_id="p1",
            ip_address="1.2.3.4",
            user_agent="Mozilla/5.0",
        )
        fp = pm.compute_fingerprint()
        assert len(fp) == 64  # SHA-256 hex

    def test_verify_fingerprint(self) -> None:
        pm = PairingMetadata(
            channel_id="telegram",
            account_id="a1",
            peer_id="p1",
        )
        pm.fingerprint = pm.compute_fingerprint()
        assert pm.verify_fingerprint() is True

        pm.peer_id = "p2-spoofed"
        assert pm.verify_fingerprint() is False

    def test_no_fingerprint_always_valid(self) -> None:
        pm = PairingMetadata(channel_id="t", account_id="a", peer_id="p")
        assert pm.verify_fingerprint() is True

    def test_roundtrip(self) -> None:
        pm = PairingMetadata(
            channel_id="discord",
            account_id="a1",
            peer_id="p1",
            nonce="abc123",
        )
        d = pm.to_dict()
        restored = PairingMetadata.from_dict(d)
        assert restored.channel_id == "discord"
        assert restored.nonce == "abc123"


class TestWebhookReplayGuard:
    def test_fresh_request(self) -> None:
        guard = WebhookReplayGuard()
        assert guard.check("nonce1", time.time()) is True

    def test_replayed_nonce(self) -> None:
        guard = WebhookReplayGuard()
        now = time.time()
        assert guard.check("nonce1", now) is True
        assert guard.check("nonce1", now) is False

    def test_expired_timestamp(self) -> None:
        guard = WebhookReplayGuard(max_age_s=60)
        assert guard.check("nonce1", time.time() - 120) is False

    def test_future_timestamp(self) -> None:
        guard = WebhookReplayGuard(max_age_s=60)
        assert guard.check("nonce1", time.time() + 120) is False

    def test_different_nonces(self) -> None:
        guard = WebhookReplayGuard()
        now = time.time()
        assert guard.check("a", now) is True
        assert guard.check("b", now) is True
        assert guard.check("c", now) is True
