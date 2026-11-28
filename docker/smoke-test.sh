#!/usr/bin/env bash
# Foundation container smoke test: runs a built grenslan image on a private,
# internal Docker network with an untrusted probe container, and checks
# isolation of the bundled SearXNG endpoint (PRP-001 F05, F-G17).
#
# Usage: docker/smoke-test.sh [IMAGE]    (default grenslan:dev)
#
# Creates a temporary directory with throwaway TLS material and credentials,
# a Docker network named grenslan-smoke-<random> and containers with the same
# suffix, and removes them all on exit. Prints PASS or FAIL for each check
# and exits non-zero if any check fails. Needs no network access: the
# internal network has no route out, so the engines' upstream requests fail,
# which the egress check relies on.
set -euo pipefail

image=${1:-grenslan:dev}
here=$(cd "$(dirname "$0")" && pwd)
suffix=$(head -c 6 /dev/urandom | od -An -tx1 | tr -d ' \n')
network=grenslan-smoke-$suffix
server=grenslan-smoke-server-$suffix
work=$(mktemp -d)
failures=0

cleanup() {
    docker rm -f "$server" "$server-default" >/dev/null 2>&1 || true
    docker network rm "$network" >/dev/null 2>&1 || true
    rm -rf "$work"
}
trap cleanup EXIT

result() {
    if [[ $1 == 0 ]]; then echo "PASS  $2"; else echo "FAIL  $2"; failures=$((failures + 1)); fi
}

wait_for_provider() {
    for _ in $(seq 1 60); do
        if docker logs "$1" 2>&1 | grep -q -E "provider searxng_bundled: initializing -> (ready|unavailable)"; then
            return 0
        fi
        sleep 1
    done
    return 1
}

# Throwaway material, created with the image itself.
mkdir -p "$work/etc" "$work/secrets" "$work/tls"
docker run --rm --network none --user "$(id -u):$(id -g)" -v "$work/tls:/out" --entrypoint grenslan "$image" \
    tls new --name grenslan --name localhost --days 2 --ca-days 3 --output-dir /out/issued >/dev/null
docker run --rm --network none --entrypoint grenslan "$image" credential new > "$work/credential.txt"
token=$(sed -n 's/^token: //p' "$work/credential.txt")
token_sha=$(sed -n 's/^token_sha256: //p' "$work/credential.txt")
cp "$work/tls/issued/server.pem" "$work/secrets/grenslan_tls_cert.pem"
cp "$work/tls/issued/server.key" "$work/secrets/grenslan_tls_key.pem"
cp "$work/tls/issued/ca.pem" "$work/ca.pem"
cat > "$work/etc/service.yaml" <<EOF
config_version: "1.0"
listen: {host: 0.0.0.0, port: 8443}
tls:
  certificate_file: /run/secrets/grenslan_tls_cert.pem
  private_key_file: /run/secrets/grenslan_tls_key.pem
ingress:
  allowed_hosts: [grenslan]
  allowed_origins: []
  max_request_bytes: 1048576
  argument_limits: {max_string_chars: 65536, max_array_items: 1000, max_depth: 32}
tools: {profile: full}
credentials:
  smoke:
    application_id: smoke
    token_sha256: "$token_sha"
    permissions: [web_search, image_search, capabilities_get]
    delegation: false
security_events: {max_events_per_window: 100, window_seconds: 60}
EOF
cp "$here/../examples/providers.yaml" "$work/etc/providers.yaml"
chmod 0755 "$work" "$work/etc" "$work/secrets"
chmod 0644 "$work"/etc/* "$work"/secrets/* "$work/ca.pem"

docker network create --internal "$network" >/dev/null
run_server() {
    docker run -d --name "$1" --hostname grenslan --network "$network" --network-alias "$2" \
        --read-only --tmpfs /tmp:rw,nosuid,nodev,size=64m --cap-drop ALL --security-opt no-new-privileges \
        -v "$work/etc:/etc/grenslan:ro" -v "$work/secrets:/run/secrets:ro" "${@:3}" "$image" >/dev/null
}
probe() {
    docker run --rm --network "$network" --user 20000:20000 --cap-drop ALL --security-opt no-new-privileges \
        -v "$work/ca.pem:/ca.pem:ro" -e TOKEN="$token" --entrypoint python "$image" -I -c "$1"
}

# The checks report failures instead of stopping the script.
set +e

# 1. Non-root image.
user=$(docker image inspect "$image" --format '{{.Config.User}}')
[[ "$user" == "10001:10001" ]]; result $? "image runs as non-root user ($user)"

# 2. Without Grenslan's profile, bundled SearXNG fails closed.
run_server "$server-default" grenslan-default
wait_for_provider "$server-default"
docker logs "$server-default" 2>&1 | grep -q "provider searxng_bundled: initializing -> unavailable"
result $? "with Docker's default seccomp profile, bundled SearXNG is unavailable (fails closed)"
docker rm -f "$server-default" >/dev/null

# 3. With Grenslan's profile, it is ready.
run_server "$server" grenslan --security-opt "seccomp=$here/seccomp.json"
wait_for_provider "$server"
docker logs "$server" 2>&1 | grep -q "provider searxng_bundled: initializing -> ready"
result $? "with Grenslan's seccomp profile, bundled SearXNG is ready"
sleep 2

# 4. Configured ingress works over verified TLS; it requires a credential.
probe '
import json, os, ssl, http.client
context = ssl.create_default_context(cafile="/ca.pem")
def call(headers):
    connection = http.client.HTTPSConnection("grenslan", 8443, context=context, timeout=10)
    connection.request("POST", "/api/v1/tools/capabilities_get", body="{}", headers={"Content-Type": "application/json", **headers})
    response = connection.getresponse()
    return response.status, response.read()
status, _ = call({})
assert status == 401, status
status, body = call({"Authorization": "Bearer " + os.environ["TOKEN"]})
assert status == 200 and json.loads(body)["status"] == "completed", (status, body[:200])
'
result $? "probe reaches HTTPS ingress with a verified certificate; 401 without a token, 200 with one"

# 5. A full TCP port scan from the probe finds only the ingress port.
open_ports=$(probe '
import asyncio, socket
address = socket.gethostbyname("grenslan")
async def check(port, limit):
    async with limit:
        try:
            _, writer = await asyncio.wait_for(asyncio.open_connection(address, port), 2)
        except (OSError, asyncio.TimeoutError):
            return None
        writer.close()
        return port
async def main():
    limit = asyncio.Semaphore(512)
    found = await asyncio.gather(*(check(port, limit) for port in range(1, 65536)))
    print(" ".join(str(port) for port in found if port))
asyncio.run(main())
')
[[ "$open_ports" == "8443" ]]; result $? "full TCP scan from the probe finds only port 8443 open (found: ${open_ports:-none})"

# 6. Inside the container, the only listening socket is the ingress port. On a
# user-defined network, Docker's embedded DNS resolver also listens inside each
# container's namespace on 127.0.0.11; that listener belongs to dockerd and is
# reported separately.
listeners=$(docker exec "$server" python -I -c '
ports, docker_dns = set(), set()
for name in ("/proc/net/tcp", "/proc/net/tcp6"):
    for line in open(name).read().splitlines()[1:]:
        fields = line.split()
        if fields[3] == "0A":
            address, port = fields[1].rsplit(":", 1)
            (docker_dns if address == "0B00007F" else ports).add(int(port, 16))
print(" ".join(map(str, sorted(ports))), "|", " ".join(map(str, sorted(docker_dns))))
')
[[ "${listeners%% |*}" == "8443" ]]
result $? "the container's network namespace listens only on 8443 (found: ${listeners%% |*}; Docker DNS on 127.0.0.11: ${listeners##*| })"

# 7. SearXNG and the egress proxy are reachable only through owner-only Unix sockets.
docker exec --user 20000:20000 "$server" python -I -c '
import glob, socket
paths = glob.glob("/tmp/grenslan-searxng-*/*.sock")
assert not paths, paths  # the runtime directory itself is not even listable
' 2>/dev/null
listing=$?
docker exec --user 20000:20000 "$server" python -I -c '
import os, socket, sys
runtime = [name for name in os.listdir("/tmp") if name.startswith("grenslan-searxng-")]
assert len(runtime) == 1
for name in ("searxng.sock", "egress.sock"):
    client = socket.socket(socket.AF_UNIX)
    try:
        client.connect(f"/tmp/{runtime[0]}/{name}")
    except PermissionError:
        continue
    sys.exit(f"{name} accepted a connection from another user")
'
connecting=$?
[[ $listing == 0 && $connecting == 0 ]]; result $? "another user in the container cannot reach SearXNG's or the proxy's socket"

# 8. A confined process has only loopback and no route out.
docker exec "$server" python -I -m grenslan.searxng.confine --relay-port 3128 --egress-socket /tmp/none.sock -- \
    python -I -c '
import socket
names = sorted(name for _, name in socket.if_nameindex())
assert names == ["lo"], names
for address in ("1.1.1.1", "172.17.0.1", "169.254.169.254"):
    try:
        socket.create_connection((address, 443), timeout=3)
    except OSError as error:
        assert error.errno in (101, 113), error  # ENETUNREACH or EHOSTUNREACH
    else:
        raise SystemExit(f"connected to {address}")
'
result $? "a confined process sees only loopback and cannot reach outside addresses"

# 9. SearXNG works over its socket, and its egress proxy enforces the network scope.
docker exec "$server" python -I -c '
import glob, httpcore2, json
socket_path = glob.glob("/tmp/grenslan-searxng-*/searxng.sock")[0]
with httpcore2.ConnectionPool(uds=socket_path) as pool:
    response = pool.request("POST", "http://searxng/search", headers={"Content-Type": "application/x-www-form-urlencoded"},
        content=b"q=grenslan+smoke&format=json&engines=wikipedia,duckduckgo,brave&pageno=1")
body = json.loads(response.content)
assert response.status == 200, response.status
assert not body["results"], body["results"][:1]
assert {name for name, _ in body["unresponsive_engines"]} == {"wikipedia", "duckduckgo", "brave"}, body["unresponsive_engines"]
'
result $? "a search reaches SearXNG over its socket; every engine fails, since the network has no route out"
docker exec "$server" python -I -c '
import glob, socket
egress = glob.glob("/tmp/grenslan-searxng-*/egress.sock")[0]
def tunnel(authority):
    client = socket.socket(socket.AF_UNIX)
    client.settimeout(20)
    client.connect(egress)
    client.sendall(f"CONNECT {authority} HTTP/1.1\r\nHost: {authority}\r\n\r\n".encode())
    status = client.recv(4096).split(b" ", 2)[1]
    client.close()
    return int(status)
results = {authority: tunnel(authority) for authority in (
    "example.com:443", "169.254.169.254:443", "127.0.0.1:8443", "grenslan:8443", "en.wikipedia.org:80", "en.wikipedia.org:443")}
expected = {"example.com:443": 403, "169.254.169.254:443": 403, "127.0.0.1:8443": 403, "grenslan:8443": 403,
    "en.wikipedia.org:80": 403, "en.wikipedia.org:443": 502}
assert results == expected, results
'
result $? "the egress proxy refuses unlisted hosts, metadata, loopback and Grenslan itself (403); a listed host passes policy and fails only for lack of a route (502)"
docker exec "$server" python -I -c '
import socket
try:
    socket.getaddrinfo("en.wikipedia.org", 443)
except OSError:
    pass
else:
    raise SystemExit("the internal network resolved an external name")
'
result $? "the smoke network gives no name resolution or route out"

# 10. No Docker socket or host control interface inside the container.
docker exec "$server" sh -c 'test ! -e /var/run/docker.sock && test ! -e /run/docker.sock'
result $? "no Docker socket inside the container"

# 11. A stop is clean: SearXNG is stopped, its runtime directory removed, and the service exits 0.
start=$(date +%s)
docker stop -t 30 "$server" >/dev/null
elapsed=$(( $(date +%s) - start ))
status=$(docker inspect "$server" --format '{{.State.ExitCode}}')
logs=$(docker logs "$server" 2>&1)
grep -q "provider searxng_bundled: stopping -> stopped" <<< "$logs" \
    && ! grep -q -E "provider searxng_bundled: shutdown (failed|exceeded)" <<< "$logs"
stopped=$?
[[ "$status" == 0 && $stopped == 0 && $elapsed -lt 30 ]]
result $? "docker stop shuts SearXNG down and exits 0 in ${elapsed}s (exit status $status)"

if (( failures > 0 )); then
    echo "$failures check(s) failed"
    exit 1
fi
echo "all checks passed"
