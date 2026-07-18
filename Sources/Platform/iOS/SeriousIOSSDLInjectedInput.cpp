#include "SeriousIOSPlatformBridge.h"

#include <SDL.h>

#include <array>
#include <atomic>
#include <deque>
#include <mutex>

namespace {

std::mutex gInputMutex;
std::deque<SDL_Event> gEventQueue;
std::array<Uint8, SDL_NUM_SCANCODES> gKeyboardState{};
std::array<SDL_Keycode, SDL_NUM_SCANCODES> gKeycodes{};
std::atomic<int> gRelativeMouseX{0};
std::atomic<int> gRelativeMouseY{0};
Uint32 gInjectedMouseButtons = 0;

SDL_Scancode scancodeForKey(SDL_Keycode key) {
    if (key >= SDLK_a && key <= SDLK_z) {
        return static_cast<SDL_Scancode>(
            SDL_SCANCODE_A + static_cast<int>(key - SDLK_a));
    }
    if (key >= SDLK_1 && key <= SDLK_9) {
        return static_cast<SDL_Scancode>(
            SDL_SCANCODE_1 + static_cast<int>(key - SDLK_1));
    }
    switch (key) {
        case SDLK_0: return SDL_SCANCODE_0;
        case SDLK_ESCAPE: return SDL_SCANCODE_ESCAPE;
        case SDLK_RETURN: return SDL_SCANCODE_RETURN;
        case SDLK_SPACE: return SDL_SCANCODE_SPACE;
        case SDLK_LCTRL: return SDL_SCANCODE_LCTRL;
        case SDLK_RCTRL: return SDL_SCANCODE_RCTRL;
        case SDLK_LSHIFT: return SDL_SCANCODE_LSHIFT;
        case SDLK_RSHIFT: return SDL_SCANCODE_RSHIFT;
        case SDLK_LALT: return SDL_SCANCODE_LALT;
        case SDLK_RALT: return SDL_SCANCODE_RALT;
        case SDLK_UP: return SDL_SCANCODE_UP;
        case SDLK_DOWN: return SDL_SCANCODE_DOWN;
        case SDLK_LEFT: return SDL_SCANCODE_LEFT;
        case SDLK_RIGHT: return SDL_SCANCODE_RIGHT;
        case SDLK_PAUSE: return SDL_SCANCODE_PAUSE;
        case SDLK_LEFTBRACKET: return SDL_SCANCODE_LEFTBRACKET;
        case SDLK_RIGHTBRACKET: return SDL_SCANCODE_RIGHTBRACKET;
        default: break;
    }
    if ((key & SDLK_SCANCODE_MASK) != 0) {
        const int raw = static_cast<int>(key & ~SDLK_SCANCODE_MASK);
        if (raw > SDL_SCANCODE_UNKNOWN && raw < SDL_NUM_SCANCODES) {
            return static_cast<SDL_Scancode>(raw);
        }
    }
    return SDL_SCANCODE_UNKNOWN;
}

void appendKeyEventLocked(SDL_Keycode key, SDL_Scancode scancode, bool pressed) {
    SDL_Event event{};
    event.type = pressed ? SDL_KEYDOWN : SDL_KEYUP;
    event.key.type = event.type;
    event.key.state = pressed ? SDL_PRESSED : SDL_RELEASED;
    event.key.repeat = 0;
    event.key.keysym.scancode = scancode;
    event.key.keysym.sym = key;
    event.key.keysym.mod = KMOD_NONE;
    gEventQueue.push_back(event);
}

void appendMouseButtonEventLocked(uint8_t button, bool pressed) {
    SDL_Event event{};
    event.type = pressed ? SDL_MOUSEBUTTONDOWN : SDL_MOUSEBUTTONUP;
    event.button.type = event.type;
    event.button.button = button;
    event.button.state = pressed ? SDL_PRESSED : SDL_RELEASED;
    event.button.clicks = 1;
    gEventQueue.push_back(event);
}

} // namespace

extern "C" void SeriousIOS_QueueSDLKey(int keycode, bool pressed) {
    const SDL_Keycode key = static_cast<SDL_Keycode>(keycode);
    const SDL_Scancode scancode = scancodeForKey(key);
    if (scancode == SDL_SCANCODE_UNKNOWN) {
        return;
    }

    std::lock_guard<std::mutex> lock(gInputMutex);
    const size_t index = static_cast<size_t>(scancode);
    const bool wasPressed = gKeyboardState[index] != 0;
    if (wasPressed == pressed) {
        return;
    }
    gKeyboardState[index] = pressed ? 1 : 0;
    gKeycodes[index] = key;
    appendKeyEventLocked(key, scancode, pressed);
}

extern "C" void SeriousIOS_QueueSDLMouseButton(uint8_t button, bool pressed) {
    if (button == 0 || button > 5) {
        return;
    }

    int mouseX = 0;
    int mouseY = 0;
    const Uint32 currentButtons = SDL_GetMouseState(&mouseX, &mouseY);
    const Uint32 mask = SDL_BUTTON(button);

    {
        std::lock_guard<std::mutex> lock(gInputMutex);
        const bool wasPressed = (gInjectedMouseButtons & mask) != 0;
        if (wasPressed == pressed) {
            return;
        }
        if (pressed) {
            gInjectedMouseButtons |= mask;
        } else {
            gInjectedMouseButtons &= ~mask;
        }
        appendMouseButtonEventLocked(button, pressed);
    }

    const Uint32 externalButtons = currentButtons & ~mask;
    SeriousIOS_SetSDLMouseState(
        mouseX,
        mouseY,
        externalButtons | (pressed ? mask : 0));
}

extern "C" void SeriousIOS_AddSDLRelativeMouseDelta(int deltaX, int deltaY) {
    gRelativeMouseX.fetch_add(deltaX, std::memory_order_relaxed);
    gRelativeMouseY.fetch_add(deltaY, std::memory_order_relaxed);
}

extern "C" void SeriousIOS_ReleaseSDLInput(void) {
    int mouseX = 0;
    int mouseY = 0;
    SDL_GetMouseState(&mouseX, &mouseY);

    {
        std::lock_guard<std::mutex> lock(gInputMutex);
        for (size_t index = 1; index < gKeyboardState.size(); ++index) {
            if (gKeyboardState[index] == 0) {
                continue;
            }
            const SDL_Keycode key = gKeycodes[index];
            const SDL_Scancode scancode = static_cast<SDL_Scancode>(index);
            gKeyboardState[index] = 0;
            appendKeyEventLocked(key, scancode, false);
        }
        for (uint8_t button = 1; button <= 5; ++button) {
            const Uint32 mask = SDL_BUTTON(button);
            if ((gInjectedMouseButtons & mask) != 0) {
                appendMouseButtonEventLocked(button, false);
            }
        }
        gInjectedMouseButtons = 0;
    }

    gRelativeMouseX.store(0, std::memory_order_relaxed);
    gRelativeMouseY.store(0, std::memory_order_relaxed);
    SeriousIOS_SetSDLMouseState(mouseX, mouseY, 0);
}

extern "C" const Uint8* SDLCALL SDL_GetKeyboardState(int* keyCount) {
    if (keyCount != nullptr) {
        *keyCount = SDL_NUM_SCANCODES;
    }
    return gKeyboardState.data();
}

extern "C" SDL_Scancode SDLCALL SDL_GetScancodeFromKey(SDL_Keycode key) {
    return scancodeForKey(key);
}

extern "C" Uint32 SDLCALL SDL_GetRelativeMouseState(int* x, int* y) {
    if (x != nullptr) {
        *x = gRelativeMouseX.exchange(0, std::memory_order_acq_rel);
    } else {
        gRelativeMouseX.store(0, std::memory_order_release);
    }
    if (y != nullptr) {
        *y = gRelativeMouseY.exchange(0, std::memory_order_acq_rel);
    } else {
        gRelativeMouseY.store(0, std::memory_order_release);
    }
    return SDL_GetMouseState(nullptr, nullptr);
}

extern "C" int SDLCALL SDL_PollEvent(SDL_Event* event) {
    if (event == nullptr) {
        return 0;
    }
    std::lock_guard<std::mutex> lock(gInputMutex);
    if (gEventQueue.empty()) {
        return 0;
    }
    *event = gEventQueue.front();
    gEventQueue.pop_front();
    return 1;
}
