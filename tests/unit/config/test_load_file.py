"""Loading operator configuration files end to end."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from grenslan.config import provider_config
from grenslan.config.loader import ConfigLoadError, load_provider_config_file

from config_fixtures import IMPLEMENTATIONS, connected_config

DOCS_SCHEMA = Path(__file__).resolve().parents[3] / "docs" / "contracts" / "PROVIDER_CONFIG_SCHEMA.json"


def test_packaged_schema_is_byte_identical_to_adopted_contract() -> None:
    assert provider_config.PACKAGED_SCHEMA.read_bytes() == DOCS_SCHEMA.read_bytes()


def test_loads_valid_file(tmp_path: Path) -> None:
    path = tmp_path / "config.yaml"
    path.write_text(yaml.safe_dump(connected_config()), encoding="utf-8")
    config = load_provider_config_file(path, IMPLEMENTATIONS)
    assert config.routes("search") == ("searxng_local",)


def test_yaml_problem_is_reported_with_line(tmp_path: Path) -> None:
    path = tmp_path / "config.yaml"
    path.write_text("config_version: '1.0'\nconfig_version: '1.0'\n", encoding="utf-8")
    with pytest.raises(ConfigLoadError) as excinfo:
        load_provider_config_file(path, IMPLEMENTATIONS)
    assert [str(p) for p in excinfo.value.problems] == ["line 2: duplicate key"]


def test_schema_problems_are_reported(tmp_path: Path) -> None:
    path = tmp_path / "config.yaml"
    path.write_text("config_version: '1.0'\n", encoding="utf-8")
    with pytest.raises(ConfigLoadError) as excinfo:
        load_provider_config_file(path, IMPLEMENTATIONS)
    assert all(str(p).startswith("/") for p in excinfo.value.problems)
    assert excinfo.value.problems


def test_invalid_utf8_is_rejected(tmp_path: Path) -> None:
    path = tmp_path / "config.yaml"
    path.write_bytes(b"config_version: '\xff'\n")
    with pytest.raises(ConfigLoadError, match="utf-8"):
        load_provider_config_file(path, IMPLEMENTATIONS)


def test_missing_file_is_reported_without_raising_oserror(tmp_path: Path) -> None:
    with pytest.raises(ConfigLoadError, match="cannot be read"):
        load_provider_config_file(tmp_path / "absent.yaml", IMPLEMENTATIONS)


def test_oversized_file_is_rejected(tmp_path: Path) -> None:
    path = tmp_path / "config.yaml"
    path.write_text("a: " + "x" * 2048 + "\n", encoding="utf-8")
    with pytest.raises(ConfigLoadError, match="size"):
        load_provider_config_file(path, IMPLEMENTATIONS, max_bytes=1024)
