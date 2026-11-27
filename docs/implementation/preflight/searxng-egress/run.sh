#!/bin/sh
# Observe SearXNG's outbound connection attempts with no route out. Results: docs/implementation/SEARXNG-EGRESS.md.
# Usage: run.sh <image> <direct|proxied> <output-dir>
set -eu
image=$1; mode=$2; out=$3
here=$(cd "$(dirname "$0")" && pwd)
net=grenslan-probe
docker network rm $net >/dev/null 2>&1 || true
docker network create --internal --subnet 172.31.250.0/24 $net >/dev/null
cleanup() { docker rm -f grenslan-probe-dns grenslan-probe-searxng >/dev/null 2>&1 || true; docker network rm $net >/dev/null 2>&1 || true; }
trap cleanup EXIT
mkdir -p "$out"
docker run -d --name grenslan-probe-dns --network $net --ip 172.31.250.2 \
  -v "$here/probe.py:/probe.py:ro" --entrypoint python3 "$image" -u /probe.py 172.31.250.2 >/dev/null
sleep 2
docker run -d --name grenslan-probe-searxng --network $net --ip 172.31.250.3 --dns 172.31.250.2 \
  -v "$here/settings-$mode.yml:/etc/searxng/settings.yml:ro" "$image" >/dev/null
# Startup window: anything contacted before any search.
sleep 25
echo "{\"kind\":\"marker\",\"phase\":\"search\",\"t\":$(date +%s)}" > "$out/marker.json"
docker exec grenslan-probe-searxng python3 -c '
import json, urllib.request
with urllib.request.urlopen("http://127.0.0.1:8080/search?q=grenslan+egress+probe&format=json", timeout=60) as r:
    body = json.load(r)
print(json.dumps({"results": len(body.get("results", [])), "unresponsive": body.get("unresponsive_engines", [])}))
' > "$out/search.json" 2>&1 || true
sleep 5
docker logs grenslan-probe-dns > "$out/probe.jsonl" 2>&1
docker logs grenslan-probe-searxng > "$out/searxng.log" 2>&1
