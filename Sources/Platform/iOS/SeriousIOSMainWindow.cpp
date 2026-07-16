#include "SeriousIOSPlatformBridge.h"

#include <Engine/Engine.h>
#include <SeriousSam/MainWindow.h>

#include <cstdint>

extern HWND _hwndMain;

BOOL _bWindowChanging = FALSE;

namespace {

std::uintptr_t gFallbackWindowToken = 1;

HWND hostWindowHandle() {
    void* context = SeriousIOS_GetGLContext();
    if (context != nullptr) {
        return reinterpret_cast<HWND>(context);
    }
    return reinterpret_cast<HWND>(&gFallbackWindowToken);
}

void attachHostWindow() {
    _hwndMain = hostWindowHandle();
    SE_UpdateWindowHandle(_hwndMain);
}

} // namespace

CTString strWindow1251ToUtf8(CTString from) {
    return from;
}

void MainWindow_Init(void) {
    attachHostWindow();
}

void MainWindow_End(void) {
    _hwndMain = nullptr;
}

void CloseMainWindow(void) {
    // UIKit owns the actual window and CAEAGLLayer lifetime. The legacy handle is
    // detached only so display-mode transitions can reattach it deterministically.
    _hwndMain = nullptr;
}

void OpenMainWindowNormal(PIX pixSizeI, PIX pixSizeJ) {
    SeriousIOS_SetSDLWindowSize(pixSizeI, pixSizeJ);
    attachHostWindow();
}

void ResetMainWindowNormal(void) {
    attachHostWindow();
}

void OpenMainWindowFullScreen(PIX pixSizeI, PIX pixSizeJ) {
    SeriousIOS_SetSDLWindowSize(pixSizeI, pixSizeJ);
    attachHostWindow();
}

void OpenMainWindowInvisible(void) {
    attachHostWindow();
}
