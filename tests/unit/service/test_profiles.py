"""Tool profile exposure (TC-043, TC-054)."""

from __future__ import annotations

import pytest

from grenslan.contracts.registry import ToolRegistry
from grenslan.service.profiles import ALWAYS_AVAILABLE, PROFILES, UnknownProfileError, profile_tools

BASIC_RESEARCH = {"web_search", "web_open", "web_read", "web_find", "image_search", "artifact_get"}
TECHNICAL_ADDITIONS = {
    "document_open", "document_inspect", "document_read", "document_find", "document_tables",
    "document_render", "document_media", "image_open", "image_inspect", "image_transform", "image_ocr",
    "web_links", "web_traverse", "source_verify", "quotation_verify", "citation_get",
}  # fmt: skip
BROWSER = {
    "browser_session_create", "browser_navigate", "browser_observe", "browser_interact",
    "browser_screenshot", "browser_session_close",
}  # fmt: skip


def test_capability_and_operation_tools_are_outside_research_profiles() -> None:
    assert {"capabilities_get", "operation_status", "operation_results", "operation_cancel"} == ALWAYS_AVAILABLE


def test_basic_profile() -> None:
    assert profile_tools("basic") == BASIC_RESEARCH | ALWAYS_AVAILABLE


def test_technical_profile() -> None:
    assert profile_tools("technical") == BASIC_RESEARCH | TECHNICAL_ADDITIONS | ALWAYS_AVAILABLE


def test_advanced_profile() -> None:
    assert profile_tools("advanced") == BASIC_RESEARCH | TECHNICAL_ADDITIONS | BROWSER | ALWAYS_AVAILABLE


def test_full_profile_is_every_registry_tool() -> None:
    assert profile_tools("full") == set(ToolRegistry.load().tool_names)


def test_profile_names() -> None:
    assert set(PROFILES) == {"basic", "technical", "advanced", "full"}


def test_unknown_profile_rejected() -> None:
    with pytest.raises(UnknownProfileError):
        profile_tools("everything")


def test_custom_profile_always_keeps_capability_and_operation_tools() -> None:
    assert profile_tools("custom", custom={"web_search"}) == {"web_search"} | ALWAYS_AVAILABLE


def test_custom_profile_rejects_unknown_tool_names() -> None:
    with pytest.raises(UnknownProfileError):
        profile_tools("custom", custom={"web_search", "shell_exec"})
