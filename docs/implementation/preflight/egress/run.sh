#!/usr/bin/env bash
# Disposable outbound-enforcement preflight. Creates a throwaway private test CA
# and localhost server certificate in a temporary directory, runs
# egress_spike.py against loopback fixtures, and removes everything on exit.
# Not Grenslan service code or conformance evidence.
#
# Usage: run.sh <python-with-httpcore2>
set -euo pipefail
PY=${1:?python interpreter with httpcore2 and anyio installed}
HERE=$(cd "$(dirname "$0")" && pwd)
WORK=$(mktemp -d)
trap 'rm -rf "$WORK"' EXIT
cd "$WORK"
openssl req -x509 -newkey rsa:2048 -nodes -days 1 -subj "/CN=Grenslan Preflight Test CA" \
  -addext "basicConstraints=critical,CA:TRUE" -addext "keyUsage=critical,keyCertSign,cRLSign" \
  -keyout ca.key -out ca.pem 2>/dev/null
openssl req -newkey rsa:2048 -nodes -subj "/CN=localhost" -keyout server.key -out server.csr 2>/dev/null
printf 'subjectAltName=DNS:localhost\nextendedKeyUsage=serverAuth\nbasicConstraints=CA:FALSE\n' > ext.cnf
openssl x509 -req -in server.csr -CA ca.pem -CAkey ca.key -CAcreateserial -days 1 \
  -extfile ext.cnf -out server.pem 2>/dev/null
chmod 600 ./*.key
"$PY" "$HERE/egress_spike.py" "$WORK/ca.pem" "$WORK/server.pem" "$WORK/server.key"
