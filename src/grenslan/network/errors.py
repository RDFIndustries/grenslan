"""Outbound failure classes, kept distinct so callers can report them precisely (PC-023)."""

from __future__ import annotations

from typing import Literal

FailureKind = Literal["denied", "unresolved", "connect", "tls", "timeout", "redirect_limit", "too_large", "protocol"]


class OutboundError(Exception):
    """An outbound request did not produce a response. ``kind`` says why."""

    def __init__(self, kind: FailureKind, message: str) -> None:
        super().__init__(message)
        self.kind: FailureKind = kind


class DestinationDenied(OutboundError):
    """The network scope does not permit the destination; nothing was sent to it."""

    def __init__(self, message: str) -> None:
        super().__init__("denied", message)
