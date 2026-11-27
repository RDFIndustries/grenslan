"""The extension launcher pattern of docs/implementation/EXTENSIONS.md, with the fixture as the extension.

A real deployment puts a module like this in a derived image and uses it as
the container command. Tests import ``run`` instead of executing the module.
"""

from __future__ import annotations

from collections.abc import Sequence

from grenslan.cli import main
from grenslan.providers.builtin import builtin_implementations

from fixture_providers import FixtureSet


def run(argv: Sequence[str]) -> int:
    return main(argv, implementations=[*builtin_implementations(), FixtureSet().implementation()])


if __name__ == "__main__":
    import sys

    raise SystemExit(run(sys.argv[1:]))
