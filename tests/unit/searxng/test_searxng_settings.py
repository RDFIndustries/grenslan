"""Generated SearXNG settings (SEARXNG-EGRESS.md S3)."""

from __future__ import annotations

import json
from typing import Any

import pytest

from grenslan.searxng.settings import render_settings


def rendered(**overrides: Any) -> dict[str, Any]:
    options: dict[str, Any] = {
        "engines": ["wikipedia", "google cse"],
        "secret_key": "fixture-secret-not-a-credential",
        "relay_port": 3128,
        "request_timeout": 3.0,
        "max_request_timeout": 6.0,
    }
    options.update(overrides)
    return json.loads(render_settings(**options))  # type: ignore[no-any-return]


def test_only_the_configured_engines_are_kept() -> None:
    assert rendered()["use_default_settings"] == {"engines": {"keep_only": ["wikipedia", "google cse"]}}


def test_no_plugins_are_loaded_so_nothing_downloads_at_start() -> None:
    assert rendered()["plugins"] == {}


def test_all_outgoing_requests_use_the_relay_with_verification() -> None:
    outgoing = rendered()["outgoing"]
    assert outgoing["proxies"] == {"all://": ["http://127.0.0.1:3128"]}
    assert outgoing["verify"] is True


def test_only_json_is_served_and_public_features_are_off() -> None:
    settings = rendered()
    assert settings["search"]["formats"] == ["json"]
    assert settings["server"]["limiter"] is False
    assert settings["server"]["image_proxy"] is False
    assert settings["general"]["enable_metrics"] is False


@pytest.mark.parametrize(
    "overrides",
    [
        pytest.param({"engines": []}, id="no-engines"),
        pytest.param({"engines": ["wikipedia", "wikipedia"]}, id="duplicate"),
        pytest.param({"engines": ["wiki\n  disabled: true"]}, id="newline"),
        pytest.param({"engines": ["Wikipedia"]}, id="upper-case"),
        pytest.param({"request_timeout": 0}, id="zero-timeout"),
        pytest.param({"request_timeout": 7.0}, id="timeout-above-maximum"),
    ],
)
def test_invalid_settings_are_refused(overrides: dict[str, Any]) -> None:
    with pytest.raises(ValueError, match=r"engine|timeout"):
        rendered(**overrides)


INJECTION = 'x"\n plugins: {evil: 1}'


def test_values_cannot_change_the_document_structure() -> None:
    settings = rendered(secret_key=INJECTION)
    assert settings["plugins"] == {}
    assert settings["server"]["secret_key"] == INJECTION
