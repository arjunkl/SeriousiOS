#!/usr/bin/env bash
set -euo pipefail

if [[ $# -ne 2 ]]; then
  echo "usage: $0 <SeriousSamClassic checkout> <output directory>" >&2
  exit 64
fi

UPSTREAM=$(cd "$1" && pwd)
OUTPUT=$2
mkdir -p "$OUTPUT"
OUTPUT=$(cd "$OUTPUT" && pwd)
exec > >(tee "$OUTPUT/host-tools-build.log") 2>&1

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
CXX_BIN=$(find_tool "${CXX_BIN:-}" clang++)

printf 'flex:  %s\n' "$FLEX_BIN"
printf 'bison: %s\n' "$BISON_BIN"
printf 'cxx:   %s\n' "$CXX_BIN"

build_ecc() {
  local encounter=$1
  local source_dir="$UPSTREAM/Sam${encounter}/Sources/Ecc"
  local stage_root="$OUTPUT/${encounter}/stage"
  local build_dir="$stage_root/Ecc"
  local install_dir="$OUTPUT/${encounter}/bin"

  echo "::group::Build ecc-se for ${encounter}"
  test -d "$source_dir"
  rm -rf "$stage_root"
  mkdir -p "$build_dir" "$install_dir"

  cp "$source_dir/Main.cpp" \
     "$source_dir/Main.h" \
     "$source_dir/StdH.h" \
     "$source_dir/Parser.y" \
     "$source_dir/Scanner.l" \
     "$build_dir/"

  # Scanner.l intentionally includes Ecc/StdH.h, Ecc/Main.h and Ecc/Parser.h.
  # Generate and compile from the staging root so the host build mirrors the
  # include topology used by the upstream CMake project.
  pushd "$stage_root" >/dev/null
  set -x
  "$FLEX_BIN" -oEcc/Scanner.cpp Ecc/Scanner.l
  "$BISON_BIN" -oEcc/Parser.cpp Ecc/Parser.y -d
  set +x

  # Upstream's CMake pipeline normalizes Bison's C++-named header to Parser.h.
  if [[ -f Ecc/Parser.hpp ]]; then
    cp Ecc/Parser.hpp Ecc/Parser.h
  elif [[ ! -f Ecc/Parser.h ]]; then
    echo "Bison did not produce Ecc/Parser.hpp or Ecc/Parser.h" >&2
    find Ecc -maxdepth 1 -type f -print | sort
    exit 1
  fi

  set -x
  "$CXX_BIN" \
    -std=c++14 \
    -DPLATFORM_UNIX=1 \
    -fno-strict-aliasing \
    -Wno-deprecated-register \
    -Wno-write-strings \
    -I. \
    Ecc/Main.cpp Ecc/Parser.cpp Ecc/Scanner.cpp \
    -o "$install_dir/ecc-se"
  set +x
  popd >/dev/null

  test -x "$install_dir/ecc-se"
  file "$install_dir/ecc-se"
  echo "::endgroup::"
}

build_ecc TFE
build_ecc TSE

cat > "$OUTPUT/host-tools-manifest.txt" <<MANIFEST
SeriousSamClassic=$(git -C "$UPSTREAM" rev-parse HEAD)
flex=$($FLEX_BIN --version | head -n 1)
bison=$($BISON_BIN --version | head -n 1)
compiler=$($CXX_BIN --version | head -n 1)
TFE=$(shasum -a 256 "$OUTPUT/TFE/bin/ecc-se" | awk '{print $1}')
TSE=$(shasum -a 256 "$OUTPUT/TSE/bin/ecc-se" | awk '{print $1}')
MANIFEST

cat "$OUTPUT/host-tools-manifest.txt"
