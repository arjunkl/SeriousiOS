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
APP_SOURCE="$REPOSITORY_ROOT/Sources/App/iOS/SeriousIOSHost.mm"

case "$ENCOUNTER" in
  TFE)
    define=SERIOUSIOS_TFE
    display_name="Serious Sam: The First Encounter"
    bundle_id="com.arjunkl.seriousios.simulator.tfe"
    archives=(engine_safemath Engine Game Shaders Entities)
    ;;
  TSE)
    define=SERIOUSIOS_TSE
    display_name="Serious Sam: The Second Encounter"
    bundle_id="com.arjunkl.seriousios.simulator.tse"
    archives=(engine_safemathMP EngineMP GameMP ShadersMP EntitiesMP)
    ;;
  *)
    echo "encounter must be TFE or TSE" >&2
    exit 64
    ;;
esac

SDK_PATH=$(xcrun --sdk iphonesimulator --show-sdk-path)
SDK_VERSION=$(xcrun --sdk iphonesimulator --show-sdk-version)
CXX=$(xcrun --sdk iphonesimulator --find clang++)
TARGET=arm64-apple-ios15.0-simulator
OBJECT_DIR="$EVIDENCE/${ENCOUNTER}-objects"
APP_DIR="$EVIDENCE/SeriousIOS-${ENCOUNTER}-Simulator.app"
EXECUTABLE="SeriousIOS-${ENCOUNTER}"
mkdir -p "$OBJECT_DIR" "$APP_DIR"

common_compile=(
  -target "$TARGET"
  -isysroot "$SDK_PATH"
  -std=c++17
  -fms-extensions
  -Wall -Wextra -Werror
  -Wno-unused-parameter
  -Wno-deprecated-declarations
  -I "$PLATFORM_ROOT"
)

"$CXX" "${common_compile[@]}" \
  -fobjc-arc \
  -D"$define" \
  -x objective-c++ \
  -c "$APP_SOURCE" \
  -o "$OBJECT_DIR/uikit-host.o"
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
  archive=$(find "$BUILD_DIR" -type f -name "lib${target}.a" -print -quit)
  if [[ -z "$archive" || ! -s "$archive" ]]; then
    echo "missing simulator archive: lib${target}.a" >&2
    exit 1
  fi
  archive_arguments+=("-Wl,-force_load,$archive")
done

"$CXX" \
  -target "$TARGET" \
  -isysroot "$SDK_PATH" \
  "$OBJECT_DIR/uikit-host.o" \
  "$OBJECT_DIR/entity-registry.o" \
  "$OBJECT_DIR/runtime-registry.o" \
  "$OBJECT_DIR/host-globals.o" \
  "${archive_arguments[@]}" \
  -Wl,-dead_strip \
  -framework Foundation \
  -framework UIKit \
  -framework UniformTypeIdentifiers \
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
  -o "$APP_DIR/$EXECUTABLE" \
  2>&1 | tee "$EVIDENCE/${ENCOUNTER}-simulator-link.log"

cat > "$APP_DIR/Info.plist" <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>CFBundleDevelopmentRegion</key>
  <string>en</string>
  <key>CFBundleDisplayName</key>
  <string>${display_name}</string>
  <key>CFBundleExecutable</key>
  <string>${EXECUTABLE}</string>
  <key>CFBundleIdentifier</key>
  <string>${bundle_id}</string>
  <key>CFBundleInfoDictionaryVersion</key>
  <string>6.0</string>
  <key>CFBundleName</key>
  <string>SeriousIOS</string>
  <key>CFBundlePackageType</key>
  <string>APPL</string>
  <key>CFBundleShortVersionString</key>
  <string>0.1</string>
  <key>CFBundleVersion</key>
  <string>1</string>
  <key>CFBundleSupportedPlatforms</key>
  <array>
    <string>iPhoneSimulator</string>
  </array>
  <key>DTPlatformName</key>
  <string>iphonesimulator</string>
  <key>DTSDKName</key>
  <string>iphonesimulator${SDK_VERSION}</string>
  <key>MinimumOSVersion</key>
  <string>15.0</string>
  <key>UILaunchScreen</key>
  <dict/>
  <key>UIRequiresFullScreen</key>
  <true/>
  <key>UISupportedInterfaceOrientations</key>
  <array>
    <string>UIInterfaceOrientationLandscapeLeft</string>
    <string>UIInterfaceOrientationLandscapeRight</string>
  </array>
</dict>
</plist>
PLIST

plutil -lint "$APP_DIR/Info.plist" | tee "$EVIDENCE/${ENCOUNTER}-simulator-plist.txt"
codesign --force --sign - "$APP_DIR"
file "$APP_DIR/$EXECUTABLE" | tee "$EVIDENCE/${ENCOUNTER}-simulator-product.txt"
shasum -a 256 "$APP_DIR/$EXECUTABLE" | tee -a "$EVIDENCE/${ENCOUNTER}-simulator-product.txt"
echo "$bundle_id" > "$EVIDENCE/${ENCOUNTER}-simulator-bundle-id.txt"
