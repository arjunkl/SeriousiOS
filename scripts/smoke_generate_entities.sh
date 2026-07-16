#!/usr/bin/env bash
set -euo pipefail

if [[ $# -ne 3 ]]; then
  echo "usage: $0 <SeriousSamClassic checkout> <host tools directory> <output directory>" >&2
  exit 64
fi

UPSTREAM=$(cd "$1" && pwd)
TOOLS=$(cd "$2" && pwd)
OUTPUT=$3
rm -rf "$OUTPUT"
mkdir -p "$OUTPUT"
OUTPUT=$(cd "$OUTPUT" && pwd)

smoke_encounter() {
  local encounter=$1
  local entity_dir=$2
  local source_root="$UPSTREAM/Sam${encounter}/Sources"
  local tool="$TOOLS/${encounter}/bin/ecc-se"
  local work="$OUTPUT/${encounter}"

  test -x "$tool"
  mkdir -p "$work/Engine/Classes" "$work/$entity_dir"

  cp "$source_root/Engine/Classes/BaseEvents.es" "$work/Engine/Classes/"
  cp "$source_root/$entity_dir/Player.es" "$work/$entity_dir/"

  pushd "$work" >/dev/null
  "$tool" Engine/Classes/BaseEvents.es
  "$tool" "$entity_dir/Player.es"
  popd >/dev/null

  for base in "Engine/Classes/BaseEvents" "$entity_dir/Player"; do
    for suffix in .cpp .h _tables.h; do
      test -s "$work/${base}${suffix}"
    done
  done

  find "$work" -type f \( -name '*.cpp' -o -name '*.h' \) -print0 \
    | sort -z \
    | xargs -0 shasum -a 256 > "$work/generated.sha256"
}

smoke_encounter TFE Entities
smoke_encounter TSE EntitiesMP

{
  echo "Generated entity smoke test"
  echo "upstream=$(git -C "$UPSTREAM" rev-parse HEAD)"
  echo ""
  echo "TFE files:"
  cat "$OUTPUT/TFE/generated.sha256"
  echo ""
  echo "TSE files:"
  cat "$OUTPUT/TSE/generated.sha256"
} | tee "$OUTPUT/generation-manifest.txt"
