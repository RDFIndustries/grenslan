"""Typed public request records for the tools enabled in the foundation.

Records are built only from arguments that have already passed the tool's
projected input schema. A field the caller omitted takes the default declared
in the schema, or ``None`` where the schema declares none (TC-047): the core
resolves those from operator policy instead of inventing a value here. A test
keeps field names, required fields and defaults aligned with the canonical
schemas.

``semantic_issues`` covers checks TC-049 requires that depend only on the
request itself. Checks against configured limits, cursors or other server
state belong to the handler that owns that state.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, fields
from datetime import date
from typing import Any, ClassVar, Literal, Self

from grenslan.contracts.envelope import Issue, IssueCode

Freshness = Literal["default", "cache_only", "revalidate", "fresh_independent"]
Category = Literal[
    "general", "news", "images", "video", "academic", "software", "patents", "government", "documents",
    "technical", "local", "enterprise", "products", "maps",
]  # fmt: skip
SafeSearch = Literal["off", "moderate", "strict"]
Ranking = Literal["provider_order", "relevance", "recency"]
Representation = Literal["original", "text", "structured", "image", "html", "metadata"]


class RequestRecord:
    """Build a frozen record from schema-validated arguments."""

    _nested: ClassVar[Mapping[str, type[RequestRecord]]] = {}

    @classmethod
    def from_arguments(cls, arguments: Mapping[str, Any]) -> Self:
        values: dict[str, Any] = {}
        for field in fields(cls):  # type: ignore[arg-type]
            if field.name not in arguments:
                continue
            value = arguments[field.name]
            nested = cls._nested.get(field.name)
            if nested is not None:
                value = nested.from_arguments(value)
            elif isinstance(value, list | tuple):
                value = tuple(value)
            values[field.name] = value
        return cls(**values)


@dataclass(frozen=True, slots=True)
class Execution(RequestRecord):
    mode: Literal["sync", "async"] = "sync"
    timeout_ms: int | None = None
    max_output_bytes: int | None = None
    max_download_bytes: int | None = None


@dataclass(frozen=True, slots=True)
class RetrieveOption(RequestRecord):
    max_sources: int
    representation: Representation | None = None


def _normalized_domain(domain: str) -> str:
    return domain.strip().rstrip(".").lower()


def _domain_conflict(include: tuple[str, ...] | None, exclude: tuple[str, ...] | None) -> list[Issue]:
    if include and exclude and {_normalized_domain(d) for d in include} & {_normalized_domain(d) for d in exclude}:
        return [Issue(IssueCode.INVALID_REQUEST, "a domain is both included and excluded")]
    return []


@dataclass(frozen=True, slots=True)
class WebSearchRequest(RequestRecord):
    _nested: ClassVar[Mapping[str, type[RequestRecord]]] = {"retrieve": RetrieveOption, "execution": Execution}

    query: str
    providers: tuple[str, ...] | None = None
    max_results: int | None = None
    language: str | None = None
    region: str | None = None
    include_domains: tuple[str, ...] | None = None
    exclude_domains: tuple[str, ...] | None = None
    safe_search: SafeSearch | None = None
    cursor: str | None = None
    freshness: Freshness = "default"
    category: Category = "general"
    date_from: str | None = None
    date_to: str | None = None
    file_types: tuple[str, ...] | None = None
    ranking: Ranking | None = None
    retrieve: RetrieveOption | None = None
    execution: Execution | None = None

    def semantic_issues(self) -> list[Issue]:
        issues = _domain_conflict(self.include_domains, self.exclude_domains)
        if self.date_from and self.date_to and date.fromisoformat(self.date_from) > date.fromisoformat(self.date_to):
            issues.append(Issue(IssueCode.INVALID_REQUEST, "date_from is after date_to"))
        if self.retrieve and self.max_results is not None and self.retrieve.max_sources > self.max_results:
            issues.append(Issue(IssueCode.INVALID_REQUEST, "retrieve.max_sources exceeds max_results"))
        return issues


@dataclass(frozen=True, slots=True)
class ImageSearchRequest(RequestRecord):
    _nested: ClassVar[Mapping[str, type[RequestRecord]]] = {"execution": Execution}

    query: str
    providers: tuple[str, ...] | None = None
    max_results: int | None = None
    language: str | None = None
    region: str | None = None
    include_domains: tuple[str, ...] | None = None
    exclude_domains: tuple[str, ...] | None = None
    safe_search: SafeSearch | None = None
    cursor: str | None = None
    freshness: Freshness = "default"
    min_width: int | None = None
    min_height: int | None = None
    execution: Execution | None = None

    def semantic_issues(self) -> list[Issue]:
        return _domain_conflict(self.include_domains, self.exclude_domains)


@dataclass(frozen=True, slots=True)
class CapabilitiesGetRequest(RequestRecord):
    tools: tuple[str, ...] | None = None


@dataclass(frozen=True, slots=True)
class OperationStatusRequest(RequestRecord):
    operation_id: str


@dataclass(frozen=True, slots=True)
class OperationResultsRequest(RequestRecord):
    operation_id: str
    continuation: str | None = None
    max_output_bytes: int | None = None


@dataclass(frozen=True, slots=True)
class OperationCancelRequest(RequestRecord):
    operation_id: str
