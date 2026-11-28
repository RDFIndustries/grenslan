#!/usr/bin/env bash
# Offline installation test (PRP-001 F-G19): installs Grenslan and the bundled
# SearXNG with no network, from approved, hash-verified dependencies
# prepared in advance.
#
# Usage: docker/offline-install-test.sh
#
# 1. Connected: builds the Dockerfile's "tools" stage (base image, git, uv),
#    downloads the hash-locked wheels of both environments into a wheelhouse,
#    builds Grenslan's wheel, and mirrors SearXNG's pinned commit into a
#    local git repository.
# 2. Offline (--network none): installs both environments from those files
#    alone, with every hash and the SearXNG commit still verified. Then checks
#    the notices against what was installed, and that both environments
#    import and run.
#
# Everything is created in a temporary directory and removed on exit.
# Prints PASS or FAIL for each step and exits non-zero on failure.
set -euo pipefail

root=$(cd "$(dirname "$0")/.." && pwd)
work=$(mktemp -d)
tools=grenslan-tools:offline-test
failures=0
trap 'rm -rf "$work"' EXIT

result() {
    if [[ $1 == 0 ]]; then echo "PASS  $2"; else echo "FAIL  $2"; failures=$((failures + 1)); fi
}

as_me=(--user "$(id -u):$(id -g)" -e HOME=/tmp -v "$root:/src:ro" -v "$work:/work" -w /src)

# 1. Connected preparation.
docker build -q --network host -f "$root/docker/Dockerfile" --target tools -t "$tools" "$root" >/dev/null
docker run --rm --network host "${as_me[@]}" "$tools" sh -euc '
    mkdir -p /work/wheels/grenslan /work/wheels/searxng /work/project
    uv export --frozen --no-dev --no-emit-project --format requirements-txt --output-file /work/requirements.txt -q
    python -m pip download -q --disable-pip-version-check --no-deps --require-hashes \
        -r /work/requirements.txt -d /work/wheels/grenslan
    python -m pip download -q --disable-pip-version-check --no-deps --require-hashes \
        -r packaging/searxng/requirements.lock -d /work/wheels/searxng
    cp -r /src/pyproject.toml /src/uv.lock /src/README.md /src/LICENSE /src/src /work/project/
    uv build -q --wheel --out-dir /work/wheels/project /work/project
    commit=$(sed -n "s/^commit=//p" packaging/searxng/SOURCE)
    repository=$(sed -n "s/^repository=//p" packaging/searxng/SOURCE)
    git init -q --bare /work/searxng.git
    git -C /work/searxng.git fetch -q --depth 1 "$repository" "$commit"
    git -C /work/searxng.git update-ref refs/heads/pinned "$commit"
'
echo "prepared: $(ls "$work/wheels/grenslan" | wc -l) Grenslan wheels, $(ls "$work/wheels/searxng" | wc -l) SearXNG wheels, SearXNG mirror"

# The checks report failures instead of stopping the script.
set +e

# 2. Offline installation.
docker run --rm --network none "${as_me[@]}" -e UV_OFFLINE=1 "$tools" sh -euc '
    python -m venv --without-pip /work/opt/venv
    uv pip install -q --python /work/opt/venv/bin/python --offline --no-index --find-links /work/wheels/grenslan \
        --require-hashes --no-deps -r /work/requirements.txt
    uv pip install -q --python /work/opt/venv/bin/python --offline --no-index --no-deps /work/wheels/project/grenslan-*.whl
'
result $? "Grenslan installs with no network from the hash-verified wheelhouse"

docker run --rm --network none "${as_me[@]}" -e SEARXNG_GIT_URL=/work/searxng.git -e PIP_NO_INDEX=1 \
    -e PIP_FIND_LINKS=/work/wheels/searxng "$tools" packaging/searxng/install.sh /work/opt/searxng /usr/local/bin/python3.12 \
    >/dev/null
result $? "SearXNG installs with no network from the local mirror (commit verified) and wheelhouse (hashes verified)"

docker run --rm --network none "${as_me[@]}" "$tools" python3 -I packaging/notices/notices.py check --site-packages \
    /work/opt/venv/lib/python3.12/site-packages /work/opt/searxng/venv/lib/python3.12/site-packages >/dev/null
result $? "the committed notices match the offline-installed packages"

docker run --rm --network none "${as_me[@]}" "$tools" sh -euc '
    /work/opt/venv/bin/grenslan --help >/dev/null
    /work/opt/venv/bin/python -I -c "import grenslan.server.runner, grenslan.searxng.provider"
    /work/opt/searxng/venv/bin/python -I -c "import sys; sys.path.insert(0, \"/work/opt/searxng/src\")
import searx.version, flask, lxml.etree, curl_cffi, msgspec; print(searx.version.VERSION_STRING)" \
        | grep -qx "$(sed -n "s/^version=//p" /work/opt/searxng/SOURCE)"
    /work/opt/searxng/venv/bin/granian --version >/dev/null
'
result $? "both offline installations import and run (Grenslan CLI, SearXNG at its pinned version, Granian)"

docker image rm -f "$tools" >/dev/null 2>&1
if (( failures > 0 )); then
    echo "$failures check(s) failed"
    exit 1
fi
echo "all checks passed"
