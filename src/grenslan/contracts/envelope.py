"""Typed public result envelopes (TC-005, TC-007, TC-008, TC-050).

Builders enforce the envelope invariants that the schema also expresses, so a
programming error fails at construction rather than producing an envelope the
output validator later rejects: completed and partial carry a result, partial
and every failure status carry at least one issue, and accepted carries an
operation in its initial queued or running state.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

SCHEMA_VERSION = "1.0"


class IssueCode(StrEnum):
    INVALID_REQUEST = "invalid_request"
    UNSUPPORTED_CAPABILITY = "unsupported_capability"
    UNAUTHORIZED = "unauthorized"
    ACCESS_RESTRICTED = "access_restricted"
    PROVIDER_UNAVAILABLE = "provider_unavailable"
    RATE_LIMITED = "rate_limited"
    NETWORK_ERROR = "network_error"
    RETRIEVAL_FAILED = "retrieval_failed"
    EXTRACTION_FAILED = "extraction_failed"
    RESOURCE_LIMIT = "resource_limit"
    ARTIFACT_EXPIRED = "artifact_expired"
    ARTIFACT_UNAVAILABLE = "artifact_unavailable"
    INTEGRITY_ERROR = "integrity_error"
    TIMEOUT = "timeout"
    CANCELLED = "cancelled"
    INTERRUPTED = "interrupted"
    INTERNAL_ERROR = "internal_error"
    STALE_HANDLE = "stale_handle"
    CURSOR_EXPIRED = "cursor_expired"
    CONFLICT = "conflict"
    NOT_FOUND = "not_found"


class Status(StrEnum):
    COMPLETED = "completed"
    PARTIAL = "partial"
    ACCEPTED = "accepted"
    FAILED = "failed"
    CANCELLED = "cancelled"
    TIMED_OUT = "timed_out"
    INTERRUPTED = "interrupted"


class EffectiveMode(StrEnum):
    SYNC = "sync"
    ASYNC = "async"


FAILURE_STATUSES = frozenset({Status.FAILED, Status.CANCELLED, Status.TIMED_OUT, Status.INTERRUPTED})


@dataclass(frozen=True, slots=True)
class Issue:
    """A machine-readable failure or limitation. Messages must be safe to disclose."""

    code: IssueCode
    message: str
    retryable: bool | None = None
    provider: str | None = None
    item_index: int | None = None
    retry_after_ms: int | None = None

    def __post_init__(self) -> None:
        if not self.message:
            raise ValueError("issue message must be nonempty")

    def to_wire(self) -> dict[str, Any]:
        wire: dict[str, Any] = {"code": self.code.value, "message": self.message}
        for name in ("retryable", "provider", "item_index", "retry_after_ms"):
            value = getattr(self, name)
            if value is not None:
                wire[name] = value
        return wire


def _base(request_id: str, status: Status, mode: EffectiveMode, issues: Iterable[Issue]) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "request_id": request_id,
        "status": status.value,
        "effective_mode": mode.value,
        "issues": [issue.to_wire() for issue in issues],
    }


def completed(
    request_id: str,
    result: Mapping[str, Any],
    *,
    issues: Iterable[Issue] = (),
    mode: EffectiveMode = EffectiveMode.SYNC,
) -> dict[str, Any]:
    envelope = _base(request_id, Status.COMPLETED, mode, issues)
    envelope["result"] = dict(result)
    return envelope


def partial(
    request_id: str,
    result: Mapping[str, Any],
    *,
    issues: Iterable[Issue],
    mode: EffectiveMode = EffectiveMode.SYNC,
) -> dict[str, Any]:
    issue_list = list(issues)
    if not issue_list:
        raise ValueError("a partial outcome requires at least one explanatory issue")
    envelope = _base(request_id, Status.PARTIAL, mode, issue_list)
    envelope["result"] = dict(result)
    return envelope


def failed(
    request_id: str,
    *,
    issues: Iterable[Issue],
    status: Status = Status.FAILED,
    result: Mapping[str, Any] | None = None,
    mode: EffectiveMode = EffectiveMode.SYNC,
) -> dict[str, Any]:
    if status not in FAILURE_STATUSES:
        raise ValueError(f"{status.value!r} is not a failure status")
    issue_list = list(issues)
    if not issue_list:
        raise ValueError("a failure outcome requires at least one issue")
    envelope = _base(request_id, status, mode, issue_list)
    if result is not None:
        envelope["result"] = dict(result)
    return envelope


def accepted(request_id: str, operation: Mapping[str, Any], *, issues: Iterable[Issue] = ()) -> dict[str, Any]:
    if operation.get("state") not in ("queued", "running"):
        raise ValueError("an accepted operation must be in its queued or running state")
    envelope = _base(request_id, Status.ACCEPTED, EffectiveMode.ASYNC, issues)
    envelope["operation"] = dict(operation)
    return envelope
