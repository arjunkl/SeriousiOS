#include <SDL.h>

#include <atomic>
#include <cstdarg>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <dlfcn.h>
#include <mach/mach_time.h>
#include <time.h>

#ifdef SDL_memset
#undef SDL_memset
#endif
#ifdef SDL_free
#undef SDL_free
#endif
#ifdef SDL_snprintf
#undef SDL_snprintf
#endif

namespace {

const char* kSeriousIOSError =
    "SeriousiOS SDL compatibility service is not available in the current host";

using PresentCallback = void (*)(void* context);

std::atomic<int> gWindowWidth{0};
std::atomic<int> gWindowHeight{0};
std::atomic<int> gSwapInterval{0};
std::atomic<int> gCursorState{SDL_ENABLE};
std::atomic<int> gJoystickEventState{SDL_ENABLE};
std::atomic<Uint32> gNextUserEvent{SDL_USEREVENT};
std::atomic<int> gNextTimerId{1};
std::atomic<PresentCallback> gPresentCallback{nullptr};
std::atomic<void*> gPresentContext{nullptr};
Uint8 gKeyboardState[SDL_NUM_SCANCODES] = {};

void writeZero(int* value) {
    if (value != nullptr) {
        *value = 0;
    }
}

char* duplicatePath(const char* value) {
    if (value == nullptr) {
        return nullptr;
    }
    const size_t size = std::strlen(value) + 1;
    char* result = static_cast<char*>(std::malloc(size));
    if (result != nullptr) {
        std::memcpy(result, value, size);
    }
    return result;
}

} // namespace

extern "C" {

void SeriousIOS_SetSDLWindowSize(int width, int height) {
    gWindowWidth.store(width > 0 ? width : 0, std::memory_order_relaxed);
    gWindowHeight.store(height > 0 ? height : 0, std::memory_order_relaxed);
}

void SeriousIOS_SetPresentCallback(PresentCallback callback, void* context) {
    gPresentContext.store(context, std::memory_order_release);
    gPresentCallback.store(callback, std::memory_order_release);
}

int SDLCALL SDL_Init(Uint32 flags) {
    (void)flags;
    return 0;
}

void SDLCALL SDL_Quit(void) {
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

SDL_TimerID SDLCALL SDL_AddTimer(
    Uint32 interval,
    SDL_TimerCallback callback,
    void* parameter) {
    (void)interval;
    (void)callback;
    (void)parameter;
    return gNextTimerId.fetch_add(1, std::memory_order_relaxed);
}

SDL_bool SDLCALL SDL_RemoveTimer(SDL_TimerID timer) {
    return timer > 0 ? SDL_TRUE : SDL_FALSE;
}

Uint32 SDLCALL SDL_RegisterEvents(int count) {
    if (count <= 0) {
        return static_cast<Uint32>(-1);
    }
    const Uint32 first = gNextUserEvent.fetch_add(
        static_cast<Uint32>(count), std::memory_order_relaxed);
    if (first > SDL_LASTEVENT || first + static_cast<Uint32>(count) > SDL_LASTEVENT) {
        return static_cast<Uint32>(-1);
    }
    return first;
}

void* SDLCALL SDL_GL_GetProcAddress(const char* procedure) {
    return procedure == nullptr ? nullptr : dlsym(RTLD_DEFAULT, procedure);
}

int SDLCALL SDL_GL_LoadLibrary(const char* path) {
    (void)path;
    return 0;
}

SDL_GLContext SDLCALL SDL_GL_CreateContext(SDL_Window* window) {
    (void)window;
    // The UIKit host owns the EAGLContext. Return a stable non-null token so
    // Serious Engine's SDL abstraction can retain its normal lifecycle.
    return reinterpret_cast<SDL_GLContext>(gPresentContext.load(std::memory_order_acquire));
}

void SDLCALL SDL_GL_DeleteContext(SDL_GLContext context) {
    (void)context;
}

int SDLCALL SDL_GL_MakeCurrent(SDL_Window* window, SDL_GLContext context) {
    (void)window;
    (void)context;
    return 0;
}

int SDLCALL SDL_GL_SetAttribute(SDL_GLattr attribute, int value) {
    (void)attribute;
    (void)value;
    return 0;
}

int SDLCALL SDL_GL_GetAttribute(SDL_GLattr attribute, int* value) {
    (void)attribute;
    writeZero(value);
    return 0;
}

int SDLCALL SDL_GL_SetSwapInterval(int interval) {
    if (interval < -1 || interval > 1) {
        return -1;
    }
    gSwapInterval.store(interval, std::memory_order_relaxed);
    return 0;
}

int SDLCALL SDL_GL_GetSwapInterval(void) {
    return gSwapInterval.load(std::memory_order_relaxed);
}

void SDLCALL SDL_GL_SwapWindow(SDL_Window* window) {
    (void)window;
    PresentCallback callback = gPresentCallback.load(std::memory_order_acquire);
    void* context = gPresentContext.load(std::memory_order_acquire);
    if (callback != nullptr) {
        callback(context);
    }
}

void SDLCALL SDL_GL_GetDrawableSize(SDL_Window* window, int* width, int* height) {
    SDL_GetWindowSize(window, width, height);
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

Uint32 SDLCALL SDL_GetWindowFlags(SDL_Window* window) {
    (void)window;
    return SDL_WINDOW_OPENGL | SDL_WINDOW_SHOWN | SDL_WINDOW_FULLSCREEN;
}

void SDLCALL SDL_DestroyWindow(SDL_Window* window) {
    (void)window;
}

int SDLCALL SDL_GetDesktopDisplayMode(int displayIndex, SDL_DisplayMode* mode) {
    if (displayIndex != 0 || mode == nullptr) {
        return -1;
    }
    std::memset(mode, 0, sizeof(*mode));
    mode->format = SDL_PIXELFORMAT_RGBA8888;
    mode->w = gWindowWidth.load(std::memory_order_relaxed);
    mode->h = gWindowHeight.load(std::memory_order_relaxed);
    mode->refresh_rate = 60;
    return 0;
}

int SDLCALL SDL_GetNumDisplayModes(int displayIndex) {
    return displayIndex == 0 ? 1 : -1;
}

int SDLCALL SDL_GetDisplayMode(int displayIndex, int modeIndex, SDL_DisplayMode* mode) {
    return modeIndex == 0 ? SDL_GetDesktopDisplayMode(displayIndex, mode) : -1;
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

int SDLCALL SDL_ShowMessageBox(
    const SDL_MessageBoxData* messageBoxData,
    int* buttonId) {
    if (buttonId != nullptr) {
        *buttonId = -1;
    }
    if (messageBoxData != nullptr) {
        std::fprintf(
            stderr,
            "SeriousiOS message: %s: %s\n",
            messageBoxData->title == nullptr ? "Serious Engine" : messageBoxData->title,
            messageBoxData->message == nullptr ? "" : messageBoxData->message);
    }
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

const char* SDLCALL SDL_JoystickNameForIndex(int deviceIndex) {
    (void)deviceIndex;
    return "SeriousiOS virtual input";
}

SDL_Joystick* SDLCALL SDL_JoystickOpen(int deviceIndex) {
    (void)deviceIndex;
    return nullptr;
}

void SDLCALL SDL_JoystickClose(SDL_Joystick* joystick) {
    (void)joystick;
}

int SDLCALL SDL_JoystickNumAxes(SDL_Joystick* joystick) {
    (void)joystick;
    return 0;
}

int SDLCALL SDL_JoystickNumButtons(SDL_Joystick* joystick) {
    (void)joystick;
    return 0;
}

int SDLCALL SDL_JoystickNumHats(SDL_Joystick* joystick) {
    (void)joystick;
    return 0;
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

const char* SDLCALL SDL_GetCurrentAudioDriver(void) {
    return "SeriousiOS";
}

int SDLCALL SDL_GetNumAudioDevices(int isCapture) {
    return isCapture == 0 ? 1 : 0;
}

const char* SDLCALL SDL_GetAudioDeviceName(int index, int isCapture) {
    return index == 0 && isCapture == 0 ? "SeriousiOS Audio" : nullptr;
}

SDL_AudioDeviceID SDLCALL SDL_OpenAudioDevice(
    const char* device,
    int isCapture,
    const SDL_AudioSpec* desired,
    SDL_AudioSpec* obtained,
    int allowedChanges) {
    (void)device;
    (void)allowedChanges;
    if (isCapture != 0 || desired == nullptr) {
        return 0;
    }
    if (obtained != nullptr) {
        *obtained = *desired;
    }
    return 1;
}

void SDLCALL SDL_CloseAudioDevice(SDL_AudioDeviceID device) {
    (void)device;
}

void SDLCALL SDL_PauseAudioDevice(SDL_AudioDeviceID device, int pauseOn) {
    (void)device;
    (void)pauseOn;
}

void SDLCALL SDL_LockAudioDevice(SDL_AudioDeviceID device) {
    (void)device;
}

void SDLCALL SDL_UnlockAudioDevice(SDL_AudioDeviceID device) {
    (void)device;
}

char* SDLCALL SDL_GetBasePath(void) {
    return duplicatePath("./");
}

char* SDLCALL SDL_GetPrefPath(const char* organization, const char* application) {
    (void)organization;
    (void)application;
    return duplicatePath("./Documents/");
}

void SDLCALL SDL_free(void* memory) {
    std::free(memory);
}

int SDLCALL SDL_snprintf(char* text, size_t maxLength, const char* format, ...) {
    va_list arguments;
    va_start(arguments, format);
    const int result = std::vsnprintf(text, maxLength, format, arguments);
    va_end(arguments);
    return result;
}

void* SDLCALL SDL_memset(void* destination, int value, size_t length) {
    return std::memset(destination, value, length);
}

} // extern "C"
