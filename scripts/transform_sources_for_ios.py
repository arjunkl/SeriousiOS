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


def replace_identifier(path: Path, old: str, new: str, minimum: int = 1) -> int:
    text = path.read_text(encoding="utf-8")
    pattern = re.compile(rf"\b{re.escape(old)}\b")
    count = len(pattern.findall(text))
    if count < minimum:
        raise RuntimeError(
            f"{path}: expected at least {minimum} occurrences of {old!r}, found {count}"
        )
    transformed = pattern.sub(new, text)
    if pattern.search(transformed):
        raise RuntimeError(f"{path}: failed to replace every occurrence of {old!r}")
    path.write_text(transformed, encoding="utf-8")
    return count


def disable_armv7_neon_on_ios(path: Path) -> int:
    lines = path.read_text(encoding="utf-8").splitlines(keepends=True)
    count = 0
    transformed: list[str] = []

    for line in lines:
        stripped = line.lstrip()
        if (
            stripped.startswith(("#if", "#elif"))
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


def emit_shader_math_helpers(path: Path) -> int:
    replacements = (
        ("inline void MatrixVectorToMatrix12(", "void MatrixVectorToMatrix12("),
        ("inline void TransformVertex(", "void TransformVertex("),
        ("inline void RotateVector(", "void RotateVector("),
        ("inline void MatrixTranspose(", "void MatrixTranspose("),
    )
    changed = 0
    for old, new in replacements:
        changed += replace_exact(path, old, new)
    return changed


def internalize_tfe_light_coordinate_tables(path: Path) -> int:
    text = path.read_text(encoding="utf-8")
    pattern = re.compile(r"(?m)^FLOAT (_f[A-Za-z0-9]+Coordinates\s*\[)")
    count = len(pattern.findall(text))
    if count != 10:
        raise RuntimeError(
            f"{path}: expected 10 TFE light coordinate tables, found {count}"
        )
    path.write_text(pattern.sub(r"static FLOAT \1", text), encoding="utf-8")
    return count


def configure_engine_ios_paths(path: Path) -> int:
    changes = 0
    changes += replace_exact(
        path,
        "#include <Engine/Base/FileSystem.h>\n",
        '''#include <Engine/Base/FileSystem.h>
#ifdef PLATFORM_IOS
#include "SeriousIOSPlatformBridge.h"
#endif
''',
    )
    changes += replace_exact(
        path,
        '''#ifdef PLATFORM_UNIX
    // rcg01012002 calculate user dir.
  char buf[MAX_PATH];
  _pFileSystem->GetUserDirectory(buf, sizeof (buf));
  _fnmUserDir = CTString(buf);
#endif
  try {
    _fnmApplicationExe.RemoveApplicationPath_t();
  } catch (const char *strError) {
    (void) strError;
    ASSERT(FALSE);
  }''',
        '''#ifdef PLATFORM_UNIX
    // rcg01012002 calculate user dir.
  char buf[MAX_PATH];
  _pFileSystem->GetUserDirectory(buf, sizeof (buf));
  _fnmUserDir = CTString(buf);
#endif
#ifdef PLATFORM_IOS
  ASSERT(SeriousIOS_ArePathsConfigured());
  _fnmApplicationPath = CTString(SeriousIOS_GetDataPath());
  _fnmApplicationExe = CTString(SeriousIOS_GetExecutablePath());
  _fnmUserDir = CTString(SeriousIOS_GetUserPath());
#endif
#ifndef PLATFORM_IOS
  try {
    _fnmApplicationExe.RemoveApplicationPath_t();
  } catch (const char *strError) {
    (void) strError;
    ASSERT(FALSE);
  }
#endif''',
    )
    changes += replace_exact(
        path,
        '''#ifdef PLATFORM_UNIX
#if defined(__OpenBSD__) || defined(__FreeBSD__)''',
        '''#if defined(PLATFORM_IOS)
  sys_iSysPath = 0;
  _fnmModLibPath = _fnmApplicationPath;
#elif defined(PLATFORM_UNIX)
#if defined(__OpenBSD__) || defined(__FreeBSD__)''',
    )
    return changes


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

    engine_header = root / "Engine/Engine.h"
    counts["malloc_header"] = replace_exact(
        engine_header,
        "#if (!defined __INTEL_COMPILER) && (!defined PLATFORM_MACOSX)",
        "#if (!defined __INTEL_COMPILER) && (!defined PLATFORM_MACOSX) && (!defined PLATFORM_IOS)",
    )

    engine_source = root / "Engine/Engine.cpp"
    counts["ios_path_contract"] = configure_engine_ios_paths(engine_source)

    zconf = root / "Engine/zlib/zconf.h"
    counts["zlib_byte_type"] = replace_exact(
        zconf,
        "#if !defined(MACOS) && !defined(TARGET_OS_MAC)",
        "#if !defined(MACOS) && (!defined(TARGET_OS_MAC) || defined(PLATFORM_IOS))",
    )

    for relative in (
        "Engine/World/WorldRayCasting.cpp",
        "Engine/Models/RenderModel_View.cpp",
    ):
        path = root / relative
        counts[relative] = disable_armv7_neon_on_ios(path)

    rm_render = root / "Engine/Ska/RMRender.cpp"
    counts["shader_math_exports"] = emit_shader_math_helpers(rm_render)

    camera = root / "GameMP/Camera.cpp"
    counts["camera_initialized_symbol"] = replace_identifier(
        camera,
        "_bInitialized",
        "_bCameraInitialized",
        minimum=2,
    )

    if encounter == "TFE":
        light_fixes = root / "Entities/Common/LightFixes.h"
        counts["light_coordinate_internal_linkage"] = (
            internalize_tfe_light_coordinate_tables(light_fixes)
        )

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
