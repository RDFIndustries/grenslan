"""docker/seccomp.json is Docker's default profile plus exactly one confinement rule."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[3]


def load(name: str) -> dict[str, Any]:
    data: dict[str, Any] = json.loads((ROOT / "docker" / name).read_text(encoding="utf-8"))
    return data


def test_the_profile_is_dockers_default_plus_one_rule() -> None:
    default, grenslan = load("seccomp-docker-default.json"), load("seccomp.json")
    assert {k: v for k, v in grenslan.items() if k != "syscalls"} == {
        k: v for k, v in default.items() if k != "syscalls"
    }
    assert grenslan["syscalls"][: len(default["syscalls"])] == default["syscalls"]
    added = grenslan["syscalls"][len(default["syscalls"]) :]
    assert len(added) == 1
    assert added[0]["names"] == ["unshare"]
    assert added[0]["action"] == "SCMP_ACT_ALLOW"
    assert "includes" not in added[0]
    assert "excludes" not in added[0]


def test_the_rule_allows_only_a_new_user_and_network_namespace() -> None:
    (rule,) = load("seccomp.json")["syscalls"][-1:]
    assert rule["args"] == [{"index": 0, "value": os.CLONE_NEWUSER | os.CLONE_NEWNET, "op": "SCMP_CMP_EQ"}]


def test_the_default_still_denies_everything_unlisted() -> None:
    grenslan = load("seccomp.json")
    assert grenslan["defaultAction"] == "SCMP_ACT_ERRNO"
    unconditional = {
        name
        for rule in grenslan["syscalls"]
        if rule["action"] == "SCMP_ACT_ALLOW" and not rule.get("args") and not rule.get("includes")
        for name in rule["names"]
    }
    assert not unconditional & {"unshare", "setns", "mount", "clone3", "bpf", "ptrace"}


def test_the_committed_profile_is_current() -> None:
    import subprocess
    import sys

    result = subprocess.run([sys.executable, str(ROOT / "docker" / "seccomp.py"), "--check"], capture_output=True)  # noqa: S603
    assert result.returncode == 0, result.stderr
