#!/usr/bin/env bash
set -euo pipefail

if [[ $# -ne 1 ]]; then
  echo "usage: $0 <app bundle>" >&2
  exit 64
fi

APP_DIR=$1
REPOSITORY_ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
ASSET_ROOT="$REPOSITORY_ROOT/Assets"

if [[ ! -d "$APP_DIR" ]]; then
  echo "app bundle does not exist: $APP_DIR" >&2
  exit 1
fi

ICON_2X="$APP_DIR/Icon-60@2x.png"
ICON_3X="$APP_DIR/Icon-60@3x.png"

tr -d '\r\n' < "$ASSET_ROOT/Icon-60@2x.png.base64" \
  | /usr/bin/base64 -D > "$ICON_2X"

{
  cat "$ASSET_ROOT/Icon-60@3x.part1.base64"
  cat "$ASSET_ROOT/Icon-60@3x.part2.base64"
  cat "$ASSET_ROOT/Icon-60@3x.part3.base64"
  cat "$ASSET_ROOT/Icon-60@3x.part4.base64"
} | tr -d '\r\n' | /usr/bin/base64 -D > "$ICON_3X"

EXPECTED_2X="97e95a8d02acb5a77fe04b1cb8290a9afcccd2bf40e3808cfc5bfb70bd76ffb0"
EXPECTED_3X="d5967f08623e0d56b78dfe2df37a116932a38c873bf059b65dd7c8e9dcf06d4c"
ACTUAL_2X=$(shasum -a 256 "$ICON_2X" | awk '{print $1}')
ACTUAL_3X=$(shasum -a 256 "$ICON_3X" | awk '{print $1}')

if [[ "$ACTUAL_2X" != "$EXPECTED_2X" ]]; then
  echo "120px app icon hash mismatch: expected $EXPECTED_2X, got $ACTUAL_2X" >&2
  exit 1
fi
if [[ "$ACTUAL_3X" != "$EXPECTED_3X" ]]; then
  echo "180px app icon hash mismatch: expected $EXPECTED_3X, got $ACTUAL_3X" >&2
  exit 1
fi

width_2x=$(sips -g pixelWidth "$ICON_2X" | awk '/pixelWidth:/ {print $2}')
height_2x=$(sips -g pixelHeight "$ICON_2X" | awk '/pixelHeight:/ {print $2}')
width_3x=$(sips -g pixelWidth "$ICON_3X" | awk '/pixelWidth:/ {print $2}')
height_3x=$(sips -g pixelHeight "$ICON_3X" | awk '/pixelHeight:/ {print $2}')
alpha_2x=$(sips -g hasAlpha "$ICON_2X" | awk '/hasAlpha:/ {print $2}')
alpha_3x=$(sips -g hasAlpha "$ICON_3X" | awk '/hasAlpha:/ {print $2}')

if [[ "$width_2x" != "120" || "$height_2x" != "120" ]]; then
  echo "unexpected 2x icon dimensions: ${width_2x}x${height_2x}" >&2
  exit 1
fi
if [[ "$width_3x" != "180" || "$height_3x" != "180" ]]; then
  echo "unexpected 3x icon dimensions: ${width_3x}x${height_3x}" >&2
  exit 1
fi
if [[ "$alpha_2x" != "no" || "$alpha_3x" != "no" ]]; then
  echo "iOS app icons must be opaque: 2x=$alpha_2x 3x=$alpha_3x" >&2
  exit 1
fi

printf 'app_icon_2x=%s size=%sx%s alpha=%s sha256=%s\n' \
  "$ICON_2X" "$width_2x" "$height_2x" "$alpha_2x" "$ACTUAL_2X"
printf 'app_icon_3x=%s size=%sx%s alpha=%s sha256=%s\n' \
  "$ICON_3X" "$width_3x" "$height_3x" "$alpha_3x" "$ACTUAL_3X"
