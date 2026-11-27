"""Configured tool profiles (TC-043, TC-054).

A profile limits which tools are exposed; it never grants authority.
Effective permission is checked separately on every invocation. Capability
discovery and operation management are available irrespective of the research
profile, subject to authorization.
"""

from __future__ import annotations

from collections.abc import Iterable

ALWAYS_AVAILABLE = frozenset({"capabilities_get", "operation_status", "operation_results", "operation_cancel"})

_BASIC = frozenset({"web_search", "web_open", "web_read", "web_find", "image_search", "artifact_get"})
_TECHNICAL = frozenset({
    "document_open", "document_inspect", "document_read", "document_find", "document_tables",
    "document_render", "document_media", "image_open", "image_inspect", "image_transform", "image_ocr",
    "web_links", "web_traverse", "source_verify", "quotation_verify", "citation_get",
})  # fmt: skip
_BROWSER = frozenset({
    "browser_session_create", "browser_navigate", "browser_observe", "browser_interact",
    "browser_screenshot", "browser_session_close",
})  # fmt: skip

PROFILES: dict[str, frozenset[str]] = {
    "basic": _BASIC | ALWAYS_AVAILABLE,
    "technical": _BASIC | _TECHNICAL | ALWAYS_AVAILABLE,
    "advanced": _BASIC | _TECHNICAL | _BROWSER | ALWAYS_AVAILABLE,
    "full": _BASIC | _TECHNICAL | _BROWSER | ALWAYS_AVAILABLE,
}


class UnknownProfileError(ValueError):
    """The profile name or a custom profile member is not recognised."""


def profile_tools(name: str, *, custom: Iterable[str] | None = None) -> frozenset[str]:
    """Return the tools exposed by a named profile or an operator-defined custom one."""
    if name == "custom":
        selected = frozenset(custom or ())
        unknown = selected - PROFILES["full"]
        if unknown:
            raise UnknownProfileError(f"custom profile names unknown tools: {sorted(unknown)}")
        return selected | ALWAYS_AVAILABLE
    try:
        return PROFILES[name]
    except KeyError:
        raise UnknownProfileError(f"unknown profile {name!r}") from None
