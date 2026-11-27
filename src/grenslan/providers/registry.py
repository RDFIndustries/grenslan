"""Explicit registration of approved provider implementations (PC-002, PC-004, PC-056).

Implementations are registered in code by implementation ID and family. There
is no discovery of installed packages and no loading by name from
configuration: configuration can only select an implementation that is already
registered, which is what makes provider installation an operator action and
not something a request or a configuration value can trigger.

When a configured instance is created, its self-description is checked against
its registration and its callable methods, and its dependency manifest is
verified against the description, the running platform and the installed
files (PROVIDER-REGISTRATION.md). A mismatch is a configuration error that
stops startup. Only enabled instances are created, so a disabled provider's
implementation is never verified.

Factories must only construct the provider: they run during ``check-config``
as well as at startup, and all I/O belongs in ``initialize``.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from grenslan.config.provider_config import ImplementationSpec, ProviderConfig
from grenslan.providers.contract import Family, Provider, ProviderDescription
from grenslan.providers.manifest import ManifestError, load_manifest, running_platform, verify_manifest

CONTRACT_VERSION = "1.0"
_LIFECYCLE_METHODS = ("describe", "initialize", "health", "shutdown")

# The method each capability is executed through (PC-056).
METHOD_BY_CAPABILITY: Mapping[str, str] = {
    "search.query": "search",
    "retrieval.http": "retrieve",
    "browser.session": "create_session",
    "browser.navigate": "navigate",
    "browser.observe": "observe",
    "browser.interact": "interact",
    "browser.screenshot": "screenshot",
    "content.inspect": "inspect",
    "content.read": "read",
    "content.find": "find",
    "content.tables": "extract_tables",
    "content.render": "render",
    "content.media": "extract_media",
    "content.transform": "transform",
    "ocr.recognize": "recognize",
    "intelligence.vision": "interpret",
    "intelligence.document_interpretation": "interpret",
    "intelligence.summarization": "interpret",
    "intelligence.translation": "interpret",
    "intelligence.model_ocr": "interpret",
}
_EXTRA_METHODS: Mapping[str, tuple[str, ...]] = {"browser": ("close_session",)}


def capability_family(capability: str) -> str:
    return capability.split(".", 1)[0]


class ProviderRegistrationError(Exception):
    """A configured provider instance does not match its registered implementation."""


@dataclass(frozen=True, slots=True)
class InstanceSettings:
    """What an implementation's factory receives: the instance ID and its validated configuration."""

    provider_id: str
    settings: Mapping[str, Any]


@dataclass(frozen=True, slots=True)
class Implementation:
    implementation_id: str
    family: Family
    factory: Callable[[InstanceSettings], Provider]
    manifest: Path
    settings_schema: Mapping[str, Any] | None = None

    def spec(self) -> ImplementationSpec:
        return ImplementationSpec(family=self.family, settings_schema=self.settings_schema)


class ImplementationRegistry:
    def __init__(self, implementations: Iterable[Implementation], *, platform: str | None = None) -> None:
        self.platform = running_platform() if platform is None else platform
        self._by_id: dict[str, Implementation] = {}
        for implementation in implementations:
            if implementation.implementation_id in self._by_id:
                raise ValueError(f"duplicate implementation {implementation.implementation_id!r}")
            self._by_id[implementation.implementation_id] = implementation

    def specs(self) -> Mapping[str, ImplementationSpec]:
        """The implementations configuration may select, for provider configuration validation."""
        return {implementation_id: impl.spec() for implementation_id, impl in self._by_id.items()}

    def create(self, provider_id: str, settings: Mapping[str, Any]) -> tuple[Provider, ProviderDescription]:
        """Create a configured instance and check its declaration; raises ProviderRegistrationError."""
        implementation = self._by_id.get(settings["implementation"])
        if implementation is None:
            raise ProviderRegistrationError(f"provider {provider_id!r}: implementation is not registered")
        try:
            provider = implementation.factory(InstanceSettings(provider_id, settings))
            description = provider.describe()
        except Exception:  # noqa: BLE001 - provider failures are contained, never surfaced raw
            # The exception text may carry configuration or secrets, so only its type is reported.
            raise ProviderRegistrationError(f"provider {provider_id!r}: implementation could not be created") from None
        problem = _declaration_problem(implementation, provider, description)
        if problem is not None:
            raise ProviderRegistrationError(f"provider {provider_id!r}: {problem}")
        try:
            verify_manifest(load_manifest(implementation.manifest), description, platform=self.platform)
        except ManifestError as exc:
            raise ProviderRegistrationError(f"provider {provider_id!r}: {exc}") from None
        return provider, description

    def check(self, config: ProviderConfig) -> None:
        """Register every enabled instance without initializing it, as ``check-config`` does."""
        for provider_id, settings in config.providers.items():
            if settings["enabled"]:
                self.create(provider_id, settings)


def _declaration_problem(
    implementation: Implementation, provider: Provider, description: ProviderDescription
) -> str | None:
    if description.implementation_id != implementation.implementation_id:
        return "declared implementation ID does not match its registration"
    if description.family != implementation.family:
        return "declared family does not match its registration"
    if description.contract_version != CONTRACT_VERSION:
        return f"declared contract version is not {CONTRACT_VERSION}"
    if not description.capabilities:
        return "declares no capabilities"
    seen: set[str] = set()
    for declaration in description.capabilities:
        capability = declaration.capability
        if capability not in METHOD_BY_CAPABILITY or capability_family(capability) != implementation.family:
            return f"declares capability {capability!r}, which is not in the {implementation.family} family"
        if capability in seen:
            return f"declares capability {capability!r} more than once"
        seen.add(capability)
    required = [*_LIFECYCLE_METHODS, *_EXTRA_METHODS.get(implementation.family, ())]
    required += [METHOD_BY_CAPABILITY[capability] for capability in seen]
    for method in required:
        if not callable(getattr(provider, method, None)):
            return f"has no callable {method!r} method for its declared capabilities"
    return None
