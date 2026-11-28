#!/usr/bin/env bash
# Download the source archives pinned in sources.lock into OUTDIR and verify
# each SHA-256. Any mismatch or download failure stops the script with a
# non-zero status. A file already present in OUTDIR is kept only if its hash
# matches. On success, OUTDIR also holds SHA256SUMS and a copy of
# sources.lock.
#
# Usage: fetch-sources.sh OUTDIR
set -euo pipefail

if [[ $# -ne 1 ]]; then
    echo "usage: $0 OUTDIR" >&2
    exit 2
fi
here=$(cd "$(dirname "$0")" && pwd)
lock="$here/sources.lock"
out=$1
mkdir -p "$out"

verify() {
    echo "$2  $1" | (cd "$out" && sha256sum --check --quiet --status -)
}

trap 'rm -f "$out/SHA256SUMS.partial" "$out"/*.part' EXIT
: > "$out/SHA256SUMS.partial"
while read -r file sha url; do
    [[ -z "$file" || "$file" == \#* ]] && continue
    if [[ "$file" == */* || "$file" == .* ]]; then
        echo "invalid file name in sources.lock: $file" >&2
        exit 1
    fi
    if [[ -e "$out/$file" ]] && verify "$file" "$sha"; then
        echo "present  $file"
    else
        echo "fetching $file"
        curl --fail --location --silent --show-error --proto '=https' --tlsv1.2 \
            --output "$out/$file.part" "$url"
        mv "$out/$file.part" "$out/$file"
        if ! verify "$file" "$sha"; then
            echo "hash mismatch for $file; removed" >&2
            rm -f "$out/$file"
            exit 1
        fi
    fi
    echo "$sha  $file" >> "$out/SHA256SUMS.partial"
done < "$lock"
mv "$out/SHA256SUMS.partial" "$out/SHA256SUMS"
cp "$lock" "$out/sources.lock"
echo "all archives verified in $out"
