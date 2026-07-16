#!/usr/bin/env bash
set -euo pipefail

if [[ $# -ne 3 ]]; then
  echo "usage: $0 <CMake build directory> <TFE|TSE> <evidence directory>" >&2
  exit 64
fi

BUILD_DIR=$(cd "$1" && pwd)
ENCOUNTER=$2
EVIDENCE=$3
mkdir -p "$EVIDENCE"
EVIDENCE=$(cd "$EVIDENCE" && pwd)

case "$ENCOUNTER" in
  TFE)
    targets=(engine_safemath Engine Game Shaders Entities)
    ;;
  TSE)
    targets=(engine_safemathMP EngineMP GameMP ShadersMP EntitiesMP)
    ;;
  *)
    echo "encounter must be TFE or TSE" >&2
    exit 64
    ;;
esac

configuration=Release
overall_status=0
summary="$EVIDENCE/${ENCOUNTER}-archive-build.tsv"
printf 'target\tstatus\tarchive_count\n' > "$summary"

for target in "${targets[@]}"; do
  log="$EVIDENCE/${ENCOUNTER}-${target}.log"
  echo "::group::Build ${ENCOUNTER} ${target}"
  set +e
  cmake --build "$BUILD_DIR" \
    --config "$configuration" \
    --target "$target" \
    --parallel 4 \
    2>&1 | tee "$log"
  status=${PIPESTATUS[0]}
  set -e

  archive_count=$(find "$BUILD_DIR" -type f -name "lib${target}.a" | wc -l | tr -d ' ')
  if [[ $status -eq 0 && $archive_count -eq 0 ]]; then
    echo "${target} reported success but no lib${target}.a was produced" | tee -a "$log"
    status=86
  fi

  printf '%s\t%s\t%s\n' "$target" "$status" "$archive_count" >> "$summary"
  if [[ $status -ne 0 ]]; then
    overall_status=1
  fi
  echo "::endgroup::"
done

{
  echo "# ${ENCOUNTER} iOS runtime archive build"
  echo
  echo "Configuration: \`${configuration}\`"
  echo
  echo '| Target | Status | Matching archives |'
  echo '|---|---:|---:|'
  tail -n +2 "$summary" | while IFS=$'\t' read -r target status archives; do
    echo "| \`${target}\` | ${status} | ${archives} |"
  done
  echo
  echo '## Produced archives'
  echo
  while IFS= read -r archive; do
    relative=${archive#"$BUILD_DIR/"}
    size=$(stat -f '%z' "$archive")
    sha=$(shasum -a 256 "$archive" | awk '{print $1}')
    echo "- \`${relative}\`: ${size} bytes, SHA-256 \`${sha}\`"
  done < <(find "$BUILD_DIR" -type f -name '*.a' | LC_ALL=C sort)
} | tee "$EVIDENCE/${ENCOUNTER}-archive-build.md"

exit "$overall_status"
