#include "SeriousIOSEngineStartup.h"
#include "SeriousIOSPlatformBridge.h"

#include <Engine/Engine.h>

#include <atomic>
#include <cstdio>
#include <cstring>

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

void writeCheckpoint(const char* state, const char* error) {
    const char* temporaryPath = SeriousIOS_GetTemporaryPath();
    if (temporaryPath == nullptr || *temporaryPath == '\0') {
        return;
    }

    char markerPath[2048] = {};
    std::snprintf(
        markerPath,
        sizeof(markerPath),
        "%score-startup-checkpoint.txt",
        temporaryPath);
    markerPath[sizeof(markerPath) - 1] = '\0';

    FILE* marker = std::fopen(markerPath, "wb");
    if (marker == nullptr) {
        return;
    }
    std::fprintf(marker, "state=%s\n", state == nullptr ? "unknown" : state);
    std::fprintf(marker, "error=%s\n", error == nullptr ? "" : error);
    std::fclose(marker);
}

bool failStartup(const char* message) {
    setStartupError(message);
    writeCheckpoint("failed", gStartupError);
    gEngineState.store(SeriousIOSEngineStateFailed, std::memory_order_release);
    return false;
}

} // namespace

extern "C" bool SeriousIOS_StartCoreEngine(void) {
    SeriousIOSEngineState expected = SeriousIOSEngineStateIdle;
    if (!gEngineState.compare_exchange_strong(
            expected,
            SeriousIOSEngineStateStarting,
            std::memory_order_acq_rel)) {
        return expected == SeriousIOSEngineStateInitialized;
    }

    gStartupError[0] = '\0';
    writeCheckpoint("starting", nullptr);
    if (!SeriousIOS_ArePathsConfigured()) {
        return failStartup(
            "SeriousiOS sandbox paths were not configured before engine startup");
    }
    if (SeriousIOS_MakeGLContextCurrent() != 0) {
        return failStartup(
            "SeriousiOS could not activate the EAGL context before engine startup");
    }

    try {
        // An empty game ID intentionally stops before Network and Player.ecl
        // initialization. This validates the core engine and platform layer without
        // requiring proprietary Serious Sam data archives.
        SE_InitEngine(SeriousIOS_GetExecutablePath(), CTString(""));
        writeCheckpoint("initialized", nullptr);
        gEngineState.store(SeriousIOSEngineStateInitialized, std::memory_order_release);
        return true;
    } catch (const char* error) {
        return failStartup(error);
    } catch (...) {
        return failStartup("Serious Engine startup threw an unknown exception");
    }
}

extern "C" void SeriousIOS_StopCoreEngine(void) {
    SeriousIOSEngineState expected = SeriousIOSEngineStateInitialized;
    if (!gEngineState.compare_exchange_strong(
            expected,
            SeriousIOSEngineStateStopped,
            std::memory_order_acq_rel)) {
        return;
    }
    SE_EndEngine();
    writeCheckpoint("stopped", nullptr);
}

extern "C" SeriousIOSEngineState SeriousIOS_GetEngineState(void) {
    return gEngineState.load(std::memory_order_acquire);
}

extern "C" const char* SeriousIOS_GetEngineStartupError(void) {
    return gStartupError;
}
