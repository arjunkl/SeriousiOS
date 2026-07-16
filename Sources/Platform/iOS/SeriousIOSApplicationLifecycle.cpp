#include "SeriousIOSApplicationLifecycle.h"
#include "SeriousIOSDiagnostics.h"
#include "SeriousIOSPlatformBridge.h"

#include <Engine/Engine.h>
#include <Engine/Base/Stream.h>
#include <GameMP/Game.h>
#include <SeriousSam/Menu.h>
#include <SeriousSam/SeriousSam.h>

#include <SDL.h>

#include <cstdio>
#include <cstring>

extern BOOL Init(HINSTANCE instance, int showCommand, CTString commandLine);
extern void End(void);
extern void DoGame(void);
extern void UpdateInputEnabledState(void);

extern BOOL bMenuActive;
extern BOOL bMenuRendering;
extern BOOL _bWindowChanging;
extern INDEX sam_bAutoPlayDemos;

namespace {

bool gApplicationInitialized = false;
bool gApplicationSuspended = false;
bool gApplicationStartupFailed = false;
bool gFirstFrameCompleted = false;
bool gStreamHandlingEnabled = false;
char gApplicationError[1024] = {};
char gApplicationStage[256] = "idle";

void setError(const char* message) {
    std::snprintf(
        gApplicationError,
        sizeof(gApplicationError),
        "%s",
        message == nullptr ? "Unknown Serious Sam application failure" : message);
    gApplicationError[sizeof(gApplicationError) - 1] = '\0';
    SeriousIOS_DiagnosticsLog("error", "%s", gApplicationError);
}

const char* checkpointRoot() {
    const char* userPath = SeriousIOS_GetUserPath();
    if (userPath != nullptr && *userPath != '\0') {
        return userPath;
    }
    return SeriousIOS_GetTemporaryPath();
}

void writeCheckpoint(const char* state) {
    const char* root = checkpointRoot();
    if (root == nullptr || *root == '\0') {
        return;
    }

    char markerPath[2048] = {};
    std::snprintf(
        markerPath,
        sizeof(markerPath),
        "%sapplication-runtime-checkpoint.txt",
        root);
    markerPath[sizeof(markerPath) - 1] = '\0';

    FILE* marker = std::fopen(markerPath, "wb");
    if (marker == nullptr) {
        SeriousIOS_DiagnosticsLog(
            "checkpoint",
            "cannot_open path=%s state=%s",
            markerPath,
            state == nullptr ? "unknown" : state);
        return;
    }
    std::fprintf(marker, "state=%s\n", state == nullptr ? "unknown" : state);
    std::fprintf(marker, "stage=%s\n", gApplicationStage);
    std::fprintf(marker, "error=%s\n", gApplicationError);
    std::fflush(marker);
    std::fclose(marker);
}

bool fail(const char* message) {
    setError(message);
    writeCheckpoint("failed");
    SeriousIOS_DiagnosticsWriteSummary("application-failure");
    return false;
}

bool failStartup(const char* message) {
    gApplicationStartupFailed = true;
    return fail(message);
}

void configureInitialDisplayMode() {
    int width = 0;
    int height = 0;
    SDL_GetWindowSize(nullptr, &width, &height);
    if (width <= 0 || height <= 0) {
        SeriousIOS_DiagnosticsLog(
            "display",
            "initial_drawable_invalid width=%d height=%d",
            width,
            height);
        return;
    }

    sam_iScreenSizeI = width;
    sam_iScreenSizeJ = height;
    sam_iAspectSizeI = width;
    sam_iAspectSizeJ = height;
    sam_iDisplayDepth = DD_DEFAULT;
    sam_iDisplayAdapter = 0;
    sam_iGfxAPI = GAT_OGL;
    sam_bFullScreenActive = TRUE;
    sam_bBorderLessActive = TRUE;
    SeriousIOS_DiagnosticsLog(
        "display",
        "initial_mode width=%d height=%d api=OpenGL fullscreen=1 borderless=1",
        width,
        height);
}

void enableMainThreadStreamHandling() {
    if (gStreamHandlingEnabled) {
        return;
    }

    SeriousIOS_ApplicationSetStage("enable-stream-handling");
    CTStream::EnableStreamHandling();
    gStreamHandlingEnabled = true;
    SeriousIOS_DiagnosticsLog("stream", "main_thread_stream_handling=enabled");
}

void disableMainThreadStreamHandling() {
    if (!gStreamHandlingEnabled) {
        return;
    }

    SeriousIOS_ApplicationSetStage("disable-stream-handling");
    CTStream::DisableStreamHandling();
    gStreamHandlingEnabled = false;
    SeriousIOS_DiagnosticsLog("stream", "main_thread_stream_handling=disabled");
}

} // namespace

extern "C" void SeriousIOS_ApplicationSetStage(const char* stage) {
    std::snprintf(
        gApplicationStage,
        sizeof(gApplicationStage),
        "%s",
        stage == nullptr ? "unknown" : stage);
    gApplicationStage[sizeof(gApplicationStage) - 1] = '\0';
    SeriousIOS_DiagnosticsLogStage(gApplicationStage);
    writeCheckpoint(gApplicationInitialized ? "running" : "initializing");
}

extern "C" const char* SeriousIOS_ApplicationGetStage(void) {
    return gApplicationStage;
}

extern "C" void SeriousIOS_ApplicationRecordFatalError(const char* message) {
    gApplicationStartupFailed = true;
    setError(message == nullptr ? "Legacy FatalError terminated the process" : message);
    SeriousIOS_DiagnosticsLog(
        "fatal",
        "stage=%s message=%s",
        gApplicationStage,
        gApplicationError);
    writeCheckpoint("fatal");
    SeriousIOS_DiagnosticsWriteSummary("fatal-error");
    SeriousIOS_DiagnosticsFlush();
}

extern "C" bool SeriousIOS_ApplicationInitialize(void) {
    if (gApplicationInitialized) {
        return true;
    }
    if (gApplicationStartupFailed) {
        return fail(
            "A previous startup attempt left partially initialized engine state; close and reopen the app before retrying");
    }

    gApplicationError[0] = '\0';
    gFirstFrameCompleted = false;
    SeriousIOS_DiagnosticsLog("application", "initialize_requested");
    SeriousIOS_ApplicationSetStage("application-entry");
    if (!SeriousIOS_ArePathsConfigured()) {
        return failStartup("SeriousiOS paths were not configured before application startup");
    }
    SeriousIOS_ApplicationSetStage("activate-eagl-context");
    if (SeriousIOS_MakeGLContextCurrent() != 0) {
        return failStartup("SeriousiOS could not activate the EAGL context before application startup");
    }

    // The desktop executable wraps the entire SubMain lifetime in
    // CTSTREAM_BEGIN/CTSTREAM_END. UIKit owns the process loop on iOS, so it
    // must reproduce that same main-thread contract explicitly. This remains
    // enabled across Init, every frame, and End because streams may be opened
    // from GRO archives throughout the application session.
    enableMainThreadStreamHandling();

    SeriousIOS_ApplicationSetStage("configure-initial-display-mode");
    configureInitialDisplayMode();
    sam_bAutoPlayDemos = FALSE;

    try {
        SeriousIOS_ApplicationSetStage("upstream-init-entry");
        if (!Init(nullptr, 0, CTString(""))) {
            return failStartup("The upstream Serious Sam Init function returned false");
        }
        SeriousIOS_ApplicationSetStage("upstream-init-returned");
    } catch (const char* error) {
        return failStartup(error);
    } catch (...) {
        return failStartup("Serious Sam application initialization threw an unknown exception");
    }

    _bRunning = TRUE;
    _bQuitScreen = FALSE;
    SeriousIOS_ApplicationSetStage("start-menus");
    if (!bMenuActive) {
        StartMenus();
    }
    bMenuRendering = TRUE;
    gApplicationSuspended = false;
    gApplicationInitialized = true;
    SeriousIOS_ApplicationSetStage("application-initialized");
    writeCheckpoint("initialized");
    SeriousIOS_DiagnosticsLog(
        "application",
        "initialized menu_active=%d menu_rendering=%d",
        bMenuActive != FALSE,
        bMenuRendering != FALSE);
    SeriousIOS_DiagnosticsWriteSummary("application-initialized");
    return true;
}

extern "C" bool SeriousIOS_ApplicationFrame(void) {
    if (!gApplicationInitialized || gApplicationSuspended || !_bRunning) {
        return false;
    }
    if (SeriousIOS_MakeGLContextCurrent() != 0) {
        return fail("SeriousiOS lost its EAGL context before an application frame");
    }
    if (_pGame == nullptr) {
        return fail("Serious Sam application frame has no Game object");
    }

    if (!gFirstFrameCompleted) {
        SeriousIOS_ApplicationSetStage("first-frame-entry");
        writeCheckpoint("frame-starting");
    }

    try {
        _bWindowChanging = FALSE;
        UpdateInputEnabledState();
        _pGame->gm_bMenuOn = bMenuActive;
        DoGame();
    } catch (const char* error) {
        return fail(error);
    } catch (...) {
        return fail("Serious Sam application frame threw an unknown exception");
    }

    SeriousIOS_DiagnosticsRecordFramePresented();
    if (!gFirstFrameCompleted) {
        gFirstFrameCompleted = true;
        SeriousIOS_ApplicationSetStage("first-frame-complete");
        writeCheckpoint("first-frame-complete");
        SeriousIOS_DiagnosticsWriteSummary("first-frame-complete");
    }
    return _bRunning != FALSE;
}

extern "C" void SeriousIOS_ApplicationSuspend(void) {
    if (!gApplicationInitialized || gApplicationSuspended) {
        return;
    }
    gApplicationSuspended = true;
    if (_pNetwork != nullptr) {
        _pNetwork->SetLocalPause(TRUE);
    }
    SeriousIOS_ApplicationSetStage("suspended");
    writeCheckpoint("suspended");
    SeriousIOS_DiagnosticsRecordSuspend();
}

extern "C" void SeriousIOS_ApplicationResume(void) {
    if (!gApplicationInitialized || !gApplicationSuspended) {
        return;
    }
    if (_pNetwork != nullptr) {
        _pNetwork->SetLocalPause(FALSE);
    }
    gApplicationSuspended = false;
    SeriousIOS_ApplicationSetStage("resumed");
    writeCheckpoint("initialized");
    SeriousIOS_DiagnosticsRecordResume();
}

extern "C" void SeriousIOS_ApplicationShutdown(void) {
    if (!gApplicationInitialized) {
        return;
    }

    gApplicationSuspended = true;
    _bRunning = FALSE;
    SeriousIOS_ApplicationSetStage("shutdown-entry");
    SeriousIOS_DiagnosticsWriteSummary("application-shutdown-entry");
    if (_pGame != nullptr && _pGame->gm_bGameOn) {
        _pGame->StopGame();
    }
    try {
        End();
    } catch (...) {
        setError("Serious Sam application shutdown threw an exception");
    }

    // Match CTSTREAM_END only after upstream End has released all application
    // streams and stream-backed resources.
    disableMainThreadStreamHandling();
    gApplicationInitialized = false;
    SeriousIOS_ApplicationSetStage("stopped");
    writeCheckpoint("stopped");
    SeriousIOS_DiagnosticsWriteSummary("application-stopped");
}

extern "C" bool SeriousIOS_ApplicationIsInitialized(void) {
    return gApplicationInitialized;
}

extern "C" const char* SeriousIOS_ApplicationGetError(void) {
    return gApplicationError;
}
