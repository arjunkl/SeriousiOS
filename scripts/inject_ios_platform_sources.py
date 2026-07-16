#!/usr/bin/env python3
"""Inject SeriousiOS-owned platform sources into transformed upstream CMake."""

from __future__ import annotations

import argparse
from pathlib import Path

ENCOUNTERS = ("TFE", "TSE")


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected exactly one match, found {count}")
    return text.replace(old, new, 1)


def transform(path: Path) -> None:
    text = path.read_text(encoding="utf-8")

    text = replace_once(
        text,
        'option(SERIOUSIOS_RUNTIME_ONLY "Configure only static runtime modules for the iOS host" OFF)\n',
        '''option(SERIOUSIOS_RUNTIME_ONLY "Configure only static runtime modules for the iOS host" OFF)
if(IOS)
    if(NOT SERIOUSIOS_PLATFORM_ROOT)
        message(FATAL_ERROR "SERIOUSIOS_PLATFORM_ROOT must point to the SeriousiOS platform source directory")
    endif()
    include_directories("${SERIOUSIOS_PLATFORM_ROOT}")
endif()
''',
        f"{path}: platform root contract",
    )

    text = replace_once(
        text,
        '    Engine/Base/Unix/UnixDynamicLoader.cpp\n',
        '''    ${SERIOUSIOS_PLATFORM_ROOT}/SeriousIOSDynamicLoader.cpp
    ${SERIOUSIOS_PLATFORM_ROOT}/SeriousIOSStaticRegistry.cpp
''',
        f"{path}: dynamic loader replacement",
    )

    path.write_text(text, encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("upstream", type=Path)
    args = parser.parse_args()
    upstream = args.upstream.resolve()

    for encounter in ENCOUNTERS:
        cmake = upstream / f"Sam{encounter}" / "Sources" / "CMakeLists.txt"
        if not cmake.is_file():
            raise FileNotFoundError(cmake)
        transform(cmake)
        print(f"Injected SeriousiOS platform sources into {cmake.relative_to(upstream)}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
