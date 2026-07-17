#include "SeriousIOSPlatformBridge.h"

#include <SDL.h>

#include <atomic>

namespace {

std::atomic<int> gMouseX{0};
std::atomic<int> gMouseY{0};
std::atomic<Uint32> gMouseButtons{0};

} // namespace

extern "C" void SeriousIOS_SetSDLMouseState(int x, int y, uint32_t buttons) {
    gMouseX.store(x, std::memory_order_release);
    gMouseY.store(y, std::memory_order_release);
    gMouseButtons.store(static_cast<Uint32>(buttons), std::memory_order_release);
}

extern "C" Uint32 SDLCALL SDL_GetMouseState(int* x, int* y) {
    if (x != nullptr) {
        *x = gMouseX.load(std::memory_order_acquire);
    }
    if (y != nullptr) {
        *y = gMouseY.load(std::memory_order_acquire);
    }
    return gMouseButtons.load(std::memory_order_acquire);
}
