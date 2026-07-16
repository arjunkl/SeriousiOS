#!/usr/bin/env python3
"""Apply the first coordinated iOS transformation to upstream CMake files."""

from __future__ import annotations

import argparse
import re
from pathlib import Path

ENCOUNTERS = ("TFE", "TSE")


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected exactly one match, found {count}")
    return text.replace(old, new, 1)


def regex_once(text: str, pattern: str, replacement: str, label: str) -> str:
    updated, count = re.subn(
        pattern,
        replacement,
        text,
        count=1,
        flags=re.DOTALL | re.MULTILINE,
    )
    if count != 1:
        raise RuntimeError(f"{label}: expected exactly one regex match, found {count}")
    return updated


def encounter_from_path(path: Path) -> str:
    if "SamTFE" in path.parts:
        return "TFE"
    if "SamTSE" in path.parts:
        return "TSE"
    raise RuntimeError(f"cannot determine encounter from {path}")


def transform(path: Path) -> None:
    encounter = encounter_from_path(path)
    text = path.read_text(encoding="utf-8")

    text = regex_once(
        text,
        r'''^if\(APPLE\)\n[ \t]+set\(MACOSX TRUE\)\n.*?^endif\(\)\n\n^if\(MSVC\)''',
        '''if(CMAKE_SYSTEM_NAME STREQUAL "iOS")
    set(IOS TRUE)
    set(RPATH_SETTINGS "")
    message(STATUS "Configuring Serious Engine for iOS")
elseif(APPLE)
    set(MACOSX TRUE)
    if(CMAKE_GENERATOR STREQUAL "Unix Makefiles")
      set(RPATH_SETTINGS "-rpath,$ORIGIN")
      message(STATUS "Using cmake generator 'Unix Makefiles'")
    elseif(CMAKE_GENERATOR STREQUAL "Ninja")
      set(RPATH_SETTINGS "-rpath=/tmp")
      message(STATUS "Using cmake generator 'Ninja'")
    else()
        message(FATAL_ERROR "Unknown cmake generator")
    endif()
endif()

option(SERIOUSIOS_RUNTIME_ONLY "Configure only static runtime modules for the iOS host" OFF)
set(SERIOUS_RUNTIME_LIBRARY_TYPE SHARED)
if(IOS)
    set(SERIOUS_RUNTIME_LIBRARY_TYPE STATIC)
    set(USE_ASM OFF CACHE BOOL "Use portable C on iOS" FORCE)
endif()

if(MSVC)''',
        f"{path}: platform selection",
    )

    text = replace_once(
        text,
        'if(NOT PANDORA AND NOT PYRA AND NOT RPI4 AND NOT (MACOSX AND CMAKE_SYSTEM_PROCESSOR STREQUAL "arm64"))',
        'if(NOT PANDORA AND NOT PYRA AND NOT RPI4 AND NOT IOS AND NOT (MACOSX AND CMAKE_SYSTEM_PROCESSOR STREQUAL "arm64"))',
        f"{path}: architecture flags",
    )
    text = replace_once(
        text,
        'if(NOT PYRA AND NOT PANDORA AND ${CMAKE_HOST_SYSTEM_PROCESSOR} MATCHES "arm*")',
        'if(NOT PYRA AND NOT PANDORA AND NOT IOS AND ${CMAKE_HOST_SYSTEM_PROCESSOR} MATCHES "arm*")',
        f"{path}: host architecture flags",
    )

    text = regex_once(
        text,
        r'''^[ \t]*if\(MACOSX\)\n[ \t]*add_definitions\(-DPLATFORM_UNIX=1\)\n[ \t]*add_definitions\(-DPLATFORM_MACOSX=1\)\n[ \t]*add_definitions\(-DPRAGMA_ONCE=1\)\n[ \t]*include_directories\("/usr/local/include"\)\n[ \t]*include_directories\("/usr/X11/include/"\)\n[ \t]*elseif\(WINDOWS\)''',
        '''\tif(IOS)
        add_definitions(-DPLATFORM_UNIX=1)
        add_definitions(-DPLATFORM_IOS=1)
        add_definitions(-DSTATICALLY_LINKED=1)
        add_definitions(-DUSE_PORTABLE_C=1)
        add_definitions(-DPRAGMA_ONCE=1)
        add_compile_options(-fsigned-char)
\telseif(MACOSX)
\t\tadd_definitions(-DPLATFORM_UNIX=1)
        add_definitions(-DPLATFORM_MACOSX=1)
        add_definitions(-DPRAGMA_ONCE=1)
        include_directories("/usr/local/include")
\t\tinclude_directories("/usr/X11/include/")
\telseif(WINDOWS)''',
        f"{path}: compiler platform definitions",
    )

    text = replace_once(
        text,
        '''if(XPLUS)
    execute_process (
        COMMAND bash -c "cp -fr ${CMAKE_ADD_TARGET_DIR}/Entities${MP}/PlayerWeaponsHD.es ${CMAKE_ADD_TARGET_DIR}/Entities${MP}/PlayerWeapons.es;"
        OUTPUT_VARIABLE outVar
    )
    message(STATUS "Compile a XPLUS modification")
else()
    execute_process (
        COMMAND bash -c "cp -fr ${CMAKE_ADD_TARGET_DIR}/Entities${MP}/PlayerWeapons_old.es ${CMAKE_ADD_TARGET_DIR}/Entities${MP}/PlayerWeapons.es;"
        OUTPUT_VARIABLE outVar
    )
    message(STATUS "Compile a standard game")
endif()''',
        '''if(IOS)
    message(STATUS "SeriousiOS preserves entity inputs during configure")
elseif(XPLUS)
    execute_process (
        COMMAND bash -c "cp -fr ${CMAKE_ADD_TARGET_DIR}/Entities${MP}/PlayerWeaponsHD.es ${CMAKE_ADD_TARGET_DIR}/Entities${MP}/PlayerWeapons.es;"
        OUTPUT_VARIABLE outVar
    )
    message(STATUS "Compile a XPLUS modification")
else()
    execute_process (
        COMMAND bash -c "cp -fr ${CMAKE_ADD_TARGET_DIR}/Entities${MP}/PlayerWeapons_old.es ${CMAKE_ADD_TARGET_DIR}/Entities${MP}/PlayerWeapons.es;"
        OUTPUT_VARIABLE outVar
    )
    message(STATUS "Compile a standard game")
endif()''',
        f"{path}: immutable entity inputs",
    )

    if encounter == "TFE":
        text = replace_once(
            text,
            '''if(NOT ECC)
    add_parser_and_scanner("Ecc/Parser" "Ecc/Scanner")
    add_executable(ecc Ecc/Main.cpp Ecc/Parser.cpp Ecc/Parser.h Ecc/Scanner.cpp)
    set(ECC "ecc")
endif()''',
            '''if(NOT ECC)
    add_parser_and_scanner("Ecc/Parser" "Ecc/Scanner")
    add_executable(ecc Ecc/Main.cpp Ecc/Parser.cpp Ecc/Parser.h Ecc/Scanner.cpp)
    set(ECC "ecc")
else()
    message(STATUS "Using prebuilt host ECC: ${ECC}")
endif()''',
            f"{path}: TFE host ECC selection",
        )
    else:
        text = replace_once(
            text,
            '''if(NOT ECC)
    add_parser_and_scanner("Ecc/Parser" "Ecc/Scanner")
    add_executable(ecc-se Ecc/Main.cpp Ecc/Parser.cpp Ecc/Parser.h Ecc/Scanner.cpp)
    set(ECC-SE "ecc-se")
endif()''',
            '''if(NOT ECC)
    add_parser_and_scanner("Ecc/Parser" "Ecc/Scanner")
    add_executable(ecc-se Ecc/Main.cpp Ecc/Parser.cpp Ecc/Parser.h Ecc/Scanner.cpp)
    set(ECC-SE "ecc-se")
else()
    set(ECC-SE "${ECC}")
    message(STATUS "Using prebuilt host ECC: ${ECC-SE}")
endif()''',
            f"{path}: TSE host ECC selection",
        )

    library_replacements = {
        'add_library(${ENTITIESMPLIB} SHARED': 'add_library(${ENTITIESMPLIB} ${SERIOUS_RUNTIME_LIBRARY_TYPE}',
        'add_library(${GAMEMPLIB} SHARED': 'add_library(${GAMEMPLIB} ${SERIOUS_RUNTIME_LIBRARY_TYPE}',
        'add_library(${SHADERSLIB} SHARED': 'add_library(${SHADERSLIB} ${SERIOUS_RUNTIME_LIBRARY_TYPE}',
        'add_library(${ENGINELIB} SHARED': 'add_library(${ENGINELIB} ${SERIOUS_RUNTIME_LIBRARY_TYPE}',
        'add_library(amp11lib${MP} SHARED': 'add_library(amp11lib${MP} ${SERIOUS_RUNTIME_LIBRARY_TYPE}',
    }
    expected_counts = {
        'add_library(${ENTITIESMPLIB} SHARED': 2,
        'add_library(${GAMEMPLIB} SHARED': 1,
        'add_library(${SHADERSLIB} SHARED': 1,
        'add_library(${ENGINELIB} SHARED': 1,
        'add_library(amp11lib${MP} SHARED': 1,
    }
    for old, new in library_replacements.items():
        count = text.count(old)
        if count != expected_counts[old]:
            raise RuntimeError(
                f"{path}: {old!r} expected {expected_counts[old]} matches, found {count}"
            )
        text = text.replace(old, new)

    text = replace_once(
        text,
        'set_target_properties(${ENGINELIB} PROPERTIES ENABLE_EXPORTS ON LINK_FLAGS "-Wl,${RPATH_SETTINGS}")',
        '''if(IOS)
    set_target_properties(${ENGINELIB} PROPERTIES POSITION_INDEPENDENT_CODE ON)
else()
    set_target_properties(${ENGINELIB} PROPERTIES ENABLE_EXPORTS ON LINK_FLAGS "-Wl,${RPATH_SETTINGS}")
endif()

if(IOS AND SERIOUSIOS_RUNTIME_ONLY)
    message(STATUS "SeriousiOS runtime-only graph configured; skipping desktop hosts and tools")
    return()
endif()''',
        f"{path}: runtime-only boundary",
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
        print(f"Transformed {cmake.relative_to(upstream)}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
