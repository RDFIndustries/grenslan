"""Provider dependency manifests and their verification at registration (PROVIDER-REGISTRATION.md R1-R3).

Every registered implementation ships one manifest. Registration checks it
against the implementation's self-description and the running platform, then
checks that each listed Python distribution is installed at the listed
version, that each listed file (binaries, model weights, browser builds) has
the listed SHA-256 digest, and that each license notice exists. Any mismatch
is a :class:`ManifestError`; messages name the item, never file content.

Python package files are trusted through the image build and are not
rehashed here.
"""

from __future__ import annotations

import hashlib
import importlib.metadata
import json
import platform as host
from dataclasses import dataclass
from functools import cache
from pathlib import Path, PurePosixPath
from typing import Any

from jsonschema import Draft202012Validator

from grenslan.providers.contract import ProviderDescription

PACKAGED_SCHEMA = Path(__file__).with_name("MANIFEST_SCHEMA.json")
MAX_MANIFEST_BYTES = 256 * 1024
_CHUNK_BYTES = 1024 * 1024
_MACHINES = {"x86_64": "x86_64", "amd64": "x86_64", "aarch64": "aarch64", "arm64": "aarch64"}
ANY_PLATFORM = "any"


class ManifestError(ValueError):
    """A manifest is malformed, or the installation does not match it."""


@dataclass(frozen=True, slots=True)
class Manifest:
    path: Path
    data: dict[str, Any]


def running_platform(*, system: str | None = None, machine: str | None = None) -> str:
    """The running platform in manifest vocabulary, for example ``linux-x86_64``."""
    system = (system or host.system()).lower()
    machine = (machine or host.machine()).lower()
    return f"{system}-{_MACHINES.get(machine, machine)}"


@cache
def _validator() -> Draft202012Validator:
    schema = json.loads(PACKAGED_SCHEMA.read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    return Draft202012Validator(schema)


def _unique_members(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    members = dict(pairs)
    if len(members) != len(pairs):
        raise ValueError("duplicate member")
    return members


def _reject_constant(_name: str) -> Any:
    raise ValueError("non-finite number")


def load_manifest(path: Path) -> Manifest:
    try:
        with path.open("rb") as handle:
            raw = handle.read(MAX_MANIFEST_BYTES + 1)
    except OSError:
        raise ManifestError(f"manifest {path} cannot be read") from None
    if len(raw) > MAX_MANIFEST_BYTES:
        raise ManifestError(f"manifest {path} exceeds the size limit")
    try:
        data = json.loads(raw, object_pairs_hook=_unique_members, parse_constant=_reject_constant)
    except ValueError:
        raise ManifestError(f"manifest {path} is not strict JSON") from None
    errors = sorted(_validator().iter_errors(data), key=lambda error: list(error.absolute_path))
    if errors:
        location = "/" + "/".join(str(part) for part in errors[0].absolute_path)
        raise ManifestError(f"manifest {path} is invalid at {location} ({errors[0].validator})")
    for notice in data["license_notices"]:
        relative = PurePosixPath(notice)
        if relative.is_absolute() or ".." in relative.parts:
            raise ManifestError(f"manifest {path}: license notices must be paths inside the manifest directory")
    return Manifest(path, data)


def _digest(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(_CHUNK_BYTES):
            digest.update(chunk)
    return digest.hexdigest()


def verify_manifest(manifest: Manifest, description: ProviderDescription, *, platform: str) -> None:
    """Check the manifest against the description, the platform and the installed files."""
    data = manifest.data
    if data["manifest_id"] != description.dependency_manifest_id:
        raise ManifestError("manifest ID does not match the declared dependency manifest")
    for field in ("implementation_id", "implementation_version", "family", "contract_version"):
        if data[field] != getattr(description, field):
            raise ManifestError(f"manifest {field.replace('_', ' ')} does not match the declaration")
    platforms = set(data["supported_platforms"])
    if platforms != set(description.supported_platforms):
        raise ManifestError("manifest platforms do not match the declared supported platforms")
    if ANY_PLATFORM not in platforms and platform not in platforms:
        raise ManifestError(f"the implementation does not support the running platform {platform}")
    for distribution in data["distributions"]:
        name = distribution["name"]
        try:
            installed = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            raise ManifestError(f"required distribution {name} is not installed") from None
        if installed != distribution["version"]:
            raise ManifestError(f"required distribution {name} is installed at a different version")
    for entry in data["files"]:
        try:
            actual = _digest(Path(entry["path"]))
        except OSError:
            raise ManifestError(f"pinned file {entry['path']} cannot be read") from None
        if actual != entry["sha256"]:
            raise ManifestError(f"pinned file {entry['path']} does not match its recorded digest")
    for notice in data["license_notices"]:
        if not (manifest.path.parent / notice).is_file():
            raise ManifestError(f"license notice {notice} is missing")
