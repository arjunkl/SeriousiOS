#include <SDL.h>

#include <dlfcn.h>
#include <mach/mach_time.h>
#include <time.h>

namespace {

const char* kSeriousIOSError =
    "SeriousiOS SDL compatibility service is not available in the current host";

} // namespace

extern "C" {

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

void SDLCALL SDL_GL_SwapWindow(SDL_Window* window) {
    (void)window;
    // Presentation belongs to the future EAGL-backed iOS render surface.
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

} // extern "C"
