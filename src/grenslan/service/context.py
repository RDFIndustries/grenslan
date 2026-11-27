"""Trusted invocation context (TC-048).

The application namespace comes from the authenticated credential; user,
agent and instance identifiers come from the trusted ``Grenslan-*`` headers
that the credential is permitted to assert. ``permissions`` are the tool names
the credential is authorized to use, and ``profile`` names the credential's
exposure profile when it has one. None of these is ever read from tool
arguments, which the closed input schemas reject.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True, slots=True)
class InvocationContext:
    application_id: str
    user_id: str | None
    agent_id: str | None
    instance_id: str | None
    permissions: frozenset[str] = field(default=frozenset())
    profile: str | None = None

    def __post_init__(self) -> None:
        if not self.application_id:
            raise ValueError("an invocation context requires an authenticated application namespace")
