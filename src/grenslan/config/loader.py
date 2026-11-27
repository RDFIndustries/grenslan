"""Load and validate the operator's provider configuration file."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

from grenslan.config.provider_config import (
    ConfigValidationError,
    ImplementationSpec,
    ProviderConfig,
    validate_provider_config,
)
from grenslan.config.yaml_loader import ConfigSyntaxError, load_config_text

DEFAULT_MAX_CONFIG_BYTES = 1024 * 1024


@dataclass(frozen=True, slots=True)
class LoadProblem:
    """A problem located by source line or by JSON pointer into the parsed configuration."""

    location: str
    message: str

    def __str__(self) -> str:
        return f"{self.location}: {self.message}"


class ConfigLoadError(ValueError):
    def __init__(self, problems: list[LoadProblem]) -> None:
        super().__init__("; ".join(str(problem) for problem in problems))
        self.problems = problems


def _fail(message: str) -> ConfigLoadError:
    return ConfigLoadError([LoadProblem("file", message)])


def load_provider_config_file(
    path: Path,
    implementations: Mapping[str, ImplementationSpec],
    *,
    max_bytes: int = DEFAULT_MAX_CONFIG_BYTES,
) -> ProviderConfig:
    """Read, parse and validate ``path``; every failure is a :class:`ConfigLoadError`."""
    try:
        with path.open("rb") as handle:
            raw = handle.read(max_bytes + 1)
    except OSError:
        raise _fail("configuration file cannot be read") from None
    if len(raw) > max_bytes:
        raise _fail("configuration exceeds the size limit")
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        raise _fail("configuration is not valid utf-8") from None
    try:
        data = load_config_text(text, max_bytes=max_bytes)
    except ConfigSyntaxError as exc:
        raise ConfigLoadError([LoadProblem(f"line {exc.line}", exc.reason)]) from None
    try:
        return validate_provider_config(data, implementations)
    except ConfigValidationError as exc:
        raise ConfigLoadError([LoadProblem(p.location, p.message) for p in exc.problems]) from None
