"""The provider implementations shipped with Grenslan (PC-004).

This list is the only place production implementations are registered.
Configuration can select only what is listed here, and test fixtures are
never added to it. An operator adds an approved extension by passing it, with
this list, to ``grenslan.cli.main`` from a launcher in a derived image
(``docs/implementation/EXTENSIONS.md``).
"""

from __future__ import annotations

from grenslan.providers.registry import Implementation, ImplementationRegistry


def builtin_implementations() -> list[Implementation]:
    return []


def builtin_registry() -> ImplementationRegistry:
    return ImplementationRegistry(builtin_implementations())
