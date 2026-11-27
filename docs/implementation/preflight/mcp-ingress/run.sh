#!/usr/bin/env bash
# Disposable MCP ingress preflight: modern-only protocol gate over direct HTTPS.
# Creates a throwaway private test CA and server certificate in a temporary
# directory, starts spike_server.py on loopback, runs spike_check.py, and
# removes everything on exit. Not Grenslan service code or conformance evidence.
#
# Usage: run.sh <python-with-mcp==2.3.0> [port]
set -euo pipefail

PY=${1:?python interpreter with mcp==2.3.0 installed}
PORT=${2:-18443}
HERE=$(cd "$(dirname "$0")" && pwd)
WORK=$(mktemp -d)
SERVER_PID=""
cleanup() {
  [[ -n "$SERVER_PID" ]] && kill "$SERVER_PID" 2>/dev/null || true
  rm -rf "$WORK"
}
trap cleanup EXIT

cd "$WORK"
openssl req -x509 -newkey rsa:2048 -nodes -days 1 -subj "/CN=Grenslan Preflight Test CA" \
  -addext "basicConstraints=critical,CA:TRUE" -addext "keyUsage=critical,keyCertSign,cRLSign" \
  -keyout ca.key -out ca.pem 2>/dev/null
openssl req -newkey rsa:2048 -nodes -subj "/CN=localhost" -keyout server.key -out server.csr 2>/dev/null
printf 'subjectAltName=DNS:localhost\nextendedKeyUsage=serverAuth\nbasicConstraints=CA:FALSE\n' > ext.cnf
openssl x509 -req -in server.csr -CA ca.pem -CAkey ca.key -CAcreateserial -days 1 \
  -extfile ext.cnf -out server.pem 2>/dev/null
chmod 600 ./*.key

cd "$HERE"
"$PY" spike_server.py "$WORK/server.pem" "$WORK/server.key" "$PORT" > "$WORK/server.log" 2>&1 &
SERVER_PID=$!
for _ in $(seq 1 50); do
  (echo > "/dev/tcp/127.0.0.1/$PORT") 2>/dev/null && break
  sleep 0.2
done
"$PY" -W ignore::DeprecationWarning spike_check.py "$WORK/ca.pem" "$PORT"
