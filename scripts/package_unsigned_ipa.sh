#!/usr/bin/env bash
set -euo pipefail

if [[ $# -ne 3 ]]; then
  echo "usage: $0 <TFE|TSE> <app bundle> <output directory>" >&2
  exit 64
fi

ENCOUNTER=$1
APP_INPUT=$2
OUTPUT_DIR=$3

case "$ENCOUNTER" in
  TFE|TSE) ;;
  *)
    echo "encounter must be TFE or TSE" >&2
    exit 64
    ;;
esac

if [[ ! -d "$APP_INPUT" ]]; then
  echo "app bundle does not exist: $APP_INPUT" >&2
  exit 1
fi

APP_INPUT=$(cd "$(dirname "$APP_INPUT")" && pwd)/$(basename "$APP_INPUT")
mkdir -p "$OUTPUT_DIR"
OUTPUT_DIR=$(cd "$OUTPUT_DIR" && pwd)

APP_NAME=$(basename "$APP_INPUT")
EXECUTABLE=$(/usr/libexec/PlistBuddy -c 'Print :CFBundleExecutable' "$APP_INPUT/Info.plist")
BUNDLE_ID=$(/usr/libexec/PlistBuddy -c 'Print :CFBundleIdentifier' "$APP_INPUT/Info.plist")

if [[ ! -s "$APP_INPUT/$EXECUTABLE" ]]; then
  echo "missing executable declared by Info.plist: $APP_INPUT/$EXECUTABLE" >&2
  exit 1
fi

PRODUCT_INFO=$(file "$APP_INPUT/$EXECUTABLE")
if [[ "$PRODUCT_INFO" != *"Mach-O 64-bit executable arm64"* ]]; then
  echo "unexpected executable type: $PRODUCT_INFO" >&2
  exit 1
fi

if codesign -d "$APP_INPUT" >/dev/null 2>&1; then
  echo "expected an unsigned app bundle, but a code signature is present" >&2
  exit 1
fi

STAGE=$(mktemp -d)
trap 'rm -rf "$STAGE"' EXIT
mkdir -p "$STAGE/Payload"
ditto "$APP_INPUT" "$STAGE/Payload/$APP_NAME"

# ProMotion iPhones otherwise keep the application's display-link requests at
# the system-default ceiling. This bundle key permits the adaptive 60-120 Hz
# range requested by the generated UIKit host.
PACKAGED_PLIST="$STAGE/Payload/$APP_NAME/Info.plist"
/usr/libexec/PlistBuddy -c 'Delete :CADisableMinimumFrameDurationOnPhone' "$PACKAGED_PLIST" >/dev/null 2>&1 || true
/usr/libexec/PlistBuddy -c 'Add :CADisableMinimumFrameDurationOnPhone bool true' "$PACKAGED_PLIST"
plutil -lint "$PACKAGED_PLIST" >/dev/null
if [[ "$(plutil -extract CADisableMinimumFrameDurationOnPhone raw -o - "$PACKAGED_PLIST")" != "true" ]]; then
  echo "packaged app does not enable high-refresh display access" >&2
  exit 1
fi

IPA="$OUTPUT_DIR/SeriousIOS-${ENCOUNTER}-unsigned.ipa"
(
  cd "$STAGE"
  /usr/bin/zip -qry "$IPA" Payload
)

unzip -tq "$IPA" >/dev/null
unzip -l "$IPA" > "$OUTPUT_DIR/${ENCOUNTER}-ipa-contents.txt"
shasum -a 256 "$IPA" > "$OUTPUT_DIR/${ENCOUNTER}-ipa.sha256"

cat > "$OUTPUT_DIR/${ENCOUNTER}-ipa-manifest.txt" <<EOF
encounter=$ENCOUNTER
app_name=$APP_NAME
bundle_identifier=$BUNDLE_ID
executable=$EXECUTABLE
signed=false
high_refresh_enabled=true
ipa=$(basename "$IPA")
EOF

printf '%s\n' "$PRODUCT_INFO" >> "$OUTPUT_DIR/${ENCOUNTER}-ipa-manifest.txt"
cat "$OUTPUT_DIR/${ENCOUNTER}-ipa.sha256" >> "$OUTPUT_DIR/${ENCOUNTER}-ipa-manifest.txt"

echo "Packaged unsigned IPA: $IPA"
