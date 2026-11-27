"""The ``grenslan`` command: ``check-config``, ``serve``, ``credential new`` and ``tls new``.

``check-config``, ``serve`` and ``credential new`` are specified in
SERVICE-CONFIGURATION.md (D2, D6); ``tls new`` issues certificates for
deployments without their own issuer (``server/tls_issue.py``).

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
from pathlib import Path
from typing import TextIO

from grenslan.config.loader import ConfigLoadError
from grenslan.contracts.registry import ToolRegistry
from grenslan.providers.builtin import builtin_registry
from grenslan.providers.registry import Implementation, ImplementationRegistry, ProviderRegistrationError
from grenslan.server.runner import ConfigPaths, run_service, validate_configuration
from grenslan.server.tls import TlsConfigError
from grenslan.server.tls_issue import MAX_CA_DAYS, MAX_SERVER_DAYS, TlsIssueError, issue_certificate

TOKEN_BYTES = 32


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="grenslan", description="Grenslan research service")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("check-config", help="validate the configuration files and exit")
    commands.add_parser("serve", help="validate the configuration and serve HTTPS")
    credential = commands.add_parser("credential", help="manage consumer credentials")
    credential_commands = credential.add_subparsers(dest="credential_command", required=True)
    credential_commands.add_parser("new", help="generate a consumer token and its configuration digest")
    tls = commands.add_parser("tls", help="issue TLS certificates when no other issuer is available")
    tls_commands = tls.add_subparsers(dest="tls_command", required=True)
    tls_commands.add_parser("new", help="create a private CA and server certificate", add_help=False)
    return parser


def _tls_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="grenslan tls new",
        description="Create a server certificate signed by a new private CA, or by an existing CA you supply.",
    )
    parser.add_argument(
        "--name", action="append", required=True, help="host name or IP address clients connect to (repeatable)"
    )
    parser.add_argument("--days", type=int, required=True, help=f"server certificate validity (1-{MAX_SERVER_DAYS})")
    parser.add_argument("--ca-days", type=int, help=f"validity of a new CA (1-{MAX_CA_DAYS}); omit with --ca-key")
    parser.add_argument("--ca-certificate", type=Path, help="existing CA certificate (PEM) to sign with")
    parser.add_argument("--ca-key", type=Path, help="existing CA private key (unencrypted PEM)")
    parser.add_argument("--output-dir", type=Path, required=True, help="directory for the new files")
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


def tls_new(argv: Sequence[str], out: TextIO, err: TextIO) -> int:
    arguments = _tls_parser().parse_args(argv)
    try:
        files = issue_certificate(
            arguments.output_dir.absolute(),
            names=arguments.name,
            days=arguments.days,
            ca_days=arguments.ca_days,
            ca_certificate=arguments.ca_certificate,
            ca_key=arguments.ca_key,
        )
    except TlsIssueError as error:
        _report(error, err)
        return 1
    print("tls:", file=out)
    print(f"  certificate_file: {files.certificate}", file=out)
    print(f"  private_key_file: {files.private_key}", file=out)
    guidance = [
        f"Give consumers the CA certificate to trust: {files.ca_certificate}",
        "Restart Grenslan to start serving a new certificate.",
    ]
    if files.ca_key is not None:
        guidance.append(
            f"Keep the CA key {files.ca_key} away from the server and protected; it is needed only to issue "
            "replacement certificates with --ca-certificate and --ca-key."
        )
    print("\n".join(guidance), file=err)
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
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv[:2] == ["tls", "new"]:
        return tls_new(argv[2:], sys.stdout, sys.stderr)
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
