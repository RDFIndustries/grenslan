"""Trusted invocation context (TC-048).

The application namespace comes from the authenticated credential; user,
agent and instance identifiers come from the trusted ``Grenslan-*`` headers
that the credential is permitted to assert. None of them is ever read from tool
arguments, which the closed input schemas reject.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class InvocationContext:
    application_id: str
    user_id: str | None
    agent_id: str | None
    instance_id: str | None

    def __post_init__(self) -> None:
        if not self.application_id:
            raise ValueError("an invocation context requires an authenticated application namespace")
