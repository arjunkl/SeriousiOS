#include "SeriousIOSPlatformBridge.h"

#include <SDL.h>

#include <dlfcn.h>

extern "C" void* SDLCALL SDL_GL_GetProcAddress(const char* procedure) {
    if (procedure == nullptr || *procedure == '\0') {
        return nullptr;
    }

    if (void* textureProcedure =
            SeriousIOS_GetOpenGLTextureCompatProcAddress(procedure)) {
        return textureProcedure;
    }
    if (void* immediateProcedure =
            SeriousIOS_GetOpenGLImmediateCompatProcAddress(procedure)) {
        return immediateProcedure;
    }
    if (void* compatibilityProcedure =
            SeriousIOS_GetOpenGLCompatProcAddress(procedure)) {
        return compatibilityProcedure;
    }
    return dlsym(RTLD_DEFAULT, procedure);
}
