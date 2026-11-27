"""Runtime access to the canonical public tool registry.

The packaged ``TOOL_SCHEMAS.json`` is a byte-identical copy of
``docs/contracts/TOOL_SCHEMAS.json`` (see ``scripts/sync-contracts.sh``). Each
tool's input and output schema is projected into a self-contained Draft 2020-12
object schema: the referenced definition plus every local definition reachable
from it (TC-047). The same projected schemas are used for MCP discovery and
for validating every REST and MCP invocation.
"""

from __future__ import annotations

import copy
import json
from collections.abc import Iterator, Mapping
from dataclasses import dataclass
from functools import cached_property
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator, FormatChecker
from jsonschema.exceptions import ValidationError

PACKAGED_REGISTRY = Path(__file__).with_name("TOOL_SCHEMAS.json")
_LOCAL_REF_PREFIX = "#/$defs/"
_MAX_REPORTED_ERRORS = 20


class UnknownToolError(KeyError):
    """The tool name is not in the canonical registry."""


class RegistryError(ValueError):
    """The registry file is structurally unusable."""


@dataclass(frozen=True, slots=True)
class SchemaError:
    """A schema validation failure that names where, not what was supplied.

    Messages never include the offending instance value, so secrets or other
    caller data in an invalid request cannot be reflected back.
    """

    location: str
    message: str


def _local_refs(node: Any) -> Iterator[str]:
    if isinstance(node, dict):
        for key, value in node.items():
            if key == "$ref":
                yield value
            else:
                yield from _local_refs(value)
    elif isinstance(node, list):
        for value in node:
            yield from _local_refs(value)


def _pointer(path: Iterator[Any] | Any) -> str:
    parts = [str(part).replace("~", "~0").replace("/", "~1") for part in path]
    return "/" + "/".join(parts) if parts else ""


def describe_validation_error(error: ValidationError) -> SchemaError:
    location = _pointer(error.absolute_path)
    keyword = str(error.validator)
    if keyword == "additionalProperties":
        message = "unknown property not permitted by the schema"
    elif keyword == "required":
        message = "required property missing"
    elif keyword == "format":
        message = f"value does not match format {error.validator_value!r}"
    else:
        message = f"value fails schema keyword {keyword!r}"
    return SchemaError(location=location or "/", message=message)


class ToolRegistry:
    """Projected schemas and validators for the 32 adopted tools."""

    def __init__(self, document: Mapping[str, Any]) -> None:
        try:
            self._dialect: str = document["$schema"]
            self._definitions: Mapping[str, Any] = document["$defs"]
            self._tools: Mapping[str, Mapping[str, Any]] = document["tools"]
            self.contract_version: str = document["contract_version"]
            self._upload_ref: str = document["supporting_schemas"]["upload_response"]["$ref"]
        except (KeyError, TypeError) as exc:
            raise RegistryError("tool registry is missing a required top-level member") from exc
        # Every definition is checked against the meta-schema once; a projection
        # only selects definitions and resolves references between them.
        Draft202012Validator.check_schema({"$schema": self._dialect, "$defs": self._definitions})
        self._projections: dict[str, dict[str, Any]] = {}
        self._validators: dict[str, Draft202012Validator] = {}
        for name, record in self._tools.items():
            for direction in ("inputSchema", "outputSchema"):
                schema = self._project(record[direction]["$ref"])
                key = f"{name}:{direction}"
                self._projections[key] = schema
                self._validators[key] = Draft202012Validator(schema, format_checker=FormatChecker())

    @classmethod
    def load(cls, path: Path = PACKAGED_REGISTRY) -> ToolRegistry:
        return cls(json.loads(path.read_text(encoding="utf-8")))

    @cached_property
    def tool_names(self) -> tuple[str, ...]:
        return tuple(sorted(self._tools))

    def _record(self, tool: str) -> Mapping[str, Any]:
        try:
            return self._tools[tool]
        except KeyError:
            raise UnknownToolError(tool) from None

    def _project(self, reference: str) -> dict[str, Any]:
        if not reference.startswith(_LOCAL_REF_PREFIX):
            raise RegistryError(f"non-local schema reference {reference!r}")
        root = copy.deepcopy(self._definitions[reference.removeprefix(_LOCAL_REF_PREFIX)])
        reachable: dict[str, Any] = {}
        pending = list(_local_refs(root))
        while pending:
            ref = pending.pop()
            if not ref.startswith(_LOCAL_REF_PREFIX):
                raise RegistryError(f"non-local schema reference {ref!r}")
            name = ref.removeprefix(_LOCAL_REF_PREFIX)
            if name not in self._definitions:
                raise RegistryError(f"unresolved schema reference {ref!r}")
            if name not in reachable:
                reachable[name] = copy.deepcopy(self._definitions[name])
                pending.extend(_local_refs(reachable[name]))
        return {"$schema": self._dialect, "$defs": reachable, **root}

    def description(self, tool: str) -> str:
        return str(self._record(tool)["description"])

    def async_supported(self, tool: str) -> bool:
        return bool(self._record(tool)["async_supported"])

    def input_schema(self, tool: str) -> dict[str, Any]:
        self._record(tool)
        return copy.deepcopy(self._projections[f"{tool}:inputSchema"])

    def output_schema(self, tool: str) -> dict[str, Any]:
        self._record(tool)
        return copy.deepcopy(self._projections[f"{tool}:outputSchema"])

    def upload_result_schema(self) -> dict[str, Any]:
        return self._project(self._upload_ref)

    def _errors(self, key: str, instance: Any) -> list[SchemaError]:
        errors = sorted(self._validators[key].iter_errors(instance), key=lambda e: list(e.absolute_path))
        return [describe_validation_error(error) for error in errors[:_MAX_REPORTED_ERRORS]]

    def input_errors(self, tool: str, arguments: Any) -> list[SchemaError]:
        self._record(tool)
        return self._errors(f"{tool}:inputSchema", arguments)

    def output_errors(self, tool: str, envelope: Any) -> list[SchemaError]:
        self._record(tool)
        return self._errors(f"{tool}:outputSchema", envelope)
