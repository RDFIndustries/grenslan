"""Runtime provider types preserve the adopted declarations exactly (PC-055)."""

from __future__ import annotations

import dataclasses
import importlib.util
import inspect
import sys
import typing
from pathlib import Path
from types import ModuleType

import pytest

from grenslan.providers import contract

SPEC_PATH = Path(__file__).resolve().parents[3] / "docs" / "contracts" / "PROVIDER_INTERFACES.py"

RECORDS = [
    "Issue", "ProviderResult", "CapabilityDeclaration", "ProviderDescription", "Health", "Limits",
    "InputResource", "StagedResource", "ProviderExecutionContext", "LifecycleContext", "Range", "Region",
    "Locator", "Heading", "Metadata", "SearchRequest", "ConstraintDisposition", "Discovery", "SearchResult",
]  # fmt: skip
PROTOCOLS = ["Cancellation", "ResourceAccess", "Provider", "SearchProvider"]
ALIASES = [
    "Identifier", "Scalar", "ScalarFields", "Family", "ProviderState", "Outcome", "Format", "Category",
    "Freshness", "Method", "Capability", "IssueCode",
]  # fmt: skip


@pytest.fixture(scope="module")
def spec() -> ModuleType:
    loader_spec = importlib.util.spec_from_file_location("adopted_provider_interfaces", SPEC_PATH)
    assert loader_spec is not None
    assert loader_spec.loader is not None
    module = importlib.util.module_from_spec(loader_spec)
    sys.modules[loader_spec.name] = module
    try:
        loader_spec.loader.exec_module(module)
    except BaseException:
        del sys.modules[loader_spec.name]
        raise
    return module


def _fields(cls: type) -> list[tuple[str, object, object]]:
    return [(f.name, f.type, f.default) for f in dataclasses.fields(cls)]


@pytest.mark.parametrize("name", RECORDS)
def test_record_fields_match_declaration(spec: ModuleType, name: str) -> None:
    assert _fields(getattr(contract, name)) == _fields(getattr(spec, name))


@pytest.mark.parametrize("name", RECORDS)
def test_records_are_frozen_and_slotted(name: str) -> None:
    cls = getattr(contract, name)
    params = cls.__dataclass_params__
    assert params.frozen
    assert "__slots__" in cls.__dict__


@pytest.mark.parametrize("name", PROTOCOLS)
def test_protocol_methods_match_declaration(spec: ModuleType, name: str) -> None:
    ours, theirs = getattr(contract, name), getattr(spec, name)

    def methods(cls: type) -> dict[str, str]:
        return {
            member: str(inspect.signature(getattr(cls, member)))
            for member in dir(cls)
            if not member.startswith("_") and inspect.isfunction(getattr(cls, member))
        }

    assert methods(ours) == methods(theirs)
    assert methods(ours)


@pytest.mark.parametrize("name", ALIASES)
def test_type_aliases_match_declaration(spec: ModuleType, name: str) -> None:
    ours, theirs = getattr(contract, name), getattr(spec, name)
    assert typing.get_origin(ours) == typing.get_origin(theirs)
    assert typing.get_args(ours) == typing.get_args(theirs)
    assert ours == theirs


def test_contract_version() -> None:
    assert contract.CONTRACT_VERSION == "1.0"
