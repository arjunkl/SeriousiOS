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
    include_directories("${CMAKE_SOURCE_DIR}/libogg/include")
    include_directories("${CMAKE_SOURCE_DIR}/libvorbis/include")
    include_directories("${CMAKE_SOURCE_DIR}/libvorbis/lib")
    set_source_files_properties(
        "${SERIOUSIOS_PLATFORM_ROOT}/SeriousIOSSDLCompat.cpp"
        PROPERTIES COMPILE_DEFINITIONS
            "SDL_GL_GetProcAddress=SeriousIOS_OriginalSDL_GL_GetProcAddress;SDL_GetMouseState=SeriousIOS_OriginalSDL_GetMouseState;SDL_GetKeyboardState=SeriousIOS_OriginalSDL_GetKeyboardState;SDL_GetScancodeFromKey=SeriousIOS_OriginalSDL_GetScancodeFromKey;SDL_GetRelativeMouseState=SeriousIOS_OriginalSDL_GetRelativeMouseState;SDL_PollEvent=SeriousIOS_OriginalSDL_PollEvent;SDL_NumJoysticks=SeriousIOS_OriginalSDL_NumJoysticks;SDL_JoystickNameForIndex=SeriousIOS_OriginalSDL_JoystickNameForIndex;SDL_JoystickOpen=SeriousIOS_OriginalSDL_JoystickOpen;SDL_JoystickClose=SeriousIOS_OriginalSDL_JoystickClose;SDL_JoystickNumAxes=SeriousIOS_OriginalSDL_JoystickNumAxes;SDL_JoystickNumButtons=SeriousIOS_OriginalSDL_JoystickNumButtons;SDL_JoystickNumHats=SeriousIOS_OriginalSDL_JoystickNumHats;SDL_JoystickInstanceID=SeriousIOS_OriginalSDL_JoystickInstanceID;SDL_JoystickGetAxis=SeriousIOS_OriginalSDL_JoystickGetAxis;SDL_JoystickGetButton=SeriousIOS_OriginalSDL_JoystickGetButton;SDL_GetNumAudioDevices=SeriousIOS_OriginalSDL_GetNumAudioDevices;SDL_GetAudioDeviceName=SeriousIOS_OriginalSDL_GetAudioDeviceName;SDL_GetCurrentAudioDriver=SeriousIOS_OriginalSDL_GetCurrentAudioDriver;SDL_OpenAudioDevice=SeriousIOS_OriginalSDL_OpenAudioDevice;SDL_PauseAudioDevice=SeriousIOS_OriginalSDL_PauseAudioDevice;SDL_CloseAudioDevice=SeriousIOS_OriginalSDL_CloseAudioDevice;SDL_LockAudioDevice=SeriousIOS_OriginalSDL_LockAudioDevice;SDL_UnlockAudioDevice=SeriousIOS_OriginalSDL_UnlockAudioDevice")
endif()
''',
        f"{path}: platform root contract",
    )

    text = replace_once(
        text,
        '    Engine/Base/Unix/UnixFileSystem.cpp\n',
        '    ${SERIOUSIOS_PLATFORM_ROOT}/SeriousIOSFileSystem.cpp\n',
        f"{path}: filesystem replacement",
    )

    text = replace_once(
        text,
        '    Engine/Base/Unix/UnixDynamicLoader.cpp\n',
        '''    ${SERIOUSIOS_PLATFORM_ROOT}/SeriousIOSDynamicLoader.cpp
    ${SERIOUSIOS_PLATFORM_ROOT}/SeriousIOSStaticRegistry.cpp
    ${SERIOUSIOS_PLATFORM_ROOT}/SeriousIOSPlatformState.cpp
    ${SERIOUSIOS_PLATFORM_ROOT}/SeriousIOSDiagnostics.cpp
    ${SERIOUSIOS_PLATFORM_ROOT}/SeriousIOSEngineStartup.cpp
    ${SERIOUSIOS_PLATFORM_ROOT}/SeriousIOSInputBridge.cpp
    ${SERIOUSIOS_PLATFORM_ROOT}/SeriousIOSSDLCompat.cpp
    ${SERIOUSIOS_PLATFORM_ROOT}/SeriousIOSSDLMouse.cpp
    ${SERIOUSIOS_PLATFORM_ROOT}/SeriousIOSSDLInjectedInput.cpp
    ${SERIOUSIOS_PLATFORM_ROOT}/SeriousIOSSDLVirtualController.cpp
    ${SERIOUSIOS_PLATFORM_ROOT}/SeriousIOSSDLAudioQueue.cpp
    ${SERIOUSIOS_PLATFORM_ROOT}/SeriousIOSSDLGLProcAddress.cpp
    ${SERIOUSIOS_PLATFORM_ROOT}/SeriousIOSOpenGLCompat.cpp
    ${SERIOUSIOS_PLATFORM_ROOT}/SeriousIOSOpenGLImmediateCompat.cpp
    ${SERIOUSIOS_PLATFORM_ROOT}/SeriousIOSOpenGLTextureCompat.cpp
    ${SERIOUSIOS_PLATFORM_ROOT}/SeriousIOSOpenGLExports.cpp
    ${SERIOUSIOS_PLATFORM_ROOT}/SeriousIOSVorbisRegistry.cpp
    libogg/src/bitwise.c
    libogg/src/framing.c
    libvorbis/lib/analysis.c
    libvorbis/lib/bitrate.c
    libvorbis/lib/block.c
    libvorbis/lib/codebook.c
    libvorbis/lib/envelope.c
    libvorbis/lib/floor0.c
    libvorbis/lib/floor1.c
    libvorbis/lib/info.c
    libvorbis/lib/lookup.c
    libvorbis/lib/lpc.c
    libvorbis/lib/lsp.c
    libvorbis/lib/mapping0.c
    libvorbis/lib/mdct.c
    libvorbis/lib/psy.c
    libvorbis/lib/registry.c
    libvorbis/lib/res0.c
    libvorbis/lib/sharedbook.c
    libvorbis/lib/smallft.c
    libvorbis/lib/synthesis.c
    libvorbis/lib/vorbisenc.c
    libvorbis/lib/vorbisfile.c
    libvorbis/lib/window.c
''',
        f"{path}: dynamic loader replacement",
    )

    text = replace_once(
        text,
        '''        ${SERIOUSIOS_PLATFORM_ROOT}/SeriousIOSMainWindow.cpp
        SeriousSam/Menu.cpp''',
        '''        ${SERIOUSIOS_PLATFORM_ROOT}/SeriousIOSMainWindow.cpp
        ${SERIOUSIOS_PLATFORM_ROOT}/SeriousIOSApplicationLifecycle.cpp
        ${SERIOUSIOS_PLATFORM_ROOT}/SeriousIOSGameplayInput.cpp
        SeriousSam/Menu.cpp''',
        f"{path}: application lifecycle injection",
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
