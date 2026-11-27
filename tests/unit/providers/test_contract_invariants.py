"""Construction-time invariants of provider records (PC-057, PC-058)."""

from __future__ import annotations

import pytest

from grenslan.providers.contract import (
    MAX_ISSUE_MESSAGE_CHARS,
    ConstraintDisposition,
    Discovery,
    Issue,
    Limits,
    ProviderResult,
    SearchRequest,
    SearchResult,
)

ISSUE = Issue("provider_unavailable", "upstream engine did not respond")
LIMIT_VALUES = {
    "max_input_bytes": 1, "max_download_bytes": 1, "max_output_bytes": 1, "max_temp_bytes": 1,
    "max_memory_bytes": 1, "max_cpu_ms": 1, "max_pixels": 1, "max_expansion_bytes": 1,
    "max_recursion": 1, "max_items": 1, "max_redirects": 0, "max_retries": 0,
}  # fmt: skip


def search_result(*items: Discovery) -> SearchResult:
    return SearchResult(items=items, constraints=(), observed_at="2026-11-27T00:00:00Z")


def test_issue_message_must_be_nonempty() -> None:
    with pytest.raises(ValueError, match="message"):
        Issue("internal_error", "")


def test_issue_message_is_bounded() -> None:
    with pytest.raises(ValueError, match="message"):
        Issue("internal_error", "x" * (MAX_ISSUE_MESSAGE_CHARS + 1))


def test_issue_code_must_be_known() -> None:
    with pytest.raises(ValueError, match="code"):
        Issue("teapot", "x")  # type: ignore[arg-type]


def test_issue_retry_after_must_be_nonnegative() -> None:
    with pytest.raises(ValueError, match="retry_after_ms"):
        Issue("rate_limited", "x", retry_after_ms=-1)


def test_completed_result_is_valid() -> None:
    assert ProviderResult("completed", search_result()).outcome == "completed"


def test_completed_no_value_result_is_permitted() -> None:
    assert ProviderResult[None]("completed", None).value is None


def test_partial_requires_value_and_issue() -> None:
    with pytest.raises(ValueError, match="issue"):
        ProviderResult("partial", search_result())
    with pytest.raises(ValueError, match="value"):
        ProviderResult("partial", None, (ISSUE,))
    assert ProviderResult("partial", search_result(), (ISSUE,)).issues == (ISSUE,)


@pytest.mark.parametrize("outcome", ["failed", "cancelled", "timed_out", "interrupted"])
def test_unsuccessful_outcomes_require_issue(outcome: str) -> None:
    with pytest.raises(ValueError, match="issue"):
        ProviderResult(outcome, None)  # type: ignore[arg-type]
    ProviderResult(outcome, search_result(), (ISSUE,))  # type: ignore[arg-type]


def test_unknown_outcome_is_rejected() -> None:
    with pytest.raises(ValueError, match="outcome"):
        ProviderResult("accepted", None, (ISSUE,))  # type: ignore[arg-type]


def test_issues_must_be_a_tuple_of_issues() -> None:
    with pytest.raises(TypeError):
        ProviderResult("failed", None, [ISSUE])  # type: ignore[arg-type]


@pytest.mark.parametrize("field", sorted(LIMIT_VALUES))
def test_limits_reject_values_below_minimum(field: str) -> None:
    values = dict(LIMIT_VALUES)
    values[field] -= 1
    with pytest.raises(ValueError, match=field):
        Limits(**values)


def test_discovery_rank_starts_at_one() -> None:
    with pytest.raises(ValueError, match="original_rank"):
        Discovery(original_rank=0, url="https://example.org/")


def test_discovery_requires_a_locating_url() -> None:
    with pytest.raises(ValueError, match="url"):
        Discovery(original_rank=1, title="no address")
    Discovery(original_rank=1, url="https://example.org/")
    Discovery(original_rank=1, image_url="https://example.org/a.png")
    Discovery(original_rank=1, source_page_url="https://example.org/page")


def test_discovery_category_metadata_names_are_unique() -> None:
    with pytest.raises(ValueError, match="category_metadata"):
        Discovery(original_rank=1, url="https://example.org/", category_metadata=(("doi", "a"), ("doi", "b")))


def test_search_request_bounds() -> None:
    with pytest.raises(ValueError, match="query"):
        SearchRequest(query="", category="general", max_results=10)
    with pytest.raises(ValueError, match="max_results"):
        SearchRequest(query="q", category="general", max_results=0)


def test_constraint_disposition_status_is_checked() -> None:
    with pytest.raises(ValueError, match="status"):
        ConstraintDisposition("language", "ignored")  # type: ignore[arg-type]


def test_search_result_items_must_be_discoveries() -> None:
    with pytest.raises(TypeError):
        SearchResult(items=({"url": "x"},), constraints=(), observed_at="2026-11-27T00:00:00Z")  # type: ignore[arg-type]
