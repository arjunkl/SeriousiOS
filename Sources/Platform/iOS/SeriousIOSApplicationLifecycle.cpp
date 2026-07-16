#include "SeriousIOSApplicationLifecycle.h"
#include "SeriousIOSPlatformBridge.h"

#include <Engine/Engine.h>
#include <GameMP/Game.h>
#include <SeriousSam/Menu.h>
#include <SeriousSam/SeriousSam.h>

#include <SDL.h>

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
    if (!SeriousIOS_ArePathsConfigured()
        || SeriousIOS_MakeGLContextCurrent() != 0) {
        return false;
    }

    configureInitialDisplayMode();
    sam_bAutoPlayDemos = FALSE;

    try {
        if (!Init(nullptr, 0, CTString(""))) {
            return false;
        }
    } catch (...) {
        return false;
    }

    _bRunning = TRUE;
    _bQuitScreen = FALSE;
    if (!bMenuActive) {
        StartMenus();
    }
    bMenuRendering = TRUE;
    gApplicationSuspended = false;
    gApplicationInitialized = true;
    return true;
}

extern "C" bool SeriousIOS_ApplicationFrame(void) {
    if (!gApplicationInitialized || gApplicationSuspended || !_bRunning) {
        return false;
    }
    if (SeriousIOS_MakeGLContextCurrent() != 0 || _pGame == nullptr) {
        return false;
    }

    _bWindowChanging = FALSE;
    UpdateInputEnabledState();
    _pGame->gm_bMenuOn = bMenuActive;
    DoGame();
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
}

extern "C" void SeriousIOS_ApplicationResume(void) {
    if (!gApplicationInitialized || !gApplicationSuspended) {
        return;
    }
    if (_pNetwork != nullptr) {
        _pNetwork->SetLocalPause(FALSE);
    }
    gApplicationSuspended = false;
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
    End();
    gApplicationInitialized = false;
}

extern "C" bool SeriousIOS_ApplicationIsInitialized(void) {
    return gApplicationInitialized;
}
