#!/usr/bin/env python3
"""Apply source-level portability transforms shared by TFE and TSE."""

from __future__ import annotations

import argparse
import re
from pathlib import Path

ENCOUNTERS = ("TFE", "TSE")


def replace_exact(path: Path, old: str, new: str, expected: int = 1) -> int:
    text = path.read_text(encoding="utf-8")
    count = text.count(old)
    if count != expected:
        raise RuntimeError(
            f"{path}: expected {expected} occurrences of {old!r}, found {count}"
        )
    path.write_text(text.replace(old, new), encoding="utf-8")
    return count


def disable_armv7_neon_on_ios(path: Path) -> int:
    text = path.read_text(encoding="utf-8")
    pattern = re.compile(
        r"(?m)^(#if\s+defined(?:\s+|\()__ARM_NEON__\)?"
        r"\s*&&\s*!defined(?:\s+|\()PLATFORM_MACOSX\)?)"
        r"(?![^\n]*PLATFORM_IOS)"
    )
    updated, count = pattern.subn(r"\1 && !defined PLATFORM_IOS", text)
    if count < 1:
        raise RuntimeError(
            f"{path}: expected at least one ARM NEON/macOS guard to adapt"
        )
    path.write_text(updated, encoding="utf-8")
    return count


def transform_encounter(upstream: Path, encounter: str) -> dict[str, int]:
    root = upstream / f"Sam{encounter}" / "Sources"
    if not root.is_dir():
        raise FileNotFoundError(root)

    counts: dict[str, int] = {}

    types = root / "Engine/Base/Types.h"
    counts["ms_int64_typedef"] = replace_exact(
        types,
        '''#if (!defined __INTEL_COMPILER) && (!defined PLATFORM_FREEBSD) && (!defined PLATFORM_MACOSX)
      typedef int64_t __int64;
    #elif (!defined PLATFORM_FREEBSD) && (!defined PLATFORM_MACOSX)''',
        '''#if (!defined __INTEL_COMPILER) && (!defined PLATFORM_FREEBSD) && (!defined PLATFORM_MACOSX) && (!defined PLATFORM_IOS)
      typedef int64_t __int64;
    #elif (!defined PLATFORM_FREEBSD) && (!defined PLATFORM_MACOSX) && (!defined PLATFORM_IOS)''',
    )

    engine = root / "Engine/Engine.h"
    counts["malloc_header"] = replace_exact(
        engine,
        "#if (!defined __INTEL_COMPILER) && (!defined PLATFORM_MACOSX)",
        "#if (!defined __INTEL_COMPILER) && (!defined PLATFORM_MACOSX) && (!defined PLATFORM_IOS)",
    )

    for relative in (
        "Engine/World/WorldRayCasting.cpp",
        "Engine/Models/RenderModel_View.cpp",
    ):
        path = root / relative
        counts[relative] = disable_armv7_neon_on_ios(path)

    return counts


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("upstream", type=Path)
    args = parser.parse_args()
    upstream = args.upstream.resolve()

    for encounter in ENCOUNTERS:
        counts = transform_encounter(upstream, encounter)
        rendered = ", ".join(f"{key}={value}" for key, value in sorted(counts.items()))
        print(f"{encounter}: {rendered}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
