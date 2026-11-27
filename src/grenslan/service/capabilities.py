"""``capabilities_get``: the effective capabilities available to the caller (TC-042, TC-043, PC-010, PC-064).

Each public tool the caller can see (in the service profile and in the
caller's permissions) is reported with one status:

- ``unsupported``: this service does not implement the tool;
- ``enabled``: implemented, and every provider capability it needs is served
  by at least one ``ready`` or ``degraded`` instance;
- ``unavailable``: an enabled instance declares the capability, but none is
  currently serving it;
- ``disabled``: no enabled instance declares it.

Tools the caller cannot see are omitted. Requested by name, they are reported
as ``disabled`` with no further detail, so the response reveals no more than
an invocation would; unknown names are ``unsupported``. Provider instance and
implementation identities, endpoints and health details are never reported,
because they describe private topology.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any, get_args

from grenslan import __version__
from grenslan.config.provider_config import ProviderConfig
from grenslan.contracts.envelope import Issue, Status
from grenslan.contracts.registry import ToolRegistry
from grenslan.providers.contract import Format
from grenslan.providers.registry import capability_family
from grenslan.providers.runtime import ProviderSet
from grenslan.service.dispatch import Invocation, ToolOutcome

_FORMAT_ORDER = {name: index for index, name in enumerate(get_args(Format))}
_DEGRADED = "a provider for this function is degraded; results may be incomplete"
# Public limit name -> global provider configuration limit.
_LIMITS = {
    "max_output_bytes": "max_output_bytes",
    "max_download_bytes": "max_download_bytes",
    "max_timeout_ms": "timeout_ms",
    "max_concurrency": "max_concurrency",
}


def public_limits(config: ProviderConfig) -> dict[str, int]:
    """The operator's global limits that a consumer may plan around."""
    limits = config.data["limits"]
    return {public: int(limits[name]) for public, name in _LIMITS.items()}


class CapabilitiesHandler:
    def __init__(
        self,
        *,
        registry: ToolRegistry,
        providers: ProviderSet,
        requirements: Mapping[str, Sequence[str]],
        profile_name: str,
        profile: frozenset[str],
        limits: Mapping[str, int],
    ) -> None:
        """``requirements`` maps every implemented tool to the provider capabilities it needs (empty for core tools)."""
        if "capabilities_get" not in requirements:
            raise ValueError("requirements must declare capabilities_get, as for every implemented tool")
        unknown = set(requirements) - set(registry.tool_names)
        if unknown:
            raise ValueError(f"requirements name unknown tools: {sorted(unknown)}")
        self._tools = registry.tool_names
        self._providers = providers
        self._requirements = {tool: tuple(needed) for tool, needed in requirements.items()}
        self._profile_name = profile_name
        self._profile = profile
        self._limits = dict(limits)

    def semantic_issues(self, arguments: Mapping[str, Any]) -> Sequence[Issue]:
        return ()

    async def __call__(self, invocation: Invocation) -> ToolOutcome:
        context = invocation.context
        visible = [tool for tool in self._tools if tool in self._profile and tool in context.permissions]
        requested = invocation.arguments.get("tools")
        if requested is None:
            entries = [self._entry(tool) for tool in visible]
        else:
            entries = []
            for name in dict.fromkeys(requested):
                if name in visible:
                    entries.append(self._entry(name))
                elif name in self._tools:
                    entries.append({"name": name, "status": "disabled"})
                else:
                    entries.append({"name": name, "status": "unsupported"})
        result: dict[str, Any] = {
            "service": "grenslan",
            "service_version": __version__,
            "contract_version": "1.0",
            "profile": context.profile or self._profile_name,
            "capabilities": entries,
        }
        if self._limits:
            result["limits"] = self._limits
        return ToolOutcome(status=Status.COMPLETED, result=result)

    def _entry(self, tool: str) -> dict[str, Any]:
        needed = self._requirements.get(tool)
        if needed is None:
            return {"name": tool, "status": "unsupported"}
        status = "enabled"
        formats: set[str] = set()
        limitations: list[str] = []
        for capability in needed:
            family = capability_family(capability)
            serving = self._providers.eligible(family, capability)  # type: ignore[arg-type]
            if not serving:
                declared = self._providers.declaring(family, capability)  # type: ignore[arg-type]
                status = "unavailable" if declared and status != "disabled" else "disabled"
                continue
            for provider_id in serving:
                if self._providers.state(provider_id) == "degraded" and _DEGRADED not in limitations:
                    limitations.append(_DEGRADED)
                description = self._providers.description(provider_id)
                for declaration in description.capabilities if description is not None else ():
                    if declaration.capability == capability:
                        formats.update(declaration.formats)
                        limitations += [item for item in declaration.limitations if item not in limitations]
        entry: dict[str, Any] = {"name": tool, "status": status}
        if status == "enabled":
            if formats:
                entry["formats"] = sorted(formats, key=_FORMAT_ORDER.__getitem__)
            if limitations:
                entry["limitations"] = limitations
        return entry
