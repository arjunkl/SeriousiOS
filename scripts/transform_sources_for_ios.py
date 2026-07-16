#!/usr/bin/env python3
"""Apply source-level portability transforms shared by TFE and TSE."""

from __future__ import annotations

import argparse
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
    lines = path.read_text(encoding="utf-8").splitlines(keepends=True)
    count = 0
    transformed: list[str] = []

    for line in lines:
        stripped = line.lstrip()
        if (
            stripped.startswith("#if")
            and "__ARM_NEON__" in line
            and "PLATFORM_IOS" not in line
        ):
            newline = "\n" if line.endswith("\n") else ""
            line = line.rstrip("\r\n") + " && !defined PLATFORM_IOS" + newline
            count += 1
        transformed.append(line)

    if count < 1:
        raise RuntimeError(
            f"{path}: expected at least one ARM NEON guard to adapt"
        )
    path.write_text("".join(transformed), encoding="utf-8")
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
