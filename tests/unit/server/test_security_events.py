"""Bounded, redacted security events."""

from __future__ import annotations

import json
import logging

import pytest

from grenslan.server.auth import ApplicationCredential, token_digest
from grenslan.server.oauth import TokenPrincipal
from grenslan.server.security_events import MAX_DETAIL_CHARS, SecurityEvent, SecurityLog

CREDENTIAL = ApplicationCredential(
    credential_id="plain",
    application_id="app-a",
    token_sha256=token_digest("secret-token-value"),
    permissions=frozenset(),
    delegation=False,
    user_id=None,
    agent_id=None,
    instance_id=None,
)
TOKEN_PRINCIPAL = TokenPrincipal(
    application_id="qor",
    permissions=frozenset(),
    user_id="alice",
    issuer="https://idp.example",
    key_id="rsa-1",
    expires_at=0.0,
    trust="fingerprint",
)


class Clock:
    def __init__(self) -> None:
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now


def security_log(clock: Clock | None = None, *, limit: int = 100) -> SecurityLog:
    return SecurityLog(max_events_per_window=limit, window_seconds=60.0, clock=clock or Clock())


def events(caplog: pytest.LogCaptureFixture) -> list[dict[str, object]]:
    return [record.security_event for record in caplog.records if hasattr(record, "security_event")]


@pytest.fixture(autouse=True)
def capture(caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(logging.INFO, logger="grenslan.security")


def test_event_is_structured_and_logged_as_warning(caplog: pytest.LogCaptureFixture) -> None:
    security_log().record(SecurityEvent.AUTHENTICATION_FAILED, interface="rest", client="127.0.0.1", reason="missing")
    (record,) = caplog.records
    assert record.name == "grenslan.security"
    assert record.levelno == logging.WARNING
    fields = {"event": "authentication_failed", "interface": "rest", "client": "127.0.0.1", "reason": "missing"}
    assert record.security_event == fields  # type: ignore[attr-defined]
    assert json.loads(record.getMessage().removeprefix("security_event ")) == fields


def test_static_credential_is_attributed_by_identifier_only(caplog: pytest.LogCaptureFixture) -> None:
    security_log().record(SecurityEvent.AUTHORIZATION_DENIED, principal=CREDENTIAL, detail={"tool": "image_search"})
    (event,) = events(caplog)
    assert event["application_id"] == "app-a"
    assert event["principal"] == "credential:plain"
    assert event["tool"] == "image_search"
    assert "secret-token-value" not in caplog.text
    assert token_digest("secret-token-value").hex() not in caplog.text


def test_token_principal_is_attributed_by_issuer_and_key(caplog: pytest.LogCaptureFixture) -> None:
    security_log().record(SecurityEvent.WORK_REVOKED, principal=TOKEN_PRINCIPAL, reason="expired")
    (event,) = events(caplog)
    assert event["application_id"] == "qor"
    assert event["principal"] == "token:https://idp.example#rsa-1"


def test_detail_values_are_sanitized_and_bounded(caplog: pytest.LogCaptureFixture) -> None:
    hostile = "https://evil.example\r\nFake: entry\x00" + "é" + "x" * 500
    security_log().record(SecurityEvent.ORIGIN_REJECTED, detail={"origin": hostile})
    (event,) = events(caplog)
    origin = str(event["origin"])
    assert len(origin) <= MAX_DETAIL_CHARS
    assert origin.endswith("...")
    assert all(32 <= ord(ch) < 127 for ch in origin)
    message = caplog.records[0].getMessage()
    assert "\n" not in message
    assert "\r" not in message


def test_events_beyond_the_window_limit_are_suppressed_and_counted(caplog: pytest.LogCaptureFixture) -> None:
    clock = Clock()
    log = security_log(clock, limit=3)
    for _ in range(5):
        log.record(SecurityEvent.AUTHENTICATION_FAILED, reason="malformed")
    log.record(SecurityEvent.HOST_REJECTED)
    assert [e["event"] for e in events(caplog)] == ["authentication_failed"] * 3 + ["host_rejected"]
    clock.now += 61
    log.record(SecurityEvent.AUTHENTICATION_FAILED, reason="malformed")
    assert events(caplog)[-1]["suppressed"] == 2
    log.record(SecurityEvent.AUTHENTICATION_FAILED, reason="malformed")
    assert "suppressed" not in events(caplog)[-1]


@pytest.mark.parametrize(("limit", "window"), [(0, 60.0), (10, 0.0)])
def test_limits_must_be_positive(limit: int, window: float) -> None:
    with pytest.raises(ValueError, match="positive"):
        SecurityLog(max_events_per_window=limit, window_seconds=window)
