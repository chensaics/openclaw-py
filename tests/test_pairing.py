"""Tests for device pairing -- store, challenge, setup code."""

from __future__ import annotations

import asyncio
import tempfile
from pathlib import Path

import pytest

from pyclaw.pairing.store import (
    AllowFromEntry,
    PairingRequest,
    add_allow_from_entry,
    approve_pairing_code,
    read_allow_from_store,
    upsert_pairing_request,
)
from pyclaw.pairing.challenge import build_pairing_reply, issue_pairing_challenge
from pyclaw.pairing.setup_code import (
    PairingSetup,
    decode_pairing_setup_code,
    encode_pairing_setup_code,
)


class TestPairingStore:
    def test_upsert_and_approve(self):
        with tempfile.TemporaryDirectory() as td:
            creds = Path(td)
            req = upsert_pairing_request("telegram", "user123", "Alice", creds_dir=creds)
            assert isinstance(req, PairingRequest)
            assert req.sender_id == "user123"
            assert len(req.code) > 0

            approved = approve_pairing_code("telegram", req.code, creds_dir=creds)
            assert approved is not None
            assert approved.sender_id == "user123"

    def test_approve_wrong_code(self):
        with tempfile.TemporaryDirectory() as td:
            creds = Path(td)
            upsert_pairing_request("telegram", "user123", creds_dir=creds)
            result = approve_pairing_code("telegram", "WRONG", creds_dir=creds)
            assert result is None

    def test_approve_wrong_channel(self):
        with tempfile.TemporaryDirectory() as td:
            creds = Path(td)
            req = upsert_pairing_request("telegram", "user123", creds_dir=creds)
            result = approve_pairing_code("discord", req.code, creds_dir=creds)
            assert result is None

    def test_allow_from_store(self):
        with tempfile.TemporaryDirectory() as td:
            creds = Path(td)
            add_allow_from_entry("telegram", "alice", "Alice", creds_dir=creds)
            add_allow_from_entry("telegram", "bob", "Bob", creds_dir=creds)
            entries = read_allow_from_store("telegram", creds_dir=creds)
            assert len(entries) == 2
            ids = {e.sender_id for e in entries}
            assert ids == {"alice", "bob"}

    def test_empty_allow_from(self):
        with tempfile.TemporaryDirectory() as td:
            entries = read_allow_from_store("unknown", creds_dir=Path(td))
            assert entries == []


class TestPairingChallenge:
    def test_build_pairing_reply(self):
        reply = build_pairing_reply("ABC123")
        assert "ABC123" in reply
        assert len(reply) > 10

    def test_issue_pairing_challenge(self):
        sent = []

        async def mock_send(sender_id: str, text: str) -> None:
            sent.append(text)

        req = asyncio.run(
            issue_pairing_challenge("telegram", "user1", "User", send_reply=mock_send)
        )
        assert isinstance(req, PairingRequest)
        assert len(sent) == 1
        assert req.code in sent[0]


class TestSetupCode:
    def test_roundtrip(self):
        setup = PairingSetup(
            url="wss://gateway.example.com/ws",
            token="secret-token-123",
            password="p@ssw0rd",
        )
        encoded = encode_pairing_setup_code(setup)
        assert isinstance(encoded, str)
        assert len(encoded) > 0

        decoded = decode_pairing_setup_code(encoded)
        assert decoded.url == setup.url
        assert decoded.token == setup.token
        assert decoded.password == setup.password

    def test_empty_fields(self):
        setup = PairingSetup(url="ws://localhost", token="", password="")
        encoded = encode_pairing_setup_code(setup)
        decoded = decode_pairing_setup_code(encoded)
        assert decoded.url == "ws://localhost"
