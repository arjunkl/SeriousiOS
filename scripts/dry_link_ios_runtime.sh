#!/usr/bin/env bash
set -euo pipefail

if [[ $# -ne 5 ]]; then
  echo "usage: $0 <CMake build dir> <TFE|TSE> <entity registry.cpp> <runtime registry.cpp> <evidence dir>" >&2
  exit 64
fi

BUILD_DIR=$(cd "$1" && pwd)
ENCOUNTER=$2
ENTITY_REGISTRY=$(cd "$(dirname "$3")" && pwd)/$(basename "$3")
RUNTIME_REGISTRY=$(cd "$(dirname "$4")" && pwd)/$(basename "$4")
EVIDENCE=$5
mkdir -p "$EVIDENCE"
EVIDENCE=$(cd "$EVIDENCE" && pwd)
REPOSITORY_ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
PLATFORM_ROOT="$REPOSITORY_ROOT/Sources/Platform/iOS"

case "$ENCOUNTER" in
  TFE)
    define=SERIOUSIOS_TFE
    archives=(engine_safemath Engine Game Shaders Entities)
    ;;
  TSE)
    define=SERIOUSIOS_TSE
    archives=(engine_safemathMP EngineMP GameMP ShadersMP EntitiesMP)
    ;;
  *)
    echo "encounter must be TFE or TSE" >&2
    exit 64
    ;;
esac

SDK_PATH=$(xcrun --sdk iphoneos --show-sdk-path)
CXX=$(xcrun --sdk iphoneos --find clang++)
OBJECT_DIR="$EVIDENCE/${ENCOUNTER}-objects"
mkdir -p "$OBJECT_DIR"

common_compile=(
  -target arm64-apple-ios15.0
  -isysroot "$SDK_PATH"
  -std=c++17
  -fms-extensions
  -Wall -Wextra -Werror
  -Wno-unused-parameter
  -I "$PLATFORM_ROOT"
)

"$CXX" "${common_compile[@]}" -D"$define" \
  -c "$REPOSITORY_ROOT/Tests/IOSDryLinkMain.cpp" \
  -o "$OBJECT_DIR/main.o"
"$CXX" "${common_compile[@]}" \
  -c "$ENTITY_REGISTRY" \
  -o "$OBJECT_DIR/entity-registry.o"
"$CXX" "${common_compile[@]}" \
  -c "$RUNTIME_REGISTRY" \
  -o "$OBJECT_DIR/runtime-registry.o"
"$CXX" "${common_compile[@]}" \
  -c "$PLATFORM_ROOT/SeriousIOSHostGlobals.cpp" \
  -o "$OBJECT_DIR/host-globals.o"

archive_arguments=()
for target in "${archives[@]}"; do
  archive="$BUILD_DIR/Release-iphoneos/lib${target}.a"
  if [[ ! -s "$archive" ]]; then
    echo "missing archive: $archive" >&2
    exit 1
  fi
  archive_arguments+=("-Wl,-force_load,$archive")
done

output="$EVIDENCE/SeriousIOS-${ENCOUNTER}-DryLink"
log="$EVIDENCE/${ENCOUNTER}-dry-link.log"
command_file="$EVIDENCE/${ENCOUNTER}-dry-link-command.txt"

link_objects=(
  "$OBJECT_DIR/main.o"
  "$OBJECT_DIR/entity-registry.o"
  "$OBJECT_DIR/runtime-registry.o"
  "$OBJECT_DIR/host-globals.o"
)

printf '%q ' "$CXX" \
  -target arm64-apple-ios15.0 \
  -isysroot "$SDK_PATH" \
  "${link_objects[@]}" \
  "${archive_arguments[@]}" \
  -Wl,-dead_strip \
  -Wl,-undefined,error \
  -framework Foundation \
  -framework UIKit \
  -framework CoreFoundation \
  -framework CoreGraphics \
  -framework QuartzCore \
  -framework OpenGLES \
  -framework AudioToolbox \
  -framework AVFoundation \
  -framework CoreMotion \
  -framework GameController \
  -framework Security \
  -framework SystemConfiguration \
  -o "$output" > "$command_file"
printf '\n' >> "$command_file"

set +e
"$CXX" \
  -target arm64-apple-ios15.0 \
  -isysroot "$SDK_PATH" \
  "${link_objects[@]}" \
  "${archive_arguments[@]}" \
  -Wl,-dead_strip \
  -Wl,-undefined,error \
  -framework Foundation \
  -framework UIKit \
  -framework CoreFoundation \
  -framework CoreGraphics \
  -framework QuartzCore \
  -framework OpenGLES \
  -framework AudioToolbox \
  -framework AVFoundation \
  -framework CoreMotion \
  -framework GameController \
  -framework Security \
  -framework SystemConfiguration \
  -o "$output" \
  2>&1 | tee "$log"
status=${PIPESTATUS[0]}
set -e

echo "$status" > "$EVIDENCE/${ENCOUNTER}-dry-link-status.txt"
if [[ $status -eq 0 ]]; then
  file "$output" | tee "$EVIDENCE/${ENCOUNTER}-dry-link-product.txt"
  shasum -a 256 "$output" | tee -a "$EVIDENCE/${ENCOUNTER}-dry-link-product.txt"
fi

exit "$status"
