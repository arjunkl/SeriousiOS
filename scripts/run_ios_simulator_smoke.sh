#!/usr/bin/env bash
set -euo pipefail

if [[ $# -ne 4 ]]; then
  echo "usage: $0 <TFE|TSE> <app bundle> <simulator udid> <evidence dir>" >&2
  exit 64
fi

ENCOUNTER=$1
APP_DIR=$(cd "$2" && pwd)
UDID=$3
EVIDENCE=$4
mkdir -p "$EVIDENCE"
EVIDENCE=$(cd "$EVIDENCE" && pwd)

case "$ENCOUNTER" in
  TFE|TSE) ;;
  *)
    echo "encounter must be TFE or TSE" >&2
    exit 64
    ;;
esac

BUNDLE_ID=$(/usr/libexec/PlistBuddy -c 'Print :CFBundleIdentifier' "$APP_DIR/Info.plist")
PROCESS_NAME=$(/usr/libexec/PlistBuddy -c 'Print :CFBundleExecutable' "$APP_DIR/Info.plist")

xcrun simctl uninstall "$UDID" "$BUNDLE_ID" >/dev/null 2>&1 || true
xcrun simctl install "$UDID" "$APP_DIR"
DATA_CONTAINER=$(xcrun simctl get_app_container "$UDID" "$BUNDLE_ID" data)
MARKER="$DATA_CONTAINER/tmp/SeriousIOS/$ENCOUNTER/Temporary/core-startup-checkpoint.txt"
rm -f "$MARKER"

launch_output="$EVIDENCE/${ENCOUNTER}-simulator-launch.txt"
SIMCTL_CHILD_OS_ACTIVITY_MODE=disable \
  xcrun simctl launch --terminate-running-process "$UDID" "$BUNDLE_ID" \
  2>&1 | tee "$launch_output"

status=1
for _ in $(seq 1 90); do
  if [[ -f "$MARKER" ]]; then
    cp "$MARKER" "$EVIDENCE/${ENCOUNTER}-core-startup-checkpoint.txt"
    if grep -qx 'state=initialized' "$MARKER"; then
      status=0
      break
    fi
    if grep -qx 'state=failed' "$MARKER"; then
      status=2
      break
    fi
  fi

  if ! xcrun simctl spawn "$UDID" launchctl print "system/com.apple.SpringBoard" >/dev/null 2>&1; then
    status=3
    break
  fi
  sleep 1
done

xcrun simctl spawn "$UDID" log show \
  --style compact \
  --last 5m \
  --predicate "process == '$PROCESS_NAME'" \
  > "$EVIDENCE/${ENCOUNTER}-simulator-log.txt" 2>&1 || true

if [[ -d "$HOME/Library/Logs/DiagnosticReports" ]]; then
  find "$HOME/Library/Logs/DiagnosticReports" \
    -maxdepth 1 \
    -type f \
    -name "${PROCESS_NAME}*" \
    -exec cp {} "$EVIDENCE/" \; || true
fi

xcrun simctl terminate "$UDID" "$BUNDLE_ID" >/dev/null 2>&1 || true

if [[ $status -ne 0 ]]; then
  echo "${ENCOUNTER} simulator core startup checkpoint failed with status ${status}" >&2
  if [[ -f "$MARKER" ]]; then
    cat "$MARKER" >&2
  fi
  exit "$status"
fi

echo "${ENCOUNTER} simulator core startup checkpoint initialized"
