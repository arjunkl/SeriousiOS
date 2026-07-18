#include "SeriousIOSApplicationLifecycle.h"
#include "SeriousIOSDiagnostics.h"
#include "SeriousIOSPlatformBridge.h"

#include <Engine/Engine.h>
#include <Engine/Base/SDL/SDLEvents.h>
#include <GameMP/Game.h>
#include <SeriousSam/Menu.h>
#include <SeriousSam/SeriousSam.h>

extern BOOL bMenuActive;

extern "C" bool SeriousIOS_ApplicationGameplayControlsActive(void) {
    return SeriousIOS_ApplicationIsInitialized()
        && _pGame != nullptr
        && _pGame->gm_bGameOn != FALSE
        && bMenuActive == FALSE;
}

extern "C" void SeriousIOS_ApplicationProcessInputEvents(void) {
    if (!SeriousIOS_ApplicationIsInitialized() || _pGame == nullptr) {
        return;
    }

    MSG message;
    while (PeekMessage(&message, nullptr, 0, 0, PM_REMOVE)) {
        const bool escapePressed =
            message.message == WM_KEYDOWN && message.wParam == VK_ESCAPE;

        if (escapePressed
            && (_gmRunningGameMode == GM_DEMO || _gmRunningGameMode == GM_INTRO)) {
            _pGame->StopGame();
            _gmRunningGameMode = GM_NONE;
            SeriousIOS_ReleaseSDLInput();
            SeriousIOS_DiagnosticsLog(
                "input",
                "gameplay_escape action=stop_intro_or_demo");
            continue;
        }

        if (escapePressed && !bMenuActive) {
            StartMenus();
            SeriousIOS_ReleaseSDLInput();
            SeriousIOS_DiagnosticsLog(
                "input",
                "gameplay_escape action=open_pause_menu game_on=%d",
                _pGame->gm_bGameOn != FALSE);
            continue;
        }

        if (bMenuActive) {
            if (message.message == WM_KEYDOWN) {
                MenuOnKeyDown(message.wParam);
            } else if (message.message == WM_LBUTTONDOWN) {
                MenuOnKeyDown(VK_LBUTTON);
            } else if (message.message == WM_RBUTTONDOWN) {
                MenuOnKeyDown(VK_RBUTTON);
            } else if (message.message == WM_MOUSEMOVE) {
                MenuOnMouseMove(
                    static_cast<PIX>(LOWORD(message.lParam)),
                    static_cast<PIX>(HIWORD(message.lParam)));
            } else if (message.message == WM_CHAR) {
                MenuOnChar(message);
            }
        }
    }
}
