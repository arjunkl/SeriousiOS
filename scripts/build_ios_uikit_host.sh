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
    bundle_id="com.arjunkl.seriousios.tfe"
    archives=(engine_safemath Engine Game Shaders Entities SeriousIOSApplication)
    ;;
  TSE)
    define=SERIOUSIOS_TSE
    display_name="Serious Sam: The Second Encounter"
    bundle_id="com.arjunkl.seriousios.tse"
    archives=(engine_safemathMP EngineMP GameMP ShadersMP EntitiesMP SeriousIOSApplicationMP)
    ;;
  *)
    echo "encounter must be TFE or TSE" >&2
    exit 64
    ;;
esac

SDK_PATH=$(xcrun --sdk iphoneos --show-sdk-path)
CXX=$(xcrun --sdk iphoneos --find clang++)
OBJECT_DIR="$EVIDENCE/${ENCOUNTER}-objects"
APP_DIR="$EVIDENCE/SeriousIOS-${ENCOUNTER}.app"
EXECUTABLE="SeriousIOS-${ENCOUNTER}"
mkdir -p "$OBJECT_DIR" "$APP_DIR"

DIAGNOSTIC_APP_SOURCE="$OBJECT_DIR/SeriousIOSHost-Diagnostic.mm"
cp "$APP_SOURCE" "$DIAGNOSTIC_APP_SOURCE"
python3 "$REPOSITORY_ROOT/scripts/transform_ios_host_for_diagnostics.py" \
  "$DIAGNOSTIC_APP_SOURCE" \
  --build-id "$BUILD_IDENTIFIER" \
  2>&1 | tee "$EVIDENCE/${ENCOUNTER}-diagnostic-host-transform.log"
python3 "$REPOSITORY_ROOT/scripts/inject_ios_consolidated_diagnostics.py" \
  --self-test \
  "$DIAGNOSTIC_APP_SOURCE" \
  2>&1 | tee "$EVIDENCE/${ENCOUNTER}-consolidated-diagnostics-transform.log"
python3 "$REPOSITORY_ROOT/scripts/inject_ios_game_data_import.py" \
  --self-test \
  "$DIAGNOSTIC_APP_SOURCE" \
  2>&1 | tee "$EVIDENCE/${ENCOUNTER}-game-data-import-transform.log"
python3 "$REPOSITORY_ROOT/scripts/inject_ios_menu_touch.py" \
  "$DIAGNOSTIC_APP_SOURCE" \
  2>&1 | tee "$EVIDENCE/${ENCOUNTER}-menu-touch-transform.log"
python3 "$REPOSITORY_ROOT/scripts/inject_ios_netricsa_touch.py" \
  --self-test \
  "$DIAGNOSTIC_APP_SOURCE" \
  2>&1 | tee "$EVIDENCE/${ENCOUNTER}-netricsa-touch-transform.log"

grep -Fq '[self hasCompleteGameData]' "$DIAGNOSTIC_APP_SOURCE"
grep -Fq 'Levels/01_Hatshepsut.wld' "$DIAGNOSTIC_APP_SOURCE"
grep -Fq 'gro_copied=%lu levels_copied=%lu' "$DIAGNOSTIC_APP_SOURCE"
grep -Fq 'Import original game data' "$DIAGNOSTIC_APP_SOURCE"
grep -Fq 'SeriousIOS-diagnostics-report.txt' "$DIAGNOSTIC_APP_SOURCE"
grep -Fq 'initWithActivityItems:@[reportURL]' "$DIAGNOSTIC_APP_SOURCE"
grep -Fq 'computerActive ? @"EXIT" : @"PAUSE"' "$DIAGNOSTIC_APP_SOURCE"
grep -Fq 'SeriousIOS_ApplicationComputerActive()' "$DIAGNOSTIC_APP_SOURCE"
if grep -Fq 'initWithActivityItems:files' "$DIAGNOSTIC_APP_SOURCE"; then
  echo "generated host still contains multi-file diagnostic export" >&2
  exit 1
fi
if grep -Fq 'Import original .gro files' "$DIAGNOSTIC_APP_SOURCE"; then
  echo "generated host still contains obsolete importer wording" >&2
  exit 1
fi

common_compile=(
  -target arm64-apple-ios15.0
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
  archive="$BUILD_DIR/Release-iphoneos/lib${target}.a"
  if [[ ! -s "$archive" ]]; then
    echo "missing archive: $archive" >&2
    exit 1
  fi
  archive_arguments+=("-Wl,-force_load,$archive")
done

"$CXX" \
  -target arm64-apple-ios15.0 \
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
  2>&1 | tee "$EVIDENCE/${ENCOUNTER}-uikit-link.log"

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
  <key>LSRequiresIPhoneOS</key>
  <true/>
  <key>LSSupportsOpeningDocumentsInPlace</key>
  <true/>
  <key>MinimumOSVersion</key>
  <string>15.0</string>
  <key>UIFileSharingEnabled</key>
  <true/>
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

plutil -lint "$APP_DIR/Info.plist" | tee "$EVIDENCE/${ENCOUNTER}-plist.txt"
file_sharing=$(plutil -extract UIFileSharingEnabled raw -o - "$APP_DIR/Info.plist")
open_in_place=$(plutil -extract LSSupportsOpeningDocumentsInPlace raw -o - "$APP_DIR/Info.plist")
if [[ "$file_sharing" != "true" || "$open_in_place" != "true" ]]; then
  echo "generated Info.plist does not enable document sharing" >&2
  exit 1
fi
{
  echo "UIFileSharingEnabled=$file_sharing"
  echo "LSSupportsOpeningDocumentsInPlace=$open_in_place"
} | tee "$EVIDENCE/${ENCOUNTER}-file-sharing-plist.txt"

if find "$APP_DIR" -type f \( -iname '*.gro' -o -iname '*.wld' \) -print -quit | grep -q .; then
  echo "copyrighted game data entered the generated app bundle" >&2
  exit 1
fi

file "$APP_DIR/$EXECUTABLE" | tee "$EVIDENCE/${ENCOUNTER}-uikit-product.txt"
shasum -a 256 "$APP_DIR/$EXECUTABLE" | tee -a "$EVIDENCE/${ENCOUNTER}-uikit-product.txt"
otool -L "$APP_DIR/$EXECUTABLE" > "$EVIDENCE/${ENCOUNTER}-uikit-linked-frameworks.txt"

# Produce an unsigned IPA container suitable for downstream signing by AltStore,
# Xcode, or another user-controlled signing tool. No copyrighted data is bundled.
bash "$REPOSITORY_ROOT/scripts/package_unsigned_ipa.sh" \
  "$ENCOUNTER" \
  "$APP_DIR" \
  "$EVIDENCE"

IPA="$EVIDENCE/SeriousIOS-${ENCOUNTER}-unsigned.ipa"
PACKAGED_PLIST="$OBJECT_DIR/Packaged-Info.plist"
unzip -p "$IPA" "Payload/SeriousIOS-${ENCOUNTER}.app/Info.plist" > "$PACKAGED_PLIST"
plutil -lint "$PACKAGED_PLIST" >/dev/null
test "$(plutil -extract UIFileSharingEnabled raw -o - "$PACKAGED_PLIST")" = "true"
test "$(plutil -extract LSSupportsOpeningDocumentsInPlace raw -o - "$PACKAGED_PLIST")" = "true"
if unzip -Z1 "$IPA" | grep -Eiq '\.(gro|wld)$'; then
  echo "copyrighted game data entered the packaged IPA" >&2
  exit 1
fi
