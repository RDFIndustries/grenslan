#!/bin/sh
# Install the pinned SearXNG into PREFIX as a separately managed component:
# its complete source at the pinned commit in PREFIX/src (kept, as the
# corresponding source), and its locked, hash-verified dependencies in its
# own virtual environment, PREFIX/venv. Nothing is shared with Grenslan's
# environment. Runs at image build or development setup time only.
#
# Usage: install.sh PREFIX [PYTHON]
#
# Offline installation: set SEARXNG_GIT_URL to a local git repository that
# contains the pinned commit (the commit is still verified), and set
# PIP_NO_INDEX=1 and PIP_FIND_LINKS=DIR to install the locked wheels from a
# local directory (their hashes are still verified).
set -eu
prefix=$1
python=${2:-python3.12}
here=$(cd "$(dirname "$0")" && pwd)
repository=$(sed -n 's/^repository=//p' "$here/SOURCE")
commit=$(sed -n 's/^commit=//p' "$here/SOURCE")
version=$(sed -n 's/^version=//p' "$here/SOURCE")
fetch_from=${SEARXNG_GIT_URL:-$repository}

if [ -e "$prefix" ]; then
    echo "error: $prefix already exists" >&2
    exit 1
fi
mkdir -p "$prefix/src"
git -C "$prefix/src" init -q
git -C "$prefix/src" fetch -q --depth 1 "$fetch_from" "$commit"
git -C "$prefix/src" checkout -q --detach FETCH_HEAD
actual=$(git -C "$prefix/src" rev-parse HEAD)
if [ "$actual" != "$commit" ]; then
    echo "error: fetched commit $actual, expected $commit" >&2
    exit 1
fi
# SearXNG reads its version from git or from this generated module; write the
# module so that the installed copy does not depend on git at run time.
cat > "$prefix/src/searx/version_frozen.py" <<PY
# SPDX-License-Identifier: AGPL-3.0-or-later
# pylint: disable=missing-module-docstring
# this file is generated automatically by searx/version.py

VERSION_STRING = "$version"
VERSION_TAG = "$version"
DOCKER_TAG = "$(echo "$version" | tr + -)"
GIT_URL = "$repository"
GIT_BRANCH = "master"
PY
"$python" -m venv "$prefix/venv"
"$prefix/venv/bin/python" -m pip install -q --disable-pip-version-check --no-deps --require-hashes \
    -r "$here/requirements.lock"
cp "$here/SOURCE" "$prefix/SOURCE"
echo "installed SearXNG $version at $prefix"
