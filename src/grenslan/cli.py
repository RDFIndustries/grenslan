"""The ``grenslan`` command: ``check-config``, ``serve`` and ``credential new`` (SERVICE-CONFIGURATION.md D2, D6).

Configuration paths come from ``GRENSLAN_SERVICE_CONFIG`` and
``GRENSLAN_PROVIDER_CONFIG``, defaulting to ``/etc/grenslan/``. Problem output
names locations and reasons but never configuration values, digests or keys.
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import logging
import os
import secrets
import sys
from collections.abc import Iterable, Mapping, Sequence
from typing import TextIO

from grenslan.config.loader import ConfigLoadError
from grenslan.contracts.registry import ToolRegistry
from grenslan.providers.builtin import builtin_registry
from grenslan.providers.registry import Implementation, ImplementationRegistry, ProviderRegistrationError
from grenslan.server.runner import ConfigPaths, run_service, validate_configuration
from grenslan.server.tls import TlsConfigError

TOKEN_BYTES = 32


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="grenslan", description="Grenslan research service")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("check-config", help="validate the configuration files and exit")
    commands.add_parser("serve", help="validate the configuration and serve HTTPS")
    credential = commands.add_parser("credential", help="manage consumer credentials")
    credential_commands = credential.add_subparsers(dest="credential_command", required=True)
    credential_commands.add_parser("new", help="generate a consumer token and its configuration digest")
    return parser


def _report(error: Exception, err: TextIO) -> None:
    if isinstance(error, ConfigLoadError):
        for problem in error.problems:
            print(f"error: {problem}", file=err)
    else:
        print(f"error: {error}", file=err)


def check_config(
    environ: Mapping[str, str], out: TextIO, err: TextIO, implementations: ImplementationRegistry | None = None
) -> int:
    paths = ConfigPaths.from_environment(environ)
    registry = builtin_registry() if implementations is None else implementations
    try:
        validated = validate_configuration(paths, environ, ToolRegistry.load(), registry)
        registry.check(validated.providers)
    except (ConfigLoadError, TlsConfigError, ProviderRegistrationError) as error:
        _report(error, err)
        return 1
    print(f"configuration is valid: {paths.service}, {paths.providers}", file=out)
    return 0


def credential_new(out: TextIO, err: TextIO) -> int:
    token = secrets.token_urlsafe(TOKEN_BYTES)
    print(f"token: {token}", file=out)
    print(f"token_sha256: {hashlib.sha256(token.encode('ascii')).hexdigest()}", file=out)
    print(
        "Give the token to the consumer over a protected channel; it is not shown again.\n"
        "Put the token_sha256 line in the consumer's credential entry.",
        file=err,
    )
    return 0


def serve(environ: Mapping[str, str], err: TextIO, implementations: ImplementationRegistry | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    try:
        asyncio.run(run_service(environ, implementations=implementations))
    except (ConfigLoadError, TlsConfigError, ProviderRegistrationError) as error:
        _report(error, err)
        return 1
    return 0


def main(argv: Sequence[str] | None = None, *, implementations: Iterable[Implementation] | None = None) -> int:
    """Run a command. ``implementations`` replaces the built-in list; a launcher passes it to add an extension."""
    arguments = _parser().parse_args(argv)
    environ = dict(os.environ)
    registry = None if implementations is None else ImplementationRegistry(implementations)
    if arguments.command == "check-config":
        return check_config(environ, sys.stdout, sys.stderr, registry)
    if arguments.command == "credential":
        return credential_new(sys.stdout, sys.stderr)
    return serve(environ, sys.stderr, registry)


if __name__ == "__main__":
    sys.exit(main())
