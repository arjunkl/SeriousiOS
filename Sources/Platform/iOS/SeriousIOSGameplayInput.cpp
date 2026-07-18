#include "SeriousIOSApplicationLifecycle.h"
#include "SeriousIOSDiagnostics.h"
#include "SeriousIOSPlatformBridge.h"

#include <Engine/Engine.h>
#include <Engine/Base/Input.h>
#include <Engine/Base/SDL/SDLEvents.h>
#include <GameMP/Game.h>
#include <SeriousSam/Menu.h>
#include <SeriousSam/SeriousSam.h>

extern BOOL bMenuActive;

namespace {

bool gVirtualMovementLogged = false;

void configureVirtualMovementAxis(CAxisAction& axis, INDEX sourceAxis) {
    axis.aa_iAxisAction = sourceAxis;
    axis.aa_fSensitivity = 50.0f;
    axis.aa_fDeadZone = 0.0f;
    axis.aa_bInvert = FALSE;
    axis.aa_bRelativeControler = TRUE;
    axis.aa_bSmooth = FALSE;
    axis.aa_fLastReading = 0.0f;
    axis.aa_fAbsolute = 0.0f;
}

void configureVirtualMovementControls() {
    if (_pGame == nullptr || _pInput == nullptr) {
        return;
    }

    const INDEX moveRightAxis = FIRST_JOYAXIS;
    const INDEX moveForwardAxis = FIRST_JOYAXIS + 1;
    bool changed = false;

    for (INDEX player = 0; player < 8; ++player) {
        CControls& controls = _pGame->gm_actrlControls[player];
        CAxisAction& moveRight = controls.ctrl_aaAxisActions[AXIS_MOVE_LR];
        CAxisAction& moveForward = controls.ctrl_aaAxisActions[AXIS_MOVE_FB];
        if (moveRight.aa_iAxisAction != moveRightAxis
            || moveForward.aa_iAxisAction != moveForwardAxis) {
            configureVirtualMovementAxis(moveRight, moveRightAxis);
            configureVirtualMovementAxis(moveForward, moveForwardAxis);
            controls.CalculateInfluencesForAllAxis();
            changed = true;
        }
    }

    _pInput->SetJoyPolling(TRUE);
    if ((changed || !gVirtualMovementLogged) && !gVirtualMovementLogged) {
        gVirtualMovementLogged = true;
        SeriousIOS_DiagnosticsLog(
            "input",
            "virtual_controller_configured joystick=0 strafe_axis=%d forward_axis=%d analog=1",
            static_cast<int>(moveRightAxis),
            static_cast<int>(moveForwardAxis));
    }
}

} // namespace

extern "C" bool SeriousIOS_ApplicationGameplayControlsActive(void) {
    return SeriousIOS_ApplicationIsInitialized()
        && _pGame != nullptr
        && _pGame->gm_bGameOn != FALSE
        && bMenuActive == FALSE;
}

extern "C" bool SeriousIOS_ApplicationComputerActive(void) {
    return SeriousIOS_ApplicationIsInitialized()
        && _pGame != nullptr
        && _pGame->gm_bGameOn != FALSE
        && _pGame->gm_csComputerState != CS_OFF;
}

extern "C" void SeriousIOS_ApplicationProcessInputEvents(void) {
    if (!SeriousIOS_ApplicationIsInitialized() || _pGame == nullptr) {
        return;
    }

    if (SeriousIOS_ApplicationGameplayControlsActive()) {
        configureVirtualMovementControls();
    } else {
        SeriousIOS_SetVirtualMovement(0.0f, 0.0f);
    }

    MSG message;
    while (PeekMessage(&message, nullptr, 0, 0, PM_REMOVE)) {
        const bool escapePressed =
            message.message == WM_KEYDOWN && message.wParam == VK_ESCAPE;

        if (escapePressed && _pGame->gm_csComputerState != CS_OFF) {
            const int previousState = static_cast<int>(_pGame->gm_csComputerState);
            _pGame->ComputerForceOff();
            SeriousIOS_ReleaseVirtualController();
            SeriousIOS_ReleaseSDLInput();
            SeriousIOS_DiagnosticsLog(
                "input",
                "gameplay_escape action=close_computer previous_state=%d",
                previousState);
            continue;
        }

        if (escapePressed
            && (_gmRunningGameMode == GM_DEMO || _gmRunningGameMode == GM_INTRO)) {
            _pGame->StopGame();
            _gmRunningGameMode = GM_NONE;
            SeriousIOS_ReleaseVirtualController();
            SeriousIOS_ReleaseSDLInput();
            SeriousIOS_DiagnosticsLog(
                "input",
                "gameplay_escape action=stop_intro_or_demo");
            continue;
        }

        if (escapePressed && !bMenuActive) {
            StartMenus();
            SeriousIOS_ReleaseVirtualController();
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
