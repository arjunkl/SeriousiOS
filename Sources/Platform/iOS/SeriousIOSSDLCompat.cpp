#include <SDL.h>

#include <atomic>
#include <cstdio>
#include <cstring>
#include <dlfcn.h>
#include <mach/mach_time.h>
#include <time.h>

#ifdef SDL_memset
#undef SDL_memset
#endif

namespace {

const char* kSeriousIOSError =
    "SeriousiOS SDL compatibility service is not available in the current host";

std::atomic<int> gWindowWidth{0};
std::atomic<int> gWindowHeight{0};
std::atomic<int> gSwapInterval{0};
std::atomic<int> gCursorState{SDL_ENABLE};
std::atomic<int> gJoystickEventState{SDL_ENABLE};
Uint8 gKeyboardState[SDL_NUM_SCANCODES] = {};

void writeZero(int* value) {
    if (value != nullptr) {
        *value = 0;
    }
}

} // namespace

extern "C" {

void SeriousIOS_SetSDLWindowSize(int width, int height) {
    gWindowWidth.store(width > 0 ? width : 0, std::memory_order_relaxed);
    gWindowHeight.store(height > 0 ? height : 0, std::memory_order_relaxed);
}

const char* SDLCALL SDL_GetError(void) {
    return kSeriousIOSError;
}

Uint64 SDLCALL SDL_GetPerformanceCounter(void) {
    return static_cast<Uint64>(mach_absolute_time());
}

Uint64 SDLCALL SDL_GetPerformanceFrequency(void) {
    mach_timebase_info_data_t timebase = {};
    if (mach_timebase_info(&timebase) != KERN_SUCCESS || timebase.numer == 0) {
        return 1000000000ULL;
    }

    const long double ticksPerSecond =
        1000000000.0L * static_cast<long double>(timebase.denom) /
        static_cast<long double>(timebase.numer);
    return static_cast<Uint64>(ticksPerSecond);
}

void SDLCALL SDL_Delay(Uint32 milliseconds) {
    struct timespec request = {};
    request.tv_sec = static_cast<time_t>(milliseconds / 1000U);
    request.tv_nsec = static_cast<long>((milliseconds % 1000U) * 1000000U);
    while (nanosleep(&request, &request) == -1) {
    }
}

void* SDLCALL SDL_GL_GetProcAddress(const char* procedure) {
    return procedure == nullptr ? nullptr : dlsym(RTLD_DEFAULT, procedure);
}

int SDLCALL SDL_GL_SetSwapInterval(int interval) {
    if (interval < -1 || interval > 1) {
        return -1;
    }
    gSwapInterval.store(interval, std::memory_order_relaxed);
    return 0;
}

void SDLCALL SDL_GL_SwapWindow(SDL_Window* window) {
    (void)window;
    // Presentation belongs to the EAGL-backed iOS render surface.
}

void SDLCALL SDL_GetWindowSize(SDL_Window* window, int* width, int* height) {
    (void)window;
    if (width != nullptr) {
        *width = gWindowWidth.load(std::memory_order_relaxed);
    }
    if (height != nullptr) {
        *height = gWindowHeight.load(std::memory_order_relaxed);
    }
}

void SDLCALL SDL_DestroyWindow(SDL_Window* window) {
    (void)window;
}

int SDLCALL SDL_ShowSimpleMessageBox(
    Uint32 flags,
    const char* title,
    const char* message,
    SDL_Window* window) {
    (void)flags;
    (void)window;
    std::fprintf(
        stderr,
        "SeriousiOS message: %s: %s\n",
        title == nullptr ? "Serious Engine" : title,
        message == nullptr ? "" : message);
    return 0;
}

const Uint8* SDLCALL SDL_GetKeyboardState(int* keyCount) {
    if (keyCount != nullptr) {
        *keyCount = SDL_NUM_SCANCODES;
    }
    return gKeyboardState;
}

SDL_Scancode SDLCALL SDL_GetScancodeFromKey(SDL_Keycode key) {
    if ((key & SDLK_SCANCODE_MASK) != 0) {
        return static_cast<SDL_Scancode>(key & ~SDLK_SCANCODE_MASK);
    }
    return SDL_SCANCODE_UNKNOWN;
}

Uint32 SDLCALL SDL_GetMouseState(int* x, int* y) {
    writeZero(x);
    writeZero(y);
    return 0;
}

Uint32 SDLCALL SDL_GetRelativeMouseState(int* x, int* y) {
    writeZero(x);
    writeZero(y);
    return 0;
}

int SDLCALL SDL_SetRelativeMouseMode(SDL_bool enabled) {
    (void)enabled;
    return 0;
}

int SDLCALL SDL_ShowCursor(int toggle) {
    if (toggle == SDL_ENABLE || toggle == SDL_DISABLE) {
        gCursorState.store(toggle, std::memory_order_relaxed);
    }
    return gCursorState.load(std::memory_order_relaxed);
}

int SDLCALL SDL_PollEvent(SDL_Event* event) {
    (void)event;
    // UIKit lifecycle and SeriousIOSInputBridge are the iOS event producers.
    return 0;
}

void SDLCALL SDL_Quit(void) {
}

int SDLCALL SDL_NumJoysticks(void) {
    return 0;
}

SDL_bool SDLCALL SDL_IsGameController(int joystickIndex) {
    (void)joystickIndex;
    return SDL_FALSE;
}

SDL_GameController* SDLCALL SDL_GameControllerOpen(int joystickIndex) {
    (void)joystickIndex;
    return nullptr;
}

SDL_Joystick* SDLCALL SDL_GameControllerGetJoystick(SDL_GameController* controller) {
    (void)controller;
    return nullptr;
}

SDL_JoystickID SDLCALL SDL_JoystickInstanceID(SDL_Joystick* joystick) {
    (void)joystick;
    return static_cast<SDL_JoystickID>(-1);
}

int SDLCALL SDL_JoystickEventState(int state) {
    if (state == SDL_ENABLE || state == SDL_IGNORE) {
        gJoystickEventState.store(state, std::memory_order_relaxed);
    }
    return gJoystickEventState.load(std::memory_order_relaxed);
}

Sint16 SDLCALL SDL_JoystickGetAxis(SDL_Joystick* joystick, int axis) {
    (void)joystick;
    (void)axis;
    return 0;
}

Uint8 SDLCALL SDL_JoystickGetButton(SDL_Joystick* joystick, int button) {
    (void)joystick;
    (void)button;
    return 0;
}

void SDLCALL SDL_LockAudioDevice(SDL_AudioDeviceID device) {
    (void)device;
}

void SDLCALL SDL_UnlockAudioDevice(SDL_AudioDeviceID device) {
    (void)device;
}

void* SDLCALL SDL_memset(void* destination, int value, size_t length) {
    return std::memset(destination, value, length);
}

} // extern "C"
