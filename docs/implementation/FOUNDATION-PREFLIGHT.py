"""Reproducible initial contract checks, not Grenslan service or runtime conformance."""
import argparse
import copy
import hashlib
import json
from pathlib import Path
import runpy
import socket
import ssl
import subprocess
import tempfile
import threading

from jsonschema import Draft202012Validator, FormatChecker


def validate_contracts(folder: Path) -> None:
    registry = json.loads((folder / "TOOL_SCHEMAS.json").read_text())
    definitions = registry["$defs"]
    assert len(registry["tools"]) == 32

    def references(node):
        if isinstance(node, dict):
            for key, value in node.items():
                if key == "$ref":
                    yield value
                else:
                    yield from references(value)
        elif isinstance(node, list):
            for value in node:
                yield from references(value)

    def project(reference):
        root = copy.deepcopy(definitions[reference.split("/")[-1]])
        reachable = {}
        pending = list(references(root))
        while pending:
            ref = pending.pop()
            assert ref.startswith("#/$defs/"), ref
            name = ref.split("/")[-1]
            if name not in reachable:
                reachable[name] = definitions[name]
                pending.extend(references(definitions[name]))
        return {"$schema": registry["$schema"], "$defs": reachable, **root}

    for name, tool in registry["tools"].items():
        for prop in ("inputSchema", "outputSchema"):
            schema = project(tool[prop]["$ref"])
            assert schema["type"] == "object", (name, prop)
            Draft202012Validator.check_schema(schema)

    def valid(name, direction, value):
        schema = project(registry["tools"][name][direction + "Schema"]["$ref"])
        return Draft202012Validator(schema, format_checker=FormatChecker()).is_valid(value)

    assert valid("web_search", "input", {"query": "fixture"})
    assert not valid("web_search", "input", {"query": "fixture", "application_id": "forged"})
    assert not valid("web_search", "input", {"query": "fixture", "execution": {"timeout_ms": 0}})
    assert not valid("web_open", "input", {"url": "file:///etc/passwd"})
    uri = "grenslan://artifacts/a"
    assert valid("document_read", "input", {"artifact_uri": uri, "interpretation": {"capability": "translation", "target_language": "en"}})
    assert not valid("document_read", "input", {"artifact_uri": uri, "interpretation": {"capability": "translation"}})
    assert valid("image_ocr", "input", {"artifact_uri": uri, "allow_model_assisted": True, "provider": "configured_ocr"})
    assert valid("web_search", "output", {"schema_version": "1.0", "request_id": "r", "status": "completed",
                 "effective_mode": "sync", "issues": [], "result": {"results": [], "constraints": [],
                 "ranking": "provider_order", "freshness": "default"}})
    config = json.loads((folder / "PROVIDER_CONFIG_SCHEMA.json").read_text())
    Draft202012Validator.check_schema(config)
    declarations = runpy.run_path(str(folder / "PROVIDER_INTERFACES.py"))
    protocols = ("SearchProvider", "RetrievalProvider", "BrowserProvider", "ContentProcessor",
                 "OCRProvider", "IntelligenceProvider", "BrowserEngine", "BrowserController")
    assert all(declarations[name]._is_protocol for name in protocols)
    print("PASS: 64 projected tool schemas; 8 representative assertions; configuration meta-schema; 8 protocol declarations.")
    for name in ("TOOL_CONTRACT.md", "TOOL_SCHEMAS.json", "PROVIDER_CONTRACT.md",
                 "PROVIDER_INTERFACES.py", "PROVIDER_CONFIG_SCHEMA.json"):
        print(hashlib.sha256((folder / name).read_bytes()).hexdigest(), name)


def tls_smoke() -> None:
    # This creates and discards a test-only certificate and private key.
    # Uses an ephemeral loopback socket; never changes system trust.
    with tempfile.TemporaryDirectory() as temp:
        cert, key = Path(temp) / "cert.pem", Path(temp) / "key.pem"
        subprocess.run(["openssl", "req", "-x509", "-newkey", "rsa:2048", "-nodes",
                        "-days", "1", "-subj", "/CN=localhost",
                        "-addext", "subjectAltName=DNS:localhost",
                        "-keyout", str(key), "-out", str(cert)],
                       check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        context.minimum_version = ssl.TLSVersion.TLSv1_2
        context.load_cert_chain(cert, key)
        with socket.socket() as listener:
            listener.bind(("127.0.0.1", 0))
            listener.listen(3)
            listener.settimeout(5)
            address = listener.getsockname()

            def serve():
                for _ in range(3):
                    try:
                        connection, _ = listener.accept()
                        with connection:
                            with context.wrap_socket(connection, server_side=True) as stream:
                                stream.sendall(b"OK")
                    except (ssl.SSLError, OSError):
                        # Untrusted/incorrect-host tests intentionally fail handshakes.
                        pass

            thread = threading.Thread(target=serve, daemon=True)
            thread.start()

            def call(client_context, host):
                with socket.create_connection(address, timeout=3) as raw:
                    with client_context.wrap_socket(raw, server_hostname=host) as stream:
                        return stream.recv(2), stream.version()

            trusted = ssl.create_default_context(cafile=str(cert))
            payload, version = call(trusted, "localhost")
            assert payload == b"OK"
            for client, host in [(ssl.create_default_context(), "localhost"), (trusted, "wrong.example")]:
                try:
                    call(client, host)
                except ssl.SSLCertVerificationError:
                    pass
                else:
                    raise AssertionError("Untrusted certificate or wrong hostname accepted")
            thread.join(5)
            assert not thread.is_alive(), "TLS smoke listener failed to finish"
            print(f"PASS: explicitly trusted ephemeral certificate ({version}); untrusted certificate and wrong hostname rejected.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--contracts", type=Path, default=Path(__file__).resolve().parents[1] / "contracts")
    parser.add_argument("--tls-smoke", action="store_true", help="Optional loopback primitive check; needs openssl CLI")
    args = parser.parse_args()
    validate_contracts(args.contracts)
    if args.tls_smoke:
        tls_smoke()
