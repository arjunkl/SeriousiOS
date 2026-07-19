#include "SeriousIOSInputBridge.h"
#include "SeriousIOSPlatformBridge.h"

#include <SDL.h>

#include <algorithm>
#include <cmath>
#include <cstdint>

namespace {

seriousios::InputBridge gVirtualController;
int gVirtualJoystickToken = 0;

SDL_Joystick* virtualJoystick() {
    return reinterpret_cast<SDL_Joystick*>(&gVirtualJoystickToken);
}

bool isVirtualJoystick(SDL_Joystick* joystick) {
    return joystick == virtualJoystick();
}

Sint16 axisValue(float value) {
    const float bounded = std::max(-1.0f, std::min(1.0f, value));
    const float scaled = bounded >= 0.0f ? bounded * 32767.0f : bounded * 32768.0f;
    return static_cast<Sint16>(std::lround(scaled));
}

bool validAction(SeriousIOSVirtualAction action) {
    return action >= SERIOUSIOS_ACTION_FIRE && action < SERIOUSIOS_ACTION_COUNT;
}

void routeAction(SeriousIOSVirtualAction action, bool pressed) {
    switch (action) {
        case SERIOUSIOS_ACTION_FIRE:
            SeriousIOS_QueueSDLMouseButton(SDL_BUTTON_LEFT, pressed);
            break;
        case SERIOUSIOS_ACTION_JUMP:
            SeriousIOS_QueueSDLKey(SDLK_SPACE, pressed);
            break;
        case SERIOUSIOS_ACTION_USE:
            SeriousIOS_QueueSDLKey(SDLK_RETURN, pressed);
            break;
        case SERIOUSIOS_ACTION_NEXT_WEAPON:
        case SERIOUSIOS_ACTION_PREVIOUS_WEAPON:
        case SERIOUSIOS_ACTION_COUNT:
            break;
    }
}

} // namespace

extern "C" void SeriousIOS_SetVirtualMovement(float forward, float right) {
    gVirtualController.setMovement(forward, right);
}

extern "C" void SeriousIOS_SetVirtualAction(
    SeriousIOSVirtualAction action,
    bool pressed) {
    if (!validAction(action)) {
        return;
    }

    const seriousios::InputSnapshot before = gVirtualController.snapshot();
    const std::size_t index = static_cast<std::size_t>(action);
    if (before.heldActions[index] == pressed) {
        return;
    }

    gVirtualController.setAction(index, pressed);
    routeAction(action, pressed);
}

extern "C" void SeriousIOS_ReleaseVirtualController(void) {
    const seriousios::InputSnapshot before = gVirtualController.snapshot();
    for (int rawAction = SERIOUSIOS_ACTION_FIRE;
         rawAction < SERIOUSIOS_ACTION_COUNT;
         ++rawAction) {
        const std::size_t index = static_cast<std::size_t>(rawAction);
        if (before.heldActions[index]) {
            routeAction(static_cast<SeriousIOSVirtualAction>(rawAction), false);
        }
    }
    gVirtualController.releaseAll();
}

extern "C" float SeriousIOS_GetVirtualMovementForward(void) {
    return gVirtualController.snapshot().moveForward;
}

extern "C" float SeriousIOS_GetVirtualMovementRight(void) {
    return gVirtualController.snapshot().moveRight;
}

extern "C" int SDLCALL SDL_NumJoysticks(void) {
    return 1;
}

extern "C" const char* SDLCALL SDL_JoystickNameForIndex(int joystickIndex) {
    return joystickIndex == 0 ? "SeriousiOS Virtual Touch Controller" : nullptr;
}

extern "C" SDL_Joystick* SDLCALL SDL_JoystickOpen(int joystickIndex) {
    return joystickIndex == 0 ? virtualJoystick() : nullptr;
}

extern "C" void SDLCALL SDL_JoystickClose(SDL_Joystick* joystick) {
    (void)joystick;
}

extern "C" int SDLCALL SDL_JoystickNumAxes(SDL_Joystick* joystick) {
    return isVirtualJoystick(joystick) ? 2 : 0;
}

extern "C" int SDLCALL SDL_JoystickNumButtons(SDL_Joystick* joystick) {
    return isVirtualJoystick(joystick) ? SERIOUSIOS_ACTION_COUNT : 0;
}

extern "C" int SDLCALL SDL_JoystickNumHats(SDL_Joystick* joystick) {
    return isVirtualJoystick(joystick) ? 0 : 0;
}

extern "C" SDL_JoystickID SDLCALL SDL_JoystickInstanceID(
    SDL_Joystick* joystick) {
    return isVirtualJoystick(joystick) ? 0 : static_cast<SDL_JoystickID>(-1);
}

extern "C" Sint16 SDLCALL SDL_JoystickGetAxis(
    SDL_Joystick* joystick,
    int axis) {
    if (!isVirtualJoystick(joystick)) {
        return 0;
    }

    const seriousios::InputSnapshot state = gVirtualController.snapshot();
    switch (axis) {
        case 0:
            // Serious Engine negates AXIS_MOVE_LR when creating the player action.
            return axisValue(-state.moveRight);
        case 1:
            // Positive touch-forward must reach the engine as the opposite raw axis
            // sign from strafe because AXIS_MOVE_FB has its own movement convention.
            return axisValue(state.moveForward);
        default:
            return 0;
    }
}

extern "C" Uint8 SDLCALL SDL_JoystickGetButton(
    SDL_Joystick* joystick,
    int button) {
    if (!isVirtualJoystick(joystick)
        || button < 0
        || button >= SERIOUSIOS_ACTION_COUNT) {
        return 0;
    }
    const seriousios::InputSnapshot state = gVirtualController.snapshot();
    return state.heldActions[static_cast<std::size_t>(button)]
        ? static_cast<Uint8>(1)
        : static_cast<Uint8>(0);
}
