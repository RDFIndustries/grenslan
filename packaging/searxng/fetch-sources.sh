#!/usr/bin/env bash
# Download the source of every component of the bundled SearXNG into OUTDIR
# and verify each SHA-256. The archives are pinned in sources.lock (native
# libraries), sources-python.lock (Python packages) and sources-crates.lock
# (Granian's Rust crates), and land in OUTDIR/native, OUTDIR/python and
# OUTDIR/crates.
#
# Any mismatch or download failure stops the script with a non-zero status.
# A file already present is kept only if its hash matches. On success, OUTDIR
# also holds SHA256SUMS and copies of the three locks. SearXNG's own source
# is installed with it by install.sh.
#
# Usage: fetch-sources.sh OUTDIR
set -euo pipefail

if [[ $# -ne 1 ]]; then
    echo "usage: $0 OUTDIR" >&2
    exit 2
fi
here=$(cd "$(dirname "$0")" && pwd)
locks=(sources.lock sources-python.lock sources-crates.lock)
out=$1
mkdir -p "$out"/native "$out"/python "$out"/crates

verify() {
    echo "$2  $1" | (cd "$out" && sha256sum --check --quiet --status -)
}

trap 'rm -f "$out/SHA256SUMS.partial" "$out"/*/*.part' EXIT
: > "$out/SHA256SUMS.partial"
count=0
for lock in "${locks[@]}"; do
    while read -r path sha url; do
        [[ -z "$path" || "$path" == \#* ]] && continue
        if [[ ! "$path" =~ ^(native|python|crates)/[A-Za-z0-9_][A-Za-z0-9_.+-]*$ ]]; then
            echo "invalid path in $lock: $path" >&2
            exit 1
        fi
        if [[ ! "$sha" =~ ^[0-9a-f]{64}$ ]]; then
            echo "invalid sha256 in $lock for $path" >&2
            exit 1
        fi
        if [[ -e "$out/$path" ]] && verify "$path" "$sha"; then
            :
        else
            echo "fetching $path"
            curl --fail --location --silent --show-error --proto '=https' --proto-redir '=https' --tlsv1.2 \
                --output "$out/$path.part" "$url"
            mv "$out/$path.part" "$out/$path"
            if ! verify "$path" "$sha"; then
                echo "hash mismatch for $path; removed" >&2
                rm -f "$out/$path"
                exit 1
            fi
        fi
        echo "$sha  $path" >> "$out/SHA256SUMS.partial"
        count=$((count + 1))
    done < "$here/$lock"
    cp "$here/$lock" "$out/$lock"
done
mv "$out/SHA256SUMS.partial" "$out/SHA256SUMS"
echo "$count archives verified in $out"
