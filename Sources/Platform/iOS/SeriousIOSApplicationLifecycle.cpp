#include "SeriousIOSApplicationLifecycle.h"
#include "SeriousIOSPlatformBridge.h"

#include <Engine/Engine.h>
#include <GameMP/Game.h>
#include <SeriousSam/Menu.h>
#include <SeriousSam/SeriousSam.h>

#include <SDL.h>

#include <cstdio>

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
char gApplicationError[1024] = {};

void setError(const char* message) {
    std::snprintf(
        gApplicationError,
        sizeof(gApplicationError),
        "%s",
        message == nullptr ? "Unknown Serious Sam application failure" : message);
    gApplicationError[sizeof(gApplicationError) - 1] = '\0';
}

void writeCheckpoint(const char* state) {
    const char* temporaryPath = SeriousIOS_GetTemporaryPath();
    if (temporaryPath == nullptr || *temporaryPath == '\0') {
        return;
    }

    char markerPath[2048] = {};
    std::snprintf(
        markerPath,
        sizeof(markerPath),
        "%sapplication-runtime-checkpoint.txt",
        temporaryPath);
    markerPath[sizeof(markerPath) - 1] = '\0';

    FILE* marker = std::fopen(markerPath, "wb");
    if (marker == nullptr) {
        return;
    }
    std::fprintf(marker, "state=%s\n", state == nullptr ? "unknown" : state);
    std::fprintf(marker, "error=%s\n", gApplicationError);
    std::fclose(marker);
}

bool fail(const char* message) {
    setError(message);
    writeCheckpoint("failed");
    return false;
}

void configureInitialDisplayMode() {
    int width = 0;
    int height = 0;
    SDL_GetWindowSize(nullptr, &width, &height);
    if (width <= 0 || height <= 0) {
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
}

} // namespace

extern "C" bool SeriousIOS_ApplicationInitialize(void) {
    if (gApplicationInitialized) {
        return true;
    }

    gApplicationError[0] = '\0';
    writeCheckpoint("starting");
    if (!SeriousIOS_ArePathsConfigured()) {
        return fail("SeriousiOS paths were not configured before application startup");
    }
    if (SeriousIOS_MakeGLContextCurrent() != 0) {
        return fail("SeriousiOS could not activate the EAGL context before application startup");
    }

    configureInitialDisplayMode();
    sam_bAutoPlayDemos = FALSE;

    try {
        if (!Init(nullptr, 0, CTString(""))) {
            return fail("The upstream Serious Sam Init function returned false");
        }
    } catch (const char* error) {
        return fail(error);
    } catch (...) {
        return fail("Serious Sam application initialization threw an unknown exception");
    }

    _bRunning = TRUE;
    _bQuitScreen = FALSE;
    if (!bMenuActive) {
        StartMenus();
    }
    bMenuRendering = TRUE;
    gApplicationSuspended = false;
    gApplicationInitialized = true;
    writeCheckpoint("initialized");
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
    writeCheckpoint("suspended");
}

extern "C" void SeriousIOS_ApplicationResume(void) {
    if (!gApplicationInitialized || !gApplicationSuspended) {
        return;
    }
    if (_pNetwork != nullptr) {
        _pNetwork->SetLocalPause(FALSE);
    }
    gApplicationSuspended = false;
    writeCheckpoint("initialized");
}

extern "C" void SeriousIOS_ApplicationShutdown(void) {
    if (!gApplicationInitialized) {
        return;
    }

    gApplicationSuspended = true;
    _bRunning = FALSE;
    if (_pGame != nullptr && _pGame->gm_bGameOn) {
        _pGame->StopGame();
    }
    try {
        End();
    } catch (...) {
        setError("Serious Sam application shutdown threw an exception");
    }
    gApplicationInitialized = false;
    writeCheckpoint("stopped");
}

extern "C" bool SeriousIOS_ApplicationIsInitialized(void) {
    return gApplicationInitialized;
}

extern "C" const char* SeriousIOS_ApplicationGetError(void) {
    return gApplicationError;
}
