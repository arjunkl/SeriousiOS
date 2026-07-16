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
    if (!SeriousIOS_ArePathsConfigured()) {
        setStartupError("SeriousiOS sandbox paths were not configured before engine startup");
        gEngineState.store(SeriousIOSEngineStateFailed, std::memory_order_release);
        return false;
    }
    if (SeriousIOS_MakeGLContextCurrent() != 0) {
        setStartupError("SeriousiOS could not activate the EAGL context before engine startup");
        gEngineState.store(SeriousIOSEngineStateFailed, std::memory_order_release);
        return false;
    }

    try {
        // An empty game ID intentionally stops before Network and Player.ecl
        // initialization. This validates the core engine and platform layer without
        // requiring proprietary Serious Sam data archives.
        SE_InitEngine(SeriousIOS_GetExecutablePath(), CTString(""));
        gEngineState.store(SeriousIOSEngineStateInitialized, std::memory_order_release);
        return true;
    } catch (const char* error) {
        setStartupError(error);
    } catch (...) {
        setStartupError("Serious Engine startup threw an unknown exception");
    }

    gEngineState.store(SeriousIOSEngineStateFailed, std::memory_order_release);
    return false;
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
}

extern "C" SeriousIOSEngineState SeriousIOS_GetEngineState(void) {
    return gEngineState.load(std::memory_order_acquire);
}

extern "C" const char* SeriousIOS_GetEngineStartupError(void) {
    return gStartupError;
}
