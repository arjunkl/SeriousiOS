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

find_tool() {
  local requested=$1
  local fallback=$2
  if [[ -n "$requested" && -x "$requested" ]]; then
    printf '%s\n' "$requested"
  elif command -v "$fallback" >/dev/null 2>&1; then
    command -v "$fallback"
  else
    echo "required tool not found: $fallback" >&2
    exit 1
  fi
}

FLEX_BIN=$(find_tool "${FLEX_BIN:-}" flex)
BISON_BIN=$(find_tool "${BISON_BIN:-}" bison)

copy_and_generate_parser_pair() {
  local source_root=$1
  local work_root=$2
  local parser=$3
  local scanner=$4
  local parser_dir scanner_dir
  parser_dir=$(dirname "$parser")
  scanner_dir=$(dirname "$scanner")

  mkdir -p "$work_root/$parser_dir" "$work_root/$scanner_dir"
  cp "$source_root/${parser}.y" "$work_root/${parser}.y"
  cp "$source_root/${scanner}.l" "$work_root/${scanner}.l"

  pushd "$work_root" >/dev/null
  "$FLEX_BIN" -o"${scanner}.cpp" "${scanner}.l"
  "$BISON_BIN" -o"${parser}.cpp" "${parser}.y" -d
  if [[ -f "${parser}.hpp" ]]; then
    cp "${parser}.hpp" "${parser}.h"
  elif [[ ! -f "${parser}.h" ]]; then
    echo "missing generated parser header for ${parser}" >&2
    exit 1
  fi
  popd >/dev/null
}

generate_encounter() {
  local encounter=$1
  local source_root="$UPSTREAM/Sam${encounter}/Sources"
  local tool="$TOOLS/${encounter}/bin/ecc-se"
  local work="$OUTPUT/${encounter}"
  local list="$work/entity-inputs.txt"

  test -x "$tool"
  mkdir -p "$work"

  # Generate every entity source present at the pinned revision. This includes
  # standard and alternate PlayerWeapons variants; the later target-selection
  # stage decides which generated units enter the iOS build.
  find "$source_root/Engine/Classes" \
       "$source_root/Entities" \
       "$source_root/EntitiesMP" \
       -type f -name '*.es' -print \
    | LC_ALL=C sort > "$list"

  local count=0
  while IFS= read -r entity; do
    local relative=${entity#"$source_root/"}
    mkdir -p "$work/$(dirname "$relative")"
    cp "$entity" "$work/$relative"
    pushd "$work" >/dev/null
    "$tool" "$relative"
    popd >/dev/null
    count=$((count + 1))
  done < "$list"

  copy_and_generate_parser_pair "$source_root" "$work" \
    Engine/Base/Parser Engine/Base/Scanner
  copy_and_generate_parser_pair "$source_root" "$work" \
    Engine/Ska/smcPars Engine/Ska/smcScan

  find "$work" -type f \
    \( -name '*.cpp' -o -name '*.h' -o -name '*.hpp' \) \
    -print0 | LC_ALL=C sort -z | xargs -0 shasum -a 256 > "$work/generated.sha256"

  local generated_count
  generated_count=$(wc -l < "$work/generated.sha256" | tr -d ' ')
  printf '%s entities=%s generated_files=%s\n' "$encounter" "$count" "$generated_count" \
    | tee "$work/summary.txt"
}

generate_encounter TFE
generate_encounter TSE

{
  echo "SeriousSamClassic=$(git -C "$UPSTREAM" rev-parse HEAD)"
  cat "$OUTPUT/TFE/summary.txt"
  cat "$OUTPUT/TSE/summary.txt"
  echo "flex=$($FLEX_BIN --version | head -n 1)"
  echo "bison=$($BISON_BIN --version | head -n 1)"
} | tee "$OUTPUT/full-generation-manifest.txt"
