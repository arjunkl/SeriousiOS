#!/usr/bin/env bash
set -euo pipefail

if [[ $# -ne 1 ]]; then
  echo "usage: $0 <SeriousSamClassic checkout>" >&2
  exit 64
fi

UPSTREAM=$(cd "$1" && pwd)
REPOSITORY_ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
PATCH_DIR="$REPOSITORY_ROOT/patches"

if [[ -n "$(git -C "$UPSTREAM" status --porcelain)" ]]; then
  echo "upstream checkout must be clean before applying SeriousiOS patches" >&2
  git -C "$UPSTREAM" status --short >&2
  exit 1
fi

patches=()
while IFS= read -r patch; do
  patches+=("$patch")
done < <(find "$PATCH_DIR" -maxdepth 1 -type f -name '*.patch' | LC_ALL=C sort)

if [[ ${#patches[@]} -eq 0 ]]; then
  echo "no patches found in $PATCH_DIR" >&2
  exit 1
fi

for patch in "${patches[@]}"; do
  echo "Applying $(basename "$patch")"
  git -C "$UPSTREAM" apply --check "$patch"
  git -C "$UPSTREAM" apply "$patch"
done

python3 "$REPOSITORY_ROOT/scripts/instrument_ios_display_mode.py" "$UPSTREAM"

git -C "$UPSTREAM" diff --check
{
  echo "base=$(git -C "$UPSTREAM" rev-parse HEAD)"
  for patch in "${patches[@]}"; do
    echo "$(basename "$patch")=$(shasum -a 256 "$patch" | awk '{print $1}')"
  done
  echo "instrument_ios_display_mode.py=$(shasum -a 256 "$REPOSITORY_ROOT/scripts/instrument_ios_display_mode.py" | awk '{print $1}')"
} | tee "$UPSTREAM/seriousios-patches.manifest"
