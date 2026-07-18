#pragma once

#include <stdbool.h>
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

typedef void (*SeriousIOSPresentCallback)(void* context);
typedef int (*SeriousIOSMakeCurrentCallback)(void* context);

typedef enum SeriousIOSVirtualAction {
    SERIOUSIOS_ACTION_FIRE = 0,
    SERIOUSIOS_ACTION_JUMP = 1,
    SERIOUSIOS_ACTION_USE = 2,
    SERIOUSIOS_ACTION_CROUCH = 3,
    SERIOUSIOS_ACTION_NEXT_WEAPON = 4,
    SERIOUSIOS_ACTION_PREVIOUS_WEAPON = 5,
    SERIOUSIOS_ACTION_COUNT = 6,
} SeriousIOSVirtualAction;

bool SeriousIOS_ConfigurePaths(
    const char* executablePath,
    const char* dataPath,
    const char* userPath,
    const char* cachePath,
    const char* temporaryPath);
bool SeriousIOS_ArePathsConfigured(void);
const char* SeriousIOS_GetExecutablePath(void);
const char* SeriousIOS_GetDataPath(void);
const char* SeriousIOS_GetUserPath(void);
const char* SeriousIOS_GetCachePath(void);
const char* SeriousIOS_GetTemporaryPath(void);

void SeriousIOS_SetSDLWindowSize(int width, int height);
void SeriousIOS_SetSDLMouseState(int x, int y, uint32_t buttons);
void SeriousIOS_QueueSDLKey(int keycode, bool pressed);
void SeriousIOS_QueueSDLMouseButton(uint8_t button, bool pressed);
void SeriousIOS_AddSDLRelativeMouseDelta(int deltaX, int deltaY);
void SeriousIOS_ReleaseSDLInput(void);
void SeriousIOS_SetVirtualMovement(float forward, float right);
void SeriousIOS_SetVirtualAction(SeriousIOSVirtualAction action, bool pressed);
void SeriousIOS_ReleaseVirtualController(void);
float SeriousIOS_GetVirtualMovementForward(void);
float SeriousIOS_GetVirtualMovementRight(void);
void SeriousIOS_SetPresentCallback(
    SeriousIOSPresentCallback callback,
    void* context);
void SeriousIOS_SetGLContext(
    void* context,
    SeriousIOSMakeCurrentCallback makeCurrentCallback);
void* SeriousIOS_GetGLContext(void);
int SeriousIOS_MakeGLContextCurrent(void);

void* SeriousIOS_GetOpenGLCompatProcAddress(const char* procedure);
void* SeriousIOS_GetOpenGLImmediateCompatProcAddress(const char* procedure);
void* SeriousIOS_GetOpenGLTextureCompatProcAddress(const char* procedure);
bool SeriousIOS_ValidateOpenGLCompatibility(void);
bool SeriousIOS_ValidateOpenGLImmediateCompatibility(void);
const char* SeriousIOS_GetOpenGLCompatibilityError(void);
const char* SeriousIOS_GetOpenGLImmediateCompatibilityError(void);

#ifdef __cplusplus
} // extern "C"
#endif
