"""The provider implementations shipped with Grenslan (PC-004).

This list is the only place production implementations are registered.
Configuration can select only what is listed here, and test fixtures are
never added to it.
"""

from __future__ import annotations

from grenslan.providers.registry import ImplementationRegistry


def builtin_registry() -> ImplementationRegistry:
    return ImplementationRegistry(())
