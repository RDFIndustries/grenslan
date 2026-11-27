"""Disposable preflight checks against spike_server.py. Prints one line per check."""
from __future__ import annotations

import json
import socket
import ssl
import sys

import anyio
import httpx2

from mcp import Client
from mcp.client.streamable_http import streamable_http_client

CA, PORT = sys.argv[1], int(sys.argv[2])
URL = f"https://localhost:{PORT}/mcp"
TOKEN = "spike-test-token"
V = "2026-07-28"
results: list[tuple[str, bool, str]] = []


def record(name: str, ok: bool, detail: str = "") -> None:
    results.append((name, ok, detail))
    print(f"{'PASS' if ok else 'FAIL'}  {name}  {detail}")


def trusted() -> ssl.SSLContext:
    ctx = ssl.create_default_context(cafile=CA)
    ctx.minimum_version = ssl.TLSVersion.TLSv1_2
    return ctx


def meta() -> dict:
    return {"io.modelcontextprotocol/protocolVersion": V,
            "io.modelcontextprotocol/clientInfo": {"name": "spike-check", "version": "0"},
            "io.modelcontextprotocol/clientCapabilities": {}}


def modern_headers(method: str, name: str | None = None) -> dict:
    h = {"Authorization": f"Bearer {TOKEN}", "Accept": "application/json, text/event-stream",
         "Content-Type": "application/json", "MCP-Protocol-Version": V, "Mcp-Method": method}
    if name:
        h["Mcp-Name"] = name
    return h


async def raw(client, method="POST", headers=None, body=None, header_list=None):
    content = json.dumps(body).encode() if body is not None else None
    hdrs = header_list if header_list is not None else list((headers or {}).items())
    return await client.request(method, URL, headers=hdrs, content=content)


def rpc_code(resp) -> int | None:
    try:
        return resp.json().get("error", {}).get("code")
    except Exception:
        return None


async def main() -> None:
    # Positive path: pinned modern SDK client, no automatic fallback.
    async with httpx2.AsyncClient(verify=trusted(), headers={"Authorization": f"Bearer {TOKEN}"}) as http:
        async with Client(streamable_http_client(URL, http_client=http, terminate_on_close=False), mode=V) as c:
            tools = await c.list_tools()
            names = [t.name for t in tools.tools]
            record("modern client tools/list", names == ["web_search"], str(names))
            from spike_server import REGISTRY_PATH
            reg = json.loads(REGISTRY_PATH.read_text())
            from spike_server import project
            want_in = project(reg, reg["tools"]["web_search"]["inputSchema"]["$ref"])
            want_out = project(reg, reg["tools"]["web_search"]["outputSchema"]["$ref"])
            record("discovered input/output schemas equal canonical projection",
                   tools.tools[0].input_schema == want_in and tools.tools[0].output_schema == want_out)
            res = await c.call_tool("web_search", {"query": "fixture"})
            from jsonschema import Draft202012Validator, FormatChecker
            ok = res.structured_content is not None and Draft202012Validator(want_out, format_checker=FormatChecker()).is_valid(res.structured_content)
            record("tools/call structuredContent valid against canonical output schema", ok, json.dumps(res.structured_content)[:100])
            bad = await c.call_tool("web_search", {"query": "x", "application_id": "forged"})
            record("forged identity argument rejected as tool error", bad.is_error is True)
            record("client negotiated version", c.protocol_version == V, str(c.protocol_version))

    async with httpx2.AsyncClient(verify=trusted()) as http:
        r = await raw(http, headers=modern_headers("server/discover"),
                      body={"jsonrpc": "2.0", "id": 1, "method": "server/discover", "params": {"_meta": meta()}})
        sv = r.json().get("result", {}).get("supportedVersions")
        record("server/discover lists only current revision", r.status_code == 200 and sv == [V], f"{r.status_code} {sv}")
        record("no Mcp-Session-Id minted on modern request", "mcp-session-id" not in r.headers)

        h = modern_headers("tools/list"); del h["MCP-Protocol-Version"]
        r = await raw(http, headers=h, body={"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {"_meta": meta()}})
        record("missing MCP-Protocol-Version -> 400 HeaderMismatch", r.status_code == 400 and rpc_code(r) == -32020, f"{r.status_code} {rpc_code(r)}")

        init = {"jsonrpc": "2.0", "id": 3, "method": "initialize",
                "params": {"protocolVersion": "2025-11-25", "capabilities": {}, "clientInfo": {"name": "legacy", "version": "0"}}}
        h = {"Authorization": f"Bearer {TOKEN}", "Accept": "application/json, text/event-stream", "Content-Type": "application/json"}
        r = await raw(http, headers=h, body=init)
        record("legacy initialize without header rejected, no session", r.status_code == 400 and "mcp-session-id" not in r.headers, f"{r.status_code} {rpc_code(r)}")

        for old in ("2025-11-25", "2025-06-18", "2025-03-26", "2024-11-05", "2099-01-01"):
            r = await raw(http, headers={**h, "MCP-Protocol-Version": old}, body=init)
            data = (r.json().get("error") or {}).get("data", {}) if r.headers.get("content-type", "").startswith("application/json") else {}
            record(f"version {old} -> 400 UnsupportedProtocolVersion",
                   r.status_code == 400 and rpc_code(r) == -32022 and data.get("supported") == [V], f"{r.status_code} {rpc_code(r)} {data}")

        hl = [(k, v) for k, v in modern_headers("tools/list").items()] + [("MCP-Protocol-Version", V)]
        r = await raw(http, header_list=hl, body={"jsonrpc": "2.0", "id": 4, "method": "tools/list", "params": {"_meta": meta()}})
        record("duplicate MCP-Protocol-Version rejected", r.status_code == 400, f"{r.status_code} {rpc_code(r)}")

        for m in ("GET", "DELETE"):
            r = await raw(http, method=m, headers={"Authorization": f"Bearer {TOKEN}", "MCP-Protocol-Version": V})
            record(f"{m} /mcp -> 405", r.status_code == 405, str(r.status_code))

        r = await raw(http, headers={**modern_headers("tools/list"), "Origin": "https://evil.example"},
                      body={"jsonrpc": "2.0", "id": 5, "method": "tools/list", "params": {"_meta": meta()}})
        record("invalid Origin -> 403", r.status_code == 403, str(r.status_code))

        r = await raw(http, headers={**modern_headers("tools/list"), "Authorization": "Bearer wrong"},
                      body={"jsonrpc": "2.0", "id": 6, "method": "tools/list", "params": {"_meta": meta()}})
        record("invalid bearer -> 401", r.status_code == 401, str(r.status_code))

        r = await raw(http, headers=modern_headers("tools/call", "other_tool"),
                      body={"jsonrpc": "2.0", "id": 7, "method": "tools/call",
                            "params": {"name": "web_search", "arguments": {"query": "x"}, "_meta": meta()}})
        record("Mcp-Name/body mismatch -> 400 HeaderMismatch (SDK)", r.status_code == 400 and rpc_code(r) == -32020, f"{r.status_code} {rpc_code(r)}")

        r = await raw(http, headers={**modern_headers("tools/list"), "Mcp-Session-Id": "forged"},
                      body={"jsonrpc": "2.0", "id": 8, "method": "tools/list", "params": {"_meta": meta()}})
        record("forged Mcp-Session-Id ignored, not echoed", r.status_code == 200 and "mcp-session-id" not in r.headers, str(r.status_code))

    # Legacy SDK client must not connect.
    try:
        async with httpx2.AsyncClient(verify=trusted(), headers={"Authorization": f"Bearer {TOKEN}"}) as http:
            async with Client(streamable_http_client(URL, http_client=http, terminate_on_close=False), mode="legacy") as c:
                await c.list_tools()
        record("legacy-mode SDK client refused", False, "connected")
    except Exception as e:  # noqa: BLE001
        record("legacy-mode SDK client refused", True, type(e).__name__)

    # TLS negative paths.
    for label, ctx_factory, host in [("untrusted CA", ssl.create_default_context, "localhost"),
                                     ("wrong hostname", trusted, "127.0.0.1")]:
        try:
            async with httpx2.AsyncClient(verify=ctx_factory()) as http:
                await http.post(f"https://{host}:{PORT}/mcp")
            record(f"TLS {label} rejected", False, "accepted")
        except Exception as e:  # noqa: BLE001
            record(f"TLS {label} rejected", True, type(e).__name__)

    old = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT); old.load_verify_locations(CA)
    old.minimum_version = old.maximum_version = ssl.TLSVersion.TLSv1_1
    try:
        with socket.create_connection(("127.0.0.1", PORT), timeout=3) as s, old.wrap_socket(s, server_hostname="localhost"):
            pass
        record("TLS 1.1 refused", False, "handshake ok")
    except (ssl.SSLError, OSError) as e:
        record("TLS 1.1 refused", True, type(e).__name__)

    with socket.create_connection(("127.0.0.1", PORT), timeout=3) as s:
        s.sendall(b"POST /mcp HTTP/1.1\r\nHost: localhost\r\nContent-Length: 0\r\n\r\n")
        s.settimeout(3)
        try:
            reply = s.recv(64)
        except OSError:
            reply = b""
    record("plaintext HTTP gets no HTTP response", not reply.startswith(b"HTTP/"), repr(reply[:20]))

    with socket.create_connection(("127.0.0.1", PORT), timeout=3) as s, trusted().wrap_socket(s, server_hostname="localhost") as t:
        record("negotiated TLS version", t.version() == "TLSv1.3", t.version())

    failed = [r for r in results if not r[1]]
    print(f"SUMMARY {len(results) - len(failed)}/{len(results)} passed")
    sys.exit(1 if failed else 0)


anyio.run(main)
