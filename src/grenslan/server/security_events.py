"""Bounded, redacted security events for operators (TC-048; PRP-001 F03).

Each rejected or revoked request yields at most one structured event on the
``grenslan.security`` logger. An event names who made the request by
credential identifier, or by token issuer and key ID, and gives the client
address and a reason from a fixed vocabulary. It never contains a token, an
``Authorization`` value, a credential digest or a rejected identity-header
value. The few request-derived values that are recorded (such as a rejected
``Origin`` or ``Host``) are reduced to printable ASCII and truncated.

Events of each kind are limited per time window, so a flood of bad requests
cannot flood the log. Suppressed events are counted and the count is reported
with the next event of that kind.
"""

from __future__ import annotations

import json
import logging
import threading
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from enum import StrEnum

from grenslan.server.auth import ApplicationCredential
from grenslan.server.oauth import TokenPrincipal

MAX_DETAIL_CHARS = 128
_ELLIPSIS = "..."
_LOGGER = logging.getLogger("grenslan.security")


class SecurityEvent(StrEnum):
    AUTHENTICATION_FAILED = "authentication_failed"
    CONTEXT_REJECTED = "context_rejected"
    HOST_REJECTED = "host_rejected"
    ORIGIN_REJECTED = "origin_rejected"
    AUTHORIZATION_DENIED = "authorization_denied"
    REQUEST_TOO_LARGE = "request_too_large"
    WORK_REVOKED = "work_revoked"


def _bounded(value: str) -> str:
    printable = "".join(ch if 32 <= ord(ch) < 127 else "?" for ch in value)
    if len(printable) <= MAX_DETAIL_CHARS:
        return printable
    return printable[: MAX_DETAIL_CHARS - len(_ELLIPSIS)] + _ELLIPSIS


def _principal(principal: ApplicationCredential | TokenPrincipal) -> str:
    if isinstance(principal, TokenPrincipal):
        return f"token:{principal.issuer}#{principal.key_id or ''}"
    return f"credential:{principal.credential_id}"


@dataclass
class _Window:
    started: float
    emitted: int = 0
    suppressed: int = 0


class SecurityLog:
    def __init__(
        self,
        *,
        max_events_per_window: int,
        window_seconds: float,
        clock: Callable[[], float] = time.monotonic,
        logger: logging.Logger = _LOGGER,
    ) -> None:
        if max_events_per_window < 1 or window_seconds <= 0:
            raise ValueError("security event limits must be positive")
        self._limit = max_events_per_window
        self._window = window_seconds
        self._clock = clock
        self._logger = logger
        self._lock = threading.Lock()
        self._windows: dict[SecurityEvent, _Window] = {}

    def record(
        self,
        event: SecurityEvent,
        *,
        interface: str | None = None,
        client: str | None = None,
        principal: ApplicationCredential | TokenPrincipal | None = None,
        reason: str | None = None,
        detail: Mapping[str, str] | None = None,
    ) -> None:
        """Log one event unless its kind is over the limit for the current window.

        ``detail`` keys must be fixed names chosen by the caller; values may come
        from the request and are sanitized.
        """
        suppressed = self._admit(event)
        if suppressed is None:
            return
        fields: dict[str, object] = {"event": event.value}
        if interface is not None:
            fields["interface"] = interface
        if client is not None:
            fields["client"] = _bounded(client)
        if principal is not None:
            fields["application_id"] = principal.application_id
            fields["principal"] = _bounded(_principal(principal))
        if reason is not None:
            fields["reason"] = reason
        for name, value in (detail or {}).items():
            fields[name] = _bounded(value)
        if suppressed:
            fields["suppressed"] = suppressed
        message = json.dumps(fields, ensure_ascii=True, sort_keys=True, separators=(",", ":"))
        self._logger.warning("security_event %s", message, extra={"security_event": fields})

    def _admit(self, event: SecurityEvent) -> int | None:
        """The number of events suppressed since the last one emitted, or None to suppress this one."""
        now = self._clock()
        with self._lock:
            window = self._windows.get(event)
            if window is None or now - window.started >= self._window:
                carried = window.suppressed if window is not None else 0
                self._windows[event] = _Window(started=now, emitted=1)
                return carried
            if window.emitted >= self._limit:
                window.suppressed += 1
                return None
            window.emitted += 1
            return 0
