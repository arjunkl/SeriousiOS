#include "SeriousIOSEngineStartup.h"
#include "SeriousIOSPlatformBridge.h"

#include <Engine/Engine.h>
#include <GameMP/Game.h>

#include <atomic>
#include <cstdio>
#include <cstring>

extern CGame* _pGame;

extern "C" CGame* GAME_Create(void);

namespace {

std::atomic<SeriousIOSEngineState> gEngineState{SeriousIOSEngineStateIdle};
char gStartupError[1024] = {};

void setStartupError(const char* message) {
    std::snprintf(
        gStartupError,
        sizeof(gStartupError),
        "%s",
        message == nullptr ? "Unknown Serious Engine startup failure" : message);
    gStartupError[sizeof(gStartupError) - 1] = '\0';
}

void writeCheckpoint(
    const char* filename,
    const char* state,
    const char* error) {
    const char* temporaryPath = SeriousIOS_GetTemporaryPath();
    if (temporaryPath == nullptr || *temporaryPath == '\0') {
        return;
    }

    char markerPath[2048] = {};
    std::snprintf(
        markerPath,
        sizeof(markerPath),
        "%s%s",
        temporaryPath,
        filename);
    markerPath[sizeof(markerPath) - 1] = '\0';

    FILE* marker = std::fopen(markerPath, "wb");
    if (marker == nullptr) {
        return;
    }
    std::fprintf(marker, "state=%s\n", state == nullptr ? "unknown" : state);
    std::fprintf(marker, "error=%s\n", error == nullptr ? "" : error);
    std::fclose(marker);
}

void writeCoreCheckpoint(const char* state, const char* error) {
    writeCheckpoint("core-startup-checkpoint.txt", state, error);
}

void writeGameCheckpoint(const char* state, const char* error) {
    writeCheckpoint("game-runtime-checkpoint.txt", state, error);
}

bool validatePlatformPreconditions(const char* checkpointName) {
    if (!SeriousIOS_ArePathsConfigured()) {
        setStartupError(
            "SeriousiOS sandbox paths were not configured before engine startup");
        writeCheckpoint(checkpointName, "failed", gStartupError);
        return false;
    }
    if (SeriousIOS_MakeGLContextCurrent() != 0) {
        setStartupError(
            "SeriousiOS could not activate the EAGL context before engine startup");
        writeCheckpoint(checkpointName, "failed", gStartupError);
        return false;
    }
    return true;
}

void destroyGameRuntime(void) noexcept {
    if (_pGame == nullptr) {
        return;
    }

    try {
        _pGame->End();
    } catch (...) {
        // Continue shutdown so a partially initialized game cannot poison the next launch.
    }
    delete _pGame;
    _pGame = nullptr;
}

void endEngineAfterFailure(bool engineInitialized) noexcept {
    destroyGameRuntime();
    if (!engineInitialized) {
        return;
    }
    try {
        SE_EndEngine();
    } catch (...) {
    }
}

bool failCoreStartup(const char* message, bool engineInitialized) {
    setStartupError(message);
    writeCoreCheckpoint("failed", gStartupError);
    endEngineAfterFailure(engineInitialized);
    gEngineState.store(SeriousIOSEngineStateFailed, std::memory_order_release);
    return false;
}

bool failGameStartup(const char* message, bool engineInitialized) {
    setStartupError(message);
    writeGameCheckpoint("failed", gStartupError);
    endEngineAfterFailure(engineInitialized);
    gEngineState.store(SeriousIOSEngineStateFailed, std::memory_order_release);
    return false;
}

} // namespace

extern "C" bool SeriousIOS_StartCoreEngine(void) {
    SeriousIOSEngineState expected = SeriousIOSEngineStateIdle;
    if (!gEngineState.compare_exchange_strong(
            expected,
            SeriousIOSEngineStateCoreStarting,
            std::memory_order_acq_rel)) {
        return expected == SeriousIOSEngineStateCoreInitialized;
    }

    gStartupError[0] = '\0';
    writeCoreCheckpoint("starting", nullptr);
    if (!validatePlatformPreconditions("core-startup-checkpoint.txt")) {
        gEngineState.store(SeriousIOSEngineStateFailed, std::memory_order_release);
        return false;
    }

    bool engineInitialized = false;
    try {
        // An empty game ID intentionally stops before Network and Player.ecl
        // initialization. This validates the core engine and platform layer without
        // requiring proprietary Serious Sam data archives.
        SE_InitEngine(SeriousIOS_GetExecutablePath(), CTString(""));
        engineInitialized = true;
        writeCoreCheckpoint("initialized", nullptr);
        gEngineState.store(
            SeriousIOSEngineStateCoreInitialized,
            std::memory_order_release);
        return true;
    } catch (const char* error) {
        return failCoreStartup(error, engineInitialized);
    } catch (...) {
        return failCoreStartup(
            "Serious Engine core startup threw an unknown exception",
            engineInitialized);
    }
}

extern "C" bool SeriousIOS_StartGameRuntime(const char* gameIdentifier) {
    SeriousIOSEngineState expected = SeriousIOSEngineStateIdle;
    if (!gEngineState.compare_exchange_strong(
            expected,
            SeriousIOSEngineStateGameStarting,
            std::memory_order_acq_rel)) {
        return expected == SeriousIOSEngineStateGameInitialized;
    }

    gStartupError[0] = '\0';
    writeGameCheckpoint("starting", nullptr);
    if (gameIdentifier == nullptr || *gameIdentifier == '\0') {
        return failGameStartup(
            "SeriousiOS full game startup requires a non-empty encounter ID",
            false);
    }
    if (!validatePlatformPreconditions("game-runtime-checkpoint.txt")) {
        gEngineState.store(SeriousIOSEngineStateFailed, std::memory_order_release);
        return false;
    }

    bool engineInitialized = false;
    try {
        // This is the first data-dependent gate. It mounts the user-supplied GRO
        // archives, initializes Network and Player.ecl for the encounter, creates
        // the statically linked Game object, and loads its persistent settings.
        SE_InitEngine(
            SeriousIOS_GetExecutablePath(),
            CTString(gameIdentifier));
        engineInitialized = true;

        _pGame = GAME_Create();
        if (_pGame == nullptr) {
            return failGameStartup(
                "The statically linked GAME_Create function returned null",
                engineInitialized);
        }
        _pGame->Initialize(CTString("Data\\SeriousSam.gms"));

        writeGameCheckpoint("initialized", nullptr);
        gEngineState.store(
            SeriousIOSEngineStateGameInitialized,
            std::memory_order_release);
        return true;
    } catch (const char* error) {
        return failGameStartup(error, engineInitialized);
    } catch (...) {
        return failGameStartup(
            "Serious Sam game runtime startup threw an unknown exception",
            engineInitialized);
    }
}

extern "C" void SeriousIOS_StopEngine(void) {
    const SeriousIOSEngineState state =
        gEngineState.load(std::memory_order_acquire);
    if (state != SeriousIOSEngineStateCoreInitialized
        && state != SeriousIOSEngineStateGameInitialized) {
        return;
    }

    if (state == SeriousIOSEngineStateGameInitialized) {
        destroyGameRuntime();
    }
    SE_EndEngine();
    writeCheckpoint(
        state == SeriousIOSEngineStateGameInitialized
            ? "game-runtime-checkpoint.txt"
            : "core-startup-checkpoint.txt",
        "stopped",
        nullptr);
    gEngineState.store(SeriousIOSEngineStateStopped, std::memory_order_release);
}

extern "C" SeriousIOSEngineState SeriousIOS_GetEngineState(void) {
    return gEngineState.load(std::memory_order_acquire);
}

extern "C" const char* SeriousIOS_GetEngineStartupError(void) {
    return gStartupError;
}
