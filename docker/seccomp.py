"""Generate Grenslan's seccomp profile (docker/seccomp.json) from Docker's default.

Bundled SearXNG is confined with ``unshare(CLONE_NEWUSER | CLONE_NEWNET)``
(SEARXNG-EGRESS.md S1, S2). Docker's default profile allows ``unshare`` only
to processes with ``CAP_SYS_ADMIN``. Grenslan's profile is Docker's default
plus one rule: ``unshare`` is allowed when its flags are exactly
``CLONE_NEWUSER | CLONE_NEWNET``. Any other combination is still refused,
including either flag alone or with mount or PID namespaces added. Nothing
else changes, so the container still runs non-root with no added
capabilities.

``seccomp-docker-default.json`` is Docker's default profile from
github.com/moby/profiles tag ``seccomp/v0.2.3`` (Apache-2.0), as vendored
in Docker Engine 29.8.2.

    python3 docker/seccomp.py          # write seccomp.json
    python3 docker/seccomp.py --check  # fail if seccomp.json is out of date
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
DEFAULT = HERE / "seccomp-docker-default.json"
PROFILE = HERE / "seccomp.json"
CLONE_NEWUSER = 0x10000000
CLONE_NEWNET = 0x40000000
CONFINEMENT_RULE: dict[str, Any] = {
    "names": ["unshare"],
    "action": "SCMP_ACT_ALLOW",
    "args": [{"index": 0, "value": CLONE_NEWUSER | CLONE_NEWNET, "op": "SCMP_CMP_EQ"}],
    "comment": "Grenslan: confinement of bundled SearXNG (new user and network namespace only)",
}


def profile(default: dict[str, Any]) -> dict[str, Any]:
    derived = dict(default)
    derived["syscalls"] = [*default["syscalls"], CONFINEMENT_RULE]
    return derived


def render() -> str:
    return json.dumps(profile(json.loads(DEFAULT.read_text(encoding="utf-8"))), indent="\t") + "\n"


def main(argv: list[str]) -> int:
    expected = render()
    if argv == ["--check"]:
        if not PROFILE.exists() or PROFILE.read_text(encoding="utf-8") != expected:
            print(f"{PROFILE.name} is out of date; run python3 docker/seccomp.py", file=sys.stderr)
            return 1
        return 0
    if argv:
        print("usage: seccomp.py [--check]", file=sys.stderr)
        return 2
    PROFILE.write_text(expected, encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
