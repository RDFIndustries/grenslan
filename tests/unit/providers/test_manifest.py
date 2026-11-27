"""Dependency manifests, platform and integrity verification at registration (PROVIDER-REGISTRATION.md R1-R3)."""

from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
from typing import Any

import pytest

from grenslan.providers.manifest import ManifestError, load_manifest, running_platform, verify_manifest

from fixture_providers import FIXTURE_MANIFEST, Calls, FixtureBehaviour, FixtureSearchProvider

DESCRIPTION = FixtureSearchProvider("p", FixtureBehaviour(), Calls()).describe()


def base() -> dict[str, Any]:
    return copy.deepcopy(json.loads(FIXTURE_MANIFEST.read_text(encoding="utf-8")))


def write(directory: Path, data: dict[str, Any], *, notice: bool = True) -> Path:
    if notice:
        (directory / "fixture-notice.txt").write_text("notice", encoding="utf-8")
    path = directory / "manifest.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


def verify(tmp_path: Path, data: dict[str, Any], platform: str = "linux-x86_64", **kwargs: Any) -> None:
    verify_manifest(load_manifest(write(tmp_path, data, **kwargs)), DESCRIPTION, platform=platform)


def test_packaged_fixture_manifest_verifies() -> None:
    verify_manifest(load_manifest(FIXTURE_MANIFEST), DESCRIPTION, platform=running_platform())


@pytest.mark.parametrize(
    ("system", "machine", "expected"),
    [("Linux", "x86_64", "linux-x86_64"), ("Linux", "amd64", "linux-x86_64"), ("Linux", "arm64", "linux-aarch64"),
     ("Linux", "aarch64", "linux-aarch64"), ("Darwin", "arm64", "darwin-aarch64")],
)  # fmt: skip
def test_running_platform_is_normalized(system: str, machine: str, expected: str) -> None:
    assert running_platform(system=system, machine=machine) == expected


@pytest.mark.parametrize(
    "change",
    [
        pytest.param({"surprise": 1}, id="unknown-member"),
        pytest.param({"manifest_version": "2.0"}, id="version"),
        pytest.param({"supported_platforms": ["windows"]}, id="platform-name"),
        pytest.param(
            {"files": [{"path": "relative", "sha256": "0" * 64, "license": "MIT", "role": "binary"}]}, id="relative"
        ),
        pytest.param({"license_notices": ["../outside.txt"]}, id="notice-escapes"),
        pytest.param({"known_limitations": ["x" * 600]}, id="too-long"),
    ],
)
def test_malformed_manifests_are_refused(tmp_path: Path, change: dict[str, Any]) -> None:
    with pytest.raises(ManifestError):
        load_manifest(write(tmp_path, base() | change))


@pytest.mark.parametrize("content", ["not json", '{"a": 1, "a": 2}', '{"x": NaN}', "[]"])
def test_manifest_json_is_strict(tmp_path: Path, content: str) -> None:
    path = tmp_path / "manifest.json"
    path.write_text(content, encoding="utf-8")
    with pytest.raises(ManifestError):
        load_manifest(path)


def test_missing_manifest_is_refused(tmp_path: Path) -> None:
    with pytest.raises(ManifestError, match="cannot be read"):
        load_manifest(tmp_path / "absent.json")


@pytest.mark.parametrize(
    ("change", "message"),
    [
        pytest.param({"manifest_id": "other"}, "manifest", id="manifest-id"),
        pytest.param({"implementation_id": "other"}, "implementation", id="implementation-id"),
        pytest.param({"implementation_version": "9"}, "version", id="implementation-version"),
        pytest.param({"family": "retrieval"}, "family", id="family"),
        pytest.param({"supported_platforms": ["linux-x86_64"]}, "platform", id="platforms-differ"),
    ],
)
def test_manifest_must_match_the_description(tmp_path: Path, change: dict[str, Any], message: str) -> None:
    with pytest.raises(ManifestError, match=message):
        verify(tmp_path, base() | change)


def test_unsupported_running_platform_is_refused(tmp_path: Path) -> None:
    from dataclasses import replace

    data = base() | {"supported_platforms": ["linux-aarch64"]}
    description = replace(DESCRIPTION, supported_platforms=("linux-aarch64",))
    with pytest.raises(ManifestError, match="linux-x86_64"):
        verify_manifest(load_manifest(write(tmp_path, data)), description, platform="linux-x86_64")
    verify_manifest(load_manifest(write(tmp_path, data)), description, platform="linux-aarch64")


@pytest.mark.parametrize(
    "distribution",
    [
        {"name": "pyyaml", "version": "0.0.1", "license": "MIT"},
        {"name": "no-such-dist", "version": "1", "license": "MIT"},
    ],
)
def test_distribution_versions_must_be_installed(tmp_path: Path, distribution: dict[str, str]) -> None:
    with pytest.raises(ManifestError, match=distribution["name"]):
        verify(tmp_path, base() | {"distributions": [distribution]})


def pinned_file(tmp_path: Path) -> tuple[Path, dict[str, Any]]:
    binary = tmp_path / "tool"
    binary.write_bytes(b"\x7fELF pinned executable" * 1000)
    entry = {
        "path": str(binary),
        "sha256": hashlib.sha256(binary.read_bytes()).hexdigest(),
        "license": "MIT",
        "role": "binary",
    }
    return binary, base() | {"files": [entry]}


def test_pinned_file_verifies(tmp_path: Path) -> None:
    _, data = pinned_file(tmp_path)
    verify(tmp_path, data)


def test_modified_pinned_executable_fails_verification(tmp_path: Path) -> None:
    binary, data = pinned_file(tmp_path)
    binary.write_bytes(binary.read_bytes()[:-1] + b"!")
    with pytest.raises(ManifestError, match=str(binary)) as excinfo:
        verify(tmp_path, data)
    assert "pinned executable" not in str(excinfo.value)


def test_missing_pinned_file_fails_verification(tmp_path: Path) -> None:
    binary, data = pinned_file(tmp_path)
    binary.unlink()
    with pytest.raises(ManifestError, match="cannot be read"):
        verify(tmp_path, data)


def test_missing_license_notice_fails_verification(tmp_path: Path) -> None:
    with pytest.raises(ManifestError, match="license notice"):
        verify(tmp_path, base(), notice=False)
