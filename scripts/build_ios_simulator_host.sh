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
BUILD_IDENTIFIER=${GITHUB_SHA:-local}

case "$ENCOUNTER" in
  TFE)
    define=SERIOUSIOS_TFE
    display_name="Serious Sam: The First Encounter"
    bundle_id="com.arjunkl.seriousios.simulator.tfe"
    archives=(engine_safemath Engine Game Shaders Entities SeriousIOSApplication)
    ;;
  TSE)
    define=SERIOUSIOS_TSE
    display_name="Serious Sam: The Second Encounter"
    bundle_id="com.arjunkl.seriousios.simulator.tse"
    archives=(engine_safemathMP EngineMP GameMP ShadersMP EntitiesMP SeriousIOSApplicationMP)
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

DIAGNOSTIC_APP_SOURCE="$OBJECT_DIR/SeriousIOSHost-Diagnostic.mm"
cp "$APP_SOURCE" "$DIAGNOSTIC_APP_SOURCE"
python3 "$REPOSITORY_ROOT/scripts/transform_ios_host_for_diagnostics.py" \
  "$DIAGNOSTIC_APP_SOURCE" \
  --build-id "$BUILD_IDENTIFIER" \
  2>&1 | tee "$EVIDENCE/${ENCOUNTER}-diagnostic-host-transform.log"
python3 "$REPOSITORY_ROOT/scripts/inject_ios_menu_touch.py" \
  "$DIAGNOSTIC_APP_SOURCE" \
  2>&1 | tee "$EVIDENCE/${ENCOUNTER}-menu-touch-transform.log"
python3 "$REPOSITORY_ROOT/scripts/inject_ios_analog_touch.py" \
  --self-test \
  "$DIAGNOSTIC_APP_SOURCE" \
  2>&1 | tee "$EVIDENCE/${ENCOUNTER}-analog-touch-transform.log"
python3 "$REPOSITORY_ROOT/scripts/inject_ios_netricsa_touch.py" \
  --self-test \
  "$DIAGNOSTIC_APP_SOURCE" \
  2>&1 | tee "$EVIDENCE/${ENCOUNTER}-netricsa-touch-transform.log"
python3 "$REPOSITORY_ROOT/scripts/inject_ios_touch_customization.py" \
  --self-test \
  "$DIAGNOSTIC_APP_SOURCE" \
  2>&1 | tee "$EVIDENCE/${ENCOUNTER}-touch-customization-transform.log"
python3 "$REPOSITORY_ROOT/scripts/inject_ios_touch_input_fixes.py" \
  --self-test \
  "$DIAGNOSTIC_APP_SOURCE" \
  2>&1 | tee "$EVIDENCE/${ENCOUNTER}-touch-input-fixes-transform.log"

grep -Fq 'SeriousIOS_ApplicationComputerActive()' "$DIAGNOSTIC_APP_SOURCE"
grep -Fq 'SeriousIOS_SetVirtualMovement((float)forward, (float)right)' "$DIAGNOSTIC_APP_SOURCE"
grep -Fq 'radialDeadZone = 0.16' "$DIAGNOSTIC_APP_SOURCE"
grep -Fq '#import <CoreMotion/CoreMotion.h>' "$DIAGNOSTIC_APP_SOURCE"
grep -Fq 'controls_editor_opened' "$DIAGNOSTIC_APP_SOURCE"
grep -Fq 'SeriousIOS.GyroSensitivity' "$DIAGNOSTIC_APP_SOURCE"
grep -Fq 'SeriousIOS.TouchAimSensitivity' "$DIAGNOSTIC_APP_SOURCE"
grep -Fq 'pauseButtonLongPressed:' "$DIAGNOSTIC_APP_SOURCE"
grep -Fq 'symbol:@"scope"' "$DIAGNOSTIC_APP_SOURCE"
grep -Fq 'button.exclusiveTouch = NO;' "$DIAGNOSTIC_APP_SOURCE"
grep -Fq 'const double accumulatedX = -yawRate * deltaTime' "$DIAGNOSTIC_APP_SOURCE"
grep -Fq 'const double accumulatedY = -pitchRate * deltaTime' "$DIAGNOSTIC_APP_SOURCE"
grep -Fq 'axis_sign=-1' "$DIAGNOSTIC_APP_SOURCE"
if grep -Eq "SeriousIOS_QueueSDLKey\('[wsad]'" "$DIAGNOSTIC_APP_SOURCE"; then
  echo "generated simulator host still contains digital WASD movement" >&2
  exit 1
fi
if grep -Fq 'button.exclusiveTouch = YES;' "$DIAGNOSTIC_APP_SOURCE"; then
  echo "generated simulator host still prevents simultaneous gameplay touches" >&2
  exit 1
fi
if grep -Fq 'setTitle:(computerActive ? @"EXIT" : @"PAUSE")' "$DIAGNOSTIC_APP_SOURCE"; then
  echo "generated simulator host still contains text gameplay placeholders" >&2
  exit 1
fi

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
  -c "$DIAGNOSTIC_APP_SOURCE" \
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
  <key>NSMotionUsageDescription</key>
  <string>SeriousiOS uses device motion only for optional gyro aiming.</string>
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
test -n "$(plutil -extract NSMotionUsageDescription raw -o - "$APP_DIR/Info.plist")"
codesign --force --sign - "$APP_DIR"
file "$APP_DIR/$EXECUTABLE" | tee "$EVIDENCE/${ENCOUNTER}-simulator-product.txt"
shasum -a 256 "$APP_DIR/$EXECUTABLE" | tee -a "$EVIDENCE/${ENCOUNTER}-simulator-product.txt"
echo "$bundle_id" > "$EVIDENCE/${ENCOUNTER}-simulator-bundle-id.txt"
