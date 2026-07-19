#include "SeriousIOSPlatformBridge.h"

#include <SDL.h>

#include <algorithm>
#include <atomic>
#include <chrono>
#include <cstdarg>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <dlfcn.h>
#include <mach/mach_time.h>
#include <memory>
#include <mutex>
#include <thread>
#include <time.h>
#include <unordered_map>
#include <vector>

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
    "SeriousiOS compatibility service is not available in the current host";
const char* kAudioDriverName = "seriousios-virtual-audio";
const char* kAudioDeviceName = "SeriousiOS Virtual Output";

using PresentCallback = void (*)(void* context);

std::atomic<int> gWindowWidth{0};
std::atomic<int> gWindowHeight{0};
std::atomic<int> gSwapInterval{0};
std::atomic<int> gCursorState{SDL_ENABLE};
std::atomic<int> gJoystickEventState{SDL_ENABLE};
std::atomic<PresentCallback> gPresentCallback{nullptr};
std::atomic<void*> gPresentContext{nullptr};
std::atomic<Uint32> gNextUserEvent{SDL_USEREVENT};
std::atomic<int> gNextTimerID{1};
std::atomic<SDL_AudioDeviceID> gNextAudioDeviceID{1};
Uint8 gKeyboardState[SDL_NUM_SCANCODES] = {};

std::mutex gGLAttributeMutex;
std::unordered_map<int, int> gGLAttributes;

struct TimerState {
    std::atomic<bool> cancelled{false};
};
std::mutex gTimerMutex;
std::unordered_map<int, std::shared_ptr<TimerState>> gTimers;

struct AudioDeviceState {
    SDL_AudioSpec specification = {};
    std::atomic<bool> paused{true};
    std::atomic<bool> cancelled{false};
    std::recursive_mutex callbackMutex;
};
std::mutex gAudioDeviceMutex;
std::unordered_map<SDL_AudioDeviceID, std::shared_ptr<AudioDeviceState>> gAudioDevices;

void writeZero(int* value) {
    if (value != nullptr) {
        *value = 0;
    }
}

void fillDisplayMode(SDL_DisplayMode* mode) {
    if (mode == nullptr) {
        return;
    }
    mode->format = SDL_PIXELFORMAT_RGBA8888;
    mode->w = gWindowWidth.load(std::memory_order_relaxed);
    mode->h = gWindowHeight.load(std::memory_order_relaxed);
    if (mode->w <= 0) {
        mode->w = 1920;
    }
    if (mode->h <= 0) {
        mode->h = 1080;
    }
    mode->refresh_rate = 60;
    mode->driverdata = nullptr;
}

std::shared_ptr<AudioDeviceState> audioDevice(SDL_AudioDeviceID device) {
    std::lock_guard<std::mutex> lock(gAudioDeviceMutex);
    const auto iterator = gAudioDevices.find(device);
    return iterator == gAudioDevices.end() ? nullptr : iterator->second;
}

void runAudioDevice(const std::shared_ptr<AudioDeviceState>& state) {
    const int frequency = state->specification.freq > 0
        ? state->specification.freq
        : 44100;
    const int sampleCount = state->specification.samples > 0
        ? state->specification.samples
        : 2048;
    const auto period = std::chrono::microseconds(
        static_cast<long long>(sampleCount) * 1000000LL / frequency);
    std::vector<Uint8> buffer(state->specification.size, state->specification.silence);

    while (!state->cancelled.load(std::memory_order_acquire)) {
        std::this_thread::sleep_for(period);
        if (state->paused.load(std::memory_order_acquire)
            || state->specification.callback == nullptr) {
            continue;
        }

        std::lock_guard<std::recursive_mutex> lock(state->callbackMutex);
        std::fill(buffer.begin(), buffer.end(), state->specification.silence);
        state->specification.callback(
            state->specification.userdata,
            buffer.data(),
            static_cast<int>(buffer.size()));
    }
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

Uint32 SDLCALL SDL_RegisterEvents(int eventCount) {
    if (eventCount <= 0) {
        return static_cast<Uint32>(-1);
    }
    const Uint32 first = gNextUserEvent.fetch_add(
        static_cast<Uint32>(eventCount),
        std::memory_order_relaxed);
    if (first > static_cast<Uint32>(SDL_LASTEVENT - eventCount)) {
        return static_cast<Uint32>(-1);
    }
    return first;
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
    if (interval == 0 || callback == nullptr) {
        return 0;
    }

    const int timerID = gNextTimerID.fetch_add(1, std::memory_order_relaxed);
    auto state = std::make_shared<TimerState>();
    {
        std::lock_guard<std::mutex> lock(gTimerMutex);
        gTimers.emplace(timerID, state);
    }

    std::thread([timerID, interval, callback, parameter, state] {
        Uint32 nextInterval = interval;
        while (!state->cancelled.load(std::memory_order_acquire)
            && nextInterval != 0) {
            std::this_thread::sleep_for(std::chrono::milliseconds(nextInterval));
            if (state->cancelled.load(std::memory_order_acquire)) {
                break;
            }
            nextInterval = callback(nextInterval, parameter);
        }
        std::lock_guard<std::mutex> lock(gTimerMutex);
        gTimers.erase(timerID);
    }).detach();

    return timerID;
}

SDL_bool SDLCALL SDL_RemoveTimer(SDL_TimerID timerID) {
    std::shared_ptr<TimerState> state;
    {
        std::lock_guard<std::mutex> lock(gTimerMutex);
        const auto iterator = gTimers.find(timerID);
        if (iterator == gTimers.end()) {
            return SDL_FALSE;
        }
        state = iterator->second;
        gTimers.erase(iterator);
    }
    state->cancelled.store(true, std::memory_order_release);
    return SDL_TRUE;
}

int SDLCALL SDL_GL_LoadLibrary(const char* path) {
    (void)path;
    return 0;
}

void* SDLCALL SDL_GL_GetProcAddress(const char* procedure) {
    return procedure == nullptr ? nullptr : dlsym(RTLD_DEFAULT, procedure);
}

int SDLCALL SDL_GL_SetAttribute(SDL_GLattr attribute, int value) {
    std::lock_guard<std::mutex> lock(gGLAttributeMutex);
    gGLAttributes[static_cast<int>(attribute)] = value;
    return 0;
}

int SDLCALL SDL_GL_GetAttribute(SDL_GLattr attribute, int* value) {
    if (value == nullptr) {
        return -1;
    }
    std::lock_guard<std::mutex> lock(gGLAttributeMutex);
    const auto iterator = gGLAttributes.find(static_cast<int>(attribute));
    *value = iterator == gGLAttributes.end() ? 0 : iterator->second;
    return 0;
}

SDL_GLContext SDLCALL SDL_GL_CreateContext(SDL_Window* window) {
    (void)window;
    return SeriousIOS_MakeGLContextCurrent() == 0
        ? SeriousIOS_GetGLContext()
        : nullptr;
}

int SDLCALL SDL_GL_MakeCurrent(SDL_Window* window, SDL_GLContext context) {
    (void)window;
    if (context != SeriousIOS_GetGLContext()) {
        return -1;
    }
    return SeriousIOS_MakeGLContextCurrent();
}

void SDLCALL SDL_GL_DeleteContext(SDL_GLContext context) {
    (void)context;
    // The CAEAGLLayer host owns the EAGLContext lifetime.
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

int SDLCALL SDL_GetNumDisplayModes(int displayIndex) {
    return displayIndex == 0 ? 1 : -1;
}

int SDLCALL SDL_GetDisplayMode(
    int displayIndex,
    int modeIndex,
    SDL_DisplayMode* mode) {
    if (displayIndex != 0 || modeIndex != 0 || mode == nullptr) {
        return -1;
    }
    fillDisplayMode(mode);
    return 0;
}

int SDLCALL SDL_GetDesktopDisplayMode(int displayIndex, SDL_DisplayMode* mode) {
    if (displayIndex != 0 || mode == nullptr) {
        return -1;
    }
    fillDisplayMode(mode);
    return 0;
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
    int* buttonID) {
    if (buttonID != nullptr) {
        *buttonID = -1;
    }
    return SDL_ShowSimpleMessageBox(
        messageBoxData == nullptr ? 0 : messageBoxData->flags,
        messageBoxData == nullptr ? nullptr : messageBoxData->title,
        messageBoxData == nullptr ? nullptr : messageBoxData->message,
        messageBoxData == nullptr ? nullptr : messageBoxData->window);
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

const char* SDLCALL SDL_JoystickNameForIndex(int joystickIndex) {
    (void)joystickIndex;
    return nullptr;
}

SDL_Joystick* SDLCALL SDL_JoystickOpen(int joystickIndex) {
    (void)joystickIndex;
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

int SDLCALL SDL_GetNumAudioDevices(int capture) {
    return capture == 0 ? 1 : 0;
}

const char* SDLCALL SDL_GetAudioDeviceName(int index, int capture) {
    return capture == 0 && index == 0 ? kAudioDeviceName : nullptr;
}

const char* SDLCALL SDL_GetCurrentAudioDriver(void) {
    return kAudioDriverName;
}

SDL_AudioDeviceID SDLCALL SDL_OpenAudioDevice(
    const char* device,
    int capture,
    const SDL_AudioSpec* desired,
    SDL_AudioSpec* obtained,
    int allowedChanges) {
    (void)device;
    (void)allowedChanges;
    if (capture != 0 || desired == nullptr) {
        return 0;
    }

    auto state = std::make_shared<AudioDeviceState>();
    state->specification = *desired;
    if (state->specification.samples == 0) {
        state->specification.samples = 2048;
    }
    const int bytesPerSample = SDL_AUDIO_BITSIZE(state->specification.format) / 8;
    if (state->specification.freq <= 0
        || state->specification.channels == 0
        || bytesPerSample <= 0) {
        return 0;
    }
    state->specification.silence =
        state->specification.format == AUDIO_U8 ? 0x80 : 0;
    state->specification.size =
        static_cast<Uint32>(state->specification.samples)
        * state->specification.channels
        * static_cast<Uint32>(bytesPerSample);

    const SDL_AudioDeviceID deviceID =
        gNextAudioDeviceID.fetch_add(1, std::memory_order_relaxed);
    {
        std::lock_guard<std::mutex> lock(gAudioDeviceMutex);
        gAudioDevices.emplace(deviceID, state);
    }
    if (obtained != nullptr) {
        *obtained = state->specification;
    }
    std::thread(runAudioDevice, state).detach();
    return deviceID;
}

void SDLCALL SDL_PauseAudioDevice(SDL_AudioDeviceID device, int pauseOn) {
    const auto state = audioDevice(device);
    if (state != nullptr) {
        state->paused.store(pauseOn != 0, std::memory_order_release);
    }
}

void SDLCALL SDL_CloseAudioDevice(SDL_AudioDeviceID device) {
    std::shared_ptr<AudioDeviceState> state;
    {
        std::lock_guard<std::mutex> lock(gAudioDeviceMutex);
        const auto iterator = gAudioDevices.find(device);
        if (iterator == gAudioDevices.end()) {
            return;
        }
        state = iterator->second;
        gAudioDevices.erase(iterator);
    }
    state->cancelled.store(true, std::memory_order_release);
}

void SDLCALL SDL_LockAudioDevice(SDL_AudioDeviceID device) {
    const auto state = audioDevice(device);
    if (state != nullptr) {
        state->callbackMutex.lock();
    }
}

void SDLCALL SDL_UnlockAudioDevice(SDL_AudioDeviceID device) {
    const auto state = audioDevice(device);
    if (state != nullptr) {
        state->callbackMutex.unlock();
    }
}

char* SDLCALL SDL_GetBasePath(void) {
    const char* path = SeriousIOS_GetExecutablePath();
    if (path == nullptr) {
        return nullptr;
    }
    const char* slash = std::strrchr(path, '/');
    const size_t length = slash == nullptr
        ? std::strlen(path)
        : static_cast<size_t>(slash - path + 1);
    char* result = static_cast<char*>(std::malloc(length + 1));
    if (result != nullptr) {
        std::memcpy(result, path, length);
        result[length] = '\0';
    }
    return result;
}

char* SDLCALL SDL_GetPrefPath(const char* organization, const char* application) {
    (void)organization;
    (void)application;
    const char* path = SeriousIOS_GetUserPath();
    if (path == nullptr) {
        return nullptr;
    }
    const size_t length = std::strlen(path) + 1;
    char* result = static_cast<char*>(std::malloc(length));
    if (result != nullptr) {
        std::memcpy(result, path, length);
    }
    return result;
}

void SDLCALL SDL_free(void* memory) {
    std::free(memory);
}

int SDLCALL SDL_snprintf(
    char* destination,
    size_t maximumLength,
    const char* format,
    ...) {
    va_list arguments;
    va_start(arguments, format);
    const int result = std::vsnprintf(destination, maximumLength, format, arguments);
    va_end(arguments);
    return result;
}

void* SDLCALL SDL_memset(void* destination, int value, size_t length) {
    return std::memset(destination, value, length);
}

} // extern "C"
